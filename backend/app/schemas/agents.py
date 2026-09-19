"""Agent & job schemas (CONTRACT.md §5.14)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.enums import AgentRunKind


class AgentDefinitionOut(BaseModel):
    name: str
    description: str
    capabilities: list[str] = Field(default_factory=list)
    enabled: bool = True


class JobError(BaseModel):
    code: str
    message: str


class JobOut(BaseModel):
    job_id: str
    run_id: str | None = None
    agent: str
    run_kind: str | None = None
    status: str
    progress: float = 0.0
    input_summary: dict[str, Any] = Field(default_factory=dict)
    output_summary: dict[str, Any] | None = None
    error: JobError | None = None
    instructions_version: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime | None = None


class JobCreate(BaseModel):
    job_id: str


class AgentRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    agent_name: str
    run_kind: AgentRunKind
    status: str
    input_summary: dict[str, Any] = Field(default_factory=dict)
    output_summary: dict[str, Any] | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    triggered_by: str
    instructions_version: str | None = None
    created_at: datetime


class AgentLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    agent_run_id: str
    level: str
    message: str
    context: dict[str, Any] = Field(default_factory=dict)
    logged_at: datetime


class DailyRunRequest(BaseModel):
    """Extension: run the 16-step supervised daily workflow."""

    skip_gates: bool = Field(
        default=False,
        description="Run all steps without pausing at human gates (tests/demo only).",
    )
    input: dict[str, Any] = Field(default_factory=dict)
