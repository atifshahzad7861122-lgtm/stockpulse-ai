"""Engine + session factory. Handles SQLite dev default and Postgres switch.

SQLite: file-based URL (sqlite:///./stockpulse.db), check_same_thread=False for
FastAPI's threaded dev server. Postgres: standard pool settings from env.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


def _normalize_database_url(url: str) -> str:
    """Map hosted-Postgres URL formats to the SQLAlchemy dialect we ship.

    Railway's PostgreSQL plugin provides DATABASE_URL as ``postgresql://...``
    (sometimes legacy ``postgres://...``) with NO DBAPI driver suffix.
    SQLAlchemy 2.x requires an explicit driver, so bare ``postgresql://`` /
    ``postgres://`` schemes are rewritten to ``postgresql+psycopg://``.
    The production image installs ``psycopg[binary]`` (see
    deploy/backend.Dockerfile). SQLite and fully-qualified URLs pass through
    unchanged.
    """
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


def get_engine():
    url = _normalize_database_url(settings.database_url)
    if _is_sqlite(url):
        return create_engine(url, connect_args={"check_same_thread": False}, future=True)
    return create_engine(
        url,
        pool_size=10,
        pool_pre_ping=True,
        future=True,
    )


engine = get_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
