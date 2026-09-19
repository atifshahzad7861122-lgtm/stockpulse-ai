"""Canonical enums (docs: 08_DATABASE_SCHEMA §2). Values are UPPER_SNAKE_CASE.

API transport: enums serialize as their string values. Production-queue
transitions T01–T29 (docs: 20_PRODUCTION_PIPELINE §5) are in
ALLOWED_QUEUE_TRANSITIONS below; anything not listed is rejected with
400 INVALID_TRANSITION.
"""

from __future__ import annotations

from enum import Enum


class StrEnum(str, Enum):
    def __str__(self) -> str:  # pragma: no cover
        return self.value


class DataProvenance(StrEnum):
    VERIFIED = "VERIFIED"
    USER_PROVIDED = "USER_PROVIDED"
    THIRD_PARTY = "THIRD_PARTY"
    ESTIMATED = "ESTIMATED"
    PREDICTED = "PREDICTED"
    MOCK = "MOCK"  # contract extension: demo/placeholder data (never real)


class SourceStatus(StrEnum):
    """Phase 2 source health (PHASE2_DESIGN.md §1; API §5 exposes identically)."""

    NOT_CHECKED = "NOT_CHECKED"
    AVAILABLE = "AVAILABLE"
    CONFIGURED = "CONFIGURED"
    NEEDS_AUTH = "NEEDS_AUTH"
    UNAVAILABLE = "UNAVAILABLE"
    TEMP_FAILING = "TEMP_FAILING"


class ProductionQueueStatus(StrEnum):
    DISCOVERED = "DISCOVERED"
    ANALYZING = "ANALYZING"
    IDEA_READY = "IDEA_READY"
    PROMPT_READY = "PROMPT_READY"
    APPROVED = "APPROVED"
    IN_PRODUCTION = "IN_PRODUCTION"
    QUALITY_CHECK = "QUALITY_CHECK"
    COMPLIANCE_REVIEW = "COMPLIANCE_REVIEW"
    READY_TO_UPLOAD = "READY_TO_UPLOAD"
    SUBMITTED = "SUBMITTED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    ARCHIVED = "ARCHIVED"


# Legal transitions docs/20 §5 (T01–T29). Self-loops model regenerate/edit actions.
ALLOWED_QUEUE_TRANSITIONS: dict[ProductionQueueStatus, tuple[ProductionQueueStatus, ...]] = {
    ProductionQueueStatus.DISCOVERED: (
        ProductionQueueStatus.ANALYZING,  # T01
        ProductionQueueStatus.ARCHIVED,  # T02
    ),
    ProductionQueueStatus.ANALYZING: (
        ProductionQueueStatus.IDEA_READY,  # T03
        ProductionQueueStatus.ARCHIVED,  # T04
    ),
    ProductionQueueStatus.IDEA_READY: (
        ProductionQueueStatus.PROMPT_READY,  # T05
        ProductionQueueStatus.IDEA_READY,  # T06 regenerate
        ProductionQueueStatus.ARCHIVED,  # T07
    ),
    ProductionQueueStatus.PROMPT_READY: (
        ProductionQueueStatus.APPROVED,  # T08
        ProductionQueueStatus.PROMPT_READY,  # T09 edit
        ProductionQueueStatus.IDEA_READY,  # T10 new concept
        ProductionQueueStatus.ARCHIVED,  # T11
    ),
    ProductionQueueStatus.APPROVED: (
        ProductionQueueStatus.IN_PRODUCTION,  # T12
        ProductionQueueStatus.PROMPT_READY,  # T13 unfreeze
        ProductionQueueStatus.ARCHIVED,  # T14
    ),
    ProductionQueueStatus.IN_PRODUCTION: (ProductionQueueStatus.QUALITY_CHECK,),  # T15
    ProductionQueueStatus.QUALITY_CHECK: (
        ProductionQueueStatus.COMPLIANCE_REVIEW,  # T16
        ProductionQueueStatus.IN_PRODUCTION,  # T17 rework
    ),
    ProductionQueueStatus.COMPLIANCE_REVIEW: (
        ProductionQueueStatus.READY_TO_UPLOAD,  # T18 PASS
        ProductionQueueStatus.IN_PRODUCTION,  # T19 REVIEW remediable
        ProductionQueueStatus.ARCHIVED,  # T20 HIGH_RISK abandon
    ),
    ProductionQueueStatus.READY_TO_UPLOAD: (
        ProductionQueueStatus.SUBMITTED,  # T21
        ProductionQueueStatus.IN_PRODUCTION,  # T22 late issue
        ProductionQueueStatus.ARCHIVED,  # T23
    ),
    ProductionQueueStatus.SUBMITTED: (
        ProductionQueueStatus.ACCEPTED,  # T24
        ProductionQueueStatus.REJECTED,  # T25
    ),
    ProductionQueueStatus.ACCEPTED: (ProductionQueueStatus.ARCHIVED,),  # T28
    ProductionQueueStatus.REJECTED: (
        ProductionQueueStatus.IN_PRODUCTION,  # T26 rework
        ProductionQueueStatus.ARCHIVED,  # T27
    ),
    ProductionQueueStatus.ARCHIVED: (
        ProductionQueueStatus.DISCOVERED,  # T29 unarchive (explicit user action)
    ),
}


class ComplianceResult(StrEnum):
    PASS = "PASS"
    REVIEW = "REVIEW"
    HIGH_RISK = "HIGH_RISK"


class ComplianceCheckType(StrEnum):
    PROMPT_SCREEN = "PROMPT_SCREEN"
    ASSET_SCREEN = "ASSET_SCREEN"
    SIMILARITY_SCAN = "SIMILARITY_SCAN"
    METADATA_SCREEN = "METADATA_SCREEN"


class RuleSeverity(StrEnum):
    INFO = "INFO"
    WARN = "WARN"
    BLOCK = "BLOCK"


class IdeaStatus(StrEnum):
    DRAFT = "DRAFT"
    READY = "READY"
    IN_QUEUE = "IN_QUEUE"
    ARCHIVED = "ARCHIVED"
    DISCARDED = "DISCARDED"


class PromptStatus(StrEnum):
    DRAFT = "DRAFT"
    READY = "READY"
    APPROVED = "APPROVED"
    ARCHIVED = "ARCHIVED"


class AssetType(StrEnum):
    IMAGE = "IMAGE"
    VIDEO = "VIDEO"


class TrendLabel(StrEnum):
    """Personal performance momentum label (Phase 3, backend).

    Thresholds are owned by app.services.personal_performance
    (MOMENTUM_GROWING_MIN / MOMENTUM_DECLINING_MAX); this enum is just the
    label vocabulary: >+15% → growing, <−15% → declining, else stable.
    """

    GROWING = "growing"
    STABLE = "stable"
    DECLINING = "declining"


class AssetStatus(StrEnum):
    DRAFT = "DRAFT"
    IN_REVIEW = "IN_REVIEW"
    FINAL = "FINAL"
    REJECTED = "REJECTED"


class PredictionHorizon(StrEnum):
    H30_DAYS = "H30_DAYS"
    H90_DAYS = "H90_DAYS"
    H6_MONTHS = "H6_MONTHS"
    H12_MONTHS = "H12_MONTHS"


class PredictedDirection(StrEnum):
    UP = "up"
    FLAT = "flat"
    DOWN = "down"


class RiskLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class SubmissionStatus(StrEnum):
    PLANNED = "PLANNED"
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class NotificationType(StrEnum):
    BRIEFING_READY = "BRIEFING_READY"
    OPPORTUNITY_FOUND = "OPPORTUNITY_FOUND"
    TREND_ALERT = "TREND_ALERT"
    COMPLIANCE_ALERT = "COMPLIANCE_ALERT"
    SUBMISSION_UPDATE = "SUBMISSION_UPDATE"
    PRODUCTION_REMINDER = "PRODUCTION_REMINDER"
    PERFORMANCE_DIGEST = "PERFORMANCE_DIGEST"
    SYSTEM = "SYSTEM"


class NotificationChannel(StrEnum):
    IN_APP = "IN_APP"
    EMAIL = "EMAIL"


class AgentStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class AgentLogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class AgentRunKind(StrEnum):
    TREND_INGEST = "TREND_INGEST"
    MARKET_ANALYSIS = "MARKET_ANALYSIS"
    OPPORTUNITY_SCAN = "OPPORTUNITY_SCAN"
    PREDICTION = "PREDICTION"
    IDEA_GENERATION = "IDEA_GENERATION"
    PROMPT_GENERATION = "PROMPT_GENERATION"
    COMPLIANCE_SCREEN = "COMPLIANCE_SCREEN"
    SIMILARITY_SCAN = "SIMILARITY_SCAN"
    METADATA_DRAFT = "METADATA_DRAFT"
    PRODUCTION_PLAN = "PRODUCTION_PLAN"
    PERFORMANCE_DIGEST = "PERFORMANCE_DIGEST"
    BRIEFING_BUILD = "BRIEFING_BUILD"
    DAILY_WORKFLOW = "DAILY_WORKFLOW"
    MANUAL = "MANUAL"


class JobStatus(StrEnum):
    """Background job statuses (docs: 12 §5.15)."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    DEAD_LETTER = "dead_letter"


class SavedItemKind(StrEnum):
    TREND_SIGNAL = "TREND_SIGNAL"
    OPPORTUNITY = "OPPORTUNITY"
    IMAGE_IDEA = "IMAGE_IDEA"
    VIDEO_IDEA = "VIDEO_IDEA"
    PROMPT = "PROMPT"
    PREDICTION = "PREDICTION"


class TrendSourceType(StrEnum):
    ADOBE_REPORT = "adobe_report"
    SEARCH_TRENDS = "search_trends"
    SOCIAL_TRENDS = "social_trends"
    MARKETPLACE_FEED = "marketplace_feed"
    HUGINN = "huginn"
    USER_UPLOAD = "user_upload"
    OTHER = "other"


class SourceStatus(StrEnum):
    """Runtime health of a data-source adapter (PHASE2_DESIGN.md §1, CONTRACT §4.25).

    AVAILABLE — healthy, returning real data · CONFIGURED — credentials set,
    not yet verified · NEEDS_AUTH — needs user credentials/config ·
    UNAVAILABLE — cannot run in this environment · TEMP_FAILING — transient failure ·
    NOT_CHECKED — registered but the scheduler has never checked it.
    """

    NOT_CHECKED = "NOT_CHECKED"
    AVAILABLE = "AVAILABLE"
    CONFIGURED = "CONFIGURED"
    NEEDS_AUTH = "NEEDS_AUTH"
    UNAVAILABLE = "UNAVAILABLE"
    TEMP_FAILING = "TEMP_FAILING"


class CollectionRunStatus(StrEnum):
    """Collection run lifecycle (CONTRACT §4.26)."""

    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class CollectionRunTrigger(StrEnum):
    """What triggered a collection run (CONTRACT §4.26)."""

    SCHEDULED = "SCHEDULED"
    MANUAL = "MANUAL"
    API = "API"
