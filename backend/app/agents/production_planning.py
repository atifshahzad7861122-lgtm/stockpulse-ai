"""production_planning agent — queue priority scores + ordering suggestions."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.agents import _base
from app.engines.queue import deadline_state
from app.engines.scoring import priority_score
from app.models.platform import AgentRun
from app.models.production import ProductionQueue
from app.schemas.enums import ProductionQueueStatus


def run(db: Session, run: AgentRun, input: dict[str, Any]) -> dict[str, Any]:
    items = (
        db.query(ProductionQueue)
        .filter(
            ProductionQueue.status.notin_(
                [ProductionQueueStatus.ARCHIVED, ProductionQueueStatus.SUBMITTED]
            )
        )
        .all()
    )
    suggestions: list[dict[str, Any]] = []
    for item in items:
        import hashlib

        h = int(hashlib.sha256(item.id.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
        from datetime import date

        days_remaining = None
        if item.target_date:
            days_remaining = (item.target_date - date.today()).days
        score = priority_score(
            trend_momentum=round(40 + 50 * h, 2),
            days_remaining=days_remaining,
            predicted_value=round(40 + 50 * h, 2),
            priority_band=item.priority_band,
            rework_count=item.rework_count,
        )
        suggestions.append(
            {
                "queue_id": item.id,
                "title": item.title,
                "status": item.status.value,
                "priority_band": item.priority_band,
                "priority_score": score.score,
                "components": score.components,
                "deadline_state": deadline_state(
                    item.target_date.isoformat() if item.target_date else None
                ),
            }
        )
    suggestions.sort(key=lambda s: s["priority_score"], reverse=True)
    _base.info(db, run, f"Scored {len(suggestions)} queue items")
    return {
        "items_scored": len(suggestions),
        "ordering": [s["queue_id"] for s in suggestions],
        "top": suggestions[:5],
        "note": "Suggestions only — the agent never transitions queue states itself. "
        + _base.MOCK_NOTE,
    }
