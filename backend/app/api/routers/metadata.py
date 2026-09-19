"""Metadata bundles (CONTRACT.md §5.10). Titles/descriptions/keywords per docs/22."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api import jobs
from app.api.deps import (
    bad_request,
    get_db,
    get_idempotency_key,
    idempotent,
    not_found,
    paginate,
    pagination_params,
)
from app.engines.metadata import validate_bundle
from app.models.production import Asset
from app.models.production import MetadataRecord as Metadata
from app.schemas.agents import JobCreate
from app.schemas.common import Page
from app.schemas.enums import AgentRunKind
from app.schemas.metadata import (
    MetadataBundleOut,
    MetadataGenerate,
    MetadataUpdate,
    MetadataValidation,
    ValidationIssue,
)

router = APIRouter(prefix="/metadata", tags=["metadata"])


def _out(row: Metadata) -> MetadataBundleOut:
    return MetadataBundleOut.from_row(row)


def _get(db: Session, metadata_id: str) -> Metadata:
    row = db.query(Metadata).filter_by(id=metadata_id).one_or_none()
    if row is None:
        raise not_found("METADATA_NOT_FOUND", f"Metadata {metadata_id} not found.")
    return row


@router.post("", response_model=JobCreate, status_code=202)
def generate_metadata(
    body: MetadataGenerate, request: Request, db: Annotated[Session, Depends(get_db)]
):
    """Generate a draft via the metadata agent → 202 { job_id }."""
    from app.agents.dispatcher import dispatch

    asset = db.query(Asset).filter_by(id=body.asset_id).one_or_none()
    if asset is None:
        raise not_found("ASSET_NOT_FOUND", f"Asset {body.asset_id} not found.")

    def _run(db: Session, run):
        return dispatch("metadata", db, run, {"asset_id": body.asset_id})

    result = jobs.submit_job(
        agent_name="metadata",
        run_kind=AgentRunKind.METADATA_DRAFT,
        input_summary={"asset_id": body.asset_id},
        func=_run,
    )
    return idempotent(get_idempotency_key(request), JobCreate(**result))


@router.get("", response_model=Page[MetadataBundleOut])
def list_metadata(
    db: Annotated[Session, Depends(get_db)],
    paging: Annotated[dict, Depends(pagination_params)],
    asset_id: Annotated[str | None, Query()] = None,
    is_current: Annotated[bool | None, Query()] = None,
):
    q = db.query(Metadata).order_by(Metadata.version_number.desc())
    if asset_id:
        q = q.filter_by(asset_id=asset_id)
    if is_current is not None:
        q = q.filter_by(is_current=is_current)
    total = q.count()
    page, page_size = paging["page"], paging["page_size"]
    rows = q.offset((page - 1) * page_size).limit(page_size).all()
    return paginate([_out(r) for r in rows], page=page, page_size=page_size, total=total)


@router.get("/{metadata_id}", response_model=MetadataBundleOut)
def get_metadata(metadata_id: str, db: Annotated[Session, Depends(get_db)]):
    return _out(_get(db, metadata_id))


@router.patch("/{metadata_id}", response_model=MetadataBundleOut)
def update_metadata(
    metadata_id: str, body: MetadataUpdate, db: Annotated[Session, Depends(get_db)]
):
    """Human edit: creates a NEW version and flips is_current (never edits in place)."""
    row = _get(db, metadata_id)
    if row.is_current:
        row.is_current = False
        db.flush()
    latest = (
        db.query(Metadata)
        .filter_by(asset_id=row.asset_id)
        .order_by(Metadata.version_number.desc())
        .first()
    )
    next_number = (latest.version_number if latest else 0) + 1
    new = Metadata(
        asset_id=row.asset_id,
        version_number=next_number,
        title=body.title if body.title is not None else row.title,
        description=body.description if body.description is not None else row.description,
        keywords=list(body.keywords) if body.keywords is not None else list(row.keywords or []),
        adobe_category=(
            body.adobe_category if body.adobe_category is not None else row.adobe_category
        ),
        micro_niche_id=(
            body.micro_niche_id if body.micro_niche_id is not None else row.micro_niche_id
        ),
        language=row.language,
        is_current=True,
        created_by="user",
    )
    db.add(new)
    db.commit()
    db.refresh(new)
    return _out(new)


@router.post("/{metadata_id}/validate", response_model=MetadataValidation)
def validate_metadata(metadata_id: str, db: Annotated[Session, Depends(get_db)]):
    row = _get(db, metadata_id)
    issues = validate_bundle(
        title=row.title,
        description=row.description or "",
        keywords=list(row.keywords or []),
    )
    parsed = [
        ValidationIssue(code=i["code"], message=i["message"], severity=i["severity"])
        for i in issues
    ]
    if any(i.severity == "error" for i in parsed):
        raise bad_request(
            "VALIDATION_ERROR",
            "Metadata has hard validation violations.",
            issues=[i.model_dump() for i in parsed],
        )
    return MetadataValidation(
        valid=True,
        issues=parsed,
    )
