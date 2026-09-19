"""Prediction engine — rules-based v1 (docs: 16_PREDICTION_ENGINE_SPECIFICATION).

Deterministic, explainable weighted feature model. Every prediction carries:
score + confidence + per-factor contributions + model_version + timestamp.

NEVER guarantees sales — every public response must include DISCLAIMER_TEXT.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

MODEL_VERSION = "pred_rules_v1.0"

DISCLAIMER_TEXT = (
    "This is a probabilistic estimate, not a guarantee. Predictions are "
    "directional guidance based on trend signals and estimated market metrics; "
    "they do not predict actual sales, downloads, or Adobe Stock acceptance. "
    "No Adobe Stock sales statistics were used or invented."
)

# Feature weights (docs: 16 §3.2) — sum to 1.0
W_TS = 0.22  # F1 Trend Score
W_ACC = 0.12  # F2 Acceleration
W_SGP = 0.10  # F3 Search growth persistence
W_CD = 0.12  # F4 Content demand
W_CR = 0.10  # F5 Commercial relevance
W_SE = 0.08  # F6 Seasonality
W_SH = 0.12  # F7 Saturation headroom
W_KB = 0.06  # F8 Keyword breadth
W_EG = 0.05  # F9 Engagement momentum
W_HOL = 0.03  # F10 Historical outcome lift

# Decision bands (docs: 16 §3.4)
BAND_STRONG_MIN = 75
BAND_GOOD_MIN = 60
BAND_WATCH_MIN = 45

# Confidence gating (docs: 16 §4)
CS_PRED_DEGRADED_BELOW = 50
CS_PRED_WITHHELD_BELOW = 35

# Confidence component weights
CW_PC = 0.30
CW_FRESHNESS = 0.25
CW_SOURCE_COUNT = 0.20
CW_HISTORY = 0.15
CW_USER_DATA = 0.10

NEUTRAL_LIFT = 50.0


@dataclass(frozen=True)
class PredictionFeatures:
    """All 10 model features (0–100 scale), per micro-niche per run (docs: 16 §3.1)."""

    trend_score: float  # F1
    acceleration: float  # F2: (ACC+2)/4×100 from TV(W0)−TV(W1) clipped [−2,+2]
    search_persistence: float  # F3: fraction of last 4 weeks SG>0 × 100
    content_demand: float  # F4: CD×100
    commercial_relevance: float  # F5: CR×100
    seasonality: float  # F6: SE×100
    saturation_headroom: float  # F7: 100 − CSS
    keyword_breadth: float  # F8: min(topics with TV>0.2, 10)/10×100
    engagement_momentum: float  # F9: EG×100
    historical_lift: float = NEUTRAL_LIFT  # F10; 50 neutral when no user data


@dataclass(frozen=True)
class PredictionFactor:
    name: str
    value: float
    weight: float
    contribution: float
    direction: str  # "supports" | "drags" | "neutral"


@dataclass(frozen=True)
class HorizonEstimates:
    """The six horizon estimates (docs: 16 §3.5). Each: value 0–100."""

    seven_day: float
    thirty_day: float
    seasonal_potential: float
    commercial_potential: float
    trend_persistence: float
    saturation_risk: float


@dataclass(frozen=True)
class PredictionResult:
    prediction_score: float
    band: str
    confidence_score: float
    withheld_from_ranking: bool
    factors: tuple[PredictionFactor, ...]
    estimates: HorizonEstimates
    model_version: str
    prediction_timestamp: str
    disclaimer: str
    summary: str


def acceleration_feature(tv_w0: float, tv_w1: float) -> float:
    """F2: ACC = TV(W0) − TV(W1) clipped [−2,+2], rescaled (ACC+2)/4×100."""
    acc = max(-2.0, min(2.0, tv_w0 - tv_w1))
    return (acc + 2.0) / 4.0 * 100.0


def predict(
    features: PredictionFeatures,
    commercial_potential_score: float,
    saturation_score_css: float,
    spikiness_norm100: float,
    prediction_confidence_pc: float,
    freshness_100: float,
    n_sources: int,
    baseline_weeks: int,
    user_data_present: bool,
    user_data_contradicts: bool = False,
) -> PredictionResult:
    """Run the rules-based v1 prediction (docs: 16 §3–§5)."""
    f = features
    raw_factors = (
        ("F1 Trend Score", f.trend_score, W_TS),
        ("F2 Acceleration", f.acceleration, W_ACC),
        ("F3 Search persistence", f.search_persistence, W_SGP),
        ("F4 Content demand", f.content_demand, W_CD),
        ("F5 Commercial relevance", f.commercial_relevance, W_CR),
        ("F6 Seasonality", f.seasonality, W_SE),
        ("F7 Saturation headroom", f.saturation_headroom, W_SH),
        ("F8 Keyword breadth", f.keyword_breadth, W_KB),
        ("F9 Engagement momentum", f.engagement_momentum, W_EG),
        ("F10 Historical outcome lift", f.historical_lift, W_HOL),
    )
    factors = tuple(
        PredictionFactor(
            name=name,
            value=round(value, 2),
            weight=weight,
            contribution=round(weight * value, 2),
            direction="supports" if value >= 60 else "drags" if value < 40 else "neutral",
        )
        for name, value, weight in raw_factors
    )
    ps = round(max(0.0, min(100.0, sum(x.contribution for x in factors))), 2)

    estimates = _horizon_estimates(
        ps=ps,
        f=f,
        cps=commercial_potential_score,
        css=saturation_score_css,
        spikiness=spikiness_norm100,
    )

    # Confidence (docs: 16 §4)
    source_count_f = min(n_sources, 5) / 5 * 100.0
    history_depth = min(baseline_weeks, 12) / 12 * 100.0
    user_data_f = 0.0 if user_data_contradicts else (100.0 if user_data_present else 50.0)
    confidence = round(
        max(
            0.0,
            min(
                100.0,
                CW_PC * prediction_confidence_pc
                + CW_FRESHNESS * freshness_100
                + CW_SOURCE_COUNT * source_count_f
                + CW_HISTORY * history_depth
                + CW_USER_DATA * user_data_f,
            ),
        ),
        2,
    )
    withheld = confidence < CS_PRED_WITHHELD_BELOW

    if ps >= BAND_STRONG_MIN:
        band = "Strong opportunity"
    elif ps >= BAND_GOOD_MIN:
        band = "Good opportunity"
    elif ps >= BAND_WATCH_MIN:
        band = "Watch"
    else:
        band = "Weak"

    supporters = [x for x in factors if x.direction == "supports"]
    draggers = [x for x in factors if x.direction == "drags"]
    supporters.sort(key=lambda x: x.contribution, reverse=True)
    summary = (
        f"{band} ({ps:.0f}/100, confidence {confidence:.0f}). "
        + (
            "Strong because: "
            + ", ".join(f"{x.name.split(' ', 1)[1]} {x.value:.0f}" for x in supporters[:3])
            + ". "
            if supporters
            else ""
        )
        + (
            "Held back by: "
            + ", ".join(f"{x.name.split(' ', 1)[1]} {x.value:.0f}" for x in draggers[:2])
            + "."
            if draggers
            else ""
        )
    ).strip()

    return PredictionResult(
        prediction_score=ps,
        band=band,
        confidence_score=confidence,
        withheld_from_ranking=withheld,
        factors=factors,
        estimates=estimates,
        model_version=MODEL_VERSION,
        prediction_timestamp=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        disclaimer=DISCLAIMER_TEXT,
        summary=summary,
    )


def _horizon_estimates(
    ps: float, f: PredictionFeatures, cps: float, css: float, spikiness: float
) -> HorizonEstimates:
    """Horizon estimate formulas (docs: 16 §3.5)."""
    seven_day = 0.6 * ps + 0.4 * f.acceleration
    thirty_day = (
        0.45 * ps
        + 0.25 * f.search_persistence
        + 0.20 * f.seasonality
        + 0.10 * f.saturation_headroom
    )
    seasonal = max(f.seasonality, 0.5 * f.seasonality + 0.5 * f.commercial_relevance)
    steadiness = max(0.0, min(100.0, 100.0 - abs(f.acceleration - 50.0) * 2.0))
    persistence = (
        0.4 * f.search_persistence
        + 0.3 * f.keyword_breadth
        + 0.2 * steadiness
        + 0.1 * f.engagement_momentum
    )
    saturation_risk = 0.5 * css + 0.3 * spikiness + 0.2 * f.keyword_breadth

    def clamp(v: float) -> float:
        return round(max(0.0, min(100.0, v)), 2)

    return HorizonEstimates(
        seven_day=clamp(seven_day),
        thirty_day=clamp(thirty_day),
        seasonal_potential=clamp(seasonal),
        commercial_potential=clamp(cps),
        trend_persistence=clamp(persistence),
        saturation_risk=clamp(saturation_risk),
    )
