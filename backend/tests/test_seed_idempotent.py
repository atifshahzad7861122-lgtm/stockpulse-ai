"""Fresh seed is idempotent: rerunning changes no counts."""

from __future__ import annotations

from sqlalchemy import func

from app.models.compliance import ComplianceRule
from app.models.intelligence import TrendSnapshot, TrendSource
from app.models.platform import Notification
from app.models.settings import Setting
from app.models.taxonomy import Category, MicroNiche, Subcategory

TABLES = [
    (Category, 39),
    (Subcategory, 85),
    (MicroNiche, 171),
    (TrendSource, 19),  # 11 Phase 1 + 8 Phase 2 real-data sources
    (ComplianceRule, 28),
]


def _counts(db) -> dict[str, int]:
    return {
        "categories": db.query(func.count(Category.id)).scalar(),
        "subcategories": db.query(func.count(Subcategory.id)).scalar(),
        "micro_niches": db.query(func.count(MicroNiche.id)).scalar(),
        "trend_sources": db.query(func.count(TrendSource.id)).scalar(),
        "compliance_rules": db.query(func.count(ComplianceRule.id)).scalar(),
        "settings": db.query(func.count(Setting.id)).scalar(),
        "trend_snapshots": db.query(func.count(TrendSnapshot.id)).scalar(),
        "notifications": db.query(func.count(Notification.id)).scalar(),
    }


def test_seed_idempotent():
    """run_seed() twice on a fresh DB yields identical counts."""
    # NOTE: run_seed uses the app engine/session, not the test session, so this
    # test uses its own throwaway SQLite file.
    import os

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    import app.models  # noqa: F401 — register tables
    from app.db.base import Base

    path = "/tmp/sp_seed_idem.db"
    if os.path.exists(path):
        os.unlink(path)

    import app.db.seed as seed_mod

    eng = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(eng)
    seed_mod.engine = eng
    seed_mod.SessionLocal = lambda: Session(eng)

    seed_mod.run_seed()
    first = _counts(Session(eng))
    seed_mod.run_seed()
    second = _counts(Session(eng))
    assert first == second, f"seed not idempotent: {first} vs {second}"
    for model, expected in TABLES:
        name = model.__tablename__
        assert second[name] == expected, f"{name}: {second[name]} != {expected}"
