/**
 * Shared domain types — mirror CONTRACT.md exactly.
 * Backend source of truth: backend/app/schemas/enums.py.
 * CONTRACT v0.2.0.
 */

export type DataProvenance =
  | "VERIFIED"
  | "USER_PROVIDED"
  | "THIRD_PARTY"
  | "ESTIMATED"
  | "PREDICTED"
  | "MOCK";

export type QueueStatus =
  | "DISCOVERED"
  | "ANALYZING"
  | "IDEA_READY"
  | "PROMPT_READY"
  | "APPROVED"
  | "IN_PRODUCTION"
  | "QUALITY_CHECK"
  | "COMPLIANCE_REVIEW"
  | "READY_TO_UPLOAD"
  | "SUBMITTED"
  | "ACCEPTED"
  | "REJECTED"
  | "ARCHIVED";

export type ComplianceResult = "PASS" | "REVIEW" | "HIGH_RISK";
export type ComplianceCheckType =
  | "PROMPT_SCREEN"
  | "ASSET_SCREEN"
  | "SIMILARITY_SCAN"
  | "METADATA_SCREEN";
export type RuleSeverity = "INFO" | "WARN" | "BLOCK";
export type RiskLevel = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
export type IdeaStatus = "DRAFT" | "READY" | "IN_QUEUE" | "ARCHIVED" | "DISCARDED";
export type PromptStatus = "DRAFT" | "READY" | "APPROVED" | "ARCHIVED";
export type AssetType = "IMAGE" | "VIDEO";
export type AssetStatus = "DRAFT" | "IN_REVIEW" | "FINAL" | "REJECTED";
export type PredictionHorizon = "H30_DAYS" | "H90_DAYS" | "H6_MONTHS" | "H12_MONTHS";
export type PredictedDirection = "up" | "flat" | "down";
export type NotificationType =
  | "BRIEFING_READY"
  | "OPPORTUNITY_FOUND"
  | "TREND_ALERT"
  | "COMPLIANCE_ALERT"
  | "SUBMISSION_UPDATE"
  | "PRODUCTION_REMINDER"
  | "PERFORMANCE_DIGEST"
  | "SYSTEM";
export type NotificationChannel = "IN_APP" | "EMAIL";
export type AgentStatus = "PENDING" | "RUNNING" | "COMPLETED" | "FAILED" | "CANCELLED";
export type AgentLogLevel = "DEBUG" | "INFO" | "WARNING" | "ERROR";
export type AgentRunKind =
  | "TREND_INGEST"
  | "MARKET_ANALYSIS"
  | "OPPORTUNITY_SCAN"
  | "IDEA_GENERATION"
  | "PROMPT_GENERATION"
  | "COMPLIANCE_SCREEN"
  | "METADATA_DRAFT"
  | "PERFORMANCE_DIGEST"
  | "BRIEFING_BUILD";
export type JobStatus =
  | "queued"
  | "running"
  | "succeeded"
  | "failed"
  | "cancelled"
  | "dead_letter";
export type SavedItemKind =
  | "TREND_SIGNAL"
  | "OPPORTUNITY"
  | "IMAGE_IDEA"
  | "VIDEO_IDEA"
  | "PROMPT"
  | "PREDICTION";
export type SubmissionStatus =
  | "PLANNED"
  | "SUBMITTED"
  | "UNDER_REVIEW"
  | "ACCEPTED"
  | "REJECTED";
export type TrendSourceType =
  | "adobe_report"
  | "search_trends"
  | "social_trends"
  | "marketplace_feed"
  | "user_upload"
  | "other";
export type OpportunityStatus = "new" | "approved" | "rejected" | "in_progress" | "archived";
export type PriorityBand = "P0" | "P1" | "P2" | "P3" | "P4";
export type DeadlineState = "ON_TRACK" | "AT_RISK" | "OVERDUE";
export type ReviewDecision = "accepted" | "accepted_with_changes" | "rejected";
export type IdeaKind = "image" | "video";
export type SubjectKind =
  | "prompt"
  | "asset"
  | "image_idea"
  | "video_idea"
  | "metadata"
  | "production_queue";

export type AgentName =
  | "trend_research"
  | "market_analysis"
  | "category_intelligence"
  | "opportunity"
  | "image_ideation"
  | "video_ideation"
  | "prediction"
  | "prompt"
  | "compliance"
  | "originality"
  | "metadata"
  | "production_planning"
  | "performance_analysis";

export const AGENT_NAMES: AgentName[] = [
  "trend_research",
  "market_analysis",
  "category_intelligence",
  "opportunity",
  "image_ideation",
  "video_ideation",
  "prediction",
  "prompt",
  "compliance",
  "originality",
  "metadata",
  "production_planning",
  "performance_analysis",
];

export interface PageInfo {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface Page<T> {
  data: T[];
  pagination: PageInfo;
}

export interface ApiError {
  error: {
    code: string;
    message: string;
    severity: string;
    retryable: boolean;
    retry_in_seconds?: number;
    request_id?: string;
    trace_id?: string;
    details: Record<string, unknown>;
    help?: string;
  };
}

/** Every intelligence payload carries provenance + (for mock) a Demo-data flag. */
export interface WithProvenance {
  provenance: DataProvenance;
  mock?: boolean;
}

export interface JobAccepted {
  job_id: string;
}

// ---------------------------------------------------------------------------
// Trends (§5.2)
// ---------------------------------------------------------------------------

export interface Trend extends WithProvenance {
  id: string;
  title: string;
  score: number;
  window: "7d" | "30d" | "90d";
  categories: string[];
  signal_count: number;
  created_at: string;
  updated_at: string;
}

/** Raw signal row as returned by GET /trends/{id} and /trends/{id}/signals
 *  (backend SignalBreakdown contract — signal_name/metric_* shape). */
export interface TrendSignal extends WithProvenance {
  signal_name: string;
  metric_name?: string | null;
  metric_value?: number | null;
  metric_unit?: string | null;
  source_name?: string | null;
  confidence?: number | null;
  observed_at: string;
}

export interface TrendDetail extends Trend {
  /** Optional score breakdown; the contract does not fix its shape, so all fields are optional. */
  scores?: {
    trend_score?: number;
    opportunity_score?: number;
    commercial_score?: number;
    saturation_score?: number;
    confidence?: number;
    factors?: { name: string; value: number; weight?: number; note?: string }[];
  };
}

// ---------------------------------------------------------------------------
// Categories (§5.3)
// ---------------------------------------------------------------------------

export interface Subcategory {
  id: string;
  name: string;
  slug: string;
}

export interface Category {
  id: string;
  name: string;
  slug: string;
  description?: string;
  sort_order: number;
  is_system: boolean;
  subcategories?: Subcategory[];
  micro_niches?: MicroNiche[];
  trend_coverage: { signal_count: number; avg_score: number | null };
  created_at: string;
  updated_at: string;
}

export interface MicroNiche {
  id: string;
  category_id?: string;
  name: string;
  slug?: string;
  description?: string;
  demand_score?: number;
  saturation_score?: number;
}

// ---------------------------------------------------------------------------
// Opportunities (§5.4)
// ---------------------------------------------------------------------------

export interface DemandEvidence {
  signal_id: string;
  metric_id: string;
  note: string;
}

export interface OpportunityScores {
  trend_score?: number | null;
  commercial_score?: number | null;
  saturation_score?: number | null;
  demand_score?: number | null;
  predicted_direction?: PredictedDirection | null;
  prediction_confidence?: number | null;
}

export interface Opportunity extends WithProvenance {
  id: string;
  project_id: string | null;
  micro_niche_id: string | null;
  title: string;
  summary: string;
  opportunity_score: number;
  confidence: number;
  demand_evidence: DemandEvidence[];
  risk_notes: string | null;
  data_provenance: DataProvenance;
  status: OpportunityStatus;
  priority: number;
  reviewed_at: string | null;
  agent_run_id: string | null;
  created_at: string;
  updated_at: string;
  /** Optional display/score enrichment (see §5.4 "Detail incl. evidence + scores"). */
  category?: string | null;
  micro_niche?: string | null;
  formats?: ("image" | "video")[];
  scores?: OpportunityScores;
  /**
   * Personal Fit Score — Phase 2 (§6): how well the opportunity fits the
   * user's own Adobe Stock performance history (category/asset/keyword
   * acceptance, downloads, earnings). Nullable; null when no private
   * performance data exists.
   */
  personal_fit_score?: number | null;
}

// ---------------------------------------------------------------------------
// Ideas (§5.5)
// ---------------------------------------------------------------------------

export interface ShotItem {
  shot: string;
  camera_move?: string;
  duration_s?: number;
  notes?: string;
}

export interface Idea extends WithProvenance {
  id: string;
  kind: IdeaKind;
  project_id?: string | null;
  opportunity_id?: string | null;
  micro_niche_id?: string | null;
  title: string;
  concept: string;
  originality_notes: string;
  reference_mood: string[] | null;
  duration_target_seconds?: number | null;
  shot_list?: ShotItem[] | null;
  status: IdeaStatus;
  priority: number;
  reviewed_at?: string | null;
  agent_run_id?: string | null;
  created_at: string;
  updated_at: string;
  category?: string | null;
  micro_niche?: string | null;
  compliance?: { result: ComplianceResult; check_id: string } | null;
  similarity?: { risk_level: RiskLevel; check_id: string } | null;
}

// ---------------------------------------------------------------------------
// Prompts (§5.6)
// ---------------------------------------------------------------------------

/**
 * Generated prompt package blocks (§14 prompt-engine spec). The contract carries
 * them inside `current_version` / `parameters`; fields beyond prompt_text are
 * optional because the contract leaves their exact wire shape open.
 */
export interface PromptVersion {
  version_number: number;
  prompt_text: string;
  negative_prompt_text?: string | null;
  alternative_prompt_text?: string | null;
  technical_notes?: string | null;
  originality_notes?: string | null;
  compliance_notes?: string | null;
  parameters: Record<string, unknown>;
  change_summary?: string | null;
  created_by: "user" | "agent";
  created_at: string;
}

export interface Prompt extends WithProvenance {
  id: string;
  image_idea_id: string | null;
  video_idea_id: string | null;
  asset_type: AssetType;
  name: string;
  status: PromptStatus;
  current_version: PromptVersion;
  versions_count: number;
  approved_version_number: number | null;
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// Compliance (§5.7)
// ---------------------------------------------------------------------------

export interface ComplianceSubject {
  kind: SubjectKind;
  id: string;
  version_id?: string;
}

export interface ComplianceFinding {
  check_id: string;
  rule_key: string;
  rule_version: string;
  severity: RuleSeverity;
  triggered: boolean;
  explanation: string;
  matched_excerpt?: string;
  remediation: string;
}

export interface ComplianceCheck {
  id: string;
  check_type: ComplianceCheckType;
  subject: ComplianceSubject;
  result: ComplianceResult;
  risk_level: RiskLevel;
  findings: ComplianceFinding[];
  explanation: string;
  rules_version: string;
  review_decision?: ReviewDecision;
  reviewed_at?: string | null;
  agent_run_id?: string | null;
  created_at: string;
}

// ---------------------------------------------------------------------------
// Similarity (§5.8)
// ---------------------------------------------------------------------------

export interface SimilarityRecord {
  compared_cluster_label: string;
  similarity_score: number;
  risk_level: RiskLevel;
  cluster_sample_count: number;
  differentiators: string[];
}

export interface SimilarityCheckResult extends WithProvenance {
  id: string;
  subject: ComplianceSubject;
  risk_level: RiskLevel;
  records: SimilarityRecord[];
  created_at: string;
}

// ---------------------------------------------------------------------------
// Assets (§5.9)
// ---------------------------------------------------------------------------

export interface AssetVersion {
  version_number: number;
  storage_uri: string;
  mime_type: string;
  file_size_bytes?: number;
  width_px?: number;
  height_px?: number;
  duration_seconds?: number;
  file_hash?: string;
}

export interface Asset {
  id: string;
  project_id?: string | null;
  production_queue_id?: string | null;
  image_idea_id?: string | null;
  video_idea_id?: string | null;
  prompt_id?: string | null;
  prompt_version_id?: string | null;
  asset_type: AssetType;
  title: string;
  status: AssetStatus;
  current_version: AssetVersion | null;
  width_px?: number;
  height_px?: number;
  duration_seconds?: number;
  created_at: string;
  updated_at: string;
}

export interface AssetRegistration {
  id: string;
  type: string;
  status: string;
  upload_url: string;
  expires_at: string;
}

// ---------------------------------------------------------------------------
// Metadata (§5.10)
// ---------------------------------------------------------------------------

export interface MetadataBundle {
  id: string;
  asset_id: string;
  version_number: number;
  title: string;
  description?: string;
  keywords: string[];
  adobe_category?: string;
  micro_niche_id?: string;
  language: string;
  is_current: boolean;
  created_by: "user" | "agent";
  agent_run_id?: string | null;
  created_at: string;
}

export interface MetadataIssue {
  code: string;
  message: string;
  severity: "error" | "warning" | "info";
}

export interface MetadataValidation {
  valid: boolean;
  issues: MetadataIssue[];
}

// ---------------------------------------------------------------------------
// Production queue (§5.11)
// ---------------------------------------------------------------------------

export interface PriorityComponents {
  trend_momentum: number;
  deadline_urgency: number;
  predicted_value: number;
  user_boost: number;
  rework_penalty: number;
}

export interface QueueItem {
  id: string;
  project_id?: string | null;
  opportunity_id?: string | null;
  image_idea_id?: string | null;
  video_idea_id?: string | null;
  prompt_id?: string | null;
  asset_type: AssetType;
  title: string;
  status: QueueStatus;
  priority_band: PriorityBand;
  priority_score: number;
  priority_components?: PriorityComponents;
  target_date: string | null;
  deadline_state: DeadlineState | null;
  paused: boolean;
  target_quantity: number;
  produced_count: number;
  generation_tool: string | null;
  rework_count: number;
  blocked_reason: string | null;
  compliance: { result: ComplianceResult; check_id: string } | null;
  notes: string | null;
  status_changed_at: string;
  created_at: string;
  updated_at: string;
}

export interface QueueHistoryEvent {
  id: string;
  at: string;
  from: QueueStatus | null;
  to: QueueStatus;
  actor: string;
  note?: string;
}

export interface QueueItemDetail extends QueueItem {
  history: QueueHistoryEvent[];
}

// ---------------------------------------------------------------------------
// Submissions (§5.12)
// ---------------------------------------------------------------------------

export interface Submission {
  id: string;
  asset_id: string;
  asset_version_id: string;
  metadata_id: string;
  production_queue_id?: string | null;
  project_id?: string | null;
  status: SubmissionStatus;
  submitted_at?: string | null;
  reviewed_at?: string | null;
  adobe_reference?: string | null;
  rejection_reason?: string | null;
  notes?: string | null;
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// Analytics (§5.13)
// ---------------------------------------------------------------------------

export interface KpiValue {
  value: number | null;
  provenance: DataProvenance;
}

export interface AnalyticsOverview {
  range: { from: string; to: string };
  kpis: {
    submitted: KpiValue;
    accepted: KpiValue;
    acceptance_rate: KpiValue;
    views?: KpiValue;
    downloads?: KpiValue;
    revenue?: KpiValue;
  };
  provenance_notes: string[];
  mock?: boolean;
}

export interface FunnelStage {
  stage: string;
  count: number;
}

export interface AnalyticsFunnel {
  stages: FunnelStage[];
  mock?: boolean;
}

export interface OpportunityPerformance {
  opportunity_id: string;
  sample_size: number;
  submitted: number;
  accepted: number;
  acceptance_rate: number | null;
  note?: string;
  mock?: boolean;
}

export interface AnalyticsExport {
  id: string;
  kind: string;
  status: JobStatus;
  download_url?: string | null;
  created_at: string;
}

// ---------------------------------------------------------------------------
// Agents (§5.14)
// ---------------------------------------------------------------------------

export interface AgentDefinition {
  name: AgentName;
  display_name?: string;
  description?: string;
  capabilities?: string[];
  enabled: boolean;
  /** Operational status surfaced for the Agent Center UI. */
  status?: AgentStatus;
  last_run_at?: string | null;
  confidence?: number | null;
}

export interface AgentJob {
  job_id: string;
  run_id?: string;
  agent: AgentName;
  run_kind: AgentRunKind;
  status: JobStatus;
  progress: number;
  input_summary: Record<string, unknown>;
  output_summary: Record<string, unknown> | null;
  error: { code: string; message: string } | null;
  instructions_version: string;
  started_at?: string;
  finished_at?: string;
  created_at: string;
  logs?: AgentLog[];
}

export interface AgentLog {
  id: string;
  run_id: string;
  level: AgentLogLevel;
  message: string;
  timestamp: string;
}

// ---------------------------------------------------------------------------
// Settings (§5.15)
// ---------------------------------------------------------------------------

export type SettingsMap = Record<string, unknown>;

// ---------------------------------------------------------------------------
// Notifications (§5.16, ext)
// ---------------------------------------------------------------------------

export interface Notification {
  id: string;
  type: NotificationType;
  title: string;
  body: string;
  link_entity_kind?: SavedItemKind | string;
  link_entity_id?: string;
  channel: NotificationChannel;
  is_read: boolean;
  read_at?: string | null;
  created_at: string;
}

export interface NotificationList {
  data: Notification[];
  pagination: PageInfo;
  unread_count: number;
}

// ---------------------------------------------------------------------------
// Library (§5.17, ext)
// ---------------------------------------------------------------------------

export interface SavedItem {
  id: string;
  item_kind: SavedItemKind;
  item_id: string;
  note?: string;
  created_at: string;
}

// ---------------------------------------------------------------------------
// Health
// ---------------------------------------------------------------------------

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  timestamp: string;
  database: "ok" | "degraded";
}

// ---------------------------------------------------------------------------
// Phase 2 — real-data integration (PHASE2_DESIGN.md)
// ---------------------------------------------------------------------------

/**
 * SourceStatus — mirrors backend `SourceStatus(str, Enum)` EXACTLY:
 * NOT_CHECKED · AVAILABLE · CONFIGURED · NEEDS_AUTH · UNAVAILABLE · TEMP_FAILING
 * (PHASE2_DESIGN.md §1, §12 contract). UPPER_SNAKE_CASE everywhere.
 */
export type SourceStatus =
  | "NOT_CHECKED"
  | "AVAILABLE"
  | "CONFIGURED"
  | "NEEDS_AUTH"
  | "UNAVAILABLE"
  | "TEMP_FAILING";

/** CollectionRun.status — PHASE2_DESIGN.md §3. */
export type CollectionRunStatus =
  | "QUEUED"
  | "RUNNING"
  | "SUCCESS"
  | "PARTIAL"
  | "FAILED"
  | "SKIPPED";

/** CollectionRun.trigger — PHASE2_DESIGN.md §3. */
export type CollectionRunTrigger = "SCHEDULED" | "MANUAL" | "API";

/**
 * Source health summary as returned by GET /api/sources/
 * ("list sources with health summary + provenance"). Optional fields are
 * optional because the summary may carry either the full health row or a
 * condensed subset — both are rendered defensively.
 */
export interface SourceSummary {
  id: string;
  name: string;
  source_type: string;
  is_active: boolean;
  data_provenance?: DataProvenance | null;
  health_status?: SourceStatus | null;
  /** Legacy/actual last-fetch timestamp on TrendSource rows (fallback for last sync). */
  last_fetched_at?: string | null;
  last_success_at?: string | null;
  last_failure_at?: string | null;
  last_error?: string | null;
  records_collected?: number | null;
  auth_state?: string | null;
  health?: SourceHealth | null;
  created_at?: string;
  updated_at?: string;
}

/** Full source detail — GET /api/sources/{id} (detail + recent runs). */
export interface SourceDetail extends SourceSummary {
  recent_runs?: CollectionRun[];
}

/** SourceHealth row — GET /api/sources/health (PHASE2_DESIGN.md §3). */
export interface SourceHealth {
  id: string;
  trend_source_id: string;
  source_name?: string | null;
  source_type?: string | null;
  status: SourceStatus;
  last_success_at: string | null;
  last_failure_at: string | null;
  last_error: string | null;
  records_collected: number;
  avg_duration_ms: number | null;
  consecutive_failures: number;
  checked_at: string | null;
  auth_state: string | null;
  fallback_status: string | null;
}

/** CollectionRun — GET /api/sources/runs (PHASE2_DESIGN.md §3, §5). */
export interface CollectionRun {
  id: string;
  trend_source_id: string | null;
  source_name?: string | null;
  source_type?: string | null;
  started_at: string;
  finished_at: string | null;
  status: CollectionRunStatus;
  records_collected: number;
  records_stored: number;
  error: string | null;
  trigger: CollectionRunTrigger;
  duration_ms: number | null;
}

/** POST /api/sources/{id}/collect → 202 + run id. */
export interface CollectionRunAccepted {
  run_id: string;
  job_id?: string;
}

/**
 * Adobe Contributor connection status — GET /api/private/connection
 * (PHASE2_DESIGN.md §5). Default honest state: NOT_CONFIGURED.
 * The response NEVER carries secret values; neither does this type.
 */
export type AdobeConnectionStatus =
  | "NOT_CONFIGURED"
  | "CONFIGURED"
  | "ACTIVE"
  | "AUTH_ERROR"
  | SourceStatus;

export interface AdobeConnectionStep {
  title: string;
  detail?: string;
}

export interface AdobeConnection {
  status: AdobeConnectionStatus;
  /** Required configuration steps shown on the setup screen. */
  required_config: (string | AdobeConnectionStep)[] | null;
  last_sync: string | null;
  error: string | null;
  configured?: boolean;
  session_type?: string | null;
}

/** Body for PUT /api/private/connection — server-side only, never echoed. */
export interface AdobeConnectionConfig {
  session_type: string;
  /** Opaque session export from the user's own browser. Never displayed. */
  session_data?: string;
  notes?: string;
}

/** Personal performance — GET /api/private/performance/summary. */
export interface PrivatePerformanceTrendPoint {
  date: string;
  earnings: number;
  downloads: number;
}

export interface PrivatePerformanceSummary {
  has_data: boolean;
  totals: {
    earnings: number | null;
    currency: string;
    downloads: number | null;
    views?: number | null;
    asset_count?: number | null;
    date_from?: string | null;
    date_to?: string | null;
  } | null;
  earnings_trend?: { date: string; earnings: number }[];
  downloads_trend?: { date: string; downloads: number }[];
  by_category: PrivateCategoryPerformance[];
  by_asset_type?: { asset_type: string; downloads: number; earnings: number; asset_count: number }[];
  acceptance_rate?: number | null;
  /** Honest empty-state message from the backend when has_data is false. */
  message?: string | null;
  provenance?: DataProvenance | null;
  mock?: boolean;
}

export interface PrivateCategoryPerformance {
  category: string;
  snapshot_date?: string | null;
  downloads: number;
  earnings: number;
  asset_count: number;
}

export interface PrivateKeywordPerformance {
  keyword: string;
  snapshot_date?: string | null;
  downloads: number;
  earnings: number;
}

// ---------------------------------------------------------------------------
// Phase 3 — personal intelligence (PERSONAL INTELLIGENCE module)
// ---------------------------------------------------------------------------

export type PersonalStatus = "available" | "not_configured";
export type PersonalPeriod = "7d" | "30d" | "90d" | "1y" | "all";
export type PersonalTrendLabel = "growing" | "stable" | "declining";

/** GET /api/personal-performance?period=7d|30d|90d — honest not_configured default. */
export interface PersonalPerformanceSummary3 {
  status: PersonalStatus;
  earnings_total: number | null;
  downloads_total: number | null;
  earnings_momentum: number | null;
  downloads_momentum: number | null;
  acceptance_rate: number | null;
  assets_tracked: number | null;
  top_categories: { category: string; downloads: number; earnings: number; trend: string | null }[];
  updated_at: string | null;
  provenance?: DataProvenance | null;
  mock?: boolean;
}

/** GET /api/personal-performance/categories?period= */
export interface PersonalCategoryPerformance3 {
  category: string;
  assets_total: number;
  assets_accepted: number;
  assets_rejected: number;
  downloads: number;
  earnings: number;
  avg_downloads_per_asset: number | null;
  avg_earnings_per_asset: number | null;
  acceptance_rate: number | null;
  momentum_7d: number | null;
  momentum_30d: number | null;
  trend_label: PersonalTrendLabel;
}

export interface PersonalCategoriesResponse {
  status: PersonalStatus;
  categories: PersonalCategoryPerformance3[];
  updated_at?: string | null;
  provenance?: DataProvenance | null;
}

/** GET /api/personal-performance/content-types */
export interface ContentTypePerformance {
  content_type: "image" | "video";
  assets_total: number;
  assets_accepted: number;
  assets_rejected: number;
  downloads: number;
  earnings: number;
  avg_downloads_per_asset: number | null;
  avg_earnings_per_asset: number | null;
  acceptance_rate: number | null;
  momentum_7d: number | null;
  momentum_30d: number | null;
  trend_label: PersonalTrendLabel;
}

export interface ContentTypesResponse {
  status: PersonalStatus;
  types: ContentTypePerformance[];
  updated_at?: string | null;
  provenance?: DataProvenance | null;
}

/** GET /api/personal-performance/themes */
export interface PersonalTheme {
  theme: string;
  keywords: string[];
  assets: number;
  downloads: number;
  earnings: number;
  trend: string | null;
}

export interface PersonalThemesResponse {
  status: PersonalStatus;
  themes: PersonalTheme[];
  updated_at?: string | null;
  provenance?: DataProvenance | null;
}

// ---------------------------------------------------------------------------
// Phase 3 — opportunity fusion (OPPORTUNITY FUSION module)
// ---------------------------------------------------------------------------

export type FusionLabel = "FUSED" | "MARKET-ONLY";

export interface FusionComponents {
  market_opportunity: number | null;
  personal_fit: number | null;
  trend_momentum: number | null;
  commercial_potential: number | null;
  seasonality: number | null;
  saturation_risk: number | null;
  prediction_confidence: number | null;
  personal_momentum: number | null;
  historical_performance: number | null;
}

export interface FusionEvidence {
  /** Public market signal, private portfolio data, or model prediction. */
  source: string;
  observed_at: string | null;
  signal: string;
  private: boolean;
  prediction_version?: string | null;
}

export interface FusionScore {
  id: string;
  opportunity_id: string;
  unified_score: number;
  components: FusionComponents;
  explanation: string;
  confidence_score: number;
  label: FusionLabel;
  data_provenance: DataProvenance;
  evidence?: FusionEvidence[];
  computed_at?: string | null;
  mock?: boolean;
}

// ---------------------------------------------------------------------------
// Phase 3 — daily production planner (DAILY PRODUCTION PLANNER module)
// ---------------------------------------------------------------------------

export type ProductionRecommendationStatus =
  | "recommended"
  | "approved"
  | "rejected"
  | "archived";

export interface DailyPlan {
  plan_date: string;
  target_images: number;
  target_videos: number;
  status: string;
}

/** Backend PlanDetailOut: plan summary + embedded recommendations. */
export interface PlanDetail extends DailyPlan {
  id: string;
  recommendation_count: number;
  summary_json?: Record<string, unknown>;
  recommendations: ProductionRecommendation[];
  data_provenance?: string | null;
}

/** Backend ConceptOut: one screened concept variation for a recommendation. */
export interface ConceptVariation {
  id: string;
  recommendation_id: string;
  asset_type: string;
  title: string;
  concept_json: Record<string, unknown>;
  originality_notes: string;
  similarity_flags_json: { flags?: Array<{ flag: string; similarity?: number; [k: string]: unknown }> };
  compliance_result: "PASS" | "REVIEW" | "HIGH_RISK" | null;
  compliance_result_json: {
    result?: string;
    explanation?: string;
    findings?: Array<{ rule_key: string; severity: string; triggered: boolean; explanation: string; remediation?: string }>;
  } | null;
  variation_round: number;
  status: "draft" | "screened" | "approved" | "archived";
  ai_disclosure: boolean | null;
}

export interface ProductionRecommendation {
  id: string;
  rank: number;
  asset_type: "image" | "video";
  category: string | null;
  micro_niche_name: string | null;
  unified_score: number;
  personal_fit: number | null;
  confidence: number;
  reason: string;
  recommended_quantity: number;
  status: ProductionRecommendationStatus;
  opportunity_id?: string | null;
  evidence?: FusionEvidence[];
  created_at?: string | null;
  updated_at?: string | null;
}

export interface DailyProductionResponse {
  plan: DailyPlan | null;
  recommendations: ProductionRecommendation[];
  generated_at?: string | null;
}

export interface CapacitySettings {
  weekly_capacity: number;
  daily_target: number;
  image_target: number;
  video_target: number;
  max_daily_generation: number;
  priority_preference: string;
}

// ---------------------------------------------------------------------------
// Phase 3 — prompt packs (prompt package bundles attached to opportunities)
// ---------------------------------------------------------------------------

export interface PromptPack {
  id: string;
  opportunity_id: string | null;
  name: string;
  summary?: string | null;
  asset_type?: "image" | "video" | null;
  prompt_count: number;
  status?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  items?: PromptPackItem[];
}

export interface PromptPackItem {
  id: string;
  prompt_text: string;
  negative_prompt_text?: string | null;
  notes?: string | null;
}
