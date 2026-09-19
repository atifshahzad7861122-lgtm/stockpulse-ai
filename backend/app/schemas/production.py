"""Production queue schemas (CONTRACT.md §5.11)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import MockLabeled
from app.schemas.enums import AssetType, ProductionQueueStatus

PriorityBand = Literal["P0", "P1", "P2", "P3", "P4"]
DeadlineState = Literal["ON_TRACK", "AT_RISK", "OVERDUE"]


class PriorityComponents(BaseModel):
    trend_momentum: float = 0.0
    deadline_urgency: float = 0.0
    predicted_value: float = 0.0
    user_boost: float = 0.0
    rework_penalty: float = 0.0


class QueueComplianceSummary(BaseModel):
    result: str
    check_id: str


class QueueItemOut(MockLabeled):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str | None = None
    opportunity_id: str | None = None
    image_idea_id: str | None = None
    video_idea_id: str | None = None
    prompt_id: str | None = None
    asset_type: AssetType
    title: str
    status: ProductionQueueStatus
    priority_band: str = "P2"
    priority_score: float = 0.0
    priority_components: PriorityComponents = Field(default_factory=PriorityComponents)
    target_date: date | None = None
    deadline_state: DeadlineState | None = None
    paused: bool = False
    target_quantity: int = 1
    produced_count: int = 0
    generation_tool: str | None = None
    rework_count: int = 0
    blocked_reason: str | None = None
    compliance: QueueComplianceSummary | None = None
    notes: str | None = None
    status_changed_at: datetime
    created_at: datetime
    updated_at: datetime


class QueueItemCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    asset_type: AssetType
    opportunity_id: str | None = None
    image_idea_id: str | None = None
    video_idea_id: str | None = None
    prompt_id: str | None = None
    priority_band: PriorityBand = "P2"
    target_date: date | None = None
    target_quantity: int = Field(default=1, ge=1)
    generation_tool: str | None = None
    notes: str | None = None


class QueueTransition(BaseModel):
    to: ProductionQueueStatus
    note: str | None = None


class QueueAssign(BaseModel):
    assignee: str | None = Field(default=None, description="Reserved; single-user → informational")


class QueuePause(BaseModel):
    paused: bool
    reason: str | None = None


class QueueHistoryEvent(BaseModel):
    at: datetime
    kind: str
    from_status: str | None = None
    to_status: str | None = None
    note: str | None = None
    actor: str = "user"


class QueueItemDetail(QueueItemOut):
    history: list[QueueHistoryEvent] = Field(default_factory=list)
    allowed_transitions: list[str] = Field(default_factory=list)
