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


def get_engine():
    url = settings.database_url
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
