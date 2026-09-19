"""Settings schemas (single-user: no auth, no project scoping beyond overrides)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SettingOut(BaseModel):
    id: str
    project_id: str | None = None
    key: str
    value: Any
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SettingUpdate(BaseModel):
    value: Any = Field(...)


# Canonical settings keys (docs: 08 §3.3). Implementers must use these names.
CANONICAL_SETTING_KEYS = (
    "briefing.time",
    "briefing.timezone",
    "briefing.days",
    "opportunity.min_score",
    "opportunity.min_confidence",
    "compliance.strictness",  # standard | strict
    "notifications.email_enabled",
    "notifications.digest_time",
    "production.default_language",
    "retention.soft_delete_days",
    # Submission capacity (docs: 21) — user-configured, never invented.
    "planner.daily_capacity",
    "planner.weekly_capacity",
    "planner.blackout_dates",
    # Phase 2 — real-data layer (PHASE2_DESIGN.md §2, §8).
    "dev_mode",  # bool: when true, MOCK/demo rows drive intelligence (banner shown)
    "rss.feeds",  # JSON list of {name, url, category}; zero-config feed sources
)
