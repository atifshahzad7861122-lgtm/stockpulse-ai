"""Opportunity-fusion service layer (Phase 3).

Assembles ``FusionInputs`` from an Opportunity row + private data, runs
``OpportunityFusionEngine``, and persists ``OpportunityFusionScore`` rows.

Also exposes ``fused_opportunity_score(db, opportunity)`` — the integration
point the Daily Production Planner uses for ranking ("fused" source), with a
defensive fallback to ``opportunity_score`` when fusion cannot run.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.engines.fusion import FusionInputs, FusionResult, OpportunityFusionEngine
from app.models.fusion import OpportunityFusionScore
from app.models.intelligence import Opportunity
from app.schemas.enums import DataProvenance
from app.services.fusion_explanation import render_explanation
from app.services.personal_fit import compute_personal_fit_breakdown, personal_evidence_notes

# Neutral defaults for market inputs the caller did not supply. Labeled
# ESTIMATED provenance in component_json — never presented as measured.
_NEUTRAL_DEFAULT = 50.0


def _prov(value: DataProvenance | str | None) -> str:
    if value is None:
        return DataProvenance.ESTIMATED.value
    return value.value if hasattr(value, "value") else str(value)


def _demand_notes(opportunity: Opportunity, extra: list[str]) -> list[str]:
    notes: list[str] = []
    evidence = opportunity.demand_evidence or []
    for item in evidence:
        if isinstance(item, dict):
            note = item.get("note")
            if note:
                notes.append(str(note))
        elif item:
            notes.append(str(item))
    notes.extend(n for n in extra if n)
    return notes[:10]


def build_fusion_inputs(
    db: Session,
    opportunity: Opportunity,
    *,
    trend_momentum: float | None = None,
    commercial_potential: float | None = None,
    seasonality: float | None = None,
    saturation_risk: float | None = None,
    data_freshness: float | None = None,
    n_sources: int | None = None,
    historical_consistency: float | None = None,
    market_signal_strength: float | None = None,
    demand_evidence_notes: list[str] | None = None,
) -> tuple[FusionInputs, dict[str, str]]:
    """Assemble engine inputs + per-input provenance for one opportunity.

    Market side comes from the opportunity row; personal side from the private
    tables (None when absent — never invented); unsupplied market inputs fall
    back to the neutral default with ESTIMATED provenance.
    """
    opp_prov = _prov(getattr(opportunity, "data_provenance", None))
    market_opportunity = float(opportunity.opportunity_score or 0.0)
    prediction_confidence = float(opportunity.confidence or 0.0) * 100.0

    fit = compute_personal_fit_breakdown(
        db,
        micro_niche_id=opportunity.micro_niche_id,
        title=opportunity.title or "",
        summary=opportunity.summary or "",
    )
    comps = fit.components if fit else {}
    personal_fit = fit.score if fit else None
    personal_momentum = comps.get("momentum")
    hist_bits = [comps[k] for k in ("historical_downloads", "historical_earnings") if k in comps]
    historical_performance = sum(hist_bits) / len(hist_bits) if hist_bits else None

    provenance: dict[str, str] = {}
    provenance["market_opportunity"] = opp_prov
    provenance["prediction_confidence"] = opp_prov

    def _market(name: str, value: float | None) -> float:
        if value is None:
            provenance[name] = DataProvenance.ESTIMATED.value
            return _NEUTRAL_DEFAULT
        provenance[name] = DataProvenance.USER_PROVIDED.value
        return float(value)

    tm = _market("trend_momentum", trend_momentum)
    cp = _market("commercial_potential", commercial_potential)
    se = _market("seasonality", seasonality)
    sr = _market("saturation_risk", saturation_risk)

    # Personal provenance: USER_PROVIDED when the component had real private
    # data, ABSENT when the engine skipped it (None-means-no-data rule).
    provenance["personal_fit"] = (
        DataProvenance.USER_PROVIDED.value if personal_fit is not None else "ABSENT"
    )
    provenance["personal_momentum"] = (
        DataProvenance.USER_PROVIDED.value if personal_momentum is not None else "ABSENT"
    )
    provenance["historical_performance"] = (
        DataProvenance.USER_PROVIDED.value if historical_performance is not None else "ABSENT"
    )

    inputs = FusionInputs(
        market_opportunity=market_opportunity,
        trend_momentum=tm,
        commercial_potential=cp,
        seasonality=se,
        saturation_risk=sr,
        prediction_confidence=prediction_confidence,
        personal_fit=personal_fit,
        personal_momentum=personal_momentum,
        historical_performance=historical_performance,
        data_freshness=0.5 if data_freshness is None else data_freshness,
        n_sources=1 if n_sources is None else n_sources,
        historical_consistency=0.5 if historical_consistency is None else historical_consistency,
        market_signal_strength=(
            market_opportunity if market_signal_strength is None else market_signal_strength
        ),
        opportunity_title=opportunity.title or "",
        demand_evidence_notes=tuple(_demand_notes(opportunity, demand_evidence_notes or [])),
        personal_evidence_notes=tuple(personal_evidence_notes(fit) if fit else ()),
    )
    return inputs, provenance


def compute_and_store(
    db: Session,
    opportunity: Opportunity,
    *,
    trend_momentum: float | None = None,
    commercial_potential: float | None = None,
    seasonality: float | None = None,
    saturation_risk: float | None = None,
    data_freshness: float | None = None,
    n_sources: int | None = None,
    historical_consistency: float | None = None,
    market_signal_strength: float | None = None,
    demand_evidence_notes: list[str] | None = None,
) -> tuple[OpportunityFusionScore, str]:
    """Run the fusion engine and persist the score. Returns (row, renderer)."""
    inputs, provenance = build_fusion_inputs(
        db,
        opportunity,
        trend_momentum=trend_momentum,
        commercial_potential=commercial_potential,
        seasonality=seasonality,
        saturation_risk=saturation_risk,
        data_freshness=data_freshness,
        n_sources=n_sources,
        historical_consistency=historical_consistency,
        market_signal_strength=market_signal_strength,
        demand_evidence_notes=demand_evidence_notes,
    )
    engine = OpportunityFusionEngine()
    # compute() fills the deterministic explanation; the renderer may replace
    # it with the local-LLM phrasing (private data stays on localhost).
    result: FusionResult = engine.compute(inputs, provenance_per_input=provenance)
    explanation, renderer = render_explanation(
        deterministic_text=result.explanation,
        title=inputs.opportunity_title,
        components={k: v for k, v in result.components.items()},
        demand_evidence_notes=inputs.demand_evidence_notes,
        personal_evidence_notes=inputs.personal_evidence_notes,
    )

    component_json: dict[str, Any] = {
        "inputs": {
            name: {
                "value": value,
                "provenance": provenance.get(name, DataProvenance.ESTIMATED.value),
            }
            for name, value in result.components.items()
        },
        "weights_used": result.weights_used,
        "saturation_penalty_applied": result.saturation_penalty_applied,
        "special_case": result.special_case,
        "explanation_renderer": renderer,
    }
    row = OpportunityFusionScore(
        opportunity_id=opportunity.id,
        unified_score=result.unified_score,
        market_opportunity=result.components["market_opportunity"],
        personal_fit=result.components["personal_fit"],
        trend_momentum=result.components["trend_momentum"],
        commercial_potential=result.components["commercial_potential"],
        seasonality=result.components["seasonality"],
        saturation_risk=result.components["saturation_risk"],
        prediction_confidence=result.components["prediction_confidence"],
        personal_momentum=result.components["personal_momentum"],
        historical_performance=result.components["historical_performance"],
        component_json=component_json,
        explanation=explanation,
        confidence_score=result.confidence_score,
        confidence_factors_json=result.confidence_factors,
        label=result.label,
        # The row itself is the engine's *predicted* score — a computed output,
        # not a user-supplied fact. Per-input lineage lives in component_json
        # ("inputs" carry each component's own provenance).
        data_provenance=DataProvenance.PREDICTED,
        computed_at=datetime.now(UTC),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row, renderer


def fused_opportunity_score(db: Session, opportunity: Opportunity) -> float:
    """Unified score for ranking (Daily Production Planner integration).

    Defensive: any failure falls back to the opportunity's own market score —
    fusion must never break the planner.
    """
    try:
        inputs, provenance = build_fusion_inputs(db, opportunity)
        result = OpportunityFusionEngine().compute(inputs, provenance_per_input=provenance)
        return float(result.unified_score)
    except Exception:
        return float(opportunity.opportunity_score or 0.0)
