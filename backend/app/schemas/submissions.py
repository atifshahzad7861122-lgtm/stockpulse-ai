"""Submission planner schemas (CONTRACT.md §5.12).

Hard rule: the API never submits to Adobe Stock; mark-submitted records the
human's manual action.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import MockLabeled

SubmissionOutcome = Literal["accepted", "rejected"]


class SubmissionOut(MockLabeled):
    model_config = ConfigDict(from_attributes=True)

    id: str
    asset_id: str
    asset_version_id: str | None = None
    metadata_id: str | None = None
    production_queue_id: str | None = None
    project_id: str | None = None
    status: str
    submitted_at: datetime | None = None
    reviewed_at: datetime | None = None
    adobe_reference: str | None = None
    rejection_reason: str | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class SubmissionPlanCreate(BaseModel):
    queue_ids: list[str] = Field(min_length=1)
    week_start: date


class SubmissionMarkSubmitted(BaseModel):
    submitted_at: datetime | None = None
    adobe_reference: str | None = None


class OutcomeItem(BaseModel):
    queue_id: str
    outcome: SubmissionOutcome
    reason: str | None = None


class SubmissionRecordOutcome(BaseModel):
    items: list[OutcomeItem] = Field(min_length=1)


class SubmissionDetail(SubmissionOut):
    checklist: list[dict[str, Any]] = Field(default_factory=list)
    capacity_context: dict[str, Any] = Field(default_factory=dict)
