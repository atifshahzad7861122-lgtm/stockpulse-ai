"""Dev-mode flag (PHASE2_DESIGN.md §2).

Seeded MOCK/demo rows stay in the DB but stop driving production intelligence
unless dev mode is on. Effective dev mode = env DEV_MODE, or the `dev_mode`
setting row (so it can be toggled from the Settings UI).
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import settings


def _truthy(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)


def is_dev_mode(db: Session | None = None) -> bool:
    """Return True when demo data may drive intelligence (env or settings row).

    The seed stores settings wrapped as ``{"value": <actual>}`` while PATCH
    writes the raw value; both shapes are accepted here.
    """
    if settings.dev_mode:
        return True
    if db is None:
        return False
    try:
        from app.models.settings import Setting

        row = db.query(Setting).filter_by(key="dev_mode").one_or_none()
    except Exception:
        return False
    if row is None:
        return False
    raw = row.value
    if isinstance(raw, dict) and set(raw.keys()) == {"value"}:
        raw = raw["value"]
    return _truthy(raw)
