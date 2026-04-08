from __future__ import annotations

import json
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass
class LoadedModelArtifacts:
    delay_artifacts: dict[str, Any]
    risk_artifacts: dict[str, Any]
    prophet_model: Any
    metrics: dict[str, Any]
    forecast_template: list[dict[str, Any]]


class ModelRegistry:
    def __init__(self, models_dir: Path) -> None:
        self.models_dir = models_dir
        self._artifacts: LoadedModelArtifacts | None = None

    @property
    def artifacts(self) -> LoadedModelArtifacts:
        if self._artifacts is None:
            raise RuntimeError("Model artifacts are not loaded.")
        return self._artifacts

    def load(self) -> None:
        delay_path = self.models_dir / "delay_model.pkl"
        risk_path = self.models_dir / "risk_model.pkl"
        prophet_path = self.models_dir / "prophet_model.pkl"
        metrics_path = self.models_dir / "metrics.json"
        forecast_template_path = self.models_dir / "forecast_template.json"

        missing = [
            str(path)
            for path in [delay_path, risk_path, prophet_path, metrics_path, forecast_template_path]
            if not path.exists()
        ]
        if missing:
            raise RuntimeError(f"Missing trained model artifacts: {missing}")

        with delay_path.open("rb") as f:
            delay_artifacts = pickle.load(f)
        with risk_path.open("rb") as f:
            risk_artifacts = pickle.load(f)
        with prophet_path.open("rb") as f:
            prophet_model = pickle.load(f)
        with metrics_path.open("r", encoding="utf-8") as f:
            metrics = json.load(f)
        with forecast_template_path.open("r", encoding="utf-8") as f:
            forecast_template = json.load(f)

        self._artifacts = LoadedModelArtifacts(
            delay_artifacts=delay_artifacts,
            risk_artifacts=risk_artifacts,
            prophet_model=prophet_model,
            metrics=metrics,
            forecast_template=forecast_template,
        )

    def _build_feature_frame(self, payload: dict[str, Any], feature_columns: list[str], defaults: dict[str, Any]) -> pd.DataFrame:
        row: dict[str, Any] = {}
        for column in feature_columns:
            if column in payload:
                row[column] = payload[column]
            else:
                row[column] = defaults.get(column)
        return pd.DataFrame([row], columns=feature_columns)

    def predict_delay(self, payload: dict[str, Any]) -> tuple[str, float]:
        model = self.artifacts.delay_artifacts["model"]
        preprocessor = self.artifacts.delay_artifacts["preprocessor"]
        feature_columns = self.artifacts.delay_artifacts["feature_columns"]
        defaults = self.artifacts.delay_artifacts["defaults"]
        frame = self._build_feature_frame(payload, feature_columns, defaults)
        transformed = preprocessor.transform(frame)
        proba = float(model.predict_proba(transformed)[:, 1][0])
        label = "Delayed" if proba >= 0.5 else "On-Time"
        return label, proba

    def predict_risk(self, payload: dict[str, Any]) -> tuple[str, float]:
        model = self.artifacts.risk_artifacts["model"]
        preprocessor = self.artifacts.risk_artifacts["preprocessor"]
        feature_columns = self.artifacts.risk_artifacts["feature_columns"]
        defaults = self.artifacts.risk_artifacts["defaults"]
        class_map = self.artifacts.risk_artifacts.get("class_map", {})
        frame = self._build_feature_frame(payload, feature_columns, defaults)
        transformed = preprocessor.transform(frame)
        proba = model.predict_proba(transformed)[0]
        classes = list(model.classes_)
        idx = int(proba.argmax())
        raw_label = classes[idx]
        label = str(class_map.get(int(raw_label), raw_label))
        confidence = float(proba[idx])
        return label, confidence
