"""Metadata bundle schemas (CONTRACT.md §5.10)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import MockLabeled


class MetadataBundleOut(MockLabeled):
    model_config = ConfigDict(from_attributes=True)

    id: str
    asset_id: str
    version_number: int
    title: str
    description: str | None = None
    keywords: list[str] = Field(default_factory=list)
    adobe_category: str | None = None
    micro_niche_id: str | None = None
    language: str = "en"
    is_current: bool
    created_by: str
    agent_run_id: str | None = None
    created_at: datetime


class MetadataGenerate(BaseModel):
    asset_id: str


class MetadataUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    keywords: list[str] | None = Field(default=None, max_length=25)
    adobe_category: str | None = None
    micro_niche_id: str | None = None


class ValidationIssue(BaseModel):
    code: str
    message: str
    severity: Literal["error", "warning"]


class MetadataValidation(BaseModel):
    valid: bool
    issues: list[ValidationIssue] = Field(default_factory=list)
