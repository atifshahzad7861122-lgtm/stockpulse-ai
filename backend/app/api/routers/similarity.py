"""Similarity / originality risk (CONTRACT.md §5.8).

Boundaries are authoritative: <0.60 CLEAR, 0.60–<0.80 REVIEW, ≥0.80 HIGH_RISK.
Text-only fallback; embeddings unavailable → verdicts are screening, never
legal judgments.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api import jobs
from app.api.deps import (
    get_db,
    get_idempotency_key,
    idempotent,
    not_found,
    paginate,
    pagination_params,
)
from app.engines.similarity import scan_concept
from app.models.compliance import SimilarityRecord
from app.models.ideation import ImageIdea, VideoIdea
from app.schemas.agents import JobCreate
from app.schemas.common import Page, apply_labels
from app.schemas.enums import AgentRunKind, DataProvenance
from app.schemas.similarity import (
    SimilarityCheckCreate,
    SimilarityCheckOut,
    SimilarityMatchOut,
    SimilaritySubjectKind,
)

router = APIRouter(prefix="/similarity", tags=["similarity"])


def _corpus(db: Session) -> list[tuple[str, str, int | None]]:
    """Market clusters from seeded niches: label, representative text, samples."""
    from app.models.taxonomy import MicroNiche, Subcategory

    rows = (
        db.query(MicroNiche, Subcategory)
        .join(Subcategory, MicroNiche.subcategory_id == Subcategory.id)
        .limit(400)
        .all()
    )
    return [
        (
            niche.name,
            f"{niche.name} {niche.description or ''} {sub.name}",
            None,
        )
        for niche, sub in rows
    ]


def _subject_text(db: Session, kind: SimilaritySubjectKind, subject_id: str) -> str:
    if kind == "image_idea":
        row = db.query(ImageIdea).filter_by(id=subject_id).one_or_none()
    elif kind == "video_idea":
        row = db.query(VideoIdea).filter_by(id=subject_id).one_or_none()
    elif kind == "asset":
        from app.models.production import Asset

        row = db.query(Asset).filter_by(id=subject_id).one_or_none()
    else:
        from app.models.prompts import Prompt

        row = db.query(Prompt).filter_by(id=subject_id).one_or_none() if kind == "prompt" else None
    if row is None:
        raise not_found("SUBJECT_NOT_FOUND", f"{kind} {subject_id} not found.")
    if kind in ("image_idea", "video_idea"):
        return f"{row.title} {row.concept} {row.originality_notes}"
    if kind == "asset":
        return f"{row.title} {row.asset_type.value if row.asset_type else ''}"
    versions = sorted(row.versions, key=lambda v: v.version_number)
    return versions[-1].prompt_text if versions else row.name


def _check_column(kind: SimilaritySubjectKind) -> str:
    return f"{kind}_id"


def _run_check(db: Session, body: SimilarityCheckCreate) -> SimilarityCheckOut:
    text = _subject_text(db, body.subject_kind, body.subject_id)
    verdict = scan_concept(text, _corpus(db), top_k=5)

    column = _check_column(body.subject_kind)
    db.query(SimilarityRecord).filter(getattr(SimilarityRecord, column) == body.subject_id).delete()

    records = []
    for m in verdict.matches:
        rec = SimilarityRecord(
            subject_kind=body.subject_kind,
            compared_cluster_label=m.compared_cluster_label,
            similarity_score=m.similarity_score,
            risk_level=m.risk_level,  # type: ignore[arg-type]
            cluster_sample_count=m.cluster_sample_count,
            differentiators=m.differentiators,
            data_provenance=DataProvenance.MOCK,
        )
        setattr(rec, column, body.subject_id)
        db.add(rec)
        records.append(rec)
    db.commit()

    return apply_labels(
        SimilarityCheckOut(
            id=f"sim:{body.subject_kind}:{body.subject_id}",
            subject={"kind": body.subject_kind, "id": body.subject_id},
            verdict=verdict.verdict,
            max_score=round(verdict.max_score, 4),
            risk_level=records[0].risk_level if records else "LOW",  # type: ignore[arg-type]
            records=[
                SimilarityMatchOut(
                    compared_cluster_label=r.compared_cluster_label,
                    similarity_score=float(r.similarity_score),
                    risk_level=r.risk_level,
                    cluster_sample_count=r.cluster_sample_count,
                    differentiators=r.differentiators,
                )
                for r in records
            ],
            embedding_status=verdict.embedding_status,
            explanation=verdict.explanation,
            data_provenance=DataProvenance.MOCK,
            created_at=records[0].created_at if records else None,  # type: ignore[misc]
        ),
        records[0] if records else body,
    )


@router.post("/checks", response_model=JobCreate, status_code=202)
def create_check(
    body: SimilarityCheckCreate, request: Request, db: Annotated[Session, Depends(get_db)]
):
    result = jobs.submit_job(
        agent_name="originality",
        run_kind=AgentRunKind.SIMILARITY_SCAN,
        input_summary=body.model_dump(),
        func=lambda db, run: _run_check(db, body).model_dump(mode="json"),
    )
    return idempotent(get_idempotency_key(request), JobCreate(**result))


@router.get("", response_model=Page[SimilarityCheckOut])
def list_checks(
    db: Annotated[Session, Depends(get_db)],
    paging: Annotated[dict, Depends(pagination_params)],
    subject_kind: SimilaritySubjectKind | None = None,
):
    q = db.query(SimilarityRecord).order_by(SimilarityRecord.created_at.desc())
    if subject_kind:
        q = q.filter_by(subject_kind=subject_kind)
    total = q.count()
    page, page_size = paging["page"], paging["page_size"]
    rows = q.offset((page - 1) * page_size).limit(page_size).all()
    items = [
        apply_labels(
            SimilarityCheckOut(
                id=r.id,
                subject={
                    "kind": r.subject_kind,
                    "id": r.image_idea_id or r.video_idea_id or r.prompt_id or r.asset_id,
                },
                verdict=(
                    "REVIEW"
                    if r.risk_level in ("HIGH", "MEDIUM")
                    else ("HIGH_RISK" if r.risk_level == "CRITICAL" else "CLEAR")
                ),
                max_score=float(r.similarity_score),
                risk_level=r.risk_level,
                records=[],
                explanation=r.differentiators,
                data_provenance=r.data_provenance,
                created_at=r.created_at,
            ),
            r,
        )
        for r in rows
    ]
    return paginate(items, page=page, page_size=page_size, total=total)
