from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RiskInputs:
    delay_probability: float
    quality_risk: float
    cost_volatility: float
    external_risk_proxy: float
    demand_variability: float


def _clamp_01(value: float) -> float:
    if value < 0:
        return 0.0
    if value > 1:
        return 1.0
    return float(value)


def calculate_risk_score(inputs: RiskInputs) -> float:
    weighted = (
        0.30 * _clamp_01(inputs.delay_probability)
        + 0.25 * _clamp_01(inputs.quality_risk)
        + 0.20 * _clamp_01(inputs.cost_volatility)
        + 0.15 * _clamp_01(inputs.external_risk_proxy)
        + 0.10 * _clamp_01(inputs.demand_variability)
    )
    return round(weighted * 100.0, 2)


def risk_level(score: float) -> str:
    if score >= 70:
        return "High"
    if score >= 40:
        return "Medium"
    return "Low"
