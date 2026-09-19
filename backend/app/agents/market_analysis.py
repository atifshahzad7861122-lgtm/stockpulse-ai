"""market_analysis agent — W0/W1/baseline analysis → market_metrics."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.agents import _base
from app.engines.scoring import norm100, trend_score
from app.engines.trends import WindowValues, analyze_topic, keyword_momentum
from app.models.intelligence import MarketMetric, TrendSnapshot
from app.models.platform import AgentRun
from app.models.taxonomy import MicroNiche
from app.schemas.enums import DataProvenance


def run(db: Session, run: AgentRun, input: dict[str, Any]) -> dict[str, Any]:
    days = int(input.get("window_days", 7))
    since = datetime.now(UTC) - timedelta(days=days + 1)
    snapshots = (
        db.query(TrendSnapshot)
        .filter(TrendSnapshot.captured_at >= since)
        .order_by(TrendSnapshot.captured_at.desc())
        .all()
    )
    _base.info(db, run, f"Analyzing {len(snapshots)} snapshots from the last {days}d")

    by_topic: dict[str, dict] = {}
    for s in snapshots:
        payload = s.payload or {}
        topic = payload.get("topic")
        if topic and topic not in by_topic:
            by_topic[topic] = payload  # latest per topic

    analyzed = 0
    for topic, payload in by_topic.items():
        windows = WindowValues(
            w0=float(payload.get("w0_mean", 0)),
            w1=float(payload.get("w1_mean", 0)),
            baseline=float(payload.get("baseline_mean", 0) or 1),
        )
        keyword_tvs = list(payload.get("keyword_tvs", ()))
        analysis = analyze_topic(
            topic=topic,
            windows=windows,
            keyword_tvs=keyword_tvs,
            source_z_scores=list(payload.get("source_z_scores", ())),
            seasonality=float(payload.get("seasonal_event_strength", 0.4)),
            provenance="MOCK",
        )
        score = trend_score(
            tv_100=norm100(analysis.trend_velocity, -1, 3),
            sg_100=norm100(analysis.search_growth, -1, 3),
            km_100=norm100(analysis.keyword_momentum, -1, 3),
            eg_100=50.0,  # mock data carries no engagement signals; neutral
            seasonality=analysis.seasonality,
        ).score
        niche = db.query(MicroNiche).filter(MicroNiche.name == topic).one_or_none()
        if niche is None:
            continue
        today = date.today()
        period_start = today - timedelta(days=days)
        exists = (
            db.query(MarketMetric)
            .filter_by(micro_niche_id=niche.id, period_start=period_start, period_end=today)
            .one_or_none()
        )
        if exists is None:
            db.add(
                MarketMetric(
                    micro_niche_id=niche.id,
                    period_start=period_start,
                    period_end=today,
                    demand_index=score,
                    competition_index=round(100 - score, 2),
                    data_provenance=DataProvenance.MOCK,
                    agent_run_id=run.id,
                    notes=(
                        f"MOCK analysis: velocity={analysis.trend_velocity}, "
                        f"momentum={analysis.keyword_momentum}, "
                        f"{keyword_momentum(keyword_tvs)}."
                    ),
                )
            )
            analyzed += 1
    db.commit()
    _base.info(db, run, f"Analyzed {len(by_topic)} topics, wrote {analyzed} market metrics")
    return {
        "topics_analyzed": len(by_topic),
        "metrics_written": analyzed,
        "provenance": "MOCK",
        "note": _base.MOCK_NOTE,
    }
