"""Saved-items library (CONTRACT.md §5.17). Unsaving = hard delete."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import conflict, get_db, not_found, paginate, pagination_params
from app.models.analytics import SavedItem
from app.schemas.common import Page
from app.schemas.enums import SavedItemKind
from app.schemas.library import SavedItemCreate, SavedItemOut

router = APIRouter(prefix="/library", tags=["library"])


def _out(row: SavedItem) -> SavedItemOut:
    return SavedItemOut.from_row(row)


@router.get("", response_model=Page[SavedItemOut])
def list_saved(
    db: Annotated[Session, Depends(get_db)],
    paging: Annotated[dict, Depends(pagination_params)],
    kind: SavedItemKind | None = None,
):
    q = db.query(SavedItem).order_by(SavedItem.created_at.desc())
    if kind is not None:
        q = q.filter_by(item_kind=kind)
    total = q.count()
    page, page_size = paging["page"], paging["page_size"]
    rows = q.offset((page - 1) * page_size).limit(page_size).all()
    return paginate([_out(r) for r in rows], page=page, page_size=page_size, total=total)


@router.post("", response_model=SavedItemOut, status_code=201)
def save_item(body: SavedItemCreate, db: Annotated[Session, Depends(get_db)]):
    row = SavedItem(item_kind=body.item_kind, item_id=body.item_id, note=body.note)
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise conflict(
            "ALREADY_SAVED",
            f"{body.item_kind.value} {body.item_id} is already saved.",
        ) from None
    db.refresh(row)
    return _out(row)


@router.delete("/{item_id}", status_code=204)
def unsave(item_id: str, db: Annotated[Session, Depends(get_db)]):
    row = db.query(SavedItem).filter_by(id=item_id).one_or_none()
    if row is None:
        raise not_found("SAVED_ITEM_NOT_FOUND", f"Saved item {item_id} not found.")
    db.delete(row)
    db.commit()
    return None
