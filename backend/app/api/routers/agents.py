"""Agent runs & jobs (CONTRACT.md §5.14). All jobs are persisted over agent_runs."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.agents.daily_workflow import run_daily
from app.agents.dispatcher import dispatch
from app.agents.registry import AGENT_DEFINITIONS, AGENT_NAMES
from app.api import jobs as job_store
from app.api.deps import (
    bad_request,
    get_db,
    get_idempotency_key,
    idempotent,
    not_found,
    paginate,
    pagination_params,
)
from app.models.platform import AgentLog, AgentRun
from app.schemas.agents import (
    AgentDefinitionOut,
    AgentLogOut,
    AgentRunOut,
    DailyRunRequest,
    JobCreate,
    JobError,
    JobOut,
)
from app.schemas.common import Page
from app.schemas.enums import AgentRunKind, JobStatus

router = APIRouter(prefix="/agents", tags=["agents"])

# agent name → default run kind for ad-hoc runs
_AGENT_RUN_KINDS: dict[str, AgentRunKind] = {
    "trend_research": AgentRunKind.TREND_INGEST,
    "market_analysis": AgentRunKind.MARKET_ANALYSIS,
    "category_intelligence": AgentRunKind.MARKET_ANALYSIS,
    "opportunity": AgentRunKind.OPPORTUNITY_SCAN,
    "image_ideation": AgentRunKind.IDEA_GENERATION,
    "video_ideation": AgentRunKind.IDEA_GENERATION,
    "prediction": AgentRunKind.PREDICTION,
    "prompt": AgentRunKind.PROMPT_GENERATION,
    "compliance": AgentRunKind.COMPLIANCE_SCREEN,
    "originality": AgentRunKind.SIMILARITY_SCAN,
    "metadata": AgentRunKind.METADATA_DRAFT,
    "production_planning": AgentRunKind.PRODUCTION_PLAN,
    "performance_analysis": AgentRunKind.PERFORMANCE_DIGEST,
}


def _job_to_out(job: dict) -> JobOut:
    error = job.get("error")
    return JobOut(
        job_id=job["job_id"],
        run_id=job.get("run_id"),
        agent=job["agent"],
        run_kind=job.get("run_kind"),
        status=job["status"],
        progress=job.get("progress", 0.0),
        input_summary=job.get("input_summary", {}),
        output_summary=job.get("output_summary"),
        error=JobError(**error) if error else None,
        instructions_version=job.get("instructions_version"),
        started_at=job.get("started_at"),
        finished_at=job.get("finished_at"),
        created_at=job.get("created_at"),
    )


@router.get("", response_model=list[AgentDefinitionOut])
def list_agents():
    return [
        AgentDefinitionOut(
            name=d["name"],
            description=d.get("description", ""),
            capabilities=d.get("capabilities", []),
            enabled=d.get("enabled", True),
        )
        for d in AGENT_DEFINITIONS
    ]


@router.post("/daily-run", response_model=JobCreate, status_code=202)
def daily_run(body: DailyRunRequest, request: Request, db: Annotated[Session, Depends(get_db)]):
    """Run the 16-step supervised daily workflow (docs: 13).

    Human gates pause at steps 3/4/5/7/10/12 unless skip_gates is set.
    Never auto-submits; automated recommendations stop at DISCOVERED/IDEA_READY.
    """

    def _run(db: Session, run):
        return run_daily(db, run, {"skip_gates": body.skip_gates, **body.input})

    result = job_store.submit_job(
        agent_name="daily_workflow",
        run_kind=AgentRunKind.DAILY_WORKFLOW,
        input_summary={"skip_gates": body.skip_gates},
        func=_run,
    )
    return idempotent(get_idempotency_key(request), JobCreate(**result))


@router.post("/{agent_name}/run", response_model=JobCreate, status_code=202)
def run_agent(
    agent_name: str,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    input: dict[str, Any] | None = None,
):
    if agent_name not in AGENT_NAMES:
        raise not_found("AGENT_NOT_FOUND", f"Agent '{agent_name}' is not registered.")

    def _run(db: Session, run):
        return dispatch(agent_name, db, run, input or {})

    result = job_store.submit_job(
        agent_name=agent_name,
        run_kind=_AGENT_RUN_KINDS.get(agent_name, AgentRunKind.MANUAL),
        input_summary=input or {},
        func=_run,
    )
    return idempotent(get_idempotency_key(request), JobCreate(**result))


@router.get("/runs", response_model=Page[AgentRunOut])
def list_runs(
    db: Annotated[Session, Depends(get_db)],
    paging: Annotated[dict, Depends(pagination_params)],
    agent_name: str | None = None,
    status: JobStatus | None = None,
):
    q = db.query(AgentRun).order_by(AgentRun.created_at.desc())
    if agent_name:
        q = q.filter_by(agent_name=agent_name)
    if status is not None:
        # JobStatus <-> AgentStatus is 1:1; filter in the DB so `total` is exact.
        agent_status = job_store.job_status_to_agent_status(status)
        q = q.filter(AgentRun.status == agent_status)
    total = q.count()
    page, page_size = paging["page"], paging["page_size"]
    rows = q.offset((page - 1) * page_size).limit(page_size).all()
    items = [AgentRunOut.model_validate(r) for r in rows]
    return paginate(items, page=page, page_size=page_size, total=total)


@router.get("/runs/{run_id}", response_model=AgentRunOut)
def get_run(run_id: str, db: Annotated[Session, Depends(get_db)]):
    row = db.query(AgentRun).filter_by(id=run_id).one_or_none()
    if row is None:
        raise not_found("RUN_NOT_FOUND", f"Agent run {run_id} not found.")
    return AgentRunOut.model_validate(row)


@router.get("/runs/{run_id}/logs", response_model=list[AgentLogOut])
def run_logs(run_id: str, db: Annotated[Session, Depends(get_db)]):
    row = db.query(AgentRun).filter_by(id=run_id).one_or_none()
    if row is None:
        raise not_found("RUN_NOT_FOUND", f"Agent run {run_id} not found.")
    logs = (
        db.query(AgentLog)
        .filter_by(agent_run_id=run_id)
        .order_by(AgentLog.logged_at.asc())
        .limit(500)
        .all()
    )
    return [AgentLogOut.model_validate(log) for log in logs]


@router.get("/jobs", response_model=Page[JobOut])
def list_jobs(
    db: Annotated[Session, Depends(get_db)],
    paging: Annotated[dict, Depends(pagination_params)],
    status: JobStatus | None = None,
):
    items, total = job_store.list_jobs(
        db, status=status, page=paging["page"], page_size=paging["page_size"]
    )
    return paginate(
        [_job_to_out(j) for j in items],
        page=paging["page"],
        page_size=paging["page_size"],
        total=total,
    )


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: str, db: Annotated[Session, Depends(get_db)]):
    job = job_store.get_job(job_id)
    if job is None:
        raise not_found("JOB_NOT_FOUND", f"Job {job_id} not found.")
    return _job_to_out(job)


@router.post("/jobs/{job_id}/cancel", response_model=JobOut)
def cancel_job(job_id: str, db: Annotated[Session, Depends(get_db)]):
    try:
        payload = job_store.cancel_job(db, job_id)
    except KeyError:
        raise not_found("JOB_NOT_FOUND", f"Job {job_id} not found.") from None
    except ValueError:
        raise bad_request(
            "CANCEL_FAILED", f"Job {job_id} is terminal and cannot be cancelled."
        ) from None
    return _job_to_out(payload)


@router.get("/dead-letters", response_model=list[JobOut])
def dead_letters(db: Annotated[Session, Depends(get_db)]):
    return [_job_to_out(j) for j in job_store.dead_letters(db)]


@router.post("/dead-letters/{job_id}/retry", response_model=JobCreate)
def retry_dead_letter(job_id: str, db: Annotated[Session, Depends(get_db)]):
    result = job_store.retry_job(db, job_id)
    if result is None:
        raise not_found(
            "DEAD_LETTER_NOT_FOUND",
            f"Dead-letter job {job_id} not found (or is not FAILED).",
        )
    return JobCreate(**result)
