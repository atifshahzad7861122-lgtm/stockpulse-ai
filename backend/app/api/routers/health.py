"""Health & readiness (CONTRACT.md §5.1: GET /api/health — public, no auth)."""

from datetime import UTC, datetime

from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import settings
from app.db.session import engine
from app.schemas.common import HealthResponse

router = APIRouter(prefix="/health", tags=["health"])


def _db_status() -> str:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return "ok"
    except Exception:
        return "degraded"


@router.get("", response_model=HealthResponse, summary="Service health")
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version="0.5.0",
        timestamp=datetime.now(UTC),
        database=_db_status(),
    )
