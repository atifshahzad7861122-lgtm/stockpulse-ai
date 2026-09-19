"""Prompt package schemas (CONTRACT.md §5.6)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import MockLabeled
from app.schemas.enums import AssetType, PromptStatus


class PromptVersionOut(MockLabeled):
    model_config = ConfigDict(from_attributes=True)

    id: str
    version_number: int
    prompt_text: str
    negative_prompt_text: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    change_summary: str | None = None
    created_by: str
    created_at: datetime


class PromptOut(MockLabeled):
    model_config = ConfigDict(from_attributes=True)

    id: str
    image_idea_id: str | None = None
    video_idea_id: str | None = None
    asset_type: AssetType
    name: str
    status: PromptStatus
    current_version: PromptVersionOut | None = None
    versions_count: int = 0
    approved_version_id: str | None = None
    created_at: datetime
    updated_at: datetime


class PromptGenerate(BaseModel):
    idea_id: str
    asset_type: AssetType
    tool: str | None = None


class PromptVersionCreate(BaseModel):
    prompt_text: str = Field(min_length=10)
    negative_prompt_text: str | None = None
    parameters: dict[str, Any] | None = None
    change_summary: str = Field(min_length=3)


class PromptRegenerate(BaseModel):
    feedback: str = Field(min_length=3)


class PromptUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=3, max_length=160)
    status: PromptStatus | None = None


class JobResponse(BaseModel):
    job_id: str
