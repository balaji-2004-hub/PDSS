from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class VendorResponse(BaseModel):
    id: int
    vendor_code: str
    name: str
    category: str | None = None
    country: str | None = None
    latest_risk_score: float | None = None
    risk_level: str | None = None


class BasePredictionInput(BaseModel):
    vendor_code: str | None = Field(default=None, description="Optional vendor code for DB linkage")
    lead_time_days: float = 0.0
    order_quantity: float = 0.0
    unit_price: float = 0.0
    on_time_rate: float = 0.0
    quality_score: float = 0.0
    defect_rate: float = 0.0
    demand_variability_score: float = 0.0
    cost_volatility: float = 0.0
    external_risk_proxy: float = 0.0
    delay_frequency: float = 0.0
    rolling_delay_average: float = 0.0
    reliability_index: float = 0.0
    quality_weighted_score: float = 0.0
    country: str = "Unknown"
    category: str = "Unknown"

    def to_payload(self) -> dict[str, Any]:
        data = self.model_dump()
        data.pop("vendor_code", None)
        return data


class DelayPredictionResponse(BaseModel):
    prediction: str
    probability: float
    risk_score: float
    risk_level: str
    timestamp: datetime


class RiskPredictionResponse(BaseModel):
    risk_class: str
    confidence: float
    risk_score: float
    risk_level: str
    timestamp: datetime


class ForecastPoint(BaseModel):
    forecast_month: date
    predicted_cost: float
    lower_bound: float
    upper_bound: float


class ForecastResponse(BaseModel):
    vendor_id: int
    points: list[ForecastPoint]


class RecommendationResponse(BaseModel):
    vendor_id: int
    vendor_code: str
    vendor_name: str
    risk_score: float
    reliability_index: float
    reason: str


class DashboardSummary(BaseModel):
    total_vendors: int
    avg_risk_score: float
    high_risk_vendors: int
    delay_predictions_today: int
    risk_predictions_today: int
    forecast_points: int
    model_metrics: dict[str, Any]
