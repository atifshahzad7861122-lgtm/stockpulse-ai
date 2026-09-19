"""`settings` table — the single user's platform configuration.

docs: 08_DATABASE_SCHEMA §3.3. Single-user deviation: no `user_id` column;
`project_id` is nullable for per-project overrides. Canonical keys are
documented in docs/08 §3.3 and CONTRACT.md.
"""

from __future__ import annotations

from sqlalchemy import JSON, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditTimestampsMixin, Base, UUIDPrimaryKeyMixin


class Setting(Base, UUIDPrimaryKeyMixin, AuditTimestampsMixin):
    """Key/value platform configuration (no deleted_at — config, not content)."""

    __tablename__ = "settings"

    # Nullable project scope: NULL = user-wide default. FK to projects.id is
    # added in Phase 2 when the projects table is modeled (docs/08 §3.2).
    project_id: Mapped[str | None] = mapped_column(String(36), nullable=True, default=None)
    key: Mapped[str] = mapped_column(String(120), nullable=False)
    value: Mapped[dict] = mapped_column(JSON, nullable=False)

    __table_args__ = (
        Index("idx_settings_project", "project_id"),
        # Single-user: keys are globally unique (no tenancy).
        UniqueConstraint("key", name="uq_settings_key"),
    )
