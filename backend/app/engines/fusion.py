"""Opportunity Fusion Engine (Phase 3): market + personal signal fusion.

Fuses market-side signals (trend score, market opportunity, commercial
potential, seasonality, saturation risk, prediction confidence) with
personal-side signals (personal fit, personal momentum, historical
performance) into one transparent Unified Opportunity Score (0–100).

Design principles (docs: backend/PHASE3_FORMULAS.md):
- Every component is stored; the unified score is a documented weighted
  average with saturation risk as a SUBTRACTIVE penalty — never hidden.
- Personal inputs are None-able. When personal fit is None the output is
  labeled "MARKET-ONLY", confidence is lowered, and NO personal numbers are
  invented — the score simply renormalizes over the market components.
- Explanations are built ONLY from evidence actually passed in. The engine
  never uses guarantee language ("will sell", "will rank", "guaranteed").
- High market + poor personal fit is EXPLAINED, never auto-rejected.
- High personal fit + weak market is labeled a personal-performance
  opportunity, never presented as a market trend.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

# ---------------------------------------------------------------------------
# Named constants — unified score weights (PHASE3_FORMULAS.md §2)
# ---------------------------------------------------------------------------

# Additive components; renormalized over whichever components are present.
FUS_W_MARKET_OPPORTUNITY = 0.25
FUS_W_TREND_MOMENTUM = 0.20
FUS_W_COMMERCIAL_POTENTIAL = 0.15
FUS_W_SEASONALITY = 0.10
FUS_W_PREDICTION_CONFIDENCE = 0.05
FUS_W_PERSONAL_FIT = 0.15
FUS_W_PERSONAL_MOMENTUM = 0.05
FUS_W_HISTORICAL_PERFORMANCE = 0.05

# Saturation risk is subtractive and never enters the weight denominator:
# UNIFIED -= FUS_SATURATION_PENALTY × saturation_risk.
FUS_SATURATION_PENALTY = 0.15

# Special-case gates (PHASE3_FORMULAS.md §4).
FUS_MISMATCH_MARKET_MIN = 70.0  # market_opportunity ≥ this ...
FUS_MISMATCH_FIT_MAX = 35.0  # ... with personal_fit ≤ this → explained, not rejected
FUS_PERSONAL_FIT_MIN = 70.0  # personal_fit ≥ this ...
FUS_PERSONAL_MARKET_MAX = 40.0  # ... with market_opportunity ≤ this → personal-performance

# Confidence score weights (PHASE3_FORMULAS.md §3).
CONF_W_FRESHNESS = 0.20
CONF_W_SOURCES = 0.20
CONF_W_HISTORICAL_CONSISTENCY = 0.15
CONF_W_PREDICTION_CONFIDENCE = 0.15
CONF_W_PRIVATE_AVAILABILITY = 0.15
CONF_W_MARKET_SIGNAL = 0.15

# Market-only outputs lose confidence: no private data → weaker evidence base.
FUS_MARKET_ONLY_CONFIDENCE_PENALTY = 10.0

LABEL_FUSED = "FUSED"
LABEL_MARKET_ONLY = "MARKET-ONLY"

SPECIAL_CASE_MISMATCH = "market_personal_mismatch"
SPECIAL_CASE_PERSONAL = "personal_performance"

# Language that must never appear in an explanation (no guarantees).
_BANNED_PHRASES = (
    "guarantee",
    "guaranteed",
    "will sell",
    "will rank",
    "certain to sell",
    "sure thing",
    "can't miss",
    "cannot fail",
)


def _clip(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


@dataclass(frozen=True)
class FusionInputs:
    """All inputs to the fusion engine. Personal inputs are None-able.

    Market inputs are required 0–100 scores (clipped defensively). Confidence
    inputs: data_freshness ∈ [0,1], n_sources ≥ 0, historical_consistency ∈
    [0,1], market_signal_strength 0–100. Evidence notes are free-text strings
    actually observed — they are the ONLY narrative claims the explanation may
    repeat.
    """

    market_opportunity: float
    trend_momentum: float
    commercial_potential: float
    seasonality: float
    saturation_risk: float
    prediction_confidence: float
    personal_fit: float | None = None
    personal_momentum: float | None = None
    historical_performance: float | None = None
    data_freshness: float = 0.5
    n_sources: int = 1
    historical_consistency: float = 0.5
    market_signal_strength: float = 50.0
    opportunity_title: str = ""
    demand_evidence_notes: tuple[str, ...] = ()
    personal_evidence_notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class FusionResult:
    """Transparent fusion output — every component, weight, and the WHY text."""

    unified_score: float
    components: dict[str, float | None]  # all 9 inputs, None where absent
    weights_used: dict[str, float]  # renormalized additive weights (sum ≈ 1.0)
    saturation_penalty_applied: float  # FUS_SATURATION_PENALTY × saturation_risk
    confidence_score: float  # 0–100
    confidence_factors: dict[str, float]  # factor → 0–100 value (see docstring)
    label: str  # "FUSED" | "MARKET-ONLY"
    special_case: str | None  # "market_personal_mismatch" | "personal_performance" | None
    provenance_per_input: dict[str, str]  # component → provenance label
    opportunity_title: str
    demand_evidence_notes: tuple[str, ...]
    personal_evidence_notes: tuple[str, ...]
    explanation: str = ""


class OpportunityFusionEngine:
    """Fuses market and personal signals into one explainable score."""

    def compute(
        self,
        inputs: FusionInputs,
        *,
        provenance_per_input: dict[str, str] | None = None,
    ) -> FusionResult:
        """Compute the unified score, confidence, label, and explanation.

        Formula (PHASE3_FORMULAS.md §2):

            UNIFIED = clip( Σ(w_i·c_i) / Σ(w_i)  −  0.15·saturation_risk )

        over all present components (personal ones only when not None).
        Saturation is subtractive and never in the denominator. Label is
        "MARKET-ONLY" when personal_fit is None; confidence is then lowered
        by FUS_MARKET_ONLY_CONFIDENCE_PENALTY. No personal numbers are ever
        invented.
        """
        comps: dict[str, float | None] = {
            "market_opportunity": _clip(inputs.market_opportunity),
            "trend_momentum": _clip(inputs.trend_momentum),
            "commercial_potential": _clip(inputs.commercial_potential),
            "seasonality": _clip(inputs.seasonality),
            "saturation_risk": _clip(inputs.saturation_risk),
            "prediction_confidence": _clip(inputs.prediction_confidence),
            "personal_fit": _clip(inputs.personal_fit) if inputs.personal_fit is not None else None,
            "personal_momentum": (
                _clip(inputs.personal_momentum)
                if inputs.personal_momentum is not None
                else None
            ),
            "historical_performance": (
                _clip(inputs.historical_performance)
                if inputs.historical_performance is not None
                else None
            ),
        }
        additive_weights = {
            "market_opportunity": FUS_W_MARKET_OPPORTUNITY,
            "trend_momentum": FUS_W_TREND_MOMENTUM,
            "commercial_potential": FUS_W_COMMERCIAL_POTENTIAL,
            "seasonality": FUS_W_SEASONALITY,
            "prediction_confidence": FUS_W_PREDICTION_CONFIDENCE,
            "personal_fit": FUS_W_PERSONAL_FIT,
            "personal_momentum": FUS_W_PERSONAL_MOMENTUM,
            "historical_performance": FUS_W_HISTORICAL_PERFORMANCE,
        }
        present = {k: v for k, v in comps.items() if v is not None and k in additive_weights}
        total_w = sum(additive_weights[k] for k in present)
        base = (
            sum(present[k] * additive_weights[k] for k in present) / total_w
            if total_w > 0
            else 0.0
        )
        penalty = FUS_SATURATION_PENALTY * comps["saturation_risk"]
        unified = round(_clip(base - penalty), 2)

        label = LABEL_FUSED if comps["personal_fit"] is not None else LABEL_MARKET_ONLY
        confidence, conf_factors = self._confidence(inputs, label)
        special_case = self._special_case(comps)

        result = FusionResult(
            unified_score=unified,
            components=comps,
            weights_used={k: additive_weights[k] / total_w for k in present}
            if total_w > 0
            else {},
            saturation_penalty_applied=round(penalty, 2),
            confidence_score=confidence,
            confidence_factors=conf_factors,
            label=label,
            special_case=special_case,
            provenance_per_input=dict(provenance_per_input or {}),
            opportunity_title=inputs.opportunity_title,
            demand_evidence_notes=tuple(inputs.demand_evidence_notes),
            personal_evidence_notes=tuple(inputs.personal_evidence_notes),
        )
        # Frozen dataclass: attach the evidence-grounded explanation immutably.
        return replace(result, explanation=self.explain(result))

    def _confidence(self, inputs: FusionInputs, label: str) -> tuple[float, dict[str, float]]:
        """Confidence 0–100 (PHASE3_FORMULAS.md §3):

            CONF = 0.20·freshness + 0.20·sources + 0.15·consistency
                 + 0.15·prediction_confidence + 0.15·private_availability
                 + 0.15·market_signal_strength   (all 0–100)

        minus 10 when label is MARKET-ONLY (no private data → weaker evidence).
        """
        freshness = _clip(100.0 * max(0.0, min(1.0, inputs.data_freshness)))
        sources = _clip(100.0 * min(max(inputs.n_sources, 0), 4) / 4.0)
        consistency = _clip(100.0 * max(0.0, min(1.0, inputs.historical_consistency)))
        pred_conf = _clip(inputs.prediction_confidence)
        private = 100.0 if inputs.personal_fit is not None else 0.0
        market_signal = _clip(inputs.market_signal_strength)
        raw = (
            CONF_W_FRESHNESS * freshness
            + CONF_W_SOURCES * sources
            + CONF_W_HISTORICAL_CONSISTENCY * consistency
            + CONF_W_PREDICTION_CONFIDENCE * pred_conf
            + CONF_W_PRIVATE_AVAILABILITY * private
            + CONF_W_MARKET_SIGNAL * market_signal
        )
        penalty = FUS_MARKET_ONLY_CONFIDENCE_PENALTY if label == LABEL_MARKET_ONLY else 0.0
        factors = {
            "data_freshness": round(freshness, 2),
            "n_sources": round(sources, 2),
            "historical_consistency": round(consistency, 2),
            "prediction_confidence": round(pred_conf, 2),
            "private_data_availability": round(private, 2),
            "market_signal_strength": round(market_signal, 2),
            "market_only_penalty_applied": penalty,
        }
        return round(_clip(raw - penalty), 2), factors

    @staticmethod
    def _special_case(comps: dict[str, float | None]) -> str | None:
        market = comps["market_opportunity"]
        fit = comps["personal_fit"]
        if fit is not None and market is not None:
            if market >= FUS_MISMATCH_MARKET_MIN and fit <= FUS_MISMATCH_FIT_MAX:
                return SPECIAL_CASE_MISMATCH
            if fit >= FUS_PERSONAL_FIT_MIN and market <= FUS_PERSONAL_MARKET_MAX:
                return SPECIAL_CASE_PERSONAL
        return None

    def explain(self, result: FusionResult) -> str:
        """WHY paragraph built ONLY from evidence actually passed in.

        Every claim cites a component value or a caller-supplied evidence
        note. No guarantee language ("will sell", "will rank", "guaranteed")
        ever appears — the engine describes signals, not certainties.
        """
        c = result.components
        title = result.opportunity_title or "This opportunity"
        parts: list[str] = []  # engine's own template sentences (checked for banned language)
        quotes: list[str] = []  # verbatim caller-supplied evidence (reported, not claimed)

        parts.append(
            f"{title} scored {result.unified_score:.0f}/100 "
            f"({'fused market + personal assessment' if result.label == LABEL_FUSED else 'market-only assessment — no private performance data was available, so personal fit could not be evaluated'})."
        )

        parts.append(
            "Market side: market opportunity "
            f"{c['market_opportunity']:.0f}/100, trend momentum {c['trend_momentum']:.0f}/100, "
            f"commercial potential {c['commercial_potential']:.0f}/100, seasonality "
            f"{c['seasonality']:.0f}/100, prediction confidence {c['prediction_confidence']:.0f}/100. "
            f"Saturation risk {c['saturation_risk']:.0f}/100 reduced the score by "
            f"{result.saturation_penalty_applied:.1f} points."
        )
        demand_quoted = "; ".join(n.strip() for n in result.demand_evidence_notes if n.strip())
        if demand_quoted:
            quotes.append(f"Observed market evidence: {demand_quoted}.")

        if result.label == LABEL_FUSED:
            personal_bits = [f"personal fit {c['personal_fit']:.0f}/100"]
            if c["personal_momentum"] is not None:
                personal_bits.append(f"personal momentum {c['personal_momentum']:.0f}/100")
            if c["historical_performance"] is not None:
                personal_bits.append(
                    f"historical performance {c['historical_performance']:.0f}/100"
                )
            parts.append(
                "Personal side (your own track record): " + ", ".join(personal_bits) + "."
            )
            if result.personal_evidence_notes:
                personal_quoted = "; ".join(
                    n.strip() for n in result.personal_evidence_notes if n.strip()
                )
                if personal_quoted:
                    quotes.append(f"Observed personal evidence: {personal_quoted}.")
        else:
            parts.append(
                "No private performance data was available, so the personal side is "
                "absent from this score — treat it as a market view only."
            )

        if result.special_case == SPECIAL_CASE_MISMATCH:
            parts.append(
                f"Note the split: market signals are strong ({c['market_opportunity']:.0f}/100) "
                f"but this area is weak in your own track record (personal fit "
                f"{c['personal_fit']:.0f}/100). This is not a rejection — it means entering "
                "would rely on market demand rather than your proven strengths, so keep "
                "batches small and differentiated if you proceed."
            )
        elif result.special_case == SPECIAL_CASE_PERSONAL:
            parts.append(
                "This is a personal-performance opportunity, not a market trend: your "
                f"history in this area is strong (personal fit {c['personal_fit']:.0f}/100) "
                f"while market signals are modest (market opportunity "
                f"{c['market_opportunity']:.0f}/100). It suits playing to your strengths "
                "rather than chasing the trend."
            )

        parts.append(
            f"Confidence {result.confidence_score:.0f}/100 reflects data freshness, source "
            "count, historical consistency, prediction confidence, private-data "
            "availability, and market signal strength — not a promise of sales."
        )

        # Banned-language check covers the engine's own template sentences only:
        # caller-supplied evidence is quoted verbatim as observed evidence, never
        # presented as the engine's own claim.
        template_text = " ".join(parts)
        lowered = template_text.lower()
        for banned in _BANNED_PHRASES:
            assert banned not in lowered, f"banned phrase leaked into explanation: {banned!r}"
        return template_text + (" " + " ".join(quotes) if quotes else "")


def explanation_has_banned_language(text: str) -> bool:
    """True if `text` contains guarantee-style language (used to vet LLM output)."""
    lowered = text.lower()
    return any(banned in lowered for banned in _BANNED_PHRASES)
