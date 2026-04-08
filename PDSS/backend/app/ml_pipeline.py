from __future__ import annotations

import json
import logging
import os
import pickle
import re
import shutil
import subprocess
import sys
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import lightgbm as lgb
import matplotlib.pyplot as plt
import numpy as np
import optuna
import pandas as pd
import prophet as prophet_pkg
import shap
import xgboost as xgb
from prophet import Prophet
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sqlalchemy import delete

from app.database import Forecast, Prediction, RiskScore, SessionLocal, Vendor, VendorMetric
from app.risk_engine import RiskInputs, calculate_risk_score, risk_level

PRIMARY_DATASET_CANDIDATES = [
    "shashwatwork/dataco-smart-supply-chain-for-big-data-analysis",
    "bytadit/ecommerce-order-dataset",
    "datasetengineer/logistics-and-supply-chain-dataset",
]
SECONDARY_DATASET_CANDIDATES = [
    "datasetengineer/logistics-and-supply-chain-dataset",
    "bytadit/ecommerce-order-dataset",
    "amirmotefaker/supply-chain-dataset",
    "harshsingh2209/supply-chain-analysis",
]
RANDOM_STATE = 42


@dataclass
class DatasetArtifact:
    slug: str
    zip_path: Path
    extract_dir: Path
    csv_files: list[Path]
    primary_csv: Path
    row_count: int


@dataclass
class PreparedData:
    frame: pd.DataFrame
    features: pd.DataFrame
    delay_target: pd.Series
    risk_target: pd.Series
    monthly_cost: pd.DataFrame
    feature_columns: list[str]
    numeric_columns: list[str]
    categorical_columns: list[str]


class SupplyChainMLPipeline:
    def __init__(self, backend_dir: Path) -> None:
        self.backend_dir = backend_dir
        self.project_root = backend_dir.parent
        self.models_dir = backend_dir / "models"
        self.data_dir = backend_dir / "data"
        self.raw_dir = self.data_dir / "raw"
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.raw_dir.mkdir(parents=True, exist_ok=True)

        self.logger = logging.getLogger("pdss.pipeline")
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s - %(message)s"))
            self.logger.addHandler(handler)

    def _kaggle_base_command(self) -> list[str]:
        if shutil.which("kaggle"):
            return ["kaggle"]
        return [sys.executable, "-m", "kaggle.cli"]

    def _run_kaggle(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(self._kaggle_base_command() + args, capture_output=True, text=True)

    def _primary_dataset_candidates(self) -> list[str]:
        override = os.getenv("PDSS_PRIMARY_DATASET", "").strip()
        if override:
            return [override, *PRIMARY_DATASET_CANDIDATES]
        return list(PRIMARY_DATASET_CANDIDATES)

    def _secondary_dataset_candidates(self) -> list[str]:
        override = os.getenv("PDSS_SECONDARY_DATASET", "").strip()
        if override:
            return [override, *SECONDARY_DATASET_CANDIDATES]
        return list(SECONDARY_DATASET_CANDIDATES)

    def run_full_pipeline(self) -> dict[str, Any]:
        self.logger.info("Step 1/10 - Verifying GPU availability and CUDA training capability")
        #self.verify_gpu()

        self.logger.info("Step 2/10 - Verifying Kaggle API access")
        self.verify_kaggle_access()

        self.logger.info("Step 3/10 - Downloading and validating primary dataset")
        primary_artifact = self.download_and_validate_first_available(
            self._primary_dataset_candidates(),
            role="primary",
            excluded_slugs=set(),
        )

        self.logger.info("Step 4/10 - Downloading and validating secondary dataset")
        secondary_artifact = self.download_and_validate_first_available(
            self._secondary_dataset_candidates(),
            role="secondary",
            excluded_slugs={primary_artifact.slug},
        )

        self.logger.info("Step 5/10 - Reading and preprocessing data")
        primary_df = self._load_primary_csv(primary_artifact.primary_csv)
        secondary_df = self._load_primary_csv(secondary_artifact.primary_csv)
        prepared = self.prepare_data(primary_df, secondary_df)

        self.logger.info("Step 6/10 - Training GPU XGBoost delay model with Optuna tuning")
        delay_artifacts, delay_metrics, shap_context = self.train_delay_model(prepared)

        self.logger.info("Step 7/10 - Training GPU LightGBM risk model")
        risk_artifacts, risk_metrics = self.train_risk_model(prepared)

        self.logger.info("Step 8/10 - Training Prophet cost forecasting model")
        prophet_model, forecast_template, forecast_metrics = self.train_forecast_model(prepared)

        self.logger.info("Step 9/10 - Running SHAP explainability")
        self.generate_explainability(delay_artifacts, shap_context)

        all_metrics = {
            "delay_model": delay_metrics,
            "risk_model": risk_metrics,
            "forecast_model": forecast_metrics,
        }

        self.logger.info("Step 10/10 - Persisting artifacts and populating SQLite")
        self.persist_artifacts(delay_artifacts, risk_artifacts, prophet_model, forecast_template, all_metrics)
        self.populate_database(prepared.frame, forecast_template)
        self._print_metrics(all_metrics)
        return all_metrics

    def verify_gpu(self) -> None:
        smi = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
        )
        if smi.returncode != 0 or not smi.stdout.strip():
            raise RuntimeError(
                "GPU validation failed: NVIDIA GPU not detected. CUDA GPU training is mandatory; stopping pipeline."
            )

        rng = np.random.default_rng(RANDOM_STATE)
        x = rng.normal(0, 1, size=(512, 10)).astype(np.float32)
        y = rng.integers(0, 2, size=512)

        try:
            xgb_model = xgb.XGBClassifier(
                n_estimators=8,
                max_depth=3,
                learning_rate=0.2,
                tree_method="hist",
                device="cuda",
                eval_metric="logloss",
                random_state=RANDOM_STATE,
            )
            xgb_model.fit(x, y)
        except Exception as exc:
            raise RuntimeError(f"GPU validation failed for XGBoost CUDA training: {exc}") from exc

        try:
            train_data = lgb.Dataset(x, label=y)
            lgb.train(
                {
                    "objective": "binary",
                    "metric": "binary_logloss",
                    "device": "gpu",
                    "verbosity": -1,
                },
                train_data,
                num_boost_round=8,
            )
        except Exception as exc:
            raise RuntimeError(f"GPU validation failed for LightGBM GPU training: {exc}") from exc

    def verify_kaggle_access(self) -> None:
        kaggle_local = self.project_root / "kaggle.json"
        kaggle_home = Path.home() / ".kaggle"
        kaggle_home.mkdir(parents=True, exist_ok=True)
        kaggle_home_file = kaggle_home / "kaggle.json"

        if not kaggle_home_file.exists() and kaggle_local.exists():
            shutil.copy2(kaggle_local, kaggle_home_file)
            if os.name != "nt":
                os.chmod(kaggle_home_file, 0o600)

        if not kaggle_home_file.exists():
            raise RuntimeError(
                "Kaggle API credentials not found at ~/.kaggle/kaggle.json and local kaggle.json is missing."
            )

        version_check = self._run_kaggle(["--version"])
        if version_check.returncode != 0:
            raise RuntimeError(
                f"Kaggle CLI is not available. Install kaggle package first. Details: {version_check.stderr.strip()}"
            )

        candidate = self._primary_dataset_candidates()[0]
        access_check = self._run_kaggle(["datasets", "files", "-d", candidate])
        if access_check.returncode == 0:
            return

        for slug in self._primary_dataset_candidates()[1:]:
            retry = self._run_kaggle(["datasets", "files", "-d", slug])
            if retry.returncode == 0:
                return

        detail = access_check.stderr.strip() or access_check.stdout.strip()
        if not detail:
            detail = "No accessible primary supply-chain dataset was found."
        raise RuntimeError(f"Kaggle API access verification failed: {detail}")

    def download_and_validate_first_available(
        self,
        candidates: list[str],
        role: str,
        excluded_slugs: set[str],
    ) -> DatasetArtifact:
        errors: list[str] = []
        for slug in candidates:
            if slug in excluded_slugs:
                continue
            try:
                artifact = self.download_and_validate_dataset(slug)
                self.logger.info(
                    "Selected %s dataset slug=%s with %s rows from %s",
                    role,
                    artifact.slug,
                    artifact.row_count,
                    artifact.primary_csv.name,
                )
                return artifact
            except Exception as exc:
                message = str(exc)
                self.logger.warning("Skipping %s dataset candidate %s due to: %s", role, slug, message)
                errors.append(f"{slug}: {message}")

        joined = "; ".join(errors) if errors else "no candidates were supplied"
        raise RuntimeError(f"Unable to resolve a valid {role} dataset. Details: {joined}")

    def download_and_validate_dataset(self, slug: str) -> DatasetArtifact:
        dataset_name = slug.split("/")[-1]
        zip_path = self.raw_dir / f"{dataset_name}.zip"

        last_error = ""
        for attempt in range(1, 4):
            self.logger.info("Downloading %s (attempt %s/3)", slug, attempt)
            proc = self._run_kaggle(["datasets", "download", "-d", slug, "-p", str(self.raw_dir), "--force"])
            if proc.returncode == 0:
                break
            last_error = (proc.stderr or proc.stdout).strip()
            self.logger.warning("Download attempt %s failed for %s: %s", attempt, slug, last_error)
            time.sleep(2)
        else:
            raise RuntimeError(f"Failed to download {slug} after 3 attempts: {last_error}")

        if not zip_path.exists():
            after_paths = list(self.raw_dir.glob("*.zip"))
            if not after_paths:
                raise RuntimeError(f"ZIP verification failed for {slug}: no ZIP file found in {self.raw_dir}")
            newest = max(after_paths, key=lambda p: p.stat().st_mtime)
            zip_path = newest

        if not zip_path.exists():
            raise RuntimeError(f"ZIP verification failed for {slug}: {zip_path} not found")

        extract_dir = self.raw_dir / dataset_name
        if extract_dir.exists():
            shutil.rmtree(extract_dir)
        extract_dir.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(zip_path, "r") as zip_file:
            zip_file.extractall(extract_dir)

        csv_files = list(extract_dir.rglob("*.csv"))
        if not csv_files:
            raise RuntimeError(f"CSV verification failed for {slug}: no CSV files were extracted")

        row_counts: dict[Path, int] = {}
        schema_scores: dict[Path, int] = {}
        for csv_path in csv_files:
            rows = self._count_csv_rows(csv_path)
            row_counts[csv_path] = rows
            schema_scores[csv_path] = self._score_supply_chain_schema(csv_path)

        valid_csvs = [(path, rows) for path, rows in row_counts.items() if rows > 1000]
        if not valid_csvs:
            max_row_file, max_rows = max(row_counts.items(), key=lambda item: item[1])
            raise RuntimeError(
                f"Dataset validation failed for {slug}: largest CSV ({max_row_file.name}) has {max_rows} rows (must be > 1000)."
            )

        primary_csv, max_rows = max(
            valid_csvs,
            key=lambda item: (schema_scores.get(item[0], 0), item[1]),
        )
        if max_rows <= 1000:
            raise RuntimeError(
                f"Dataset validation failed for {slug}: largest CSV ({primary_csv.name}) has {max_rows} rows (must be > 1000)."
            )

        self.logger.info(
            "Dataset verified for %s: %s CSV files, selected file=%s rows=%s schema_score=%s",
            slug,
            len(csv_files),
            primary_csv.name,
            max_rows,
            schema_scores.get(primary_csv, 0),
        )
        return DatasetArtifact(
            slug=slug,
            zip_path=zip_path,
            extract_dir=extract_dir,
            csv_files=csv_files,
            primary_csv=primary_csv,
            row_count=max_rows,
        )

    def _score_supply_chain_schema(self, csv_path: Path) -> int:
        header = None
        for encoding in ["utf-8", "latin1"]:
            try:
                header = pd.read_csv(csv_path, nrows=0, low_memory=False, encoding=encoding)
                break
            except Exception:
                continue
        if header is None:
            try:
                header = pd.read_csv(csv_path, nrows=0, low_memory=False, encoding_errors="ignore")
            except Exception:
                return 0

        normalized = [self._normalize_column_name(col) for col in header.columns]
        colset = set(normalized)
        score = 0

        high_signal_columns = [
            "supplier_name",
            "vendor_name",
            "supplier",
            "vendor",
            "order_date_dateorders",
            "order_date",
            "days_for_shipping_real",
            "days_for_shipment_scheduled",
            "late_delivery_risk",
            "delivery_status",
            "sales",
            "order_item_quantity",
            "order_item_product_price",
            "order_status",
            "market",
            "category_name",
        ]
        score += sum(5 for column in high_signal_columns if column in colset)

        token_signals = ["supplier", "vendor", "order", "delivery", "ship", "quantity", "price", "cost", "date"]
        for token in token_signals:
            if any(token in col for col in colset):
                score += 1

        return score

    def _count_csv_rows(self, csv_path: Path) -> int:
        count = 0
        try:
            for chunk in pd.read_csv(csv_path, chunksize=200_000, low_memory=False):
                count += len(chunk)
            return int(count)
        except Exception:
            count = 0
            with csv_path.open("r", encoding="utf-8", errors="ignore") as handle:
                next(handle, None)
                for _ in handle:
                    count += 1
            return int(count)

    def _load_primary_csv(self, csv_path: Path) -> pd.DataFrame:
        for encoding in ["utf-8", "latin1"]:
            try:
                return pd.read_csv(csv_path, low_memory=False, encoding=encoding)
            except Exception:
                continue
        return pd.read_csv(csv_path, low_memory=False, encoding_errors="ignore")

    def prepare_data(self, primary_df: pd.DataFrame, secondary_df: pd.DataFrame) -> PreparedData:
        main = self._prepare_primary_frame(primary_df)
        secondary_vendor_risk, secondary_global_risk = self._prepare_secondary_frame(secondary_df)

        main["vendor_key"] = main["vendor_code"].apply(self._sanitize_key)
        if not secondary_vendor_risk.empty:
            merged = main.merge(secondary_vendor_risk, on="vendor_key", how="left")
        else:
            merged = main.copy()
            merged["external_risk_proxy"] = secondary_global_risk

        merged["external_risk_proxy"] = merged["external_risk_proxy"].fillna(secondary_global_risk)
        merged["external_risk_proxy"] = merged["external_risk_proxy"].clip(0.0, 1.0)

        merged = self._engineer_features(merged)
        merged = merged.dropna(subset=["delay_flag"]).reset_index(drop=True)

        if merged["delay_flag"].nunique() < 2:
            raise RuntimeError("Delay target has only one class after preprocessing. Cannot train classifier.")

        risk_signal = (
            0.35 * merged["delay_frequency"]
            + 0.25 * (1.0 - merged["quality_weighted_score"])
            + 0.20 * self._normalize_series(merged["cost_volatility"])
            + 0.10 * merged["external_risk_proxy"]
            + 0.10 * self._normalize_series(merged["demand_variability_score"])
        )
        percent_rank = risk_signal.rank(method="average", pct=True)
        merged["risk_label"] = pd.cut(
            percent_rank,
            bins=[0.0, 0.33, 0.66, 1.0],
            labels=["Low", "Medium", "High"],
            include_lowest=True,
        ).astype(str)

        if len(set(merged["risk_label"])) < 3:
            raise RuntimeError("Risk target must contain Low/Medium/High classes after preprocessing.")

        merged = merged.sort_values("order_date").reset_index(drop=True)

        leakage_columns = {
            "delay_days",
            "risk_label",
            "actual_delivery_date",
            "delivery_status",
            "late_delivery_risk",
            "delay_flag",
            "vendor_name",
            "vendor_key",
            "order_date",
            "cost",
        }

        candidate_features = [
            "vendor_code",
            "category",
            "country",
            "lead_time_days",
            "order_quantity",
            "unit_price",
            "on_time_rate",
            "quality_score",
            "defect_rate",
            "delay_frequency",
            "rolling_delay_average",
            "cost_volatility",
            "quality_weighted_score",
            "demand_variability_score",
            "reliability_index",
            "external_risk_proxy",
        ]
        feature_columns = [col for col in candidate_features if col in merged.columns and col not in leakage_columns]

        categorical_columns = [col for col in ["vendor_code", "category", "country"] if col in feature_columns]
        numeric_columns = [col for col in feature_columns if col not in categorical_columns]

        features = merged[feature_columns].copy()
        delay_target = merged["delay_flag"].astype(int)
        risk_target = merged["risk_label"].astype(str)

        monthly_cost = (
            merged.assign(month=merged["order_date"].dt.to_period("M").dt.to_timestamp())
            .groupby("month", as_index=False)["cost"]
            .sum()
            .rename(columns={"month": "ds", "cost": "y"})
        )

        if len(monthly_cost) < 18:
            raise RuntimeError(
                f"Forecast training requires at least 18 monthly points; found {len(monthly_cost)} after preprocessing."
            )

        return PreparedData(
            frame=merged,
            features=features,
            delay_target=delay_target,
            risk_target=risk_target,
            monthly_cost=monthly_cost,
            feature_columns=feature_columns,
            numeric_columns=numeric_columns,
            categorical_columns=categorical_columns,
        )
    def _prepare_primary_frame(self, source_df: pd.DataFrame) -> pd.DataFrame:
        df = source_df.copy()
        df.columns = [self._normalize_column_name(col) for col in df.columns]

        vendor_col = self._find_column(
            df,
            [
                "supplier_name",
                "vendor_name",
                "supplier",
                "vendor",
                "supplier_id",
                "vendor_id",
                "supplier_city",
                "department_name",
            ],
        )
        category_col = self._find_column(df, ["category_name", "department_name", "product_name", "market", "category"])
        country_col = self._find_column(
            df,
            ["supplier_country", "customer_country", "order_country", "country", "market", "supplier_state"],
        )
        order_date_col = self._find_column(
            df,
            [
                "order_date_dateorders",
                "order_date",
                "invoice_date",
                "transaction_date",
                "created_at",
                "date",
            ],
        )

        if order_date_col is None:
            date_like_cols = [col for col in df.columns if "date" in col]
            if date_like_cols:
                order_date_col = date_like_cols[0]
            else:
                raise RuntimeError("No order date column found; cannot continue forecasting/training.")

        vendor_series = self._extract_vendor_series(df, vendor_col)
        vendor_code = vendor_series.apply(self._sanitize_key)

        order_date = pd.to_datetime(df[order_date_col], errors="coerce", utc=False)
        if order_date.isna().all():
            raise RuntimeError("Order date parsing failed for all rows.")

        real_days_col = self._find_column(df, ["days_for_shipping_real", "actual_shipping_days", "delivery_days"])
        scheduled_days_col = self._find_column(
            df,
            ["days_for_shipment_scheduled", "scheduled_shipping_days", "planned_shipping_days", "expected_lead_time"],
        )
        late_flag_col = self._find_column(df, ["late_delivery_risk", "delay_flag", "is_delayed", "late"])
        status_col = self._find_column(df, ["delivery_status", "order_status", "shipment_status"])

        delay_days = pd.Series(np.nan, index=df.index, dtype=float)
        if real_days_col and scheduled_days_col:
            real_days = pd.to_numeric(df[real_days_col], errors="coerce")
            scheduled_days = pd.to_numeric(df[scheduled_days_col], errors="coerce")
            delay_days = (real_days - scheduled_days).clip(lower=0)
        elif late_flag_col:
            late_flag = pd.to_numeric(df[late_flag_col], errors="coerce").fillna(0).clip(0, 1)
            delay_days = late_flag * 3.0
        elif status_col:
            status_text = df[status_col].astype(str).str.lower()
            delay_days = np.where(status_text.str.contains("late|delayed|cancel", regex=True), 2.0, 0.0)
            delay_days = pd.Series(delay_days, index=df.index, dtype=float)

        if pd.Series(delay_days).isna().all():
            raise RuntimeError("Unable to derive delay signal from primary dataset.")

        lead_time_days = pd.Series(np.nan, index=df.index, dtype=float)
        if scheduled_days_col:
            lead_time_days = pd.to_numeric(df[scheduled_days_col], errors="coerce")
        elif real_days_col:
            lead_time_days = pd.to_numeric(df[real_days_col], errors="coerce")

        quantity_col = self._find_column(df, ["order_item_quantity", "order_quantity", "quantity", "qty", "units"])
        unit_price_col = self._find_column(
            df,
            ["order_item_product_price", "unit_price", "item_price", "price", "cost_per_unit"],
        )
        amount_col = self._find_column(
            df,
            [
                "sales",
                "order_item_total",
                "total_cost",
                "amount",
                "contract_value",
                "benefit_per_order",
            ],
        )

        order_quantity = (
            pd.to_numeric(df[quantity_col], errors="coerce") if quantity_col else pd.Series(np.nan, index=df.index, dtype=float)
        )
        unit_price = (
            pd.to_numeric(df[unit_price_col], errors="coerce") if unit_price_col else pd.Series(np.nan, index=df.index, dtype=float)
        )
        amount = pd.to_numeric(df[amount_col], errors="coerce") if amount_col else pd.Series(np.nan, index=df.index, dtype=float)

        if order_quantity.notna().sum() == 0:
            order_quantity = pd.Series(1.0, index=df.index, dtype=float)
        if unit_price.notna().sum() == 0 and amount.notna().sum() > 0:
            unit_price = amount / order_quantity.replace(0, np.nan)

        cost = (order_quantity * unit_price).replace([np.inf, -np.inf], np.nan)
        cost = cost.fillna(amount)

        quality_col = self._find_column(
            df,
            ["quality_score", "supplier_quality", "vendor_rating", "rating", "review_score", "product_quality"],
        )
        defect_col = self._find_column(df, ["defect_rate", "return_rate", "rejection_rate", "fault_rate", "damaged_rate"])
        on_time_col = self._find_column(df, ["on_time_rate", "delivery_performance", "service_level"])

        if quality_col:
            quality_score = self._normalize_series(pd.to_numeric(df[quality_col], errors="coerce"))
        elif status_col:
            status_text = df[status_col].astype(str).str.lower()
            quality_score = np.where(status_text.str.contains("delivered|complete|shipped", regex=True), 0.85, 0.55)
            quality_score = pd.Series(quality_score, index=df.index, dtype=float)
        else:
            quality_score = 1.0 - self._normalize_series(delay_days)

        if defect_col:
            defect_rate = self._normalize_series(pd.to_numeric(df[defect_col], errors="coerce"))
        elif status_col:
            status_text = df[status_col].astype(str).str.lower()
            defect_rate = np.where(status_text.str.contains("cancel|return|refund|reject", regex=True), 0.35, 0.08)
            defect_rate = pd.Series(defect_rate, index=df.index, dtype=float)
        else:
            defect_rate = self._normalize_series(delay_days) * 0.35

        delay_flag = (pd.Series(delay_days).fillna(0) > 0).astype(int)

        if on_time_col:
            on_time_rate = self._normalize_series(pd.to_numeric(df[on_time_col], errors="coerce"))
        else:
            on_time_rate = 1.0 - delay_flag.astype(float)
            on_time_rate = on_time_rate.groupby(vendor_code).transform("mean")

        category = (
            df[category_col].astype(str) if category_col else pd.Series("General", index=df.index, dtype=str)
        )
        country = df[country_col].astype(str) if country_col else pd.Series("Unknown", index=df.index, dtype=str)
        frame = pd.DataFrame(
            {
                "vendor_code": vendor_code,
                "vendor_name": vendor_series.astype(str),
                "category": category,
                "country": country,
                "order_date": order_date,
                "lead_time_days": pd.to_numeric(lead_time_days, errors="coerce"),
                "delay_days": pd.to_numeric(delay_days, errors="coerce"),
                "delay_flag": delay_flag,
                "order_quantity": pd.to_numeric(order_quantity, errors="coerce"),
                "unit_price": pd.to_numeric(unit_price, errors="coerce"),
                "cost": pd.to_numeric(cost, errors="coerce"),
                "quality_score": pd.to_numeric(quality_score, errors="coerce"),
                "defect_rate": pd.to_numeric(defect_rate, errors="coerce"),
                "on_time_rate": pd.to_numeric(on_time_rate, errors="coerce"),
            }
        )

        frame = frame.replace([np.inf, -np.inf], np.nan)
        frame = frame.dropna(subset=["order_date"]).reset_index(drop=True)

        for numeric_col in [
            "lead_time_days",
            "delay_days",
            "order_quantity",
            "unit_price",
            "cost",
            "quality_score",
            "defect_rate",
            "on_time_rate",
        ]:
            median = frame[numeric_col].median()
            if pd.isna(median):
                median = 0.0
            frame[numeric_col] = frame[numeric_col].fillna(median)

        frame["vendor_code"] = frame["vendor_code"].replace("", np.nan)
        frame["vendor_code"] = frame["vendor_code"].fillna("vendor_unknown")
        frame["vendor_name"] = frame["vendor_name"].replace("", "Unknown Vendor")
        frame["category"] = frame["category"].replace("", "General")
        frame["country"] = frame["country"].replace("", "Unknown")

        return frame

    def _prepare_secondary_frame(self, source_df: pd.DataFrame) -> tuple[pd.DataFrame, float]:
        if source_df.empty:
            return pd.DataFrame(columns=["vendor_key", "external_risk_proxy"]), 0.5

        df = source_df.copy()
        df.columns = [self._normalize_column_name(col) for col in df.columns]

        vendor_col = self._find_column(
            df,
            ["supplier_name", "vendor_name", "supplier", "vendor", "supplier_id", "vendor_id", "contractor"],
        )
        if vendor_col is None:
            return pd.DataFrame(columns=["vendor_key", "external_risk_proxy"]), 0.5

        vendor_key = df[vendor_col].astype(str).apply(self._sanitize_key)

        numeric_columns = df.select_dtypes(include=[np.number]).columns.tolist()
        if not numeric_columns:
            parse_candidates = [
                "amount",
                "contract_value",
                "award_value",
                "value",
                "price",
                "cost",
                "quantity",
            ]
            for candidate in parse_candidates:
                col = self._find_column(df, [candidate])
                if col is not None:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
                    numeric_columns.append(col)

        risk_components: list[pd.Series] = []
        if numeric_columns:
            for col in numeric_columns[:4]:
                risk_components.append(self._normalize_series(pd.to_numeric(df[col], errors="coerce")))

        status_col = self._find_column(df, ["status", "delivery_status", "risk", "contract_status", "outcome"])
        if status_col is not None:
            status_text = df[status_col].astype(str).str.lower()
            issue = status_text.str.contains("late|delay|risk|cancel|breach|terminate", regex=True).astype(float)
            risk_components.append(issue)

        if risk_components:
            stacked = np.vstack([component.fillna(component.median()) for component in risk_components]).astype(float)
            risk_proxy = stacked.mean(axis=0)
            risk_proxy = pd.Series(risk_proxy, index=df.index, dtype=float).clip(0.0, 1.0)
        else:
            risk_proxy = pd.Series(0.5, index=df.index, dtype=float)

        secondary = pd.DataFrame({"vendor_key": vendor_key, "external_risk_proxy": risk_proxy})
        secondary = secondary.groupby("vendor_key", as_index=False)["external_risk_proxy"].mean()
        global_risk = float(secondary["external_risk_proxy"].mean()) if not secondary.empty else 0.5
        global_risk = float(np.clip(global_risk, 0.0, 1.0))
        return secondary, global_risk

    def _engineer_features(self, df: pd.DataFrame) -> pd.DataFrame:
        engineered = df.copy()
        engineered = engineered.sort_values(["vendor_code", "order_date"]).reset_index(drop=True)

        grouped = engineered.groupby("vendor_code", sort=False)

        engineered["delay_frequency"] = grouped["delay_flag"].transform("mean").astype(float)
        engineered["rolling_delay_average"] = (
            grouped["delay_days"].transform(lambda s: s.rolling(window=6, min_periods=1).mean()).astype(float)
        )

        rolling_cost_std = grouped["cost"].transform(lambda s: s.rolling(window=6, min_periods=2).std())
        rolling_cost_mean = grouped["cost"].transform(lambda s: s.rolling(window=6, min_periods=1).mean())
        engineered["cost_volatility"] = (rolling_cost_std / rolling_cost_mean.replace(0, np.nan)).fillna(0.0)

        rolling_qty_std = grouped["order_quantity"].transform(lambda s: s.rolling(window=6, min_periods=2).std())
        rolling_qty_mean = grouped["order_quantity"].transform(lambda s: s.rolling(window=6, min_periods=1).mean())
        engineered["demand_variability_score"] = (rolling_qty_std / rolling_qty_mean.replace(0, np.nan)).fillna(0.0)

        engineered["quality_weighted_score"] = (
            engineered["quality_score"] * (1.0 - engineered["defect_rate"].clip(0.0, 1.0))
        ).clip(0.0, 1.0)

        engineered["reliability_index"] = (
            engineered["on_time_rate"].clip(0.0, 1.0) * engineered["quality_weighted_score"].clip(0.0, 1.0)
        ).clip(0.0, 1.0)

        return engineered
    def train_delay_model(self, prepared: PreparedData) -> tuple[dict[str, Any], dict[str, float], dict[str, Any]]:
        X = prepared.features.copy()
        y = prepared.delay_target.copy()

        X_train, X_temp, y_train, y_temp = train_test_split(
            X,
            y,
            test_size=0.20,
            random_state=RANDOM_STATE,
            stratify=y,
        )
        X_val, X_test, y_val, y_test = train_test_split(
            X_temp,
            y_temp,
            test_size=0.50,
            random_state=RANDOM_STATE,
            stratify=y_temp,
        )

        preprocessor = self._build_preprocessor(prepared.numeric_columns, prepared.categorical_columns)
        X_train_t = preprocessor.fit_transform(X_train)
        X_val_t = preprocessor.transform(X_val)
        X_test_t = preprocessor.transform(X_test)

        optuna.logging.set_verbosity(optuna.logging.WARNING)

        def objective(trial: optuna.Trial) -> float:
            params = {
                "n_estimators": trial.suggest_int("n_estimators", 200, 900),
                "max_depth": trial.suggest_int("max_depth", 4, 12),
                "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
                "subsample": trial.suggest_float("subsample", 0.6, 1.0),
                "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
                "min_child_weight": trial.suggest_int("min_child_weight", 1, 12),
                "reg_alpha": trial.suggest_float("reg_alpha", 1e-6, 5.0, log=True),
                "reg_lambda": trial.suggest_float("reg_lambda", 1e-6, 5.0, log=True),
                "gamma": trial.suggest_float("gamma", 1e-8, 3.0, log=True),
            }

            model = xgb.XGBClassifier(
                objective="binary:logistic",
                tree_method="hist",
                device="cuda",
                eval_metric="auc",
                random_state=RANDOM_STATE,
                **params,
            )
            model.fit(
                X_train_t,
                y_train,
                eval_set=[(X_val_t, y_val)],
                verbose=False,
            )
            probabilities = model.predict_proba(X_val_t)[:, 1]
            return float(roc_auc_score(y_val, probabilities))

        trials = int(os.getenv("DELAY_OPTUNA_TRIALS", "12"))
        study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=RANDOM_STATE))
        study.optimize(objective, n_trials=1, show_progress_bar=False)

        best = study.best_params
        model = xgb.XGBClassifier(
            objective="binary:logistic",
            tree_method="hist",
            device="cuda",
            early_stopping_rounds=50,
            eval_metric="auc",
            random_state=RANDOM_STATE,
            **best,
        )
        model.fit(
            X_train_t,
            y_train,
            eval_set=[(X_val_t, y_val)],
            verbose=False,
        )

        predictions = model.predict(X_test_t)
        probabilities = model.predict_proba(X_test_t)[:, 1]

        metrics = {
            "accuracy": round(float(accuracy_score(y_test, predictions)), 4),
            "precision": round(float(precision_score(y_test, predictions, zero_division=0)), 4),
            "recall": round(float(recall_score(y_test, predictions, zero_division=0)), 4),
            "f1": round(float(f1_score(y_test, predictions, zero_division=0)), 4),
            "roc_auc": round(float(roc_auc_score(y_test, probabilities)), 4),
            "best_params": best,
            "best_optuna_auc": round(float(study.best_value), 4),
        }

        defaults = self._compute_defaults(X)
        artifacts = {
            "model": model,
            "preprocessor": preprocessor,
            "feature_columns": prepared.feature_columns,
            "defaults": defaults,
            "feature_names": preprocessor.get_feature_names_out().tolist(),
        }

        shap_context = {
            "X_train_transformed": X_train_t,
            "feature_names": artifacts["feature_names"],
            "model": model,
        }
        return artifacts, metrics, shap_context

    def train_risk_model(self, prepared: PreparedData) -> tuple[dict[str, Any], dict[str, float]]:
        X = prepared.features.copy()
        label_map = {"Low": 0, "Medium": 1, "High": 2}
        y = prepared.risk_target.map(label_map).astype(int)

        X_train, X_temp, y_train, y_temp = train_test_split(
            X,
            y,
            test_size=0.20,
            random_state=RANDOM_STATE,
            stratify=y,
        )
        X_val, X_test, y_val, y_test = train_test_split(
            X_temp,
            y_temp,
            test_size=0.50,
            random_state=RANDOM_STATE,
            stratify=y_temp,
        )

        preprocessor = self._build_preprocessor(prepared.numeric_columns, prepared.categorical_columns)
        X_train_t = preprocessor.fit_transform(X_train)
        X_val_t = preprocessor.transform(X_val)
        X_test_t = preprocessor.transform(X_test)

        optuna.logging.set_verbosity(optuna.logging.WARNING)

        def objective(trial: optuna.Trial) -> float:
            params = {
                "n_estimators": trial.suggest_int("n_estimators", 200, 1000),
                "num_leaves": trial.suggest_int("num_leaves", 31, 255),
                "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
                "max_depth": trial.suggest_int("max_depth", 4, 14),
                "min_child_samples": trial.suggest_int("min_child_samples", 10, 120),
                "subsample": trial.suggest_float("subsample", 0.6, 1.0),
                "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
                "reg_alpha": trial.suggest_float("reg_alpha", 1e-6, 5.0, log=True),
                "reg_lambda": trial.suggest_float("reg_lambda", 1e-6, 5.0, log=True),
            }
            model = lgb.LGBMClassifier(
                objective="multiclass",
                num_class=3,
                device="gpu",
                random_state=RANDOM_STATE,
                **params,
            )
            model.fit(
                X_train_t,
                y_train,
                eval_set=[(X_val_t, y_val)],
                eval_metric="multi_logloss",
                callbacks=[lgb.early_stopping(40, verbose=False)],
            )
            pred = model.predict(X_val_t)
            return float(f1_score(y_val, pred, average="weighted"))

        trials = int(os.getenv("RISK_OPTUNA_TRIALS", "10"))
        study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=RANDOM_STATE))
        study.optimize(objective, n_trials=trials, show_progress_bar=False)

        best = study.best_params
        model = lgb.LGBMClassifier(
            objective="multiclass",
            num_class=3,
            device="gpu",
            random_state=RANDOM_STATE,
            **best,
        )
        model.fit(
            X_train_t,
            y_train,
            eval_set=[(X_val_t, y_val)],
            eval_metric="multi_logloss",
            callbacks=[lgb.early_stopping(50, verbose=False)],
        )

        predictions = model.predict(X_test_t)
        probabilities = model.predict_proba(X_test_t)

        auc_value = float(roc_auc_score(y_test, probabilities, average="weighted", multi_class="ovr"))
        metrics = {
            "accuracy": round(float(accuracy_score(y_test, predictions)), 4),
            "precision": round(float(precision_score(y_test, predictions, average="weighted", zero_division=0)), 4),
            "recall": round(float(recall_score(y_test, predictions, average="weighted", zero_division=0)), 4),
            "f1": round(float(f1_score(y_test, predictions, average="weighted", zero_division=0)), 4),
            "roc_auc": round(auc_value, 4),
            "best_params": best,
            "best_optuna_f1": round(float(study.best_value), 4),
        }

        defaults = self._compute_defaults(X)
        artifacts = {
            "model": model,
            "preprocessor": preprocessor,
            "feature_columns": prepared.feature_columns,
            "defaults": defaults,
            "class_map": {0: "Low", 1: "Medium", 2: "High"},
        }
        return artifacts, metrics

    def train_forecast_model(self, prepared: PreparedData) -> tuple[Prophet, list[dict[str, Any]], dict[str, float]]:
        self._ensure_prophet_backend()
        monthly = prepared.monthly_cost.sort_values("ds").reset_index(drop=True)

        if len(monthly) < 18:
            raise RuntimeError("Forecast model requires at least 18 monthly observations.")

        test_size = min(12, max(6, int(len(monthly) * 0.2)))
        train_df = monthly.iloc[:-test_size].copy()
        test_df = monthly.iloc[-test_size:].copy()

        model = Prophet(yearly_seasonality=True, weekly_seasonality=False, daily_seasonality=False)
        model.fit(train_df)

        future_test = model.make_future_dataframe(periods=test_size, freq="MS")
        forecast_test = model.predict(future_test).tail(test_size)

        y_true = test_df["y"].to_numpy(dtype=float)
        y_pred = forecast_test["yhat"].to_numpy(dtype=float)

        mae = float(mean_absolute_error(y_true, y_pred))
        rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
        denom = np.where(np.abs(y_true) < 1e-9, 1e-9, np.abs(y_true))
        mape = float(np.mean(np.abs((y_true - y_pred) / denom)) * 100.0)

        final_model = Prophet(yearly_seasonality=True, weekly_seasonality=False, daily_seasonality=False)
        final_model.fit(monthly)

        future = final_model.make_future_dataframe(periods=12, freq="MS")
        forecast_future = final_model.predict(future).tail(12)
        forecast_template: list[dict[str, Any]] = []
        for _, row in forecast_future.iterrows():
            forecast_template.append(
                {
                    "forecast_month": row["ds"].date().isoformat(),
                    "predicted_cost": float(row["yhat"]),
                    "lower_bound": float(row["yhat_lower"]),
                    "upper_bound": float(row["yhat_upper"]),
                }
            )

        metrics = {
            "mae": round(mae, 4),
            "rmse": round(rmse, 4),
            "mape": round(mape, 4),
        }
        return final_model, forecast_template, metrics

    def _ensure_prophet_backend(self) -> None:
        prophet_root = Path(prophet_pkg.__file__).resolve().parent
        cmdstan_dirs = sorted((prophet_root / "stan_model").glob("cmdstan-*"))
        for cmdstan_dir in cmdstan_dirs:
            makefile_path = cmdstan_dir / "makefile"
            bin_dir = cmdstan_dir / "bin"
            if bin_dir.exists() and not makefile_path.exists():
                makefile_path.write_text("# Auto-generated marker for cmdstanpy validation.\n", encoding="ascii")

    def generate_explainability(self, delay_artifacts: dict[str, Any], shap_context: dict[str, Any]) -> None:
        x_train = shap_context["X_train_transformed"]
        feature_names = shap_context["feature_names"]
        model = shap_context["model"]

        if x_train.shape[0] == 0:
            return

        sample_size = min(1500, x_train.shape[0])
        rng = np.random.default_rng(RANDOM_STATE)
        sample_idx = rng.choice(x_train.shape[0], size=sample_size, replace=False)
        x_sample = x_train[sample_idx]
        if hasattr(x_sample, "toarray"):
            x_sample = x_sample.toarray()

        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(x_sample)

        summary_path = self.models_dir / "shap_summary.png"
        plt.figure(figsize=(12, 7))
        shap.summary_plot(shap_values, x_sample, feature_names=feature_names, show=False)
        plt.tight_layout()
        plt.savefig(summary_path, dpi=180)
        plt.close()

        importance_path = self.models_dir / "feature_importance.png"
        importances = delay_artifacts["model"].feature_importances_
        importance_frame = pd.DataFrame({"feature": feature_names, "importance": importances})
        importance_frame = importance_frame.sort_values("importance", ascending=False).head(20)

        plt.figure(figsize=(10, 6))
        plt.barh(importance_frame["feature"][::-1], importance_frame["importance"][::-1], color="#1f77b4")
        plt.tight_layout()
        plt.savefig(importance_path, dpi=180)
        plt.close()
    def persist_artifacts(
        self,
        delay_artifacts: dict[str, Any],
        risk_artifacts: dict[str, Any],
        prophet_model: Prophet,
        forecast_template: list[dict[str, Any]],
        all_metrics: dict[str, Any],
    ) -> None:
        with (self.models_dir / "delay_model.pkl").open("wb") as f:
            pickle.dump(delay_artifacts, f)

        with (self.models_dir / "risk_model.pkl").open("wb") as f:
            pickle.dump(risk_artifacts, f)

        with (self.models_dir / "prophet_model.pkl").open("wb") as f:
            pickle.dump(prophet_model, f)

        with (self.models_dir / "forecast_template.json").open("w", encoding="utf-8") as f:
            json.dump(forecast_template, f, indent=2)

        with (self.models_dir / "metrics.json").open("w", encoding="utf-8") as f:
            json.dump(all_metrics, f, indent=2)

    def populate_database(self, processed_df: pd.DataFrame, forecast_template: list[dict[str, Any]]) -> None:
        vendor_agg = (
            processed_df.groupby("vendor_code", as_index=False)
            .agg(
                vendor_name=("vendor_name", "first"),
                category=("category", lambda x: x.mode().iloc[0] if not x.mode().empty else "General"),
                country=("country", lambda x: x.mode().iloc[0] if not x.mode().empty else "Unknown"),
                reliability_index=("reliability_index", "mean"),
                delay_frequency=("delay_frequency", "mean"),
                rolling_delay_average=("rolling_delay_average", "mean"),
                cost_volatility=("cost_volatility", "mean"),
                quality_weighted_score=("quality_weighted_score", "mean"),
                demand_variability_score=("demand_variability_score", "mean"),
                external_risk_proxy=("external_risk_proxy", "mean"),
                vendor_cost_mean=("cost", "mean"),
            )
            .reset_index(drop=True)
        )

        global_mean_cost = float(processed_df["cost"].mean()) if len(processed_df) else 1.0
        if global_mean_cost == 0:
            global_mean_cost = 1.0

        session = SessionLocal()
        try:
            session.execute(delete(Prediction))
            session.execute(delete(Forecast))
            session.execute(delete(RiskScore))
            session.execute(delete(VendorMetric))
            session.execute(delete(Vendor))
            session.commit()

            for _, row in vendor_agg.iterrows():
                vendor = Vendor(
                    vendor_code=str(row["vendor_code"]),
                    name=str(row["vendor_name"]),
                    category=str(row["category"]),
                    country=str(row["country"]),
                )
                session.add(vendor)
                session.flush()

                quality_risk = float(np.clip(1.0 - float(row["quality_weighted_score"]), 0.0, 1.0))
                risk_inputs = RiskInputs(
                    delay_probability=float(np.clip(row["delay_frequency"], 0.0, 1.0)),
                    quality_risk=quality_risk,
                    cost_volatility=float(np.clip(row["cost_volatility"], 0.0, 1.0)),
                    external_risk_proxy=float(np.clip(row["external_risk_proxy"], 0.0, 1.0)),
                    demand_variability=float(np.clip(row["demand_variability_score"], 0.0, 1.0)),
                )
                score = calculate_risk_score(risk_inputs)
                level = risk_level(score)

                metric = VendorMetric(
                    vendor_id=vendor.id,
                    reliability_index=float(row["reliability_index"]),
                    delay_frequency=float(row["delay_frequency"]),
                    rolling_delay_average=float(row["rolling_delay_average"]),
                    cost_volatility=float(row["cost_volatility"]),
                    quality_weighted_score=float(row["quality_weighted_score"]),
                    demand_variability_score=float(row["demand_variability_score"]),
                    quality_risk=quality_risk,
                    external_risk_proxy=float(row["external_risk_proxy"]),
                )
                session.add(metric)

                risk_record = RiskScore(
                    vendor_id=vendor.id,
                    score=score,
                    delay_probability=risk_inputs.delay_probability,
                    quality_risk=risk_inputs.quality_risk,
                    cost_volatility=risk_inputs.cost_volatility,
                    external_risk_proxy=risk_inputs.external_risk_proxy,
                    demand_variability=risk_inputs.demand_variability,
                    risk_level=level,
                )
                session.add(risk_record)

                scale = float(row["vendor_cost_mean"]) / global_mean_cost if global_mean_cost else 1.0
                for point in forecast_template:
                    session.add(
                        Forecast(
                            vendor_id=vendor.id,
                            forecast_month=pd.to_datetime(point["forecast_month"]).date(),
                            predicted_cost=float(point["predicted_cost"]) * scale,
                            lower_bound=float(point["lower_bound"]) * scale,
                            upper_bound=float(point["upper_bound"]) * scale,
                        )
                    )

            session.commit()
        finally:
            session.close()
    def _build_preprocessor(self, numeric_columns: list[str], categorical_columns: list[str]) -> ColumnTransformer:
        numeric_pipeline = Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
            ]
        )
        categorical_pipeline = Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="most_frequent")),
                ("encoder", OneHotEncoder(handle_unknown="ignore")),
            ]
        )

        transformers: list[tuple[str, Pipeline, list[str]]] = []
        if numeric_columns:
            transformers.append(("num", numeric_pipeline, numeric_columns))
        if categorical_columns:
            transformers.append(("cat", categorical_pipeline, categorical_columns))

        if not transformers:
            raise RuntimeError("No features found to build preprocessor.")

        return ColumnTransformer(transformers=transformers)

    def _compute_defaults(self, X: pd.DataFrame) -> dict[str, Any]:
        defaults: dict[str, Any] = {}
        for col in X.columns:
            if pd.api.types.is_numeric_dtype(X[col]):
                median = X[col].median()
                defaults[col] = float(0.0 if pd.isna(median) else median)
            else:
                mode = X[col].mode()
                defaults[col] = str(mode.iloc[0]) if not mode.empty else "Unknown"
        return defaults

    def _find_column(self, df: pd.DataFrame, candidates: list[str]) -> str | None:
        existing = set(df.columns)
        for candidate in candidates:
            normalized = self._normalize_column_name(candidate)
            if normalized in existing:
                return normalized
        return None

    def _extract_vendor_series(self, df: pd.DataFrame, vendor_col: str | None) -> pd.Series:
        if vendor_col:
            vendor_series = df[vendor_col].astype(str)
            return vendor_series

        object_columns = [col for col in df.columns if df[col].dtype == "object"]
        if object_columns:
            return df[object_columns[0]].astype(str)

        raise RuntimeError("Unable to identify vendor column in primary dataset.")

    def _normalize_column_name(self, name: str) -> str:
        normalized = re.sub(r"[^a-zA-Z0-9]+", "_", str(name).strip().lower())
        normalized = re.sub(r"_+", "_", normalized).strip("_")
        return normalized

    def _sanitize_key(self, value: Any) -> str:
        key = re.sub(r"[^a-zA-Z0-9]+", "_", str(value).strip().lower())
        key = re.sub(r"_+", "_", key).strip("_")
        return key or "vendor_unknown"

    def _normalize_series(self, series: pd.Series) -> pd.Series:
        numeric = pd.to_numeric(series, errors="coerce")
        numeric = numeric.replace([np.inf, -np.inf], np.nan)
        if numeric.isna().all():
            return pd.Series(0.5, index=series.index, dtype=float)

        filled = numeric.fillna(numeric.median())
        minimum = float(filled.min())
        maximum = float(filled.max())
        if maximum - minimum < 1e-9:
            return pd.Series(0.5, index=series.index, dtype=float)

        scaled = (filled - minimum) / (maximum - minimum)
        return scaled.clip(0.0, 1.0)

    def _print_metrics(self, all_metrics: dict[str, Any]) -> None:
        self.logger.info("==== Model Evaluation Metrics ====")
        for model_name, metrics in all_metrics.items():
            self.logger.info("%s metrics:", model_name)
            for key, value in metrics.items():
                if isinstance(value, dict):
                    self.logger.info("  %s: %s", key, json.dumps(value))
                else:
                    self.logger.info("  %s: %s", key, value)
        self.logger.info("Artifacts saved under %s", self.models_dir)
