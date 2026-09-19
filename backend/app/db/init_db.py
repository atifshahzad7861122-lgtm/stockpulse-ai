"""One-time database bootstrap for local dev.

Creates all tables registered on Base.metadata and applies seed data
(categories, trend sources, compliance rules) via the seed module.
Phase 1: schema tables are placeholders — only `settings` is fully defined.
"""

from __future__ import annotations

from app.db.base import Base
from app.db.session import engine


def init_db() -> None:
    """Create tables and apply idempotent seed data. Idempotent."""
    # Import models so they register on Base.metadata (added in later phases).
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    # Apply seed data idempotently on every boot so new seed rows
    # (e.g. Phase 2 trend sources) reach existing databases.
    # run_seed() is idempotent and guarded against duplicate demo rows.
    from app.db.seed import run_seed

    run_seed()
