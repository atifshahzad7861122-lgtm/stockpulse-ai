"""Compliance checks (CONTRACT.md §5.7).

Every response explains each flag and never promises Adobe Stock acceptance.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api import jobs
from app.api.deps import (
    bad_request,
    conflict,
    get_db,
    get_idempotency_key,
    idempotent,
    not_found,
    paginate,
    pagination_params,
)
from app.engines.compliance import RuleSpec, ScreenSubject, run_screen
from app.models.compliance import ComplianceCheck, ComplianceRule
from app.models.ideation import ImageIdea, VideoIdea
from app.models.production import Asset, MetadataRecord, ProductionQueue
from app.models.prompts import Prompt
from app.schemas.agents import JobCreate
from app.schemas.common import Page, apply_labels
from app.schemas.compliance import (
    ComplianceCheckCreate,
    ComplianceCheckOut,
    ComplianceReview,
    ComplianceRuleOut,
    RuleFindingOut,
)
from app.schemas.enums import AgentRunKind

router = APIRouter(prefix="/compliance", tags=["compliance"])

_SUBJECT_KIND_TO_COLUMN = {
    "prompt": ("prompt_id",),
    "asset": ("asset_id",),
    "image_idea": ("image_idea_id",),
    "video_idea": ("video_idea_id",),
    "metadata": ("metadata_id",),
    "production_queue": ("production_queue_id",),
}

# Reverse lookup: id column -> subject kind. The frontend's ComplianceSubject
# contract is {kind, id, version_id?}; the serializer below emits that shape.
_COLUMN_TO_SUBJECT_KIND: dict[str, str] = {
    column: kind for kind, (column,) in _SUBJECT_KIND_TO_COLUMN.items()
}
_SUBJECT_VERSION_COLUMN: dict[str, str] = {
    "prompt": "prompt_version_id",
    "asset": "asset_version_id",
}


def _rules_specs(db: Session) -> list[RuleSpec]:
    rows = db.query(ComplianceRule).filter_by(is_enabled=True).all()
    return [
        RuleSpec(
            rule_key=r.rule_key,
            severity=r.severity,
            check_method=(r.rule_config or {}).get("check_method", "human_review"),
            applies_to=tuple(r.applies_to or []),
        )
        for r in rows
    ]


def _load_subject(db: Session, kind: str, subject_id: str) -> ScreenSubject:
    """Build a ScreenSubject for any supported subject kind.

    Text-only evaluation: pixel/temporal properties (blur, anatomy, exposure,
    video artifacts) cannot be assessed from text and always stay REVIEW/manual —
    never an automatic PASS.
    """
    if kind == "prompt":
        row = db.query(Prompt).filter_by(id=subject_id).one_or_none()
        if row is None:
            raise not_found("PROMPT_NOT_FOUND", f"Prompt {subject_id} not found.")
        versions = sorted(row.versions, key=lambda v: v.version_number)
        text = versions[-1].prompt_text if versions else ""
        neg = versions[-1].negative_prompt_text if versions else ""
        return ScreenSubject(prompt_text=text, negative_prompt_text=neg, title=row.name)
    if kind in ("image_idea", "video_idea"):
        model = ImageIdea if kind == "image_idea" else VideoIdea
        row = db.query(model).filter_by(id=subject_id).one_or_none()
        if row is None:
            raise not_found("SUBJECT_NOT_FOUND", f"{kind} {subject_id} not found.")
        return ScreenSubject(
            concept=row.concept or "",
            originality_notes=row.originality_notes or "",
            title=row.title or "",
        )
    if kind == "asset":
        row = db.query(Asset).filter_by(id=subject_id).one_or_none()
        if row is None:
            raise not_found("SUBJECT_NOT_FOUND", f"asset {subject_id} not found.")
        return ScreenSubject(
            title=row.title or "",
            width_px=row.width_px,
            height_px=row.height_px,
            asset_type=row.asset_type.value if row.asset_type else "IMAGE",
            ai_disclosure=True,
            generation_tool="mock-generation-provider",
        )
    if kind == "metadata":
        row = db.query(MetadataRecord).filter_by(id=subject_id).one_or_none()
        if row is None:
            raise not_found("SUBJECT_NOT_FOUND", f"metadata {subject_id} not found.")
        return ScreenSubject(
            title=row.title or "",
            description=row.description or "",
            keywords=tuple(row.keywords or []),
            adobe_category=row.adobe_category,
        )
    if kind == "production_queue":
        row = db.query(ProductionQueue).filter_by(id=subject_id).one_or_none()
        if row is None:
            raise not_found("SUBJECT_NOT_FOUND", f"production_queue {subject_id} not found.")
        return ScreenSubject(
            title=row.title or "",
            asset_type=row.asset_type.value if row.asset_type else "IMAGE",
            generation_tool=row.generation_tool,
        )
    raise bad_request("UNSUPPORTED_SUBJECT_KIND", f"Unsupported subject kind: {kind}.")


def _subject_out(check: ComplianceCheck) -> dict[str, Any]:
    """Serialize the check subject as {kind, id, version_id?}.

    Matches the frontend's ComplianceSubject contract (types/index.ts).
    Exactly one subject FK is set per row (enforced at write time); the
    fallback below is defensive only and cannot occur via the API.
    """
    for column, kind in _COLUMN_TO_SUBJECT_KIND.items():
        subject_id = getattr(check, column, None)
        if subject_id is not None:
            subject: dict[str, Any] = {"kind": kind, "id": subject_id}
            version_column = _SUBJECT_VERSION_COLUMN.get(kind)
            if version_column:
                version_id = getattr(check, version_column, None)
                if version_id is not None:
                    subject["version_id"] = version_id
            return subject
    return {"kind": "prompt", "id": ""}


def _out(check: ComplianceCheck) -> ComplianceCheckOut:
    subject = _subject_out(check)
    return apply_labels(
        ComplianceCheckOut(
            id=check.id,
            check_type=check.check_type,
            subject=subject,
            result=check.result,
            risk_level=check.risk_level,
            findings=[
                RuleFindingOut(**{**f, "check_id": check.id}) if isinstance(f, dict) else f
                for f in (check.findings or [])
            ],
            explanation=check.explanation,
            rules_version="1.0.0",
            review_decision=check.review_decision,
            reviewed_at=check.reviewed_at,
            agent_run_id=check.agent_run_id,
            created_at=check.created_at,
        ),
        check,
    )


def _run_check(db: Session, body: ComplianceCheckCreate) -> ComplianceCheckOut:
    subject = _load_subject(db, body.subject_kind, body.subject_id)
    specs = _rules_specs(db)
    check_type_value = body.check_type.value
    result = run_screen(check_type_value, subject, specs)
    column = _SUBJECT_KIND_TO_COLUMN[body.subject_kind][0]
    # Build findings with the real check_id before persistence — never mutate
    # the JSON column in place after commit.
    check_id = str(uuid.uuid4())
    row = ComplianceCheck(
        id=check_id,
        check_type=body.check_type,
        result=result.result,  # type: ignore[arg-type]
        risk_level=result.risk_level,  # type: ignore[arg-type]
        findings=[
            {
                "check_id": check_id,
                "rule_key": f.rule_key,
                "rule_version": f.rule_version,
                "severity": f.severity.value,
                "triggered": f.triggered,
                "explanation": f.explanation,
                "matched_excerpt": f.matched_excerpt,
                "remediation": f.remediation,
            }
            for f in result.findings
        ],
        explanation=result.explanation,
    )
    setattr(row, column, body.subject_id)
    if body.subject_version_id:
        row.prompt_version_id = body.subject_version_id
    db.add(row)
    db.commit()
    db.refresh(row)
    return _out(row)


@router.post("/checks", response_model=JobCreate, status_code=202)
def create_check(
    body: ComplianceCheckCreate, request: Request, db: Annotated[Session, Depends(get_db)]
):
    result = jobs.submit_job(
        agent_name="compliance",
        run_kind=AgentRunKind.COMPLIANCE_SCREEN,
        input_summary={
            "check_type": body.check_type.value,
            "subject_kind": body.subject_kind,
            "subject_id": body.subject_id,
        },
        func=lambda db, run: _run_check(db, body).model_dump(mode="json"),
    )
    return idempotent(get_idempotency_key(request), JobCreate(**result))


@router.get("/checks", response_model=Page[ComplianceCheckOut])
def list_checks(
    db: Annotated[Session, Depends(get_db)],
    paging: Annotated[dict, Depends(pagination_params)],
    result: Annotated[str | None, Query(pattern="^(PASS|REVIEW|HIGH_RISK)$")] = None,
    subject_kind: Annotated[str | None, Query()] = None,
    subject_id: str | None = None,
    pending_review: bool = False,
):
    q = db.query(ComplianceCheck).order_by(ComplianceCheck.created_at.desc())
    if result:
        q = q.filter_by(result=result)
    if pending_review:
        q = q.filter(ComplianceCheck.reviewed_at.is_(None))
    if subject_kind and subject_id and subject_kind in _SUBJECT_KIND_TO_COLUMN:
        q = q.filter(
            getattr(ComplianceCheck, _SUBJECT_KIND_TO_COLUMN[subject_kind][0]) == subject_id
        )
    total = q.count()
    page, page_size = paging["page"], paging["page_size"]
    rows = q.offset((page - 1) * page_size).limit(page_size).all()
    return paginate([_out(r) for r in rows], page=page, page_size=page_size, total=total)


@router.get("/checks/{check_id}", response_model=ComplianceCheckOut)
def get_check(check_id: str, db: Annotated[Session, Depends(get_db)]):
    row = db.query(ComplianceCheck).filter_by(id=check_id).one_or_none()
    if row is None:
        raise not_found("CHECK_NOT_FOUND", f"Compliance check {check_id} not found.")
    return _out(row)


@router.post("/checks/{check_id}/review", response_model=ComplianceCheckOut)
def review_check(check_id: str, body: ComplianceReview, db: Annotated[Session, Depends(get_db)]):
    row = db.query(ComplianceCheck).filter_by(id=check_id).one_or_none()
    if row is None:
        raise not_found("CHECK_NOT_FOUND", f"Compliance check {check_id} not found.")
    if row.reviewed_at is not None:
        raise conflict("ALREADY_REVIEWED", "This check already has a human review decision.")
    row.review_decision = body.decision
    row.reviewed_at = datetime.now(UTC)
    if body.note:
        row.explanation = f"{row.explanation}\n\nHuman review ({body.decision}): {body.note}"
    db.commit()
    return _out(row)


@router.get("/rules", response_model=list[ComplianceRuleOut])
def list_rules(db: Annotated[Session, Depends(get_db)]):
    rows = db.query(ComplianceRule).order_by(ComplianceRule.rule_key).all()
    return [ComplianceRuleOut.model_validate(r) for r in rows]
