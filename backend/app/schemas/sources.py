"""Schemas for /api/sources (CONTRACT.md §5.18, PHASE2_DESIGN.md §5).

Field names mirror PHASE2_DESIGN.md §3 (SourceHealth, CollectionRun). The
``app.models.sources`` models are created by the sibling models agent — this
module maps rows defensively so the API works before and after they land.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.enums import (
    CollectionRunStatus,
    CollectionRunTrigger,
    DataProvenance,
    SourceStatus,
)


class SourceHealthOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    trend_source_id: str
    source_name: str | None = None
    source_type: str | None = None
    status: SourceStatus
    last_success_at: datetime | None = None
    last_failure_at: datetime | None = None
    last_error: str | None = None
    records_collected: int = 0
    avg_duration_ms: float | None = None
    consecutive_failures: int = 0
    checked_at: datetime | None = None
    auth_state: str | None = None
    fallback_status: str | None = None


class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    source_type: str
    endpoint_or_reference: str | None = None
    fetch_schedule: str | None = None
    is_active: bool
    data_provenance: DataProvenance
    last_fetched_at: datetime | None = None
    health: SourceHealthOut | None = None
    created_at: datetime
    updated_at: datetime


class CollectionRunOut(BaseModel):
    id: str
    trend_source_id: str
    status: CollectionRunStatus
    trigger: CollectionRunTrigger
    started_at: datetime | None = None
    finished_at: datetime | None = None
    records_collected: int = 0
    records_stored: int = 0
    duration_ms: float | None = None
    error: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SourceDetailOut(SourceOut):
    recent_runs: list[CollectionRunOut] = Field(default_factory=list)


class CollectResponse(BaseModel):
    """202 payload for POST /api/sources/{id}/collect."""

    run_id: str | None = Field(
        default=None,
        description="CollectionRun id (None until Phase-2 source models are wired).",
    )
    job_id: str = Field(description="Background job id — poll GET /api/agents/jobs/{job_id}.")
    status: str = "queued"
    message: str
