"""One-time database bootstrap for local dev.

Creates all tables registered on Base.metadata and applies seed data
(categories, trend sources, compliance rules) via the seed module.
Phase 1: schema tables are placeholders — only `settings` is fully defined.
"""

from __future__ import annotations

from app.db.base import Base
from app.db.session import engine


def _ensure_idea_provenance_columns() -> None:
    """Idempotent schema patch for pre-existing databases.

    ``Base.metadata.create_all`` never ALTERs existing tables, so databases
    created before ``data_provenance`` was added to the idea models need this
    explicit column. Safe to run on every boot (no-op when present).
    """
    from sqlalchemy import inspect, text

    with engine.begin() as conn:
        insp = inspect(conn)
        existing_tables = set(insp.get_table_names())
        for table in ("image_ideas", "video_ideas"):
            if table not in existing_tables:
                continue
            cols = {c["name"] for c in insp.get_columns(table)}
            if "data_provenance" not in cols:
                conn.execute(
                    text(f"ALTER TABLE {table} ADD COLUMN data_provenance VARCHAR(16)")
                )


def init_db() -> None:
    """Create tables and apply idempotent seed data. Idempotent."""
    # Import models so they register on Base.metadata (added in later phases).
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_idea_provenance_columns()

    # Apply seed data idempotently on every boot so new seed rows
    # (e.g. Phase 2 trend sources) reach existing databases.
    # run_seed() is idempotent and guarded against duplicate demo rows.
    from app.db.seed import run_seed

    run_seed()
