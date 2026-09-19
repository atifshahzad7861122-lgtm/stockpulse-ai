"""Production recommendations (Phase 3).

User-gated actions: approve / reject / edit / prioritize / archive /
regenerate concepts. Approval creates a production_queue item via legal
transitions only and is blocked when a linked concept is HIGH_RISK
compliance or carries an originality blocker.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import (
    audit_log,
    bad_request,
    get_db,
    not_found,
    paginate,
    pagination_params,
    unprocessable,
)
from app.models.planning import ConceptVariation, ProductionRecommendation
from app.schemas.common import Page, apply_labels
from app.schemas.planning import (
    ApproveResponse,
    ConceptGenerateRequest,
    ConceptOut,
    ConceptStatusUpdate,
    PrioritizeRequest,
    RecommendationOut,
    RecommendationUpdate,
)
from app.services import production_planner
from app.services.concepts import generate_concepts, regenerate_concepts

router = APIRouter(prefix="/production-recommendations", tags=["production-recommendations"])

_VALID_REC_STATUSES = ("recommended", "approved", "rejected", "archived")
_VALID_CONCEPT_STATUSES = ("draft", "screened", "approved", "archived")


def _out(row: ProductionRecommendation) -> RecommendationOut:
    return apply_labels(RecommendationOut.model_validate(row), row)


def _concept_out(row: ConceptVariation) -> ConceptOut:
    return apply_labels(ConceptOut.model_validate(row), row)


def _get(db: Session, rec_id: str) -> ProductionRecommendation:
    row = db.query(ProductionRecommendation).filter_by(id=rec_id).one_or_none()
    if row is None:
        raise not_found("RECOMMENDATION_NOT_FOUND", f"Recommendation {rec_id} not found.")
    return row


@router.get("", response_model=Page[RecommendationOut])
def list_recommendations(
    db: Annotated[Session, Depends(get_db)],
    paging: Annotated[dict, Depends(pagination_params)],
    plan_id: Annotated[str | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
):
    q = db.query(ProductionRecommendation).order_by(ProductionRecommendation.rank.asc())
    if plan_id:
        q = q.filter_by(plan_id=plan_id)
    if status:
        if status not in _VALID_REC_STATUSES:
            raise bad_request(
                "INVALID_STATUS",
                f"status must be one of {', '.join(_VALID_REC_STATUSES)}.",
            )
        q = q.filter_by(status=status)
    total = q.count()
    page, page_size = paging["page"], paging["page_size"]
    rows = q.offset((page - 1) * page_size).limit(page_size).all()
    return paginate([_out(r) for r in rows], page=page, page_size=page_size, total=total)


@router.get("/{rec_id}", response_model=RecommendationOut)
def get_recommendation(rec_id: str, db: Annotated[Session, Depends(get_db)]):
    return _out(_get(db, rec_id))


@router.post("/{rec_id}/approve", response_model=ApproveResponse)
def approve(rec_id: str, db: Annotated[Session, Depends(get_db)]):
    try:
        rec, queue_item = production_planner.approve_recommendation(db, rec_id)
    except ValueError as exc:
        msg = str(exc)
        if "blocked" in msg.lower():
            raise unprocessable("APPROVAL_BLOCKED", msg)
        raise bad_request("APPROVAL_FAILED", msg)
    db.commit()
    audit_log(
        db,
        action="approve_recommendation",
        entity_kind="production_recommendation",
        entity_id=rec.id,
        after={"status": rec.status, "queue_item_id": queue_item.id},
        note="User approved; production-queue item created (DISCOVERED).",
    )
    db.commit()
    return ApproveResponse(
        recommendation=_out(rec),
        queue_item_id=queue_item.id,
        queue_status=queue_item.status.value,
        note=(
            "Queue item created at DISCOVERED — nothing was auto-generated. "
            "Advance it through the queue manually."
        ),
    )


@router.post("/{rec_id}/reject", response_model=RecommendationOut)
def reject(rec_id: str, db: Annotated[Session, Depends(get_db)]):
    try:
        rec = production_planner.reject_recommendation(db, rec_id)
    except ValueError as exc:
        raise bad_request("REJECT_FAILED", str(exc))
    db.commit()
    audit_log(db, action="reject_recommendation", entity_kind="production_recommendation",
              entity_id=rec.id, after={"status": rec.status})
    db.commit()
    return _out(rec)


@router.post("/{rec_id}/archive", response_model=RecommendationOut)
def archive(rec_id: str, db: Annotated[Session, Depends(get_db)]):
    try:
        rec = production_planner.archive_recommendation(db, rec_id)
    except ValueError as exc:
        raise bad_request("ARCHIVE_FAILED", str(exc))
    db.commit()
    audit_log(db, action="archive_recommendation", entity_kind="production_recommendation",
              entity_id=rec.id, after={"status": rec.status})
    db.commit()
    return _out(rec)


@router.patch("/{rec_id}", response_model=RecommendationOut)
def edit(rec_id: str, body: RecommendationUpdate, db: Annotated[Session, Depends(get_db)]):
    try:
        rec = production_planner.edit_recommendation(db, rec_id, **body.model_dump())
    except ValueError as exc:
        raise bad_request("EDIT_FAILED", str(exc))
    db.commit()
    audit_log(db, action="edit_recommendation", entity_kind="production_recommendation",
              entity_id=rec.id, after=body.model_dump(exclude_none=True))
    db.commit()
    return _out(rec)


@router.post("/{rec_id}/prioritize", response_model=RecommendationOut)
def prioritize(rec_id: str, body: PrioritizeRequest, db: Annotated[Session, Depends(get_db)]):
    try:
        rec = production_planner.prioritize_recommendation(
            db, rec_id, rank=body.rank, note=body.priority_note
        )
    except ValueError as exc:
        raise bad_request("PRIORITIZE_FAILED", str(exc))
    db.commit()
    audit_log(db, action="prioritize_recommendation", entity_kind="production_recommendation",
              entity_id=rec.id, after={"rank": rec.rank})
    db.commit()
    return _out(rec)


@router.post("/{rec_id}/concepts", response_model=list[ConceptOut], status_code=201)
def generate_concepts_for(rec_id: str, body: ConceptGenerateRequest, db: Annotated[Session, Depends(get_db)]):
    """Generate distinct, compliance+originality-screened concept variations.

    Retiring earlier rounds (they stay in the DB for audit, status archived).
    """
    rec = _get(db, rec_id)
    rows = regenerate_concepts(db, rec, count=body.count)
    next_round = rows[0].variation_round if rows else 1
    db.commit()
    audit_log(
        db,
        action="generate_concepts",
        entity_kind="production_recommendation",
        entity_id=rec.id,
        after={"variation_round": next_round, "count": len(rows)},
        note="Deterministic template-based concepts; screened for compliance and originality.",
    )
    db.commit()
    return [_concept_out(r) for r in rows]


@router.get("/{rec_id}/concepts", response_model=list[ConceptOut])
def list_concepts(rec_id: str, db: Annotated[Session, Depends(get_db)]):
    _get(db, rec_id)
    rows = (
        db.query(ConceptVariation)
        .filter_by(recommendation_id=rec_id)
        .order_by(ConceptVariation.variation_round.desc(), ConceptVariation.created_at.asc())
        .all()
    )
    return [_concept_out(r) for r in rows]


@router.get("/concepts/{concept_id}", response_model=ConceptOut)
def get_concept(concept_id: str, db: Annotated[Session, Depends(get_db)]):
    row = db.query(ConceptVariation).filter_by(id=concept_id).one_or_none()
    if row is None:
        raise not_found("CONCEPT_NOT_FOUND", f"Concept {concept_id} not found.")
    return _concept_out(row)


@router.patch("/concepts/{concept_id}", response_model=ConceptOut)
def update_concept_status(concept_id: str, body: ConceptStatusUpdate, db: Annotated[Session, Depends(get_db)]):
    row = db.query(ConceptVariation).filter_by(id=concept_id).one_or_none()
    if row is None:
        raise not_found("CONCEPT_NOT_FOUND", f"Concept {concept_id} not found.")
    if body.status not in _VALID_CONCEPT_STATUSES:
        raise bad_request(
            "INVALID_STATUS", f"status must be one of {', '.join(_VALID_CONCEPT_STATUSES)}."
        )
    if body.ai_disclosure is not None:
        # Explicit human disclosure decision: record it and re-screen so the
        # gen-01 BLOCK finding can clear. Nothing is defaulted or implied.
        from app.services.concepts import screen_compliance

        row.ai_disclosure = body.ai_disclosure
        outcome, result_json = screen_compliance(
            db, row.asset_type.value, row.concept_json or {}, row.title,
            ai_disclosure=body.ai_disclosure,
        )
        row.compliance_result = outcome
        row.compliance_result_json = result_json
        if outcome != "HIGH_RISK" and row.status == "screened":
            row.status = "draft"
        audit_log(db, action="concept_disclosure", entity_kind="concept_variation",
                  entity_id=row.id, after={"ai_disclosure": body.ai_disclosure,
                                           "compliance_result": outcome})
    if body.status == "approved":
        from app.services.concepts import blockers_for_promotion

        blockers = blockers_for_promotion(row)
        if blockers:
            raise unprocessable("CONCEPT_BLOCKED", " | ".join(blockers))
    row.status = body.status
    db.commit()
    audit_log(db, action="concept_status", entity_kind="concept_variation",
              entity_id=row.id, after={"status": row.status})
    db.commit()
    return _concept_out(row)
