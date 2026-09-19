"""SQLAlchemy entity models (docs: 08_DATABASE_SCHEMA).

SINGLE-USER DEVIATION: there is no `users` table and no `user_id` columns —
the app is single-user (see CHANGELOG 0.2.0). UUID PKs (String(36)) +
created_at/updated_at audit fields are kept per docs/08.

Tables (47): categories, subcategories, micro_niches, trend_sources,
trend_snapshots, trend_signals, market_metrics, opportunities, image_ideas,
video_ideas, predictions, prompts, prompt_versions, compliance_rules,
compliance_checks, similarity_records, assets, asset_versions, metadata,
production_queue, submission_records, performance_metrics, saved_items,
agent_runs, agent_logs, notifications, settings, audit_logs (28 in v0.3.0),
plus Phase 2: source_health, collection_runs, raw_payloads and the nine
append-only private tables (private_daily_earnings, private_downloads,
private_sales, private_asset_performance, private_submission_results,
private_category_performance, private_keyword_performance, private_snapshots,
private_collection_runs), plus Phase 3: personal_performance_snapshots,
personal_category_metrics, personal_content_type_metrics,
personal_theme_metrics, personal_keyword_metrics, personal_fit_scores,
opportunity_fusion_scores.
"""

from app.models.analytics import PerformanceMetric, SavedItem
from app.models.compliance import ComplianceCheck, ComplianceRule, SimilarityRecord
from app.models.fusion import OpportunityFusionScore
from app.models.ideation import ImageIdea, VideoIdea
from app.models.intelligence import (
    MarketMetric,
    Opportunity,
    Prediction,
    TrendSignal,
    TrendSnapshot,
    TrendSource,
)
from app.models.planning import (
    ConceptVariation,
    DailyProductionPlan,
    ProductionRecommendation,
    PromptPack,
)
from app.models.personal import (
    PersonalCategoryMetric,
    PersonalContentTypeMetric,
    PersonalFitScore,
    PersonalKeywordMetric,
    PersonalPerformanceSnapshot,
    PersonalThemeMetric,
)
from app.models.platform import AgentLog, AgentRun, AuditLog, Notification
from app.models.private import (
    PrivateAssetPerformance,
    PrivateCategoryPerformance,
    PrivateCollectionRun,
    PrivateDailyEarning,
    PrivateDownload,
    PrivateKeywordPerformance,
    PrivateSale,
    PrivateSnapshot,
    PrivateSubmissionResult,
)
from app.models.production import (
    Asset,
    AssetVersion,
    MetadataRecord,
    ProductionQueue,
    SubmissionRecord,
)
from app.models.prompts import Prompt, PromptVersion
from app.models.settings import Setting
from app.models.sources import CollectionRun, RawPayload, SourceHealth
from app.models.taxonomy import Category, MicroNiche, Subcategory

__all__ = [
    "Asset",
    "AssetVersion",
    "AgentLog",
    "AgentRun",
    "AuditLog",
    "Category",
    "CollectionRun",
    "ComplianceCheck",
    "ComplianceRule",
    "ConceptVariation",
    "DailyProductionPlan",
    "ImageIdea",
    "MarketMetric",
    "MetadataRecord",
    "MicroNiche",
    "Notification",
    "Opportunity",
    "OpportunityFusionScore",
    "PerformanceMetric",
    "PersonalCategoryMetric",
    "PersonalContentTypeMetric",
    "PersonalFitScore",
    "PersonalKeywordMetric",
    "PersonalPerformanceSnapshot",
    "PersonalThemeMetric",
    "Prediction",
    "PrivateAssetPerformance",
    "PrivateCategoryPerformance",
    "PrivateCollectionRun",
    "PrivateDailyEarning",
    "PrivateDownload",
    "PrivateKeywordPerformance",
    "PrivateSale",
    "PrivateSnapshot",
    "PrivateSubmissionResult",
    "ProductionQueue",
    "ProductionRecommendation",
    "Prompt",
    "PromptPack",
    "PromptVersion",
    "RawPayload",
    "SavedItem",
    "Setting",
    "SimilarityRecord",
    "SourceHealth",
    "Subcategory",
    "SubmissionRecord",
    "TrendSignal",
    "TrendSnapshot",
    "TrendSource",
    "VideoIdea",
]
