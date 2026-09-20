"""Trend analysis engine — 7-day analysis model (docs: 15 §3).

For each topic/micro-niche, three windows are compared:
- W0 (current): most recent complete 7 days
- W1 (previous): the 7 days before W0
- B (historical baseline): trailing 12-week median of 7-day values

Metrics: TV (trend velocity), SG (search growth), KM (keyword momentum),
MC (market consistency), SE (seasonality), plus velocity/momentum/seasonality flags.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field

# Named constants from docs/15 §3.2
DIVIDE_BY_ZERO_EPSILON = 1.0
CLIP_MIN_RAW = -1.0
CLIP_MAX_RAW = 3.0
MC_SINGLE_SOURCE_PENALTY = 0.3
USER_PERFORMANCE_AGREEMENT_BONUS = 0.1
SEASONALITY_HIGH_THRESHOLD = 0.6
VELOCITY_HIGH_THRESHOLD = 1.0
MOMENTUM_HIGH_THRESHOLD = 0.5
TOP_KEYWORDS_FOR_MOMENTUM = 5


def _clip_raw(value: float) -> float:
    return max(CLIP_MIN_RAW, min(CLIP_MAX_RAW, value))


@dataclass(frozen=True)
class WindowValues:
    """Aggregate signal values for the three analysis windows."""

    w0: float
    w1: float
    baseline: float


def trend_velocity(w0: float, w1: float) -> float:
    """TV = (V(W0) − V(W1)) / max(V(W1), ε), clipped [−1, +3]."""
    return _clip_raw((w0 - w1) / max(w1, DIVIDE_BY_ZERO_EPSILON))


def search_growth(w0: float, baseline: float) -> float:
    """SG = (V(W0) − V(B)) / max(V(B), ε), clipped [−1, +3]."""
    return _clip_raw((w0 - baseline) / max(baseline, DIVIDE_BY_ZERO_EPSILON))


def keyword_momentum(keyword_tvs: list[float]) -> float:
    """KM = mean TV over top-5 related keywords, clipped [−1, +3]."""
    if not keyword_tvs:
        return 0.0
    top = sorted(keyword_tvs, reverse=True)[:TOP_KEYWORDS_FOR_MOMENTUM]
    return _clip_raw(sum(top) / len(top))


def market_consistency(
    source_z_scores: list[float], user_performance_agrees: bool = False
) -> float:
    """MC = 1 − (std_dev(source_z) / (mean_abs_z + ε)), clipped [0,1].

    Single source → 0.3 penalty. User performance agreeing adds +0.1 (cap 1.0).
    """
    if len(source_z_scores) < 2:
        mc = MC_SINGLE_SOURCE_PENALTY
    else:
        mean_abs = statistics.fmean(abs(z) for z in source_z_scores)
        std = statistics.pstdev(source_z_scores)
        mc = 1.0 - (std / (mean_abs + DIVIDE_BY_ZERO_EPSILON))
        mc = max(0.0, min(1.0, mc))
    if user_performance_agrees:
        mc = min(1.0, mc + USER_PERFORMANCE_AGREEMENT_BONUS)
    return round(mc, 3)


@dataclass(frozen=True)
class TrendAnalysis:
    topic: str
    trend_velocity: float
    search_growth: float
    keyword_momentum: float
    market_consistency: float
    seasonality: float
    velocity_flag: str
    momentum_flag: str
    seasonality_flag: str
    explanation: str
    provenance: str = "THIRD_PARTY"


def analyze_topic(
    topic: str,
    windows: WindowValues,
    keyword_tvs: list[float],
    source_z_scores: list[float],
    seasonality: float,
    user_performance_agrees: bool = False,
    provenance: str = "THIRD_PARTY",
) -> TrendAnalysis:
    """Run the full 7-day analysis for one topic/micro-niche."""
    tv = trend_velocity(windows.w0, windows.w1)
    sg = search_growth(windows.w0, windows.baseline)
    km = keyword_momentum(keyword_tvs)
    mc = market_consistency(source_z_scores, user_performance_agrees)

    velocity_flag = (
        "accelerating"
        if tv >= VELOCITY_HIGH_THRESHOLD
        else "rising" if tv > 0 else "stable" if tv > -0.25 else "declining"
    )
    momentum_flag = "broad" if km >= MOMENTUM_HIGH_THRESHOLD else "narrow" if km > 0 else "stalled"
    seasonality_flag = (
        "in-season"
        if seasonality >= SEASONALITY_HIGH_THRESHOLD
        else "approaching" if seasonality > 0.2 else "off-season"
    )

    explanation = (
        f"{topic}: velocity {tv:+.2f} ({velocity_flag}) vs previous 7 days; "
        f"search growth {sg:+.2f} vs 12-week baseline; "
        f"keyword momentum {km:+.2f} ({momentum_flag} across related terms); "
        f"source agreement {mc:.2f}; seasonality {seasonality:.2f} ({seasonality_flag})."
    )
    return TrendAnalysis(
        topic=topic,
        trend_velocity=round(tv, 3),
        search_growth=round(sg, 3),
        keyword_momentum=round(km, 3),
        market_consistency=mc,
        seasonality=round(seasonality, 3),
        velocity_flag=velocity_flag,
        momentum_flag=momentum_flag,
        seasonality_flag=seasonality_flag,
        explanation=explanation,
        provenance=provenance,
    )


@dataclass(frozen=True)
class SevenDayRun:
    """Result of a 7-day analysis run over multiple topics."""

    window_w0_start: str
    window_w0_end: str
    analyses: tuple[TrendAnalysis, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------------------
# 30-day analysis (FINAL MASTER SPEC §11–12).
#
# Same math as the 7-day model, but on 30-day windows:
# - M0 (current): most recent complete 30 days
# - M1 (previous): the 30 days before M0
# ---------------------------------------------------------------------------

# Momentum classification thresholds on a velocity value clipped to [-1, +3].
MOMENTUM_STRONGLY_RISING_MIN = 1.0
MOMENTUM_RISING_MIN = 0.25
MOMENTUM_STABLE_MIN = -0.25
MOMENTUM_DECLINING_MIN = -1.0

# Signal band thresholds on a 0–100 normalized score.
SIGNAL_HIGH_MIN = 66.0
SIGNAL_MEDIUM_MIN = 33.0


def monthly_velocity(m0: float, m1: float) -> float:
    """MV = (V(M0) − V(M1)) / max(V(M1), ε), clipped [−1, +3]."""
    return _clip_raw((m0 - m1) / max(m1, DIVIDE_BY_ZERO_EPSILON))


def classify_momentum(velocity: float) -> str:
    """Five-level momentum classification (spec §10).

    STRONGLY_RISING | RISING | STABLE | DECLINING | STRONGLY_DECLINING
    """
    if velocity >= MOMENTUM_STRONGLY_RISING_MIN:
        return "STRONGLY_RISING"
    if velocity >= MOMENTUM_RISING_MIN:
        return "RISING"
    if velocity >= MOMENTUM_STABLE_MIN:
        return "STABLE"
    if velocity >= MOMENTUM_DECLINING_MIN:
        return "DECLINING"
    return "STRONGLY_DECLINING"


def signal_band(score_100: float) -> str:
    """HIGH | MEDIUM | LOW band for a 0–100 normalized signal."""
    if score_100 >= SIGNAL_HIGH_MIN:
        return "HIGH"
    if score_100 >= SIGNAL_MEDIUM_MIN:
        return "MEDIUM"
    return "LOW"


@dataclass(frozen=True)
class ThirtyDayValues:
    """Aggregate signal values for the two 30-day analysis windows."""

    m0: float
    m1: float


@dataclass(frozen=True)
class ThirtyDayAnalysis:
    topic: str
    monthly_velocity: float
    momentum: str
    signal: str
    explanation: str
    provenance: str = "THIRD_PARTY"


def analyze_30d(
    topic: str,
    months: ThirtyDayValues,
    score_100: float,
    provenance: str = "THIRD_PARTY",
) -> ThirtyDayAnalysis:
    """Run the 30-day analysis for one topic/micro-niche.

    ``score_100`` is the already-normalized 0–100 30-day signal (see
    engines.market_intelligence); it drives the HIGH/MEDIUM/LOW band.
    """
    mv = monthly_velocity(months.m0, months.m1)
    momentum = classify_momentum(mv)
    band = signal_band(score_100)
    explanation = (
        f"{topic}: 30-day velocity {mv:+.2f} ({momentum.lower().replace('_', ' ')}) "
        f"vs previous 30 days; 30-day signal {band} ({score_100:.0f}/100)."
    )
    return ThirtyDayAnalysis(
        topic=topic,
        monthly_velocity=round(mv, 3),
        momentum=momentum,
        signal=band,
        explanation=explanation,
        provenance=provenance,
    )


def _direction(momentum: str) -> str:
    if momentum in ("STRONGLY_RISING", "RISING"):
        return "up"
    if momentum in ("STRONGLY_DECLINING", "DECLINING"):
        return "down"
    return "flat"


def _stronger(m1: str, m2: str, direction: str) -> str:
    order = ["STRONGLY_DECLINING", "DECLINING", "STABLE", "RISING", "STRONGLY_RISING"]
    i1, i2 = order.index(m1), order.index(m2)
    return order[max(i1, i2)] if direction == "up" else order[min(i1, i2)]


@dataclass(frozen=True)
class WindowComparison:
    """7-day vs 30-day comparison for one topic (spec §12)."""

    topic: str
    velocity_7d: float
    velocity_30d: float
    momentum_7d: str
    momentum_30d: str
    signal_7d: str
    signal_30d: str
    momentum: str
    explanation: str


def compare_7d_30d(
    topic: str,
    tv_7d: float,
    tv_30d: float,
    score_7d: float,
    score_30d: float,
) -> WindowComparison:
    """Compare short-term (7d) vs longer-term (30d) movement.

    Combined momentum: the stronger agreeing direction when both windows agree;
    STABLE when they diverge (a short-term spike inside a declining market, or
    vice versa), with the divergence spelled out in the explanation.
    """
    m7 = classify_momentum(tv_7d)
    m30 = classify_momentum(tv_30d)
    s7 = signal_band(score_7d)
    s30 = signal_band(score_30d)
    d7, d30 = _direction(m7), _direction(m30)
    if d7 == d30 and d7 != "flat":
        combined = _stronger(m7, m30, d7)
        note = f"7D and 30D agree ({combined.lower().replace('_', ' ')})."
    elif d7 == "flat" and d30 == "flat":
        combined = "STABLE"
        note = "7D and 30D both flat."
    else:
        combined = "STABLE"
        note = (
            f"7D and 30D diverge (7D {m7.lower().replace('_', ' ')}, "
            f"30D {m30.lower().replace('_', ' ')}) — treated as stable until they agree."
        )
    explanation = (
        f"{topic}: 7D signal {s7} (velocity {tv_7d:+.2f}), "
        f"30D signal {s30} (velocity {tv_30d:+.2f}). {note}"
    )
    return WindowComparison(
        topic=topic,
        velocity_7d=round(tv_7d, 3),
        velocity_30d=round(tv_30d, 3),
        momentum_7d=m7,
        momentum_30d=m30,
        signal_7d=s7,
        signal_30d=s30,
        momentum=combined,
        explanation=explanation,
    )
