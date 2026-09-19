"""Immediate-completion job manager (CONTRACT.md §5.14).

Async flows in v1 use persisted immediate-completion jobs: POST returns
`202 { job_id }`, and GET /agents/jobs/{job_id} is the poll target. Every job
is recorded as an agent_runs row (job_id == agent run id) with structured
agent_logs; results are also kept in an in-process registry for polling.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.platform import AgentLog, AgentRun
from app.schemas.enums import AgentLogLevel, AgentRunKind, AgentStatus, JobStatus

# In-process job result registry: job_id → public poll payload.
_JOB_REGISTRY: dict[str, dict[str, Any]] = {}


def _now() -> datetime:
    return datetime.now(UTC)


def _log(
    db: Session, run_id: str, level: AgentLogLevel, message: str, context: dict | None = None
) -> None:
    db.add(AgentLog(agent_run_id=run_id, level=level, message=message, context=context or {}))


def agent_status_to_job_status(status: AgentStatus) -> JobStatus:
    return {
        AgentStatus.PENDING: JobStatus.QUEUED,
        AgentStatus.RUNNING: JobStatus.RUNNING,
        AgentStatus.COMPLETED: JobStatus.SUCCEEDED,
        AgentStatus.FAILED: JobStatus.FAILED,
        AgentStatus.CANCELLED: JobStatus.CANCELLED,
    }[status]


def job_status_to_agent_status(status: JobStatus) -> AgentStatus:
    """Inverse of agent_status_to_job_status (1:1 mapping)."""
    return {
        JobStatus.QUEUED: AgentStatus.PENDING,
        JobStatus.RUNNING: AgentStatus.RUNNING,
        JobStatus.SUCCEEDED: AgentStatus.COMPLETED,
        JobStatus.FAILED: AgentStatus.FAILED,
        JobStatus.CANCELLED: AgentStatus.CANCELLED,
    }[status]


def submit_job(
    *,
    agent_name: str,
    run_kind: AgentRunKind,
    input_summary: dict[str, Any],
    func: Callable[[Session, AgentRun], dict[str, Any]],
    triggered_by: str = "api",
    instructions_version: str | None = None,
) -> dict[str, str]:
    """Create the run row, execute `func` synchronously (retry-once on failure),
    persist the outcome, and return the 202 payload `{ job_id }`.

    Retry policy: on exception the function is retried once; a second failure
    marks the run FAILED with a human-readable error.
    """
    db: Session = SessionLocal()
    try:
        run = AgentRun(
            agent_name=agent_name,
            run_kind=run_kind,
            status=AgentStatus.RUNNING,
            input_summary=input_summary,
            started_at=_now(),
            triggered_by=triggered_by,
            instructions_version=instructions_version,
        )
        db.add(run)
        db.flush()
        _log(db, run.id, AgentLogLevel.INFO, f"Job started: {agent_name}", {"input": input_summary})
        db.commit()

        output: dict[str, Any] | None = None
        error: dict[str, str] | None = None
        attempt = 0
        while attempt < 2:
            attempt += 1
            try:
                output = func(db, run)
                break
            except Exception as exc:  # noqa: BLE001 — retry once, then fail with readable error
                _log(
                    db,
                    run.id,
                    AgentLogLevel.WARNING if attempt == 1 else AgentLogLevel.ERROR,
                    f"Attempt {attempt} failed: {type(exc).__name__}: {exc}",
                )
                db.commit()
                if attempt == 2:
                    error = {
                        "code": "AGENT_FAILED",
                        "message": f"{agent_name} failed after 2 attempts: {exc}",
                    }

        run.finished_at = _now()
        if error is None:
            run.status = AgentStatus.COMPLETED
            run.output_summary = output or {}
            _log(db, run.id, AgentLogLevel.INFO, "Job completed", {"output": run.output_summary})
        else:
            run.status = AgentStatus.FAILED
            run.error_message = error["message"]
            _log(db, run.id, AgentLogLevel.ERROR, "Job failed", error)
        db.commit()

        payload = {
            "job_id": run.id,
            "run_id": run.id,
            "agent": agent_name,
            "run_kind": run_kind.value,
            "status": agent_status_to_job_status(run.status).value,
            "progress": 1.0 if run.status == AgentStatus.COMPLETED else 0.0,
            "input_summary": input_summary,
            "output_summary": run.output_summary,
            "error": error,
            "instructions_version": instructions_version,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
            "created_at": run.created_at.isoformat() if run.created_at else None,
        }
        _JOB_REGISTRY[run.id] = payload
        return {"job_id": run.id}
    finally:
        db.close()


def get_job(job_id: str) -> dict[str, Any] | None:
    """Poll payload for a job; falls back to the agent_runs row if the
    in-process registry missed it (e.g. after restart)."""
    if job_id in _JOB_REGISTRY:
        return _JOB_REGISTRY[job_id]
    db: Session = SessionLocal()
    try:
        run = db.query(AgentRun).filter_by(id=job_id).one_or_none()
        if run is None:
            return None
        payload = {
            "job_id": run.id,
            "run_id": run.id,
            "agent": run.agent_name,
            "run_kind": run.run_kind.value if run.run_kind else None,
            "status": agent_status_to_job_status(run.status).value,
            "progress": 1.0 if run.status == AgentStatus.COMPLETED else 0.0,
            "input_summary": run.input_summary,
            "output_summary": run.output_summary,
            "error": (
                {"code": "AGENT_FAILED", "message": run.error_message}
                if run.error_message
                else None
            ),
            "instructions_version": run.instructions_version,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
            "created_at": run.created_at.isoformat() if run.created_at else None,
        }
        _JOB_REGISTRY[job_id] = payload
        return payload
    finally:
        db.close()


def list_jobs(
    db: Session,
    *,
    status: JobStatus | None = None,
    agent: str | None = None,
    run_kind: AgentRunKind | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict[str, Any]], int]:
    q = db.query(AgentRun).order_by(AgentRun.created_at.desc())
    if agent:
        q = q.filter(AgentRun.agent_name == agent)
    if run_kind:
        q = q.filter(AgentRun.run_kind == run_kind)
    runs = q.all()
    items = []
    for run in runs:
        payload = get_job(run.id) or {}
        if status and payload.get("status") != status.value:
            continue
        items.append(payload)
    total = len(items)
    start = (page - 1) * page_size
    return items[start : start + page_size], total


def cancel_job(db: Session, job_id: str) -> dict[str, Any]:
    run = db.query(AgentRun).filter_by(id=job_id).one_or_none()
    if run is None:
        raise KeyError(job_id)
    if run.status in (AgentStatus.COMPLETED, AgentStatus.FAILED, AgentStatus.CANCELLED):
        raise ValueError("terminal")
    run.status = AgentStatus.CANCELLED
    run.finished_at = _now()
    _log(db, run.id, AgentLogLevel.WARNING, "Job cancelled by user")
    db.commit()
    payload = get_job(job_id) or {}
    payload["status"] = JobStatus.CANCELLED.value
    _JOB_REGISTRY[job_id] = payload
    return payload


def dead_letters(db: Session) -> list[dict[str, Any]]:
    runs = (
        db.query(AgentRun)
        .filter(AgentRun.status == AgentStatus.FAILED)
        .order_by(AgentRun.created_at.desc())
        .all()
    )
    return [get_job(r.id) for r in runs if get_job(r.id)]


def retry_job(db: Session, job_id: str) -> dict[str, str] | None:
    """Re-run a dead-letter job's agent. The original func isn't persisted, so
    retry re-dispatches the run's agent with its original input_summary."""
    from app.agents.dispatcher import dispatch

    run = db.query(AgentRun).filter_by(id=job_id).one_or_none()
    if run is None or run.status != AgentStatus.FAILED:
        return None
    agent_name = run.agent_name
    run_kind = run.run_kind
    input_summary = dict(run.input_summary or {})
    return submit_job(
        agent_name=agent_name,
        run_kind=run_kind,
        input_summary=input_summary,
        func=lambda db, run: dispatch(agent_name, db, run, input_summary),
        triggered_by="retry",
    )
