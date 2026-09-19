"""trend_research agent — collect + normalize trend data into trend_snapshots."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.agents import _base
from app.models.intelligence import TrendSnapshot, TrendSource
from app.models.platform import AgentRun
from app.providers.providers import get_trend_provider


def run(db: Session, run: AgentRun, input: dict[str, Any]) -> dict[str, Any]:
    topics: list[str] = input.get("topics") or []
    if not topics:
        # Default: derive topics from micro-niche names (first N).
        from app.models.taxonomy import MicroNiche

        topics = [
            r[0]
            for r in db.query(MicroNiche.name)
            .order_by(MicroNiche.name)
            .limit(int(input.get("topic_limit", 10)))
            .all()
        ]
    provider = get_trend_provider()
    _base.info(db, run, f"Fetching {len(topics)} topics via {provider.name}")
    payloads = provider.fetch_topics(topics, window_days=int(input.get("window_days", 7)))

    source = db.query(TrendSource).filter_by(is_active=True).first()
    source_id = source.id if source else "mock"
    written = 0
    for p in payloads:
        payload = {
            "topic": p.topic,
            "w0_mean": p.value_w0,
            "w1_mean": p.value_w1,
            "baseline_mean": p.value_baseline,
            "keyword_tvs": list(p.keyword_tvs),
            "source_z_scores": list(p.source_z_scores),
            "source_id": p.source_id,
            "mock": True,
        }
        payload_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        exists = (
            db.query(TrendSnapshot)
            .filter_by(trend_source_id=source_id, payload_hash=payload_hash)
            .one_or_none()
        )
        if exists is None:
            db.add(
                TrendSnapshot(
                    trend_source_id=source_id,
                    captured_at=datetime.now(UTC),
                    payload=payload,
                    payload_hash=payload_hash,
                    agent_run_id=run.id,
                )
            )
            written += 1
    db.commit()
    _base.info(db, run, f"Wrote {written} new snapshots ({len(payloads) - written} deduped)")
    return {
        "topics": len(payloads),
        "snapshots_written": written,
        "provider": provider.name,
        "provenance": "MOCK",
        "note": _base.MOCK_NOTE,
    }
