"""Assets & uploads (CONTRACT.md §5.9). Signed URLs are local/mock representations."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, not_found, paginate, pagination_params
from app.models.production import Asset, AssetVersion
from app.schemas.assets import (
    AssetCreate,
    AssetCreateResponse,
    AssetOut,
    AssetVersionCreate,
    AssetVersionOut,
)
from app.schemas.common import Page
from app.schemas.enums import AssetStatus, AssetType

router = APIRouter(prefix="/assets", tags=["assets"])

UPLOAD_URL_TTL_SECONDS = 3600


def _version_out(v: AssetVersion) -> AssetVersionOut:
    return AssetVersionOut.from_row(v)


def _out(row: Asset) -> AssetOut:
    current = next((v for v in row.versions if v.id == row.current_version_id), None)
    if current is None and row.versions:
        current = max(row.versions, key=lambda v: v.version_number)
    data = AssetOut.from_row(row)
    data.current_version = _version_out(current) if current else None
    data.download_url = f"/api/assets/{row.id}/versions/{current.id}/download" if current else None
    return data


def _get(db: Session, asset_id: str) -> Asset:
    row = db.query(Asset).filter_by(id=asset_id).one_or_none()
    if row is None:
        raise not_found("ASSET_NOT_FOUND", f"Asset {asset_id} not found.")
    return row


@router.get("", response_model=Page[AssetOut])
def list_assets(
    db: Annotated[Session, Depends(get_db)],
    paging: Annotated[dict, Depends(pagination_params)],
    asset_type: AssetType | None = None,
    status: AssetStatus | None = None,
    idea_id: str | None = None,
):
    q = db.query(Asset).order_by(Asset.created_at.desc())
    if asset_type is not None:
        q = q.filter_by(asset_type=asset_type)
    if status is not None:
        q = q.filter_by(status=status)
    if idea_id:
        q = q.filter((Asset.image_idea_id == idea_id) | (Asset.video_idea_id == idea_id))
    total = q.count()
    page, page_size = paging["page"], paging["page_size"]
    rows = q.offset((page - 1) * page_size).limit(page_size).all()
    return paginate([_out(r) for r in rows], page=page, page_size=page_size, total=total)


@router.post("", response_model=AssetCreateResponse, status_code=201)
def create_asset(body: AssetCreate, db: Annotated[Session, Depends(get_db)]):
    row = Asset(
        production_queue_id=body.production_queue_id,
        image_idea_id=body.idea_id if body.asset_type == AssetType.IMAGE else None,
        video_idea_id=body.idea_id if body.asset_type == AssetType.VIDEO else None,
        prompt_id=body.prompt_id,
        asset_type=body.asset_type,
        title=body.title,
        status=AssetStatus.DRAFT,
        width_px=body.width_px,
        height_px=body.height_px,
        duration_seconds=body.duration_seconds,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return AssetCreateResponse(
        id=row.id,
        type=body.asset_type,
        upload_url=f"/api/assets/{row.id}/upload?token=mock-upload-token&expires_in={UPLOAD_URL_TTL_SECONDS}",
        expires_at=datetime.now(UTC) + timedelta(seconds=UPLOAD_URL_TTL_SECONDS),
    )


@router.get("/{asset_id}", response_model=AssetOut)
def get_asset(asset_id: str, db: Annotated[Session, Depends(get_db)]):
    return _out(_get(db, asset_id))


@router.get("/{asset_id}/versions", response_model=list[AssetVersionOut])
def list_asset_versions(asset_id: str, db: Annotated[Session, Depends(get_db)]):
    row = _get(db, asset_id)
    return [
        _version_out(v) for v in sorted(row.versions, key=lambda v: v.version_number, reverse=True)
    ]


@router.post("/{asset_id}/versions", response_model=AssetVersionOut, status_code=201)
def add_asset_version(
    asset_id: str, body: AssetVersionCreate, db: Annotated[Session, Depends(get_db)]
):
    row = _get(db, asset_id)
    next_number = max((v.version_number for v in row.versions), default=0) + 1
    version = AssetVersion(
        asset_id=row.id,
        version_number=next_number,
        storage_uri=body.storage_uri,
        mime_type=body.mime_type,
        file_size_bytes=body.file_size_bytes,
        width_px=body.width_px,
        height_px=body.height_px,
        duration_seconds=body.duration_seconds,
        file_hash=body.file_hash,
        change_summary=body.change_summary,
    )
    db.add(version)
    db.flush()  # ensure version.id (Python-side UUID default) exists before linking
    row.current_version_id = version.id
    row.status = AssetStatus.FINAL
    db.commit()
    db.refresh(version)
    return _version_out(version)


@router.get("/{asset_id}/versions/{version_id}/download")
def download_version(asset_id: str, version_id: str, db: Annotated[Session, Depends(get_db)]):
    row = _get(db, asset_id)
    version = next((v for v in row.versions if v.id == version_id), None)
    if version is None:
        raise not_found("VERSION_NOT_FOUND", f"Version {version_id} not found.")
    return {"download_url": version.storage_uri, "mime_type": version.mime_type}
