"""Opportunity fusion (Phase 3, PERSONAL INTELLIGENCE).

POST /opportunity-fusion/compute {opportunity_id} → compute & store a fresh
fusion score (one new row per request; GET returns the latest).
GET  /opportunity-fusion/{opportunity_id} → latest score with component
breakdown, explanation, and per-input provenance.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import audit_log, get_db, not_found
from app.models.fusion import OpportunityFusionScore
from app.models.intelligence import Opportunity
from app.schemas.fusion import FusionComputeRequest, FusionScoreOut
from app.services.opportunity_fusion import compute_and_store

router = APIRouter(prefix="/opportunity-fusion", tags=["opportunity-fusion"])


def _get_opportunity(db: Session, opportunity_id: str) -> Opportunity:
    row = db.query(Opportunity).filter_by(id=opportunity_id).one_or_none()
    if row is None:
        raise not_found("OPPORTUNITY_NOT_FOUND", f"Opportunity {opportunity_id} not found.")
    return row


def _latest(db: Session, opportunity_id: str) -> OpportunityFusionScore:
    row = (
        db.query(OpportunityFusionScore)
        .filter_by(opportunity_id=opportunity_id)
        .order_by(
            OpportunityFusionScore.computed_at.desc(),
            OpportunityFusionScore.created_at.desc(),
        )
        .first()
    )
    if row is None:
        raise not_found(
            "FUSION_SCORE_NOT_FOUND",
            f"No fusion score computed yet for opportunity {opportunity_id}.",
        )
    return row


@router.post("/compute", response_model=FusionScoreOut, status_code=201)
def compute_fusion(body: FusionComputeRequest, db: Annotated[Session, Depends(get_db)]):
    """Compute the fused market+personal score for an opportunity and store it.

    Personal inputs come only from the private tables — never from the request
    body, never invented. When no private data exists the score is labeled
    MARKET-ONLY with lowered confidence.
    """
    opportunity = _get_opportunity(db, body.opportunity_id)
    row, renderer = compute_and_store(
        db,
        opportunity,
        trend_momentum=body.trend_momentum,
        commercial_potential=body.commercial_potential,
        seasonality=body.seasonality,
        saturation_risk=body.saturation_risk,
        data_freshness=body.data_freshness,
        n_sources=body.n_sources,
        historical_consistency=body.historical_consistency,
        market_signal_strength=body.market_signal_strength,
        demand_evidence_notes=body.demand_evidence_notes,
    )
    audit_log(
        db,
        action="compute_fusion",
        entity_kind="opportunity_fusion_score",
        entity_id=row.id,
        note=f"opportunity={opportunity.id} label={row.label} renderer={renderer}",
    )
    db.commit()
    return row


@router.get("/{opportunity_id}", response_model=FusionScoreOut)
def get_fusion(opportunity_id: str, db: Annotated[Session, Depends(get_db)]):
    """Latest fusion score for an opportunity, with full breakdown."""
    _get_opportunity(db, opportunity_id)  # 404 on unknown opportunity first
    return _latest(db, opportunity_id)
