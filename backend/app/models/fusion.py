"""Opportunity fusion score records (Phase 3, PERSONAL INTELLIGENCE).

One row per compute: the unified market+personal score with EVERY component
stored individually (full transparency), the evidence-grounded WHY text,
confidence breakdown, and per-input provenance. Append-only by design —
recompute writes a new row; GET returns the latest.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Numeric, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditTimestampsMixin, Base, UUIDPrimaryKeyMixin, utcnow
from app.schemas.enums import DataProvenance


def _prov_enum() -> SAEnum:
    return SAEnum(DataProvenance, native_enum=False, length=16)


class OpportunityFusionScore(Base, UUIDPrimaryKeyMixin, AuditTimestampsMixin):
    """Fused opportunity score (docs: backend/PHASE3_FORMULAS.md).

    ``opportunity_id`` is a logical reference to ``opportunities.id``
    (unenforced FK, codebase style). All component columns are 0–100;
    personal components are NULL when no private data exists (never faked).
    ``label`` ∈ FUSED | MARKET-ONLY. ``component_json`` records every input's
    value + provenance + source; ``confidence_factors_json`` records the
    confidence breakdown. ``explanation`` is the evidence-grounded WHY text.
    """

    __tablename__ = "opportunity_fusion_scores"

    opportunity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    unified_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)

    # --- market components (always present) ---
    market_opportunity: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    trend_momentum: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    commercial_potential: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    seasonality: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    saturation_risk: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    prediction_confidence: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)

    # --- personal components (NULL = no private data, never invented) ---
    personal_fit: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    personal_momentum: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    historical_performance: Mapped[float | None] = mapped_column(
        Numeric(5, 2), nullable=True
    )

    component_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)

    confidence_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    confidence_factors_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    label: Mapped[str] = mapped_column(String(16), nullable=False, default="FUSED")
    data_provenance: Mapped[DataProvenance] = mapped_column(_prov_enum(), nullable=False)

    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


__all__ = ["OpportunityFusionScore"]
