"""Compliance & originality models: compliance_rules (versioned), compliance_checks
(evidentiary), similarity_records (docs: 08 §8, 17, 18).

Rules are retired via effective_to, never deleted. Checks never default to PASS.
Similarity records describe clusters, never individual artists.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditTimestampsMixin, Base, UUIDPrimaryKeyMixin, utcnow
from app.schemas.enums import (
    ComplianceCheckType,
    ComplianceResult,
    DataProvenance,
    RiskLevel,
    RuleSeverity,
)


def _prov_enum() -> SAEnum:
    return SAEnum(DataProvenance, native_enum=False, length=16)


class ComplianceRule(Base, UUIDPrimaryKeyMixin, AuditTimestampsMixin):
    """Versioned screening rule (docs: 08 §8.1). One row per (rule_key, version).

    `applies_to` is a JSON list of ComplianceCheckType values — many of the 28
    canonical rules apply to multiple check types, and a JSON list preserves
    exactly one row per rule (no rule duplication). Seed: 28 rules v1.0.0
    (SEED_PLAN.md §4). Rules retired via effective_to.
    """

    __tablename__ = "compliance_rules"

    rule_key: Mapped[str] = mapped_column(String(120), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[RuleSeverity] = mapped_column(
        SAEnum(RuleSeverity, native_enum=False, length=8), nullable=False
    )
    rule_config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    applies_to: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list
    )  # list of ComplianceCheckType values
    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        UniqueConstraint("rule_key", "version", name="uq_compliance_rules_key_version"),
    )


class ComplianceCheck(Base, UUIDPrimaryKeyMixin, AuditTimestampsMixin):
    """Record of one screening execution (docs: 08 §8.2).

    Exactly one subject FK set per row (enforced at API layer). Evidentiary:
    never deleted, never defaults to PASS.
    """

    __tablename__ = "compliance_checks"

    check_type: Mapped[ComplianceCheckType] = mapped_column(
        SAEnum(ComplianceCheckType, native_enum=False, length=24), nullable=False
    )
    prompt_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    prompt_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    asset_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    asset_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    image_idea_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    video_idea_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    metadata_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    production_queue_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    result: Mapped[ComplianceResult] = mapped_column(
        SAEnum(ComplianceResult, native_enum=False, length=16), nullable=False
    )
    risk_level: Mapped[RiskLevel] = mapped_column(
        SAEnum(RiskLevel, native_enum=False, length=16), nullable=False
    )
    findings: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    review_decision: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    agent_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


class SimilarityRecord(Base, UUIDPrimaryKeyMixin, AuditTimestampsMixin):
    """Originality comparison vs a market cluster (docs: 08 §8.3, 17).

    compared_cluster_label is descriptive (niche/motif/composition family) —
    never identifies individual artists.
    """

    __tablename__ = "similarity_records"

    compliance_check_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    subject_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    image_idea_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    video_idea_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    prompt_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    asset_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    compared_cluster_label: Mapped[str] = mapped_column(String(200), nullable=False)
    similarity_score: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    risk_level: Mapped[RiskLevel] = mapped_column(
        SAEnum(RiskLevel, native_enum=False, length=16), nullable=False
    )
    cluster_sample_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    differentiators: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_provenance: Mapped[DataProvenance] = mapped_column(_prov_enum(), nullable=False)
    agent_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
