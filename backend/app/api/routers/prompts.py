"""Prompt generation & versions (CONTRACT.md §5.6)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session, joinedload

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
from app.models.prompts import Prompt, PromptVersion
from app.schemas.agents import JobCreate
from app.schemas.common import Page
from app.schemas.enums import AgentRunKind, AssetType, PromptStatus
from app.schemas.prompts import (
    PromptGenerate,
    PromptOut,
    PromptRegenerate,
    PromptUpdate,
    PromptVersionCreate,
    PromptVersionOut,
)

router = APIRouter(prefix="/prompts", tags=["prompts"])


def _version_out(v: PromptVersion) -> PromptVersionOut:
    return PromptVersionOut.from_row(v)


def _out(row: Prompt) -> PromptOut:
    current = next((v for v in row.versions if v.id == row.current_version_id), None)
    if current is None and row.versions:
        current = max(row.versions, key=lambda v: v.version_number)
    data = PromptOut.from_row(row)
    data.current_version = _version_out(current) if current else None
    data.versions_count = len(row.versions)
    return data


def _get(db: Session, prompt_id: str) -> Prompt:
    row = (
        db.query(Prompt).options(joinedload(Prompt.versions)).filter_by(id=prompt_id).one_or_none()
    )
    if row is None:
        raise not_found("PROMPT_NOT_FOUND", f"Prompt {prompt_id} not found.")
    return row


@router.get("", response_model=Page[PromptOut])
def list_prompts(
    db: Annotated[Session, Depends(get_db)],
    paging: Annotated[dict, Depends(pagination_params)],
    status: PromptStatus | None = None,
    asset_type: AssetType | None = None,
    idea_id: str | None = None,
):
    q = db.query(Prompt).options(joinedload(Prompt.versions))
    if status is not None:
        q = q.filter_by(status=status)
    if asset_type is not None:
        q = q.filter_by(asset_type=asset_type)
    if idea_id:
        q = q.filter((Prompt.image_idea_id == idea_id) | (Prompt.video_idea_id == idea_id))
    total = q.count()
    page, page_size = paging["page"], paging["page_size"]
    rows = (
        q.order_by(Prompt.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    )
    return paginate([_out(r) for r in rows], page=page, page_size=page_size, total=total)


@router.post("/generate", response_model=JobCreate, status_code=202)
def generate_prompt(
    body: PromptGenerate, request: Request, db: Annotated[Session, Depends(get_db)]
):
    from app.agents.dispatcher import dispatch

    def _run(db: Session, run):
        return dispatch(
            "prompt",
            db,
            run,
            {"idea_id": body.idea_id, "asset_type": body.asset_type.value, "tool": body.tool},
        )

    result = jobs.submit_job(
        agent_name="prompt",
        run_kind=AgentRunKind.PROMPT_GENERATION,
        input_summary=body.model_dump(),
        func=_run,
    )
    return idempotent(get_idempotency_key(request), JobCreate(**result))


@router.get("/{prompt_id}", response_model=PromptOut)
def get_prompt(prompt_id: str, db: Annotated[Session, Depends(get_db)]):
    return _out(_get(db, prompt_id))


@router.patch("/{prompt_id}", response_model=PromptOut)
def update_prompt(prompt_id: str, body: PromptUpdate, db: Annotated[Session, Depends(get_db)]):
    row = _get(db, prompt_id)
    if body.name is not None:
        row.name = body.name
    if body.status is not None:
        row.status = body.status
    db.commit()
    db.refresh(row)
    return _out(row)


@router.get("/{prompt_id}/versions", response_model=list[PromptVersionOut])
def list_versions(prompt_id: str, db: Annotated[Session, Depends(get_db)]):
    row = _get(db, prompt_id)
    versions = sorted(row.versions, key=lambda v: v.version_number, reverse=True)
    return [_version_out(v) for v in versions]


@router.post("/{prompt_id}/versions", response_model=PromptVersionOut, status_code=201)
def add_version(prompt_id: str, body: PromptVersionCreate, db: Annotated[Session, Depends(get_db)]):
    row = _get(db, prompt_id)
    next_number = max((v.version_number for v in row.versions), default=0) + 1
    version = PromptVersion(
        prompt_id=row.id,
        version_number=next_number,
        prompt_text=body.prompt_text,
        negative_prompt_text=body.negative_prompt_text,
        parameters=body.parameters or {},
        change_summary=body.change_summary,
        created_by="user",
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    return _version_out(version)


@router.post("/{prompt_id}/versions/{version_number}/activate", response_model=PromptOut)
def activate_version(prompt_id: str, version_number: int, db: Annotated[Session, Depends(get_db)]):
    row = _get(db, prompt_id)
    match = next((v for v in row.versions if v.version_number == version_number), None)
    if match is None:
        raise not_found(
            "VERSION_NOT_FOUND",
            f"Version {version_number} of prompt {prompt_id} not found.",
        )
    row.current_version_id = match.id
    db.commit()
    db.refresh(row)
    return _out(row)


@router.post("/{prompt_id}/regenerate", response_model=JobCreate, status_code=202)
def regenerate_prompt(
    prompt_id: str,
    body: PromptRegenerate,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    from app.agents.dispatcher import dispatch

    row = _get(db, prompt_id)

    def _run(db: Session, run):
        return dispatch(
            "prompt",
            db,
            run,
            {"idea_id": prompt_id, "feedback": body.feedback, "regenerate": True},
        )

    result = jobs.submit_job(
        agent_name="prompt",
        run_kind=AgentRunKind.PROMPT_GENERATION,
        input_summary={"prompt_id": row.id, "feedback": body.feedback[:120]},
        func=_run,
    )
    return idempotent(get_idempotency_key(request), JobCreate(**result))


@router.post("/{prompt_id}/approve", response_model=PromptOut)
def approve_prompt(prompt_id: str, db: Annotated[Session, Depends(get_db)]):
    row = _get(db, prompt_id)
    if not row.versions:
        raise bad_request("NO_VERSION", "Cannot approve a prompt with no versions.")
    row.status = PromptStatus.APPROVED
    row.approved_version_id = max(row.versions, key=lambda v: v.version_number).id
    db.commit()
    db.refresh(row)
    return _out(row)
