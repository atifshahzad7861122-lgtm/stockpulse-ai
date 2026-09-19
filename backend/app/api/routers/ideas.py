"""Image & video ideation (CONTRACT.md §5.5)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api import jobs
from app.api.deps import (
    audit_log,
    bad_request,
    conflict,
    get_db,
    get_idempotency_key,
    idempotent,
    not_found,
    paginate,
    pagination_params,
)
from app.models.ideation import ImageIdea, VideoIdea
from app.schemas.agents import JobCreate
from app.schemas.common import Page
from app.schemas.enums import AgentRunKind, IdeaStatus
from app.schemas.ideas import (
    IdeaCreate,
    IdeaKind,
    IdeaOut,
    IdeaUpdate,
)

router = APIRouter(prefix="/ideas", tags=["ideas"])


def _model(kind: IdeaKind):
    return ImageIdea if kind == "image" else VideoIdea


def _out(kind: IdeaKind, row) -> IdeaOut:
    data = IdeaOut.from_row(row)
    data.kind = kind
    if kind == "image":
        data.duration_target_seconds = None
        data.shot_list = None
    return data


def _resolve(db: Session, idea_id: str, kind: IdeaKind | None) -> tuple[IdeaKind, object]:
    """Resolve an idea by id, optionally constrained to one kind table.

    ``kind`` is a lookup hint, not a security boundary: when omitted, both
    tables are searched (ids are UUIDs, so a hit is unambiguous). Raises
    IDEA_NOT_FOUND when neither table has the id.
    """
    kinds: tuple[IdeaKind, ...] = (kind,) if kind is not None else ("image", "video")
    for k in kinds:
        row = db.query(_model(k)).filter_by(id=idea_id).one_or_none()
        if row is not None:
            return k, row
    raise not_found("IDEA_NOT_FOUND", f"idea {idea_id} not found.")


@router.get("", response_model=Page[IdeaOut])
def list_ideas(
    db: Annotated[Session, Depends(get_db)],
    paging: Annotated[dict, Depends(pagination_params)],
    kind: IdeaKind | None = None,
    status: IdeaStatus | None = None,
    opportunity_id: str | None = None,
    min_priority: Annotated[int | None, Query(ge=0)] = None,
):
    rows: list[tuple[IdeaKind, object]] = []
    for k in (
        ("image",) if kind == "image" else ("video",) if kind == "video" else ("image", "video")
    ):
        q = db.query(_model(k))  # type: ignore[arg-type]
        if status is not None:
            q = q.filter_by(status=status)
        if opportunity_id:
            q = q.filter_by(opportunity_id=opportunity_id)
        if min_priority is not None:
            q = q.filter(_model(k).priority >= min_priority)  # type: ignore[arg-type]
        rows.extend((k, r) for r in q.all())  # type: ignore[misc]
    rows.sort(key=lambda t: t[1].created_at, reverse=True)
    total = len(rows)
    page, page_size = paging["page"], paging["page_size"]
    items = [_out(k, r) for k, r in rows[(page - 1) * page_size : page * page_size]]
    return paginate(items, page=page, page_size=page_size, total=total)


@router.post("", response_model=IdeaOut, status_code=201)
def create_idea(body: IdeaCreate, db: Annotated[Session, Depends(get_db)]):
    cls = _model(body.kind)
    kwargs: dict = {
        "opportunity_id": body.opportunity_id,
        "micro_niche_id": body.micro_niche_id,
        "title": body.title,
        "concept": body.concept,
        "originality_notes": body.originality_notes,
        "reference_mood": body.reference_mood or [],
        "status": IdeaStatus.DRAFT,
    }
    if body.kind == "video":
        kwargs["duration_target_seconds"] = body.duration_target_seconds
        kwargs["shot_list"] = [s.model_dump() for s in (body.shot_list or [])]
    row = cls(**kwargs)
    db.add(row)
    db.commit()
    db.refresh(row)
    return _out(body.kind, row)


@router.get("/{idea_id}", response_model=IdeaOut)
def get_idea(
    idea_id: str,
    db: Annotated[Session, Depends(get_db)],
    kind: Annotated[IdeaKind | None, Query()] = None,
):
    k, row = _resolve(db, idea_id, kind)
    return _out(k, row)


@router.patch("/{idea_id}", response_model=IdeaOut)
def update_idea(
    idea_id: str,
    body: IdeaUpdate,
    db: Annotated[Session, Depends(get_db)],
    kind: Annotated[IdeaKind | None, Query()] = None,
):
    k, row = _resolve(db, idea_id, kind)
    for field in ("title", "concept", "originality_notes", "reference_mood", "status"):
        value = getattr(body, field, None)
        if value is not None:
            setattr(row, field, value)
    if k == "video":
        if body.duration_target_seconds is not None:
            row.duration_target_seconds = body.duration_target_seconds
        if body.shot_list is not None:
            row.shot_list = [s.model_dump() for s in body.shot_list]
    if body.priority is not None:
        row.priority = body.priority
    db.commit()
    db.refresh(row)
    return _out(k, row)


@router.delete("/{idea_id}", status_code=204)
def delete_idea(
    idea_id: str,
    db: Annotated[Session, Depends(get_db)],
    kind: Annotated[IdeaKind | None, Query()] = None,
):
    _, row = _resolve(db, idea_id, kind)
    db.delete(row)
    db.commit()
    return None


@router.post("/{idea_id}/promote", response_model=IdeaOut)
def promote_idea(
    idea_id: str,
    db: Annotated[Session, Depends(get_db)],
    kind: Annotated[IdeaKind | None, Query()] = None,
):
    k, row = _resolve(db, idea_id, kind)
    if row.status not in (IdeaStatus.DRAFT,):
        raise bad_request(
            "INVALID_TRANSITION",
            f"Only DRAFT ideas can be promoted; current status is {row.status.value}.",
        )
    row.status = IdeaStatus.READY
    db.commit()
    db.refresh(row)
    return _out(k, row)


@router.post("/{idea_id}/archive", response_model=IdeaOut)
def archive_idea(
    idea_id: str,
    db: Annotated[Session, Depends(get_db)],
    kind: Annotated[IdeaKind | None, Query()] = None,
):
    """Archive an idea (DRAFT/READY/IN_QUEUE -> ARCHIVED). The drawer calls
    this without a kind hint, so the resolver searches both idea tables."""
    k, row = _resolve(db, idea_id, kind)
    if row.status == IdeaStatus.ARCHIVED:
        raise conflict("ALREADY_ARCHIVED", "Idea is already archived.")
    row.status = IdeaStatus.ARCHIVED
    db.commit()
    db.refresh(row)
    audit_log(db, action="archive", entity_kind=f"{k}_idea", entity_id=row.id)
    db.commit()
    return _out(k, row)


@router.post("/generate-concepts", response_model=JobCreate, status_code=202)
def generate_concepts(
    request: Request, db: Annotated[Session, Depends(get_db)], opportunity_id: str | None = None
):
    from app.agents.dispatcher import dispatch

    def _run(db: Session, run):
        return {
            "image": dispatch("image_ideation", db, run, {"opportunity_id": opportunity_id}),
            "video": dispatch("video_ideation", db, run, {"opportunity_id": opportunity_id}),
        }

    result = jobs.submit_job(
        agent_name="image_ideation",
        run_kind=AgentRunKind.IDEA_GENERATION,
        input_summary={"opportunity_id": opportunity_id},
        func=_run,
    )
    return idempotent(get_idempotency_key(request), JobCreate(**result))
