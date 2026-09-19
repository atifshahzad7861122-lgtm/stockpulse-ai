"""Asset schemas (CONTRACT.md §5.9)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import MockLabeled
from app.schemas.enums import AssetStatus, AssetType


class AssetVersionOut(MockLabeled):
    model_config = ConfigDict(from_attributes=True)

    id: str
    version_number: int
    storage_uri: str
    mime_type: str
    file_size_bytes: int | None = None
    width_px: int | None = None
    height_px: int | None = None
    duration_seconds: float | None = None
    file_hash: str | None = None
    change_summary: str | None = None
    created_at: datetime


class AssetOut(MockLabeled):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str | None = None
    production_queue_id: str | None = None
    image_idea_id: str | None = None
    video_idea_id: str | None = None
    prompt_id: str | None = None
    prompt_version_id: str | None = None
    asset_type: AssetType
    title: str
    status: AssetStatus
    current_version: AssetVersionOut | None = None
    width_px: int | None = None
    height_px: int | None = None
    duration_seconds: float | None = None
    download_url: str | None = None
    created_at: datetime
    updated_at: datetime


class AssetCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    asset_type: AssetType
    mime_type: str = Field(min_length=3, max_length=100)
    production_queue_id: str | None = None
    idea_id: str | None = None
    prompt_id: str | None = None
    width_px: int | None = Field(default=None, gt=0)
    height_px: int | None = Field(default=None, gt=0)
    duration_seconds: float | None = Field(default=None, gt=0)


class AssetCreateResponse(BaseModel):
    id: str
    type: AssetType
    status: str = "processing"
    upload_url: str
    expires_at: datetime


class AssetVersionCreate(BaseModel):
    storage_uri: str = Field(min_length=5)
    mime_type: str = Field(min_length=3, max_length=100)
    file_size_bytes: int | None = Field(default=None, ge=0)
    width_px: int | None = Field(default=None, gt=0)
    height_px: int | None = Field(default=None, gt=0)
    duration_seconds: float | None = Field(default=None, gt=0)
    file_hash: str | None = None
    change_summary: str | None = None
