"""Scoring engine — CONTRACT.md §8 formulas (docs: 15).

All scores are 0–100. Every scoring function returns a float and a factor
breakdown (explainability is a product principle, docs/13 §19).
No magic numbers: all weights are named constants.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Named constants (CONTRACT.md §8)
# ---------------------------------------------------------------------------

# Trend Score weights — TS = 0.30·TV₁₀₀ + 0.25·SG₁₀₀ + 0.20·KM₁₀₀ + 0.15·EG₁₀₀ + 0.10·(SE×100)
TS_W_TV = 0.30
TS_W_SG = 0.25
TS_W_KM = 0.20
TS_W_EG = 0.15
TS_W_SE = 0.10

# Opportunity Score weights — OS = 0.35·TS + 0.25·(CR×100) + 0.20·(CD×100) + 0.20·(100 − CS×100)
OS_W_TS = 0.35
OS_W_CR = 0.25
OS_W_CD = 0.20
OS_W_SAT = 0.20

# Commercial Potential Score weights
CPS_W_CR = 0.35
CPS_W_CD = 0.25
CPS_W_SE = 0.15
CPS_W_ROOM = 0.15
CPS_W_FORMAT = 0.10

# Content Saturation Score weights — CSS = 100 × (0.55·CS + 0.45·CO)
CSS_W_CS = 0.55
CSS_W_CO = 0.45

# Prediction Confidence weights
PC_W_MC = 0.30
PC_W_FRESHNESS = 0.25
PC_W_SOURCES = 0.20
PC_W_STABILITY = 0.15
PC_W_AGREEMENT = 0.10

# Priority score weights (docs: 20 §6)
PRIO_W_TREND = 0.35
PRIO_W_DEADLINE = 0.25
PRIO_W_VALUE = 0.25
PRIO_W_BOOST = 0.15
PRIO_REWORK_PENALTY_PER = 5
PRIO_REWORK_CAP = 3
PRIO_DEADLINE_WINDOW_DAYS = 30

# Bands / gates
CSS_BAND_OPEN_MAX = 30
CSS_BAND_MODERATE_MAX = 55
CSS_BAND_CROWDED_MAX = 75

OS_ACTIONABLE_MIN = 55
DATA_CONFIDENCE_ACTIONABLE_MIN = 0.5
PC_BLOCKED_BELOW = 35
PC_DEGRADED_BELOW = 50

USER_BOOST_BY_BAND = {"P0": 100, "P1": 75, "P2": 50, "P3": 25, "P4": 0}


@dataclass(frozen=True)
class Factor:
    name: str
    value: float
    weight: float
    contribution: float
    direction: str  # "supports" | "drags" | "neutral"


@dataclass(frozen=True)
class ScoreResult:
    score: float
    factors: tuple[Factor, ...] = field(default_factory=tuple)
    band: str | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)


def clip(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def norm100(x: float, p5: float, p95: float) -> float:
    """Min-max normalize against trailing 12-week per-category distribution."""
    if p95 <= p5:
        return 50.0
    return clip(100.0 * (x - p5) / (p95 - p5))


def _factor(name: str, value: float, weight: float) -> Factor:
    contribution = weight * value
    if contribution >= 5.0:
        direction = "supports"
    elif contribution <= -5.0:
        direction = "drags"
    else:
        direction = "neutral"
    return Factor(
        name=name,
        value=round(value, 2),
        weight=weight,
        contribution=round(contribution, 2),
        direction=direction,
    )


# ---------------------------------------------------------------------------
# 8.1 Trend Score — "How hot is this trend right now?"
# ---------------------------------------------------------------------------


def trend_score(
    tv_100: float, sg_100: float, km_100: float, eg_100: float, seasonality: float
) -> ScoreResult:
    """TS = 0.30·TV₁₀₀ + 0.25·SG₁₀₀ + 0.20·KM₁₀₀ + 0.15·EG₁₀₀ + 0.10·(SE×100)."""
    se_100 = seasonality * 100.0
    factors = (
        _factor("Trend velocity (TV)", tv_100, TS_W_TV),
        _factor("Search growth (SG)", sg_100, TS_W_SG),
        _factor("Keyword momentum (KM)", km_100, TS_W_KM),
        _factor("Engagement signals (EG)", eg_100, TS_W_EG),
        _factor("Seasonality (SE)", se_100, TS_W_SE),
    )
    score = clip(sum(f.contribution for f in factors))
    return ScoreResult(score=round(score, 2), factors=factors)


# ---------------------------------------------------------------------------
# 8.2 Opportunity Score — "Should we act on this?"
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OpportunityScoreResult:
    score: float
    data_confidence: float
    actionable: bool
    factors: tuple[Factor, ...] = field(default_factory=tuple)
    notes: tuple[str, ...] = field(default_factory=tuple)


def opportunity_score(
    trend_score_value: float,
    commercial_relevance: float,
    content_demand: float,
    content_saturation: float,
    market_consistency: float,
    source_freshness: float,
    n_sources: int,
    prediction_confidence: float,
) -> OpportunityScoreResult:
    """OS = 0.35·TS + 0.25·(CR×100) + 0.20·(CD×100) + 0.20·(100 − CS×100).

    Confidence gating (binding): actionable only if OS ≥ 55 AND
    data-confidence ≥ 0.5. PC < 35 blocks the actionable list regardless of OS.
    """
    cr_100 = commercial_relevance * 100.0
    cd_100 = content_demand * 100.0
    room_100 = 100.0 - content_saturation * 100.0
    factors = (
        _factor("Trend score (TS)", trend_score_value, OS_W_TS),
        _factor("Commercial relevance (CR)", cr_100, OS_W_CR),
        _factor("Content demand (CD)", cd_100, OS_W_CD),
        _factor("Niche room (100 − saturation)", room_100, OS_W_SAT),
    )
    score = round(clip(sum(f.contribution for f in factors)), 2)

    data_confidence = (
        0.5 * market_consistency + 0.3 * source_freshness + 0.2 * (min(n_sources, 4) / 4)
    )
    data_confidence = round(data_confidence, 3)

    notes: list[str] = []
    actionable = True
    if score < OS_ACTIONABLE_MIN:
        actionable = False
        notes.append(
            f"Opportunity score {score} is below the actionable threshold " f"{OS_ACTIONABLE_MIN}."
        )
    if data_confidence < DATA_CONFIDENCE_ACTIONABLE_MIN:
        actionable = False
        notes.append(
            "Insufficient evidence — do not act "
            f"(data-confidence {data_confidence} < {DATA_CONFIDENCE_ACTIONABLE_MIN})."
        )
    if prediction_confidence < PC_BLOCKED_BELOW:
        actionable = False
        notes.append(
            f"Prediction confidence {prediction_confidence} < {PC_BLOCKED_BELOW}: "
            "blocked from the actionable list regardless of score."
        )
    return OpportunityScoreResult(
        score=score,
        data_confidence=data_confidence,
        actionable=actionable,
        factors=factors,
        notes=tuple(notes),
    )


# ---------------------------------------------------------------------------
# 8.3 Commercial Potential Score — "How sellable is this niche?"
# ---------------------------------------------------------------------------


def commercial_potential_score(
    commercial_relevance: float,
    content_demand: float,
    seasonality: float,
    competition: float,
    format_fit: float,
) -> ScoreResult:
    """CPS = 0.35·(CR×100) + 0.25·(CD×100) + 0.15·(SE×100)
    + 0.15·(100 − CO×100) + 0.10·format_fit."""
    room_100 = 100.0 - competition * 100.0
    factors = (
        _factor("Commercial relevance (CR)", commercial_relevance * 100.0, CPS_W_CR),
        _factor("Content demand (CD)", content_demand * 100.0, CPS_W_CD),
        _factor("Seasonality (SE)", seasonality * 100.0, CPS_W_SE),
        _factor("Competition room (100 − CO)", room_100, CPS_W_ROOM),
        _factor("Format fit", format_fit, CPS_W_FORMAT),
    )
    score = clip(sum(f.contribution for f in factors))
    return ScoreResult(score=round(score, 2), factors=factors)


# ---------------------------------------------------------------------------
# 8.4 Content Saturation Score — "How crowded is this niche?"
# ---------------------------------------------------------------------------


def saturation_score(content_saturation: float, competition: float) -> ScoreResult:
    """CSS = 100 × (0.55·CS + 0.45·CO). Higher = more saturated."""
    score = round(clip(100.0 * (CSS_W_CS * content_saturation + CSS_W_CO * competition)), 2)
    if score <= CSS_BAND_OPEN_MAX:
        band = "Open"
        guidance = "Up to 8 assets recommended."
    elif score <= CSS_BAND_MODERATE_MAX:
        band = "Moderate"
        guidance = "Up to 5 assets recommended."
    elif score <= CSS_BAND_CROWDED_MAX:
        band = "Crowded"
        guidance = "Max 3 assets recommended."
    else:
        band = "Saturated"
        guidance = "Max 2 assets recommended."
    return ScoreResult(score=score, band=band, notes=(guidance,))


# ---------------------------------------------------------------------------
# 8.5 Prediction Confidence — "How much should we trust these numbers?"
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PredictionConfidenceResult:
    confidence: float
    status: str  # "ok" | "degraded" | "low"
    factors: tuple[Factor, ...] = field(default_factory=tuple)
    notes: tuple[str, ...] = field(default_factory=tuple)


def prediction_confidence(
    market_consistency: float,
    freshness_100: float,
    n_sources: int,
    stability_100: float,
    user_agreement_100: float,
) -> PredictionConfidenceResult:
    """PC per CONTRACT §8.5. PC < 50 → degraded; used with low-confidence wording."""
    source_term = min(n_sources, 5) / 5 * 100.0
    factors = (
        _factor("Market consistency (MC)", market_consistency * 100.0, PC_W_MC),
        _factor("Source freshness", freshness_100, PC_W_FRESHNESS),
        _factor("Source count", source_term, PC_W_SOURCES),
        _factor("Stability", stability_100, PC_W_STABILITY),
        _factor("User agreement", user_agreement_100, PC_W_AGREEMENT),
    )
    confidence = round(clip(sum(f.contribution for f in factors)), 2)
    if confidence < PC_DEGRADED_BELOW:
        status = "degraded"
        notes = ("Low confidence — directional only.",)
    else:
        status = "ok"
        notes = ()
    return PredictionConfidenceResult(
        confidence=confidence, status=status, factors=factors, notes=notes
    )


# ---------------------------------------------------------------------------
# 8.6 Priority score (production queue, docs: 20 §6)
# ---------------------------------------------------------------------------


def deadline_urgency(days_remaining: float | None) -> float:
    """100 × (1 − days_remaining/30), clamped [0,100]; 100 when overdue; 0 if no deadline."""
    if days_remaining is None:
        return 0.0
    return clip(100.0 * (1.0 - days_remaining / PRIO_DEADLINE_WINDOW_DAYS))


@dataclass(frozen=True)
class PriorityScoreResult:
    score: float
    components: dict[str, float]
    priority_band: str


def priority_score(
    trend_momentum: float,
    days_remaining: float | None,
    predicted_value: float,
    priority_band: str,
    rework_count: int,
) -> PriorityScoreResult:
    """Queue priority_score with always-visible component breakdown."""
    user_boost = USER_BOOST_BY_BAND.get(priority_band.upper(), 50)
    urgency = deadline_urgency(days_remaining)
    rework_penalty = PRIO_REWORK_PENALTY_PER * min(rework_count, PRIO_REWORK_CAP)
    raw = (
        PRIO_W_TREND * trend_momentum
        + PRIO_W_DEADLINE * urgency
        + PRIO_W_VALUE * predicted_value
        + PRIO_W_BOOST * user_boost
        - rework_penalty
    )
    components = {
        "trend_momentum": round(PRIO_W_TREND * trend_momentum, 2),
        "deadline_urgency": round(PRIO_W_DEADLINE * urgency, 2),
        "predicted_value": round(PRIO_W_VALUE * predicted_value, 2),
        "user_boost": round(PRIO_W_BOOST * user_boost, 2),
        "rework_penalty": round(-rework_penalty, 2),
    }
    return PriorityScoreResult(
        score=round(clip(raw), 2), components=components, priority_band=priority_band
    )
