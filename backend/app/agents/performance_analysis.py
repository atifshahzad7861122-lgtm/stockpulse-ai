"""performance_analysis agent — KPI digest (never invents Adobe sales data)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.agents import _base
from app.models.analytics import PerformanceMetric
from app.models.platform import AgentRun
from app.models.production import SubmissionRecord


def run(db: Session, run: AgentRun, input: dict[str, Any]) -> dict[str, Any]:
    metrics = (
        db.query(PerformanceMetric).order_by(PerformanceMetric.created_at.desc()).limit(200).all()
    )
    submissions = db.query(SubmissionRecord).all()

    by_provenance: dict[str, int] = {}
    for m in metrics:
        key = m.data_provenance.value if m.data_provenance else "UNKNOWN"
        by_provenance[key] = by_provenance.get(key, 0) + 1

    submitted = len(submissions)
    accepted = sum(1 for s in submissions if (s.status or "").upper() == "ACCEPTED")
    acceptance_rate = round(accepted / submitted, 3) if submitted else None

    sample_warning = None
    if submitted < 30:
        sample_warning = (
            f"Small sample (n={submitted} submissions): acceptance_rate is directional only."
        )
        _base.warn(db, run, sample_warning)

    digest = {
        "metrics_analyzed": len(metrics),
        "metrics_by_provenance": by_provenance,
        "submissions": submitted,
        "accepted": accepted,
        "acceptance_rate": acceptance_rate,
        "sample_warning": sample_warning,
        "generated_at": datetime.now().isoformat(),
        "provenance_notes": (
            "USER_PROVIDED/VERIFIED rows come only from the user's own dashboard imports. "
            "No Adobe sales numbers are invented; MOCK rows are labeled."
        ),
    }
    _base.info(db, run, f"Digest: {submitted} submissions, acceptance_rate={acceptance_rate}")
    digest["note"] = _base.MOCK_NOTE
    return digest
