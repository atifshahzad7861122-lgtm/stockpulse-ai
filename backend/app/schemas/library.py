"""Saved-items library schemas (CONTRACT.md §5.17)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import MockLabeled
from app.schemas.enums import SavedItemKind


class SavedItemOut(MockLabeled):
    model_config = ConfigDict(from_attributes=True)

    id: str
    item_kind: SavedItemKind
    item_id: str
    note: str | None = None
    created_at: datetime
    updated_at: datetime


class SavedItemCreate(BaseModel):
    item_kind: SavedItemKind
    item_id: str = Field(min_length=1)
    note: str | None = None
