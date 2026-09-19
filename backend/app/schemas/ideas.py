"""Idea schemas (CONTRACT.md §5.5)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import MockLabeled
from app.schemas.enums import IdeaStatus

IdeaKind = Literal["image", "video"]


class ShotItem(BaseModel):
    shot: str
    camera_move: str | None = None
    duration_s: float | None = None
    notes: str | None = None


class IdeaOut(MockLabeled):
    model_config = ConfigDict(from_attributes=True)

    id: str
    kind: IdeaKind = "image"
    project_id: str | None = None
    opportunity_id: str | None = None
    micro_niche_id: str | None = None
    title: str
    concept: str
    originality_notes: str
    reference_mood: list[str] | None = None
    duration_target_seconds: int | None = None
    shot_list: list[dict[str, Any]] | None = None
    status: IdeaStatus
    priority: int
    reviewed_at: datetime | None = None
    agent_run_id: str | None = None
    created_at: datetime
    updated_at: datetime


class IdeaCreate(BaseModel):
    kind: IdeaKind
    title: str = Field(min_length=3, max_length=200)
    concept: str = Field(min_length=10)
    originality_notes: str = Field(min_length=10)
    opportunity_id: str | None = None
    micro_niche_id: str | None = None
    reference_mood: list[str] | None = None
    duration_target_seconds: int | None = Field(default=None, gt=0)
    shot_list: list[ShotItem] | None = None


class IdeaUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    concept: str | None = Field(default=None, min_length=10)
    originality_notes: str | None = Field(default=None, min_length=10)
    reference_mood: list[str] | None = None
    duration_target_seconds: int | None = Field(default=None, gt=0)
    shot_list: list[ShotItem] | None = None
    status: IdeaStatus | None = None
    priority: int | None = Field(default=None, ge=0)


class GenerateConceptsResponse(BaseModel):
    job_id: str
