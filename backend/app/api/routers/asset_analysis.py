"""Asset analyzer API (FINAL MASTER SPEC §21–32).

POST /generate submits a background job (same pattern as /api/prompts/generate):
the job calls the EXISTING Gemini integration, which extracts commercial
attributes and produces an ORIGINAL concept + PROMPT A / B / C + negative
prompt as TEXT. No image or video is generated; nothing is uploaded.

GET /by-opportunity/{id} returns the cached completed analysis when one
exists (prompt caching) so the user is not re-billed for the same analysis.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api import jobs
from app.api.deps import (
    check_rate_limit,
    get_db,
    get_idempotency_key,
    idempotent,
    not_found,
)
from app.models.intelligence import AssetAnalysis, Opportunity
from app.providers.providers import get_llm_provider
from app.schemas.agents import JobCreate
from app.schemas.asset_analysis import AssetAnalysisGenerate, AssetAnalysisOut
from app.schemas.enums import AgentRunKind
from app.services import asset_analyzer

router = APIRouter(prefix="/asset-analysis", tags=["asset-analysis"])


def _out(row: AssetAnalysis) -> AssetAnalysisOut:
    ca = row.commercial_analysis or {}
    return AssetAnalysisOut(
        id=row.id,
        opportunity_id=row.opportunity_id,
        asset_type=row.asset_type,
        status=row.status,
        market_context=row.market_context or {},
        commercial_analysis={
            k: ca.get(k)
            for k in (
                "topic", "category", "micro_niche", "primary_keywords",
                "secondary_keywords", "commercial_use_case", "subject",
                "environment", "composition", "visual_characteristics",
                "content_type",
            )
        },
        original_concept=row.original_concept,
        prompt_a=row.prompt_a,
        prompt_b=row.prompt_b,
        prompt_c=row.prompt_c,
        negative_prompt=row.negative_prompt,
        model=row.model,
        provenance=row.data_provenance.value if row.data_provenance else "THIRD_PARTY",
        error_message=row.error_message,
        created_at=row.created_at,
    )


@router.post("/generate", response_model=JobCreate, status_code=202)
def generate_analysis(
    request: Request,
    body: AssetAnalysisGenerate,
    db: Annotated[Session, Depends(get_db)],
):
    check_rate_limit("asset-analysis:generate", max_calls=10, per_seconds=3600)
    opp = db.query(Opportunity).filter_by(id=body.opportunity_id).one_or_none()
    if opp is None:
        raise not_found("OPPORTUNITY_NOT_FOUND", f"Opportunity {body.opportunity_id} not found.")
    provider = get_llm_provider()
    if getattr(provider, "name", "") == "mock":
        # Refuse rather than present mock output as a real analysis.
        _mock_refused()
    # Cached analysis exists → return it directly, no new job.
    cached = asset_analyzer.get_cached_analysis(db, body.opportunity_id, body.asset_type)
    if cached is not None:
        def _cached(db: Session, run):
            return {"analysis_id": cached.id, "cached": True}

        result = jobs.submit_job(
            agent_name="asset_analysis",
            run_kind=AgentRunKind.ASSET_ANALYSIS,
            input_summary={
                "opportunity_id": body.opportunity_id,
                "asset_type": body.asset_type,
                "cached": True,
            },
            func=_cached,
        )
        return idempotent(get_idempotency_key(request), JobCreate(**result))

    def _run(db: Session, run):
        row = asset_analyzer.generate(db, body.opportunity_id, body.asset_type)
        return {"analysis_id": row.id, "cached": False}

    result = jobs.submit_job(
        agent_name="asset_analysis",
        run_kind=AgentRunKind.ASSET_ANALYSIS,
        input_summary={"opportunity_id": body.opportunity_id, "asset_type": body.asset_type},
        func=_run,
    )
    return idempotent(get_idempotency_key(request), JobCreate(**result))


def _mock_refused():
    from fastapi import HTTPException

    raise HTTPException(
        status_code=400,
        detail={
            "code": "LLM_NOT_CONFIGURED",
            "message": (
                "The LLM provider is not configured (mock). Set "
                "STOCKPULSE_LLM_PROVIDER=gemini with a valid GEMINI_API_KEY "
                "to generate original prompts."
            ),
        },
    )


@router.get("/by-opportunity/{opportunity_id}", response_model=AssetAnalysisOut)
def by_opportunity(
    opportunity_id: str,
    db: Annotated[Session, Depends(get_db)],
    asset_type: Annotated[str, Query(pattern="^(image|video)$")] = "image",
):
    row = asset_analyzer.get_cached_analysis(db, opportunity_id, asset_type)
    if row is None:
        raise not_found(
            "ANALYSIS_NOT_FOUND",
            f"No completed {asset_type} analysis for opportunity {opportunity_id}.",
        )
    return _out(row)


@router.get("/{analysis_id}", response_model=AssetAnalysisOut)
def get_analysis(analysis_id: str, db: Annotated[Session, Depends(get_db)]):
    row = db.query(AssetAnalysis).filter_by(id=analysis_id).one_or_none()
    if row is None:
        raise not_found("ANALYSIS_NOT_FOUND", f"Analysis {analysis_id} not found.")
    return _out(row)
