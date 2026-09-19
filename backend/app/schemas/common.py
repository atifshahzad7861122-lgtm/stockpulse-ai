"""Shared response shapes: error envelope, pagination, health (CONTRACT.md §2–§4)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, Self, TypeVar

from pydantic import BaseModel, Field

from app.schemas.enums import DataProvenance


class ErrorDetail(BaseModel):
    code: str = Field(
        ..., description="Machine-readable code, e.g. E-AI-202 or OPPORTUNITY_NOT_FOUND"
    )
    message: str = Field(..., description="Human-readable, safe to display")
    severity: str = Field(default="error")
    retryable: bool = Field(default=False)
    retry_in_seconds: int | None = None
    request_id: str | None = None
    trace_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    help: str | None = None


class ErrorEnvelope(BaseModel):
    error: ErrorDetail


T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """Standard paginated list shape (CONTRACT.md)."""

    data: list[T]
    pagination: PageInfo


class PageInfo(BaseModel):
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1, le=100)
    total: int = Field(..., ge=0)
    total_pages: int = Field(..., ge=0)


class HealthResponse(BaseModel):
    status: str = Field(default="ok")
    service: str = Field(default="stockpulse-ai")
    version: str = Field(default="0.2.0")
    timestamp: datetime


class FeatureFlags(BaseModel):
    """Contract §5.15: simple flags map."""

    flags: dict[str, bool] = Field(default_factory=dict)
    database: str = Field(default="unknown", description="ok | degraded | unknown")


_DEMO_TEXT_ATTRS = (
    "notes",
    "title",
    "body",
    "concept",
    "name",
    "originality_notes",
    "change_summary",
    "explanation",
)
_DEMO_JSON_ATTRS = ("parameters", "input_summary", "output_summary")


def _json_has_demo_marker(value: Any, depth: int = 0) -> bool:
    """Recursively scan JSON for demo/mock marker strings."""
    if depth > 4:
        return False
    if isinstance(value, str):
        lowered = value.lower()
        return "demo" in lowered or "mock" in lowered
    if isinstance(value, dict):
        return any(_json_has_demo_marker(v, depth + 1) for v in value.values())
    if isinstance(value, list | tuple):
        return any(_json_has_demo_marker(v, depth + 1) for v in value)
    return False


def resolve_provenance(row: Any) -> DataProvenance | None:
    """Best-effort provenance for an ORM row (CONTRACT.md §3).

    - ``data_provenance`` column wins when present.
    - Rows produced by the mock agent pipeline (agent_run_id set) are MOCK.
    - Demo-seed rows are detected via demo markers in text fields or the
      mock generation-tool label.
    """
    prov = getattr(row, "data_provenance", None)
    if prov is not None:
        return DataProvenance(prov)
    # NOTE: the agent_run_id ⇒ MOCK inference is valid only while every agent
    # run executes the deterministic mock pipeline. If a real (non-mock)
    # provider pipeline is ever added, this must become run-aware instead of
    # silently mislabeling real runs.
    if getattr(row, "agent_run_id", None):
        return DataProvenance.MOCK
    for attr in _DEMO_TEXT_ATTRS:
        val = getattr(row, attr, None)
        if isinstance(val, str) and "demo" in val.lower():
            return DataProvenance.MOCK
    for attr in _DEMO_JSON_ATTRS:
        val = getattr(row, attr, None)
        if val is not None and _json_has_demo_marker(val):
            return DataProvenance.MOCK
    tool = getattr(row, "generation_tool", None)
    if isinstance(tool, str) and "mock" in tool.lower():
        return DataProvenance.MOCK
    return None


class MockLabeled(BaseModel):
    """CONTRACT.md §3: every record carrying demo/placeholder data must expose
    ``provenance: "MOCK"`` and payload-level ``mock: true``."""

    provenance: DataProvenance | None = Field(
        default=None, description="MOCK for demo/placeholder records"
    )
    mock: bool = Field(default=False, description="Payload-level mock flag")

    @classmethod
    def from_row(cls, row: Any) -> Self:
        out = cls.model_validate(row)
        return apply_labels(out, row)


def apply_labels(out: MockLabeled, row: Any) -> MockLabeled:
    """Stamp CONTRACT.md §3 mock labels from an ORM row onto a response."""
    prov = resolve_provenance(row)
    out.provenance = prov
    out.mock = prov == DataProvenance.MOCK
    return out
