"""SQLAlchemy database layer.

Local-dev default is SQLite (docs: SQLite fallback — see README).
Types are chosen to be Postgres-compatible:
- UUID PKs stored as String(36) (not native UUID), generated in Python
- datetimes stored as timezone-aware DateTime (UTC)
- flexible JSON stored via JSON columns
"""

from app.db.base import Base
from app.db.session import SessionLocal, engine, get_engine

__all__ = ["Base", "SessionLocal", "engine", "get_engine"]
