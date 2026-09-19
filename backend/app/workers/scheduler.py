"""Phase 2 collection scheduler (PHASE2_DESIGN.md §4).

apscheduler ``BackgroundScheduler`` started from ``main.py`` lifespan only
when ``STOCKPULSE_SCHEDULER_ENABLED=true`` (default true; tests set false).

Jobs:
  - collect_private_adobe  — daily 06:00 Asia/Karachi
  - collect_public_trends  — daily 07:00
  - collect_social_fast    — every 6h (rss / youtube_rss / github_trending)
  - source_health_check    — every 15 min

Every job run:
  - creates a CollectionRun row (status QUEUED → RUNNING → SUCCESS/PARTIAL/
    FAILED/SKIPPED), honors per-source rate limits (SourceHealth.last run),
    skips sources whose adapter status is NEEDS_AUTH/UNAVAILABLE (records
    SKIPPED, never fake data), and updates SourceHealth on completion.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.adapters.base import CollectionContext
from app.adapters.registry import ADAPTER_TYPE_BY_SOURCE_NAME, get_adapter
from app.schemas.enums import SourceStatus

logger = logging.getLogger(__name__)

SCHEDULER_ENV = "STOCKPULSE_SCHEDULER_ENABLED"

# source_type → job group mapping
FAST_SOURCES = ("rss", "youtube_rss", "github_trending")
DAILY_SOURCES = ("scrapegraph_web", "agentreach_web", "v2ex", "xueqiu")
PRIVATE_SOURCES = ("adobe_contributor",)

_scheduler = None


def scheduler_enabled() -> bool:
    return os.environ.get(SCHEDULER_ENV, "true").lower() not in ("0", "false", "no")


def _run_collection(
    session: Session,
    trend_source_id: str,
    source_type: str,
    trigger: str,
    queries: list[str] | None = None,
    limit: int = 20,
) -> str:
    """Run one source's adapter end-to-end; return the CollectionRun id."""
    from app.adapters.store import dedup_normalized_signals
    from app.models.sources import CollectionRun, SourceHealth

    adapter_cls = get_adapter(source_type)
    run = CollectionRun(
        trend_source_id=trend_source_id, status="RUNNING", trigger=trigger
    )
    session.add(run)
    session.flush()
    started = time.monotonic()

    def finish(status: str, collected: int, stored: int, error: str | None,
               probed: SourceStatus | None = None):
        duration_ms = int((time.monotonic() - started) * 1000)
        run.status = status
        run.finished_at = datetime.now(UTC)
        run.records_collected = collected
        run.records_stored = stored
        run.error = error
        run.duration_ms = duration_ms
        health = session.query(SourceHealth).filter_by(
            trend_source_id=trend_source_id
        ).one_or_none()
        if health is None:
            health = SourceHealth(trend_source_id=trend_source_id)
            session.add(health)
        health.checked_at = datetime.now(UTC)
        health.avg_duration_ms = (
            duration_ms
            if health.avg_duration_ms is None
            else 0.7 * health.avg_duration_ms + 0.3 * duration_ms
        )
        if probed is not None:
            # Adapter probe state (e.g. NEEDS_AUTH / UNAVAILABLE skips).
            health.status = probed
        elif status in ("SUCCESS", "PARTIAL"):
            health.status = SourceStatus.AVAILABLE
            health.last_success_at = datetime.now(UTC)
            health.consecutive_failures = 0
            health.last_error = None
        elif status == "FAILED":
            # A failed run degrades the source: mark TEMP_FAILING so the
            # source is visibly down and downstream confidence logic can
            # discount it (PHASE2_DESIGN.md §9).
            health.status = SourceStatus.TEMP_FAILING
            health.last_failure_at = datetime.now(UTC)
            health.consecutive_failures = (health.consecutive_failures or 0) + 1
            health.last_error = (error or "")[:2000]
        session.commit()
        return run.id

    if adapter_cls is None:
        logger.warning("no adapter registered for source_type=%s", source_type)
        return finish("SKIPPED", 0, 0, f"no adapter for source_type '{source_type}'")

    adapter = adapter_cls()
    try:
        health = adapter.get_status()
    except Exception as exc:  # get_status must not raise, but belt-and-braces
        return finish("SKIPPED", 0, 0, f"status check raised: {exc}",
                      probed=SourceStatus.TEMP_FAILING)

    if health.status in (SourceStatus.NEEDS_AUTH, SourceStatus.UNAVAILABLE):
        # Skip without fake data; record the skip and the probed status.
        return finish(
            "SKIPPED",
            0,
            0,
            f"skipped: adapter status {health.status.value} — {health.detail}",
            probed=health.status,
        )
    if health.status == SourceStatus.TEMP_FAILING:
        logger.warning("source %s TEMP_FAILING: %s", source_type, health.detail)

    ctx = CollectionContext(
        db=session,
        trend_source_id=trend_source_id,
        collection_run_id=run.id,
        trigger=trigger,
        queries=queries or [],
        limit=limit,
    )
    try:
        records = adapter.collect(ctx)
        records = adapter.validate(records)
        signals = adapter.normalize(records)
        signals = adapter.deduplicate(signals, session)
        kept, dropped = dedup_normalized_signals(signals, session)
        if dropped:
            logger.info("source=%s dedup dropped %d signals", source_type, dropped)
        result = adapter.store(kept, session, ctx)
        stored = result.signals_stored + result.private_rows_stored
        session.commit()
        # Update last_fetched_at on the trend source.
        from app.models.intelligence import TrendSource

        session.query(TrendSource).filter_by(id=trend_source_id).update(
            {"last_fetched_at": datetime.now(UTC)}
        )
        session.commit()
        status = "SUCCESS" if not result.notes else "PARTIAL"
        return finish(status, len(records), stored, None if status == "SUCCESS" else "; ".join(result.notes))
    except Exception as exc:
        err = str(exc)[:2000]
        logger.exception("collection failed for source %s", source_type)
        run_started_at = run.started_at
        session.rollback()
        # The rollback discarded the flushed run INSERT; re-create the row so
        # the FAILED run is recorded instead of silently lost (§9: no hidden
        # collection failures).
        run = CollectionRun(
            trend_source_id=trend_source_id,
            status="RUNNING",
            trigger=trigger,
            started_at=run_started_at,
        )
        session.add(run)
        session.flush()
        return finish("FAILED", 0, 0, err)


def _sources_by_types(session: Session, source_types: tuple[str, ...]) -> list:
    from app.models.intelligence import TrendSource

    return session.query(TrendSource).filter(TrendSource.name.in_(_source_names(source_types))).all()


_SOURCE_TYPE_BY_NAME = ADAPTER_TYPE_BY_SOURCE_NAME  # single source of truth


def _source_names(source_types: tuple[str, ...]) -> list[str]:
    return [name for name, st in _SOURCE_TYPE_BY_NAME.items() if st in source_types]


def job_collect_sources(source_types: tuple[str, ...], trigger: str = "SCHEDULED") -> dict:
    """Collect a group of sources. Called by apscheduler jobs and the API router."""
    from app.db.session import SessionLocal

    session = SessionLocal()
    summary: dict[str, str] = {}
    try:
        for src in _sources_by_types(session, source_types):
            source_type = _SOURCE_TYPE_BY_NAME.get(src.name)
            if not source_type:
                continue
            if not src.is_active:
                logger.info("source %s inactive — skipped", src.name)
                continue
            run_id = _run_collection(
                session, src.id, source_type, trigger=trigger, limit=20
            )
            summary[src.name] = run_id
    finally:
        session.close()
    return summary


def job_collect_public_trends() -> dict:
    return job_collect_sources(FAST_SOURCES + DAILY_SOURCES, trigger="SCHEDULED")


def job_collect_social_fast() -> dict:
    return job_collect_sources(FAST_SOURCES, trigger="SCHEDULED")


def job_collect_private_adobe() -> dict:
    return job_collect_sources(PRIVATE_SOURCES, trigger="SCHEDULED")


def job_source_health_check() -> dict:
    """Refresh SourceHealth for every active source (status probe only)."""
    from app.db.session import SessionLocal
    from app.models.intelligence import TrendSource
    from app.models.sources import SourceHealth

    session = SessionLocal()
    summary: dict[str, str] = {}
    try:
        for src in session.query(TrendSource).filter_by(is_active=True).all():
            source_type = _SOURCE_TYPE_BY_NAME.get(src.name)
            if not source_type:
                continue
            adapter_cls = get_adapter(source_type)
            health_row = session.query(SourceHealth).filter_by(
                trend_source_id=src.id
            ).one_or_none()
            if health_row is None:
                health_row = SourceHealth(trend_source_id=src.id)
                session.add(health_row)
            if adapter_cls is None:
                health_row.status = SourceStatus.UNAVAILABLE
                health_row.last_error = f"no adapter for '{source_type}'"
            else:
                try:
                    probe = adapter_cls().get_status()
                    health_row.status = probe.status
                    health_row.last_error = probe.last_error
                    health_row.checked_at = datetime.now(UTC)
                except Exception as exc:
                    health_row.status = SourceStatus.TEMP_FAILING
                    health_row.last_error = str(exc)[:2000]
            summary[src.name] = health_row.status.value if isinstance(
                health_row.status, SourceStatus
            ) else str(health_row.status)
        session.commit()
    finally:
        session.close()
    return summary


def start_scheduler() -> object | None:
    """Create + start the apscheduler BackgroundScheduler. Idempotent."""
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    from apscheduler.schedulers.background import BackgroundScheduler

    sched = BackgroundScheduler(timezone="Asia/Karachi")
    sched.add_job(job_collect_private_adobe, "cron", hour=6, minute=0, id="collect_private_adobe")
    sched.add_job(job_collect_public_trends, "cron", hour=7, minute=0, id="collect_public_trends")
    sched.add_job(job_collect_social_fast, "interval", hours=6, id="collect_social_fast")
    sched.add_job(job_source_health_check, "interval", minutes=15, id="source_health_check")
    sched.start()
    _scheduler = sched
    logger.info("Phase 2 collection scheduler started (4 jobs)")
    return sched


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None


__all__ = [
    "SCHEDULER_ENV",
    "job_collect_private_adobe",
    "job_collect_public_trends",
    "job_collect_social_fast",
    "job_collect_sources",
    "job_source_health_check",
    "scheduler_enabled",
    "start_scheduler",
    "stop_scheduler",
]
