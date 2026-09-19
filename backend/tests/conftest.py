"""Pytest fixtures: isolated SQLite test DB, seeded reference data, API client.

The whole suite runs against a dedicated test database file (never the dev
./stockpulse.db). DATABASE_URL is set before any app module is imported so the
module-level engine — also used by app.api.jobs — binds to the test DB.
Each test gets fresh tables via drop_all/create_all on that same engine.
"""

from __future__ import annotations

import os
import sys

TEST_DB = os.environ.get("STOCKPULSE_TEST_DB", "/tmp/stockpulse_pytest.db")
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"

sys.path.insert(0, "/home/hatch/workspace/stockpulse/backend")

import pytest
from fastapi.testclient import TestClient

import app.models  # noqa: F401  (register tables before create_all)
from app.db.base import Base
from app.db.session import SessionLocal, engine


def _reference_seed(session) -> None:
    from app.db.seed import (
        seed_compliance_rules,
        seed_settings,
        seed_taxonomy,
        seed_trend_sources,
    )

    seed_taxonomy(session)
    seed_trend_sources(session)
    seed_compliance_rules(session)
    seed_settings(session)
    session.commit()


@pytest.fixture(scope="function")
def db():
    """Fresh tables + reference seed (no demo rows) for every test."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    _reference_seed(session)
    yield session
    session.close()


@pytest.fixture(scope="function")
def client(db):
    """TestClient whose DB dependency resolves to the test session."""
    from app.api.deps import get_db
    from app.main import app

    def _override():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = _override
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()
