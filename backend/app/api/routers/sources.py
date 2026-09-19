"""Data sources & collection runs (CONTRACT.md §5.18, PHASE2_DESIGN.md §5).

``GET /`` lists every TrendSource with its health summary. ``POST /{id}/collect``
queues a manual collection (rate-limited like /trends/refresh → 202 + run id).

The Phase-2 source models (``app.models.sources``) and the adapter registry are
created by sibling agents; until they land, health/runs degrade to honest
empty states and collect records SKIPPED (never fake data).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api import jobs
from app.api.deps import (
    check_rate_limit,
    get_db,
    get_idempotency_key,
    idempotent,
    not_found,
    paginate,
    pagination_params,
)
from app.models.intelligence import TrendSource
from app.schemas.common import Page
from app.schemas.enums import (
    AgentRunKind,
    CollectionRunStatus,
    CollectionRunTrigger,
    SourceStatus,
)
from app.schemas.sources import (
    CollectResponse,
    CollectionRunOut,
    SourceDetailOut,
    SourceHealthOut,
    SourceOut,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sources", tags=["sources"])


def _source_models():
    """Phase-2 models (sibling agent). (CollectionRun, SourceHealth) or (None, None)."""
    try:
        from app.models.sources import CollectionRun, SourceHealth  # noqa: F401

        return CollectionRun, SourceHealth
    except ImportError:
        return None, None


def _coerce_status(value) -> SourceStatus:
    try:
        return SourceStatus(getattr(value, "value", value))
    except (ValueError, TypeError):
        return SourceStatus.TEMP_FAILING


def _health_out(row) -> SourceHealthOut:
    return SourceHealthOut(
        id=row.id,
        trend_source_id=row.trend_source_id,
        status=_coerce_status(getattr(row, "status", None)),
        last_success_at=getattr(row, "last_success_at", None),
        last_failure_at=getattr(row, "last_failure_at", None),
        last_error=getattr(row, "last_error", None),
        records_collected=getattr(row, "records_collected", 0) or 0,
        avg_duration_ms=getattr(row, "avg_duration_ms", None),
        consecutive_failures=getattr(row, "consecutive_failures", 0) or 0,
        checked_at=getattr(row, "checked_at", None),
        auth_state=getattr(row, "auth_state", None),
        fallback_status=getattr(row, "fallback_status", None),
    )


def _run_out(row) -> CollectionRunOut:
    def _coerce(enum_cls, value, default):
        try:
            return enum_cls(getattr(value, "value", value))
        except (ValueError, TypeError):
            return default

    return CollectionRunOut(
        id=row.id,
        trend_source_id=row.trend_source_id,
        status=_coerce(CollectionRunStatus, getattr(row, "status", None), CollectionRunStatus.FAILED),
        trigger=_coerce(CollectionRunTrigger, getattr(row, "trigger", None), CollectionRunTrigger.API),
        started_at=getattr(row, "started_at", None),
        finished_at=getattr(row, "finished_at", None),
        records_collected=getattr(row, "records_collected", 0) or 0,
        records_stored=getattr(row, "records_stored", 0) or 0,
        duration_ms=getattr(row, "duration_ms", None),
        error=getattr(row, "error", None),
        created_at=getattr(row, "created_at", None),
        updated_at=getattr(row, "updated_at", None),
    )


def _health_map(db: Session, source_ids: list[str]) -> dict[str, SourceHealthOut]:
    """Latest SourceHealth per source id (empty until the models land)."""
    _, SourceHealth = _source_models()
    if SourceHealth is None or not source_ids:
        return {}
    rows = (
        db.query(SourceHealth)
        .filter(SourceHealth.trend_source_id.in_(source_ids))
        .order_by(SourceHealth.checked_at.desc())
        .all()
    )
    out: dict[str, SourceHealthOut] = {}
    for r in rows:
        if r.trend_source_id not in out:
            out[r.trend_source_id] = _health_out(r)
    return out


def _source_out(row: TrendSource, health: SourceHealthOut | None) -> SourceOut:
    return SourceOut(
        id=row.id,
        name=row.name,
        source_type=str(getattr(row.source_type, "value", row.source_type)),
        endpoint_or_reference=row.endpoint_or_reference,
        fetch_schedule=row.fetch_schedule,
        is_active=bool(row.is_active),
        data_provenance=row.data_provenance,
        last_fetched_at=row.last_fetched_at,
        health=health,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _get_source(db: Session, source_id: str) -> TrendSource:
    row = db.query(TrendSource).filter_by(id=source_id).one_or_none()
    if row is None:
        raise not_found("SOURCE_NOT_FOUND", f"Source {source_id} not found.")
    return row


# NOTE: static sub-paths are declared before /{source_id} so they are not
# swallowed by the path parameter.


@router.get("/health", response_model=list[SourceHealthOut])
def source_health(db: Annotated[Session, Depends(get_db)]):
    """Per-source health, left-joined against the source registry.

    Every registered source appears exactly once: with its latest health
    check, or with status NOT_CHECKED when the scheduler has never checked
    it. Counts therefore reconcile with GET /api/sources.
    """
    sources = db.query(TrendSource).order_by(TrendSource.name).all()
    health = _health_map(db, [s.id for s in sources])
    out: list[SourceHealthOut] = []
    for s in sources:
        h = health.get(s.id)
        source_type = str(getattr(s.source_type, "value", s.source_type))
        if h is None:
            out.append(
                SourceHealthOut(
                    id=f"not-checked-{s.id}",
                    trend_source_id=s.id,
                    source_name=s.name,
                    source_type=source_type,
                    status=SourceStatus.NOT_CHECKED,
                )
            )
        else:
            h.source_name = s.name
            h.source_type = source_type
            out.append(h)
    return out


@router.get("/runs", response_model=Page[CollectionRunOut])
def list_collection_runs(
    db: Annotated[Session, Depends(get_db)],
    paging: Annotated[dict, Depends(pagination_params)],
    status: str | None = None,
    trigger: str | None = None,
    source_id: str | None = None,
):
    CollectionRun, _ = _source_models()
    if CollectionRun is None:
        return paginate([], page=paging["page"], page_size=paging["page_size"], total=0)
    q = db.query(CollectionRun).order_by(CollectionRun.started_at.desc())
    if status is not None:
        q = q.filter_by(status=status)
    if trigger is not None:
        q = q.filter_by(trigger=trigger)
    if source_id is not None:
        q = q.filter_by(trend_source_id=source_id)
    total = q.count()
    page, page_size = paging["page"], paging["page_size"]
    rows = q.offset((page - 1) * page_size).limit(page_size).all()
    return paginate([_run_out(r) for r in rows], page=page, page_size=page_size, total=total)


@router.get("/runs/{run_id}", response_model=CollectionRunOut)
def get_collection_run(run_id: str, db: Annotated[Session, Depends(get_db)]):
    CollectionRun, _ = _source_models()
    row = (
        db.query(CollectionRun).filter_by(id=run_id).one_or_none()
        if CollectionRun is not None
        else None
    )
    if row is None:
        raise not_found("COLLECTION_RUN_NOT_FOUND", f"Collection run {run_id} not found.")
    return _run_out(row)


@router.get("", response_model=Page[SourceOut])
def list_sources(
    db: Annotated[Session, Depends(get_db)],
    paging: Annotated[dict, Depends(pagination_params)],
):
    """All sources with health summary + provenance."""
    q = db.query(TrendSource).order_by(TrendSource.name)
    total = q.count()
    page, page_size = paging["page"], paging["page_size"]
    rows = q.offset((page - 1) * page_size).limit(page_size).all()
    health = _health_map(db, [r.id for r in rows])
    return paginate(
        [_source_out(r, health.get(r.id)) for r in rows],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/{source_id}", response_model=SourceDetailOut)
def get_source(source_id: str, db: Annotated[Session, Depends(get_db)]):
    """Source detail + recent collection runs."""
    row = _get_source(db, source_id)
    health = _health_map(db, [row.id]).get(row.id)
    CollectionRun, _ = _source_models()
    runs: list[CollectionRunOut] = []
    if CollectionRun is not None:
        run_rows = (
            db.query(CollectionRun)
            .filter_by(trend_source_id=row.id)
            .order_by(CollectionRun.started_at.desc())
            .limit(10)
            .all()
        )
        runs = [_run_out(r) for r in run_rows]
    detail = SourceDetailOut(**_source_out(row, health).model_dump(), recent_runs=runs)
    return detail


def _execute_collection(source_id: str, run_id: str | None, source_type: str) -> dict:
    """Run one manual collection; finalize the CollectionRun row. Never raises."""
    from app.db.session import SessionLocal

    started = datetime.now(UTC)
    db: Session = SessionLocal()
    try:
        result = _collect_via_adapter(db, source_id, run_id, source_type)
        _finalize_run(db, run_id, result, started)
        return result
    except Exception as exc:  # noqa: BLE001 — collection must never crash the job
        logger.warning("collection failed for source %s: %s", source_id, exc)
        _finalize_run(
            db,
            run_id,
            {"status": CollectionRunStatus.FAILED, "error": str(exc)[:2000]},
            started,
        )
        return {"status": CollectionRunStatus.FAILED, "error": str(exc)[:500]}
    finally:
        db.close()


def _collect_via_adapter(
    db: Session, source_id: str, run_id: str | None, source_type: str
) -> dict:
    """Adapter pipeline: status check → collect → validate → normalize → store."""
    try:
        from app.adapters.registry import get_adapter
    except ImportError:
        return {
            "status": CollectionRunStatus.SKIPPED,
            "error": "Adapter registry not available yet (Phase 2 in progress). No data fabricated.",
        }
    adapter_cls = get_adapter(source_type)
    if adapter_cls is None:
        return {
            "status": CollectionRunStatus.SKIPPED,
            "error": f"No adapter registered for source type '{source_type}'.",
        }
    adapter = adapter_cls()
    health = adapter.get_status()
    if health.status in (SourceStatus.NEEDS_AUTH, SourceStatus.UNAVAILABLE):
        return {
            "status": CollectionRunStatus.SKIPPED,
            "error": f"Source {health.status.value}: {health.detail}",
        }

    try:
        from app.adapters.base import CollectionContext
    except ImportError:
        return {
            "status": CollectionRunStatus.SKIPPED,
            "error": "Adapter base not available yet (Phase 2 in progress). No data fabricated.",
        }

    ctx = CollectionContext(
        db=db,
        trend_source_id=source_id,
        collection_run_id=run_id,
        trigger="API",
    )
    records = adapter.validate(adapter.collect(ctx))
    signals = adapter.normalize(records)
    signals = adapter.deduplicate(signals, db)
    stored = adapter.store(signals, db, ctx)
    return {
        "status": CollectionRunStatus.SUCCESS,
        "records_collected": len(records),
        "records_stored": int(
            getattr(stored, "signals_stored", 0) + getattr(stored, "private_rows_stored", 0)
        ),
        "error": None,
    }


def _finalize_run(db: Session, run_id: str | None, result: dict, started: datetime) -> None:
    """Persist run outcome + refresh the source's health row (when models exist)."""
    CollectionRun, SourceHealth = _source_models()
    if run_id is None or CollectionRun is None:
        return
    try:
        run = db.query(CollectionRun).filter_by(id=run_id).one_or_none()
        if run is None:
            return
        now = datetime.now(UTC)
        run.status = result["status"]
        run.finished_at = now
        run.records_collected = result.get("records_collected", 0) or 0
        run.records_stored = result.get("records_stored", 0) or 0
        run.duration_ms = (now - started).total_seconds() * 1000
        run.error = result.get("error")
        db.commit()

        if SourceHealth is not None:
            ok = result["status"] in (CollectionRunStatus.SUCCESS, CollectionRunStatus.PARTIAL)
            health = (
                db.query(SourceHealth)
                .filter_by(trend_source_id=run.trend_source_id)
                .one_or_none()
            )
            if health is not None:
                health.checked_at = now
                if ok:
                    health.last_success_at = now
                    health.consecutive_failures = 0
                    health.records_collected = (
                        getattr(health, "records_collected", 0) or 0
                    ) + run.records_collected
                else:
                    health.last_failure_at = now
                    health.last_error = run.error
                    health.consecutive_failures = (
                        getattr(health, "consecutive_failures", 0) or 0
                    ) + 1
                db.commit()
    except Exception as exc:  # noqa: BLE001 — bookkeeping must not fail the job
        logger.warning("collection bookkeeping failed: %s", exc)
        db.rollback()


@router.post("/{source_id}/collect", response_model=CollectResponse, status_code=202)
def collect_source(
    source_id: str,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    """Manual collection trigger → 202 + run id (rate-limited 5/hr, like /trends/refresh)."""
    source = _get_source(db, source_id)
    check_rate_limit(f"sources:collect:{source_id}", max_calls=5, per_seconds=3600)

    CollectionRun, _ = _source_models()
    run_id: str | None = None
    if CollectionRun is not None:
        run = CollectionRun(
            trend_source_id=source_id,
            status=CollectionRunStatus.QUEUED,
            trigger=CollectionRunTrigger.API,
            started_at=datetime.now(UTC),
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        run_id = run.id

    source_type = str(getattr(source.source_type, "value", source.source_type))

    def _run(job_db: Session, agent_run):  # noqa: ARG001 — jobs pattern signature
        return _execute_collection(source_id, run_id, source_type)

    result = jobs.submit_job(
        agent_name="trend_research",
        run_kind=AgentRunKind.TREND_INGEST,
        input_summary={"trigger": "manual collect", "source_id": source_id, "run_id": run_id},
        func=_run,
    )
    payload = CollectResponse(
        run_id=run_id,
        job_id=result["job_id"],
        status="queued",
        message="Collection queued."
        if run_id
        else "Collection queued (run tracking unavailable until Phase-2 source models land).",
    )
    return idempotent(get_idempotency_key(request), payload)
