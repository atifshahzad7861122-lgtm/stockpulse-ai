"""StockPulse AI API — FastAPI application entrypoint.

Single-user: no auth layer, no /auth or /users routes (see CHANGELOG 0.2.0).
Base URL: http://localhost:8000/api (CONTRACT.md).
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import routers
from app.api.deps import APIError, api_error_handler
from app.core.config import settings
from app.core.errors import error_response
from app.db.init_db import init_db
from app.workers.scheduler import scheduler_enabled, start_scheduler, stop_scheduler

import logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    # Production safety: never boot against the local SQLite file when the
    # operator asked for production. A missing DATABASE_URL on Railway would
    # otherwise silently run on an ephemeral SQLite file and lose all data on
    # redeploy. Fail fast with a clear message instead.
    if settings.app_env == "production" and settings.database_url.startswith("sqlite"):
        raise RuntimeError(
            "Refusing to boot with APP_ENV=production and a SQLite DATABASE_URL. "
            "Set DATABASE_URL to the Railway PostgreSQL connection string."
        )
    init_db()
    # Phase 2 collection scheduler — opt-out via STOCKPULSE_SCHEDULER_ENABLED=false.
    if scheduler_enabled():
        try:
            start_scheduler()
        except Exception as exc:  # scheduler is auxiliary; never block app boot
            logger.warning("Phase 2 scheduler failed to start: %s", exc)
    yield
    stop_scheduler()


# C2 hardening: never expose interactive docs or the OpenAPI schema in
# production. Dev/test keep them (local dev + contract verification).
_is_production = settings.app_env == "production"

app = FastAPI(
    title="StockPulse AI",
    description="Personal Adobe Stock intelligence — single-user. See CONTRACT.md.",
    version="0.5.0",
    docs_url=None if _is_production else "/docs",
    redoc_url=None if _is_production else "/redoc",
    openapi_url=None if _is_production else "/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_allowed_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request.state.request_id = f"req_{uuid.uuid4().hex[:12]}"
    return await call_next(request)


# Typed API errors → CONTRACT error envelope.
app.add_exception_handler(APIError, api_error_handler)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Wrap FastAPI 422s in the CONTRACT error envelope.

    Raw {"detail": [...]} shapes bypassed the envelope; clients only know how
    to parse {"error": {...}}. Explicit 422s raised via APIError (e.g. queue
    page_size, ILLEGAL_TRANSITION) are unaffected — they never reach this
    handler. Code follows the registry in app/core/errors.py (E-VAL-801).
    """
    raw_errors = jsonable_encoder(exc.errors())  # never leaks non-JSON ctx values
    field_errors = [
        {
            "field": ".".join(str(part) for part in err.get("loc", [])),
            "message": err.get("msg", ""),
            "type": err.get("type", ""),
        }
        for err in raw_errors
        if isinstance(err, dict)
    ]
    if field_errors:
        first = field_errors[0]
        message = f"Invalid request: {first['field']}: {first['message']}".rstrip(": ")
    else:
        message = "Invalid request."
    return error_response(
        code="E-VAL-801",
        message=message,
        status_code=422,
        request=request,
        severity="warning",
        retryable=False,
        details={"errors": field_errors},
    )




@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return error_response(
        code="E-DB-601" if "db" in type(exc).__name__.lower() else "INTERNAL_ERROR",
        message="Something went wrong on our side. Your work is safe — please try again.",
        status_code=500,
        request=request,
        retryable=True,
        details={"exception": type(exc).__name__},
    )


# All routers mount under /api (CONTRACT.md base path).
for _router in (
    routers.health.router,
    routers.trends.router,
    routers.categories.router,
    routers.opportunities.router,
    routers.ideas.router,
    routers.prompts.router,
    routers.compliance.router,
    routers.daily_production.router,
    routers.recommendations.router,
    routers.prompt_packs.router,
    routers.similarity.router,
    routers.assets.router,
    routers.metadata.router,
    routers.production.router,
    routers.submissions.router,
    routers.analytics.router,
    routers.agents.router,
    routers.notifications.router,
    routers.library.router,
    routers.opportunity_fusion.router,
    routers.personal_performance.router,
    routers.settings.router,
    routers.sources.router,
    routers.private.router,
):
    app.include_router(_router, prefix="/api")
