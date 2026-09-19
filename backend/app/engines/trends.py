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
