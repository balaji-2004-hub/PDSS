from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import and_, desc, func, select
from sqlalchemy.orm import Session

from app.database import Forecast, Prediction, RiskScore, Vendor, VendorMetric, get_db
from app.models_loader import ModelRegistry
from app.risk_engine import RiskInputs, calculate_risk_score, risk_level
from app.schemas.api import (
    BasePredictionInput,
    DashboardSummary,
    DelayPredictionResponse,
    ForecastPoint,
    ForecastResponse,
    RecommendationResponse,
    RiskPredictionResponse,
    VendorResponse,
)

router = APIRouter()


def _normalize(value: float, max_value: float = 1.0) -> float:
    if max_value == 0:
        return 0.0
    scaled = value / max_value
    if scaled < 0:
        return 0.0
    if scaled > 1:
        return 1.0
    return float(scaled)


def _get_registry(request: Request) -> ModelRegistry:
    registry: ModelRegistry | None = getattr(request.app.state, "model_registry", None)
    if registry is None:
        raise HTTPException(status_code=503, detail="Models are not loaded.")
    return registry


def _resolve_vendor(db: Session, vendor_code: str | None) -> Vendor | None:
    if not vendor_code:
        return None
    stmt = select(Vendor).where(Vendor.vendor_code == vendor_code)
    return db.scalar(stmt)


@router.get("/vendors", response_model=list[VendorResponse])
async def list_vendors(db: Session = Depends(get_db)) -> list[VendorResponse]:
    vendors = db.scalars(select(Vendor).order_by(Vendor.name)).all()
    output: list[VendorResponse] = []
    for vendor in vendors:
        latest_risk = db.scalar(
            select(RiskScore)
            .where(RiskScore.vendor_id == vendor.id)
            .order_by(desc(RiskScore.created_at))
            .limit(1)
        )
        output.append(
            VendorResponse(
                id=vendor.id,
                vendor_code=vendor.vendor_code,
                name=vendor.name,
                category=vendor.category,
                country=vendor.country,
                latest_risk_score=latest_risk.score if latest_risk else None,
                risk_level=latest_risk.risk_level if latest_risk else None,
            )
        )
    return output


@router.post("/predict-delay", response_model=DelayPredictionResponse)
async def predict_delay(payload: BasePredictionInput, request: Request, db: Session = Depends(get_db)) -> DelayPredictionResponse:
    registry = _get_registry(request)
    label, probability = registry.predict_delay(payload.to_payload())

    quality_risk = 1.0 - _normalize(payload.quality_score)
    inputs = RiskInputs(
        delay_probability=_normalize(probability),
        quality_risk=quality_risk,
        cost_volatility=_normalize(payload.cost_volatility),
        external_risk_proxy=_normalize(payload.external_risk_proxy),
        demand_variability=_normalize(payload.demand_variability_score),
    )
    score = calculate_risk_score(inputs)
    level = risk_level(score)

    vendor = _resolve_vendor(db, payload.vendor_code)
    prediction = Prediction(
        vendor_id=vendor.id if vendor else None,
        model_type="delay",
        input_payload=payload.model_dump(),
        predicted_label=label,
        predicted_probability=probability,
    )
    db.add(prediction)

    if vendor:
        risk_entry = RiskScore(
            vendor_id=vendor.id,
            score=score,
            delay_probability=inputs.delay_probability,
            quality_risk=inputs.quality_risk,
            cost_volatility=inputs.cost_volatility,
            external_risk_proxy=inputs.external_risk_proxy,
            demand_variability=inputs.demand_variability,
            risk_level=level,
        )
        db.add(risk_entry)

    db.commit()

    return DelayPredictionResponse(
        prediction=label,
        probability=round(probability, 4),
        risk_score=score,
        risk_level=level,
        timestamp=datetime.utcnow(),
    )


@router.post("/predict-risk", response_model=RiskPredictionResponse)
async def predict_risk(payload: BasePredictionInput, request: Request, db: Session = Depends(get_db)) -> RiskPredictionResponse:
    registry = _get_registry(request)
    risk_class, confidence = registry.predict_risk(payload.to_payload())

    quality_risk = 1.0 - _normalize(payload.quality_score)
    delay_proxy = _normalize(payload.delay_frequency)
    inputs = RiskInputs(
        delay_probability=delay_proxy,
        quality_risk=quality_risk,
        cost_volatility=_normalize(payload.cost_volatility),
        external_risk_proxy=_normalize(payload.external_risk_proxy),
        demand_variability=_normalize(payload.demand_variability_score),
    )
    score = calculate_risk_score(inputs)
    level = risk_level(score)

    vendor = _resolve_vendor(db, payload.vendor_code)
    prediction = Prediction(
        vendor_id=vendor.id if vendor else None,
        model_type="risk",
        input_payload=payload.model_dump(),
        predicted_label=risk_class,
        predicted_probability=confidence,
    )
    db.add(prediction)

    if vendor:
        risk_entry = RiskScore(
            vendor_id=vendor.id,
            score=score,
            delay_probability=inputs.delay_probability,
            quality_risk=inputs.quality_risk,
            cost_volatility=inputs.cost_volatility,
            external_risk_proxy=inputs.external_risk_proxy,
            demand_variability=inputs.demand_variability,
            risk_level=level,
        )
        db.add(risk_entry)

    db.commit()

    return RiskPredictionResponse(
        risk_class=risk_class,
        confidence=round(confidence, 4),
        risk_score=score,
        risk_level=level,
        timestamp=datetime.utcnow(),
    )


@router.get("/forecast/{vendor_id}", response_model=ForecastResponse)
async def vendor_forecast(vendor_id: int, db: Session = Depends(get_db)) -> ForecastResponse:
    vendor = db.scalar(select(Vendor).where(Vendor.id == vendor_id))
    if vendor is None:
        raise HTTPException(status_code=404, detail=f"Vendor {vendor_id} not found")

    points = db.scalars(
        select(Forecast)
        .where(Forecast.vendor_id == vendor_id)
        .order_by(Forecast.forecast_month)
    ).all()

    return ForecastResponse(
        vendor_id=vendor_id,
        points=[
            ForecastPoint(
                forecast_month=point.forecast_month,
                predicted_cost=point.predicted_cost,
                lower_bound=point.lower_bound,
                upper_bound=point.upper_bound,
            )
            for point in points
        ],
    )


@router.get("/recommend-best-vendor", response_model=RecommendationResponse)
async def recommend_best_vendor(db: Session = Depends(get_db)) -> RecommendationResponse:
    vendors = db.scalars(select(Vendor)).all()
    if not vendors:
        raise HTTPException(status_code=404, detail="No vendors available")

    best_candidate: tuple[Vendor, float, float] | None = None

    for vendor in vendors:
        latest_risk = db.scalar(
            select(RiskScore)
            .where(RiskScore.vendor_id == vendor.id)
            .order_by(desc(RiskScore.created_at))
            .limit(1)
        )
        latest_metrics = db.scalar(
            select(VendorMetric)
            .where(VendorMetric.vendor_id == vendor.id)
            .order_by(desc(VendorMetric.last_updated))
            .limit(1)
        )
        if latest_risk is None or latest_metrics is None:
            continue

        candidate = (vendor, latest_risk.score, latest_metrics.reliability_index)
        if best_candidate is None:
            best_candidate = candidate
            continue

        _, best_risk, best_rel = best_candidate
        if candidate[1] < best_risk or (candidate[1] == best_risk and candidate[2] > best_rel):
            best_candidate = candidate

    if best_candidate is None:
        raise HTTPException(status_code=404, detail="Insufficient vendor metrics for recommendation")

    vendor, score, reliability = best_candidate
    reason = (
        "Selected for lowest composite risk score and strongest reliability index "
        "among vendors with complete metrics."
    )
    return RecommendationResponse(
        vendor_id=vendor.id,
        vendor_code=vendor.vendor_code,
        vendor_name=vendor.name,
        risk_score=round(score, 2),
        reliability_index=round(reliability, 4),
        reason=reason,
    )


@router.get("/dashboard-summary", response_model=DashboardSummary)
async def dashboard_summary(request: Request, db: Session = Depends(get_db)) -> DashboardSummary:
    registry = _get_registry(request)
    today = datetime.utcnow().date()

    total_vendors = db.scalar(select(func.count(Vendor.id))) or 0
    avg_risk_score = db.scalar(select(func.coalesce(func.avg(RiskScore.score), 0.0))) or 0.0
    high_risk_vendors = db.scalar(select(func.count(RiskScore.id)).where(RiskScore.risk_level == "High")) or 0

    delay_predictions_today = db.scalar(
        select(func.count(Prediction.id)).where(
            and_(Prediction.model_type == "delay", func.date(Prediction.created_at) == str(today))
        )
    ) or 0
    risk_predictions_today = db.scalar(
        select(func.count(Prediction.id)).where(
            and_(Prediction.model_type == "risk", func.date(Prediction.created_at) == str(today))
        )
    ) or 0
    forecast_points = db.scalar(select(func.count(Forecast.id))) or 0

    return DashboardSummary(
        total_vendors=int(total_vendors),
        avg_risk_score=round(float(avg_risk_score), 2),
        high_risk_vendors=int(high_risk_vendors),
        delay_predictions_today=int(delay_predictions_today),
        risk_predictions_today=int(risk_predictions_today),
        forecast_points=int(forecast_points),
        model_metrics=registry.artifacts.metrics,
    )
