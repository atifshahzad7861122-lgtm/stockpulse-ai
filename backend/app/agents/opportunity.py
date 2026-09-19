"""opportunity agent — generate scored, gated opportunities (min 3 topics)."""

from __future__ import annotations

import hashlib
from typing import Any

from sqlalchemy.orm import Session

from app.agents import _base
from app.engines.opportunities import (
    MAX_OPPORTUNITIES_PER_RUN,
    NicheIntelligence,
    generate_opportunities,
)
from app.engines.trends import TrendAnalysis
from app.models.intelligence import Opportunity
from app.models.platform import AgentRun
from app.models.taxonomy import MicroNiche
from app.schemas.enums import DataProvenance


def _get_setting(db: Session, key: str, default: Any) -> Any:
    from app.models.settings import Setting

    row = db.query(Setting).filter_by(key=key).one_or_none()
    if row is None:
        return default
    return (row.value or {}).get("value", default)


def _analyses_for(niche_name: str, h: float) -> tuple[TrendAnalysis, ...]:
    """3 demo topic analyses per niche (MOCK) — the engine needs ≥3 topics."""

    def _make(i: int) -> TrendAnalysis:
        hh = (h + i * 0.13) % 1.0
        return TrendAnalysis(
            topic=f"{niche_name} topic {i + 1}",
            trend_velocity=round(-1 + 3 * hh, 3),
            search_growth=round(-1 + 3 * hh, 3),
            keyword_momentum=round(-1 + 3 * hh, 3),
            market_consistency=round(0.5 + 0.4 * hh, 3),
            seasonality=round(0.3 + 0.5 * hh, 3),
            velocity_flag="up",
            momentum_flag="steady",
            seasonality_flag="neutral",
            explanation=f"MOCK topic analysis for {niche_name}.",
            provenance="MOCK",
        )

    return (_make(0), _make(1), _make(2))


def run(db: Session, run: AgentRun, input: dict[str, Any]) -> dict[str, Any]:
    niche_rows = (
        db.query(MicroNiche)
        .order_by(MicroNiche.name)
        .limit(int(input.get("topic_limit", MAX_OPPORTUNITIES_PER_RUN)))
        .all()
    )
    niches: list[NicheIntelligence] = []
    for n in niche_rows:
        h = int(hashlib.sha256(n.name.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
        niches.append(
            NicheIntelligence(
                micro_niche_id=n.id,
                micro_niche_name=n.name,
                analyses=_analyses_for(n.name, h),
                commercial_relevance=round(0.4 + 0.5 * h, 3),
                content_demand=round(0.4 + 0.5 * (1 - h), 3),
                content_saturation=round(0.3 + 0.5 * h, 3),
                competition=round(0.3 + 0.5 * h, 3),
                source_freshness=0.9,
                n_sources=5,
                provenance="MOCK",
            )
        )
    min_score = float(input.get("min_score", _get_setting(db, "opportunity.min_score", 55)))
    min_confidence = float(
        input.get("min_confidence", _get_setting(db, "opportunity.min_confidence", 0.5))
    )

    generated = [
        g
        for g in generate_opportunities(niches)
        if g.opportunity_score >= min_score and g.confidence >= min_confidence
    ]
    _base.info(db, run, f"Generated {len(generated)} gated opportunities from {len(niches)} niches")

    created = 0
    for g in generated:
        dup = db.query(Opportunity).filter(Opportunity.title == g.title).one_or_none()
        if dup is not None:
            continue
        db.add(
            Opportunity(
                micro_niche_id=g.micro_niche_id,
                title=g.title,
                summary=g.summary,
                opportunity_score=g.opportunity_score,
                confidence=g.confidence,
                demand_evidence=list(g.demand_evidence),
                risk_notes=g.risk_notes,
                data_provenance=DataProvenance.MOCK,
                status="new",
                priority=0,
                agent_run_id=run.id,
            )
        )
        created += 1
    db.commit()
    return {
        "topics_evaluated": len(niches),
        "opportunities_generated": len(generated),
        "opportunities_created": created,
        "min_score": min_score,
        "min_confidence": min_confidence,
        "provenance": "MOCK",
        "note": "New opportunities require human approval before ideation. " + _base.MOCK_NOTE,
    }
