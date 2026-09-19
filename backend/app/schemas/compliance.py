"""Compliance schemas (CONTRACT.md §5.7)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import MockLabeled
from app.schemas.enums import ComplianceCheckType, ComplianceResult, RiskLevel, RuleSeverity

SubjectKind = Literal["prompt", "asset", "image_idea", "video_idea", "metadata", "production_queue"]
ReviewDecision = Literal["accepted", "accepted_with_changes", "rejected"]


class ComplianceCheckCreate(BaseModel):
    check_type: ComplianceCheckType
    subject_kind: SubjectKind
    subject_id: str
    subject_version_id: str | None = None


class RuleFindingOut(BaseModel):
    check_id: str
    rule_key: str
    rule_version: str
    severity: str
    triggered: bool
    explanation: str
    matched_excerpt: str | None = None
    remediation: str | None = None


class ComplianceCheckOut(MockLabeled):
    model_config = ConfigDict(from_attributes=True)

    id: str
    check_type: ComplianceCheckType
    subject: dict[str, Any] = Field(default_factory=dict)
    result: ComplianceResult
    risk_level: RiskLevel
    findings: list[RuleFindingOut] = Field(default_factory=list)
    explanation: str
    rules_version: str
    review_decision: str | None = None
    reviewed_at: datetime | None = None
    agent_run_id: str | None = None
    created_at: datetime


class ComplianceReview(BaseModel):
    decision: ReviewDecision
    note: str | None = None


class ComplianceRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    rule_key: str
    version: int
    name: str
    description: str
    severity: RuleSeverity
    applies_to: list[str] = Field(default_factory=list)
    is_enabled: bool
    effective_from: datetime
    effective_to: datetime | None = None
    rule_config: dict[str, Any] = Field(default_factory=dict)
