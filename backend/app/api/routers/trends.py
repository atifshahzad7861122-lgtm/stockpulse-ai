"""Trend discovery (CONTRACT.md §5.2)."""

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
    paginate,
    pagination_params,
)
from app.engines.scoring import norm100, trend_score
from app.engines.trends import keyword_momentum, search_growth, trend_velocity
from app.models.intelligence import TrendSignal, TrendSnapshot
from app.models.taxonomy import Category, MicroNiche, Subcategory
from app.schemas.agents import JobCreate
from app.schemas.common import Page
from app.schemas.enums import AgentRunKind, DataProvenance
from app.schemas.trends import SignalBreakdown, TrendDetail, TrendItem
from app.services.dev_mode import is_dev_mode

router = APIRouter(prefix="/trends", tags=["trends"])


def _score_for(payload: dict) -> float:
    """Canonical trend score from a snapshot payload (0–100 components)."""
    w0 = float(payload.get("w0_mean", 0))
    w1 = float(payload.get("w1_mean", 0))
    baseline = float(payload.get("baseline_mean", 0) or 1)
    return trend_score(
        tv_100=norm100(trend_velocity(w0, w1), -1, 3),
        sg_100=norm100(search_growth(w0, baseline), -1, 3),
        km_100=norm100(keyword_momentum(list(payload.get("keyword_tvs", []))), -1, 3),
        eg_100=50.0,  # mock data carries no engagement signals; neutral
        seasonality=float(payload.get("seasonal_event_strength", 0.4)),
    ).score


def _categories_for(db: Session, topic: str) -> list[str]:
    niche = db.query(MicroNiche).filter(MicroNiche.name == topic).one_or_none()
    if niche is None:
        return []
    sub = db.query(Subcategory).filter_by(id=niche.subcategory_id).one_or_none()
    if sub is None:
        return []
    cat = db.query(Category).filter_by(id=sub.category_id).one_or_none()
    return [cat.slug] if cat else []


def _provenance_for(payload: dict) -> DataProvenance:
    """Derive display provenance from the snapshot payload (written by the
    Phase 2 store layer). Legacy demo payloads carry no provenance key and
    default to MOCK."""
    raw = payload.get("provenance")
    try:
        return DataProvenance(raw) if raw else DataProvenance.MOCK
    except ValueError:
        return DataProvenance.MOCK


def _to_item(db: Session, snapshot: TrendSnapshot, window: str = "7d") -> TrendItem:
    payload = snapshot.payload or {}
    topic = payload.get("topic", "unknown")
    provenance = _provenance_for(payload)
    return TrendItem(
        id=snapshot.id,
        title=topic,
        score=_score_for(payload),
        window=window,  # type: ignore[arg-type]
        provenance=provenance,
        mock=provenance == DataProvenance.MOCK,
        categories=_categories_for(db, topic),
        signal_count=(
            db.query(TrendSignal)
            .filter(TrendSignal.trend_snapshot_id == snapshot.id)
            .count()
        ),
        created_at=snapshot.created_at,
        updated_at=snapshot.created_at,
    )


@router.get("", response_model=Page[TrendItem])
def list_trends(
    db: Annotated[Session, Depends(get_db)],
    paging: Annotated[dict, Depends(pagination_params)],
    category: Annotated[str | None, Query(description="Category slug filter")] = None,
    window: Annotated[str, Query(pattern="^(7d|30d|90d)$")] = "7d",
    min_score: Annotated[float, Query(ge=0, le=100)] = 0,
    sort: Annotated[str, Query(pattern="^(-score|velocity)$")] = "-score",
):
    snapshots = db.query(TrendSnapshot).order_by(TrendSnapshot.captured_at.desc()).limit(500).all()
    # Latest snapshot per topic.
    latest: dict[str, TrendSnapshot] = {}
    for s in snapshots:
        topic = (s.payload or {}).get("topic")
        if topic and topic not in latest:
            latest[topic] = s
    items = [_to_item(db, s, window) for s in latest.values()]
    if category:
        items = [i for i in items if category in i.categories]
    # Phase 2: MOCK/demo rows stop driving intelligence unless dev mode is on.
    if not is_dev_mode(db):
        items = [i for i in items if i.provenance != DataProvenance.MOCK]
    items = [i for i in items if i.score >= min_score]
    items.sort(key=lambda i: i.score, reverse=(sort == "-score"))
    total = len(items)
    page, page_size = paging["page"], paging["page_size"]
    return paginate(
        items[(page - 1) * page_size : page * page_size],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/{trend_id}", response_model=TrendDetail)
def trend_detail(trend_id: str, db: Annotated[Session, Depends(get_db)]):
    snapshot = db.query(TrendSnapshot).filter_by(id=trend_id).one_or_none()
    if snapshot is None:
        raise not_found("TREND_NOT_FOUND", f"Trend {trend_id} not found.")
    item = _to_item(db, snapshot)
    payload = snapshot.payload or {}
    topic = payload.get("topic", "")
    # Signals are linked to their snapshot by FK at collect time (see
    # adapters/store.py); query them the same way _to_item does so the
    # detail view agrees with the list's signal_count.
    signals_q = db.query(TrendSignal).filter(TrendSignal.trend_snapshot_id == snapshot.id)
    # Phase 2: MOCK/demo rows stop driving intelligence unless dev mode is on.
    if not is_dev_mode(db):
        signals_q = signals_q.filter(TrendSignal.data_provenance != DataProvenance.MOCK)
    signals = (
        signals_q.order_by(TrendSignal.observed_at.desc()).limit(20).all() if topic else []
    )
    return TrendDetail(
        **item.model_dump(),
        signals=[
            SignalBreakdown(
                signal_name=s.signal_name,
                metric_name=s.metric_name,
                metric_value=float(s.metric_value) if s.metric_value is not None else None,
                metric_unit=s.metric_unit,
                provenance=s.data_provenance,
                mock=s.data_provenance == DataProvenance.MOCK,
                confidence=float(s.confidence) if s.confidence is not None else None,
                observed_at=s.observed_at,
            )
            for s in signals
        ],
        analysis={
            "w0_mean": payload.get("w0_mean"),
            "w1_mean": payload.get("w1_mean"),
            "baseline_mean": payload.get("baseline_mean"),
            "keyword_tvs": payload.get("keyword_tvs", []),
            "mock": item.mock,
            "note": (
                "Demo values — deterministic mock, not real Adobe data."
                if item.mock
                else f"Collected from {len(signals)} third-party signal(s)."
            ),
        },
    )


@router.get("/{trend_id}/signals", response_model=list[SignalBreakdown])
def trend_signals(trend_id: str, db: Annotated[Session, Depends(get_db)]):
    detail = trend_detail(trend_id, db)
    return detail.signals


@router.post("/refresh", response_model=JobCreate, status_code=202)
def refresh_trends(request: Request, db: Annotated[Session, Depends(get_db)]):
    check_rate_limit("trends:refresh", max_calls=5, per_seconds=3600)
    from app.agents.dispatcher import dispatch

    def _run(db: Session, run):
        out1 = dispatch("trend_research", db, run, {})
        out2 = dispatch("market_analysis", db, run, {})
        return {"trend_research": out1, "market_analysis": out2}

    result = jobs.submit_job(
        agent_name="trend_research",
        run_kind=AgentRunKind.TREND_INGEST,
        input_summary={"trigger": "manual refresh"},
        func=_run,
    )
    return idempotent(get_idempotency_key(request), JobCreate(**result))
