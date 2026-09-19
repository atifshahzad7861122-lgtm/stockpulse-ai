"""Opportunity generation engine — deterministic, rules-based v1 (docs: 13 §6, 15 §6).

Consumes trend analyses + market intelligence, emits ranked opportunities.
Rules (docs/15 §6.3): minimum depth = micro-niche; max one opportunity per
(micro-niche × format) per 7-day run; a micro-niche needs ≥ 3 distinct topics
with signals before it can carry scores.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from app.engines.scoring import (
    OS_ACTIONABLE_MIN,
    opportunity_score,
    saturation_score,
    trend_score,
)

# Named constants for the opportunity stage
MIN_TOPICS_PER_NICHE = 3
MIN_TS_FOR_OPPORTUNITY = 40.0
MAX_OPPORTUNITIES_PER_RUN = 20
SUGGESTED_VOLUMES = {
    "Open": 8,
    "Moderate": 5,
    "Crowded": 3,
    "Saturated": 2,
}


@dataclass(frozen=True)
class NicheIntelligence:
    """Market intelligence for one micro-niche feeding opportunity generation."""

    micro_niche_id: str
    micro_niche_name: str
    analyses: tuple  # tuple[TrendAnalysis]
    commercial_relevance: float  # 0–1, Estimated
    content_demand: float  # 0–1, Estimated
    content_saturation: float  # 0–1, Estimated
    competition: float  # 0–1
    source_freshness: float  # 0–1
    n_sources: int
    provenance: str = "ESTIMATED"


@dataclass(frozen=True)
class GeneratedOpportunity:
    micro_niche_id: str
    title: str
    summary: str
    opportunity_score: float
    confidence: float
    actionable: bool
    demand_evidence: tuple[dict, ...]
    risk_notes: str | None
    saturation_band: str
    suggested_volume: int
    recommended_formats: tuple[str, ...]
    data_provenance: str
    notes: tuple[str, ...] = field(default_factory=tuple)


def generate_opportunities(niches: list[NicheIntelligence]) -> list[GeneratedOpportunity]:
    """Deterministic rules-based v1 opportunity scan (docs: 15 §6, 13 §6).

    Never lowers the quality bar: niches that fail the minimum-topic or minimum
    trend-score bar are skipped with no output (empty list is a valid result).
    """
    results: list[GeneratedOpportunity] = []
    for niche in niches:
        if len(niche.analyses) < MIN_TOPICS_PER_NICHE:
            continue

        # Aggregate trend score inputs: mean of per-topic raw inputs mapped 0–100.
        # Raw metrics (TV/SG/KM ∈ [−1,+3]) map to 0–100 via (x + 1) / 4 × 100.
        tv_100 = _mean100(a.trend_velocity for a in niche.analyses)
        sg_100 = _mean100(a.search_growth for a in niche.analyses)
        km_100 = _mean100(a.keyword_momentum for a in niche.analyses)
        eg_100 = 50.0  # v1: engagement placeholder until EG source wired; neutral
        se = sum(a.seasonality for a in niche.analyses) / len(niche.analyses)

        ts = trend_score(tv_100, sg_100, km_100, eg_100, se).score
        if ts < MIN_TS_FOR_OPPORTUNITY:
            continue

        mc = sum(a.market_consistency for a in niche.analyses) / len(niche.analyses)
        sat = saturation_score(niche.content_saturation, niche.competition)

        os_result = opportunity_score(
            trend_score_value=ts,
            commercial_relevance=niche.commercial_relevance,
            content_demand=niche.content_demand,
            content_saturation=niche.content_saturation,
            market_consistency=mc,
            source_freshness=niche.source_freshness,
            n_sources=niche.n_sources,
            prediction_confidence=50.0,  # v1 neutral; predictor refines downstream
        )

        evidence = tuple(
            {
                "signal_id": None,
                "metric_id": None,
                "note": a.explanation,
            }
            for a in niche.analyses
        )

        risk_notes = _risk_notes(os_result.score, sat.score, sat.band or "")
        formats = _recommended_formats(niche.micro_niche_name, sat.band or "")

        results.append(
            GeneratedOpportunity(
                micro_niche_id=niche.micro_niche_id,
                title=f"{niche.micro_niche_name} — {sat.band} window ({velocity_word(niche)})",
                summary=(
                    f"Trend score {ts:.0f}/100 across {len(niche.analyses)} tracked topics. "
                    f"{sat.band} niche (saturation {sat.score:.0f}/100). "
                    + (
                        "Actionable now."
                        if os_result.actionable
                        else "Not actionable yet — see notes."
                    )
                ),
                opportunity_score=os_result.score,
                confidence=os_result.data_confidence,
                actionable=os_result.actionable,
                demand_evidence=evidence,
                risk_notes=risk_notes,
                saturation_band=sat.band or "Unknown",
                suggested_volume=SUGGESTED_VOLUMES.get(sat.band or "", 2),
                recommended_formats=formats,
                data_provenance=niche.provenance,
                notes=os_result.notes,
            )
        )

    results.sort(key=lambda o: o.opportunity_score, reverse=True)
    return results[:MAX_OPPORTUNITIES_PER_RUN]


def _mean100(values) -> float:
    """Map raw metric values ∈ [−1, +3] to 0–100 and take the mean."""
    mapped = [((v + 1.0) / 4.0) * 100.0 for v in values]
    return sum(mapped) / len(mapped) if mapped else 50.0


def velocity_word(niche: NicheIntelligence) -> str:
    flags = [a.velocity_flag for a in niche.analyses]
    if all(f == "accelerating" for f in flags):
        return "accelerating fast"
    if "declining" in flags:
        return "mixed signals"
    return "rising interest"


def _risk_notes(score: float, css: float, band: str) -> str | None:
    parts: list[str] = []
    if score < OS_ACTIONABLE_MIN:
        parts.append(f"Score {score:.0f} below actionable bar {OS_ACTIONABLE_MIN} — monitor only.")
    if band == "Saturated":
        parts.append("Saturated niche: cap production at 2 assets, differentiation is critical.")
    elif band == "Crowded":
        parts.append("Crowded niche: keep batches small and highly differentiated.")
    return "; ".join(parts) if parts else None


def _recommended_formats(niche_name: str, band: str) -> tuple[str, ...]:
    """Image always; video added for less-saturated niches (docs/15 §6 depth rules)."""
    if band in ("Open", "Moderate"):
        return ("IMAGE", "VIDEO")
    return ("IMAGE",)


# ---------------------------------------------------------------------------
# Personal Fit Score (Phase 2 — real-data layer; extended in Phase 3)
# ---------------------------------------------------------------------------

# Component weights; renormalized over whichever components have data, so a
# score with 3 components and one with 9 are both weighted averages over what
# is actually known. Weights sum to 1.0 but renormalization means only the
# relative ratios matter.
_PFS_WEIGHTS: tuple[tuple[str, float], ...] = (
    ("category", 0.25),
    ("keyword", 0.15),
    ("asset", 0.10),
    ("content_type", 0.10),
    ("theme", 0.05),
    ("momentum", 0.10),
    ("acceptance", 0.15),
    ("historical_downloads", 0.05),
    ("historical_earnings", 0.05),
)

# Track-record depth normalization spans: log10-scaled so the curve saturates
# at a genuinely deep track record (~10k downloads / ~$100k earnings).
_PFS_HIST_DL_LOG_SPAN = 4.0
_PFS_HIST_EARN_LOG_SPAN = 5.0


def _match_key(perf: Mapping[str, Mapping[str, float]], name: str | None) -> str | None:
    """Case-insensitive key lookup; returns the actual mapping key or None."""
    if not name or not perf:
        return None
    lowered = name.strip().lower()
    for key in perf:
        if str(key).strip().lower() == lowered:
            return key
    return None


def _relative_strength(value: float, peers: Sequence[float]) -> float | None:
    """Strength of `value` vs the user's own portfolio max (0–100), or None."""
    peak = max(peers) if peers else 0.0
    if peak <= 0 or value <= 0:
        return None
    return min(100.0, max(0.0, 100.0 * value / peak))


def _row_strength(peers: Mapping[str, Mapping[str, float]], key: str) -> float | None:
    """One performance row → 0–100 (blend of earnings/downloads relative strength)."""
    row = peers.get(key, {})
    earnings_peers = [float(r.get("earnings", 0) or 0) for r in peers.values()]
    downloads_peers = [float(r.get("downloads", 0) or 0) for r in peers.values()]
    earnings = _relative_strength(float(row.get("earnings", 0) or 0), earnings_peers)
    downloads = _relative_strength(float(row.get("downloads", 0) or 0), downloads_peers)
    parts = [p for p in (earnings, downloads) if p is not None]
    return sum(parts) / len(parts) if parts else None


@dataclass(frozen=True)
class PersonalFitResult:
    """Explainable Personal Fit Score: score + per-component breakdown.

    ``components`` holds only components that had data (name → 0–100 value);
    ``weights`` are the renormalized weights actually used (sum to 1.0);
    ``missing`` names the components that had no data and were skipped —
    skipped means "no private data", never treated as a low score.
    """

    score: float
    components: dict[str, float]
    weights: dict[str, float]
    missing: tuple[str, ...]


def _momentum_score(current_7d: float, prev_7d: float) -> float | None:
    """Recent momentum 0–100 from 7-day windows: flat = 50, doubled = 100,
    halved = 0. New activity from a zero baseline = 100; zero/zero = no data."""
    cur = float(current_7d or 0.0)
    prev = float(prev_7d or 0.0)
    if prev <= 0:
        return 100.0 if cur > 0 else None
    return min(100.0, max(0.0, 50.0 + 50.0 * (cur - prev) / prev))


def _depth_score(total: float | None, log_span: float) -> float | None:
    """Track-record depth 0–100: log10-scaled so a genuinely deep history
    saturates at 100. None when the total is unknown (never guessed)."""
    if total is None or total < 0:
        return None
    return min(100.0, max(0.0, 100.0 * math.log10(1.0 + float(total)) / log_span))


def personal_fit_breakdown(
    *,
    opportunity_category: str | None = None,
    opportunity_keywords: Sequence[str] = (),
    opportunity_formats: Sequence[str] = (),
    opportunity_themes: Sequence[str] = (),
    category_performance: Mapping[str, Mapping[str, float]] | None = None,
    asset_type_performance: Mapping[str, Mapping[str, float]] | None = None,
    content_type_performance: Mapping[str, Mapping[str, float]] | None = None,
    keyword_performance: Mapping[str, Mapping[str, float]] | None = None,
    theme_performance: Mapping[str, Mapping[str, float]] | None = None,
    momentum_windows: Mapping[str, Mapping[str, float]] | None = None,
    overall_acceptance_rate: float | None = None,
    historical_downloads: float | None = None,
    historical_earnings: float | None = None,
) -> PersonalFitResult | None:
    """Full-spec Personal Fit Score with an explainable component breakdown.

    EXACT FORMULA (also documented in backend/PHASE3_FORMULAS.md):

        PFS = Σ(w_i · c_i) / Σ(w_i)     over components i that HAVE data

    Components (each 0–100; weights renormalized over the available ones):
      category (0.25)            relative strength of the opportunity's category
                                 vs the user's own portfolio max
      keyword (0.15)             mean relative strength of matched keywords
      asset (0.10)               mean relative strength across asset-type rows
                                 (unavailable: private asset snapshots carry no
                                 asset_type — component skipped, never zeroed)
      content_type (0.10)        relative strength per content type, scored for
                                 IMAGE and VIDEO independently; averaged over the
                                 opportunity's formats (all types when unknown)
      theme (0.05)               mean relative strength of matched themes
                                 (themes derived from the user's own asset
                                 titles — a different data source than keywords)
      momentum (0.10)            mean over {downloads, earnings} of
                                 clip(50 + 50·(cur7−prev7)/prev7); 50 = flat
      acceptance (0.15)          100 × overall_acceptance_rate
      historical_downloads (0.05) clip(100·log10(1+total)/4) — track-record depth
      historical_earnings (0.05)  clip(100·log10(1+total_usd)/5) — depth

    Relative strength = 100 × value / portfolio_max (per earnings/downloads,
    then averaged); None when max ≤ 0 or value ≤ 0. None-means-no-data rule:
    a component with no private data is SKIPPED (renormalized away), never
    treated as 0. Returns None when NO component has data — null means "no
    private data", not "bad fit".
    """
    components: dict[str, float] = {}

    cat = category_performance or {}
    cat_key = _match_key(cat, opportunity_category)
    if cat_key is not None:
        strength = _row_strength(cat, cat_key)
        if strength is not None:
            components["category"] = strength

    kw = keyword_performance or {}
    kw_hits: list[float] = []
    for keyword in opportunity_keywords:
        kw_key = _match_key(kw, keyword)
        if kw_key is not None:
            strength = _row_strength(kw, kw_key)
            if strength is not None:
                kw_hits.append(strength)
    if kw_hits:
        components["keyword"] = sum(kw_hits) / len(kw_hits)

    asset = asset_type_performance or {}
    asset_hits = [s for key in asset if (s := _row_strength(asset, key)) is not None]
    if asset_hits:
        components["asset"] = sum(asset_hits) / len(asset_hits)

    ctype = content_type_performance or {}
    if ctype:
        formats = {str(f).strip().upper() for f in opportunity_formats if f}
        # IMAGE and VIDEO scored independently; average over the opportunity's
        # formats, or over all content types when formats are unknown.
        type_keys = [k for k in ctype if not formats or str(k).strip().upper() in formats]
        type_hits = [s for key in type_keys if (s := _row_strength(ctype, key)) is not None]
        if type_hits:
            components["content_type"] = sum(type_hits) / len(type_hits)

    theme = theme_performance or {}
    theme_hits: list[float] = []
    for t in opportunity_themes:
        theme_key = _match_key(theme, t)
        if theme_key is not None:
            strength = _row_strength(theme, theme_key)
            if strength is not None:
                theme_hits.append(strength)
    if theme_hits:
        components["theme"] = sum(theme_hits) / len(theme_hits)

    mom = momentum_windows or {}
    mom_hits: list[float] = []
    for metric in ("downloads", "earnings"):
        window = mom.get(metric) or {}
        score = _momentum_score(window.get("current_7d", 0), window.get("prev_7d", 0))
        if score is not None:
            mom_hits.append(score)
    if mom_hits:
        components["momentum"] = sum(mom_hits) / len(mom_hits)

    if overall_acceptance_rate is not None and 0.0 <= overall_acceptance_rate <= 1.0:
        components["acceptance"] = 100.0 * overall_acceptance_rate

    depth_dl = _depth_score(historical_downloads, _PFS_HIST_DL_LOG_SPAN)
    if depth_dl is not None:
        components["historical_downloads"] = depth_dl
    depth_earn = _depth_score(historical_earnings, _PFS_HIST_EARN_LOG_SPAN)
    if depth_earn is not None:
        components["historical_earnings"] = depth_earn

    if not components:
        return None
    used = [(name, w) for name, w in _PFS_WEIGHTS if name in components]
    total_weight = sum(w for _, w in used)
    if total_weight <= 0:
        return None
    score = sum(components[name] * w for name, w in used) / total_weight
    missing = tuple(name for name, _ in _PFS_WEIGHTS if name not in components)
    return PersonalFitResult(
        score=round(min(100.0, max(0.0, score)), 2),
        components={k: round(v, 2) for k, v in components.items()},
        weights={k: w / total_weight for k, w in used},
        missing=missing,
    )


def personal_fit_score(
    *,
    opportunity_category: str | None = None,
    opportunity_keywords: Sequence[str] = (),
    opportunity_formats: Sequence[str] = (),
    opportunity_themes: Sequence[str] = (),
    category_performance: Mapping[str, Mapping[str, float]] | None = None,
    asset_type_performance: Mapping[str, Mapping[str, float]] | None = None,
    content_type_performance: Mapping[str, Mapping[str, float]] | None = None,
    keyword_performance: Mapping[str, Mapping[str, float]] | None = None,
    theme_performance: Mapping[str, Mapping[str, float]] | None = None,
    momentum_windows: Mapping[str, Mapping[str, float]] | None = None,
    overall_acceptance_rate: float | None = None,
    historical_downloads: float | None = None,
    historical_earnings: float | None = None,
) -> float | None:
    """Personal Fit Score: how well an opportunity fits the user's own track record.

    EXACT FORMULA (identical to ``personal_fit_breakdown``):

        PFS = Σ(w_i · c_i) / Σ(w_i)     over components i that HAVE data

    Components (each 0–100; weights renormalized over the available ones):
      category (0.25), keyword (0.15), asset (0.10), content_type (0.10),
      theme (0.05), momentum (0.10), acceptance (0.15),
      historical_downloads (0.05), historical_earnings (0.05).

    None-means-no-data rule: a component with no private data is SKIPPED
    (renormalized away), never treated as 0.

    Returns a 0–100 score, or **None when there is no private data at all**
    (never guesses — null means "no private data", not "bad fit"). This is the
    backward-compatible scalar wrapper around ``personal_fit_breakdown``. Kept
    fully separate from ``opportunity_score`` (CONTRACT.md §8.2); the API
    returns both.
    """
    result = personal_fit_breakdown(
        opportunity_category=opportunity_category,
        opportunity_keywords=opportunity_keywords,
        opportunity_formats=opportunity_formats,
        opportunity_themes=opportunity_themes,
        category_performance=category_performance,
        asset_type_performance=asset_type_performance,
        content_type_performance=content_type_performance,
        keyword_performance=keyword_performance,
        theme_performance=theme_performance,
        momentum_windows=momentum_windows,
        overall_acceptance_rate=overall_acceptance_rate,
        historical_downloads=historical_downloads,
        historical_earnings=historical_earnings,
    )
    return result.score if result is not None else None
