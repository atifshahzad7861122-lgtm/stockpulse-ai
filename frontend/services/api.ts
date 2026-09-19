/**
 * Typed API client. Base URL: NEXT_PUBLIC_API_URL (default http://localhost:8000/api).
 * Components must use these functions (never raw fetch) — docs/11 §4.
 * Errors are normalized to the CONTRACT.md error envelope.
 */
import type {
  AdobeConnection,
  AdobeConnectionConfig,
  AgentDefinition,
  AgentJob,
  AgentLog,
  AgentName,
  AgentRunKind,
  AnalyticsExport,
  AnalyticsFunnel,
  AnalyticsOverview,
  Asset,
  AssetRegistration,
  AssetType,
  AssetVersion,
  CapacitySettings,
  Category,
  CollectionRun,
  CollectionRunAccepted,
  ComplianceCheck,
  ComplianceCheckType,
  ComplianceResult,
  ConceptVariation,
  ContentTypesResponse,
  DailyProductionResponse,
  FusionScore,
  HealthResponse,
  Idea,
  IdeaKind,
  IdeaStatus,
  JobAccepted,
  JobStatus,
  MetadataBundle,
  MetadataValidation,
  MicroNiche,
  Notification,
  NotificationList,
  NotificationType,
  Opportunity,
  OpportunityStatus,
  Page,
  PersonalCategoriesResponse,
  PersonalPerformanceSummary3,
  PersonalPeriod,
  PersonalThemesResponse,
  PlanDetail,
  PrivateCategoryPerformance,
  PrivateKeywordPerformance,
  PrivatePerformanceSummary,
  ProductionRecommendation,
  Prompt,
  PromptPack,
  PromptStatus,
  PromptVersion,
  QueueItem,
  QueueItemDetail,
  QueueStatus,
  ReviewDecision,
  SavedItem,
  SavedItemKind,
  SettingsMap,
  SimilarityCheckResult,
  SourceDetail,
  SourceHealth,
  SourceSummary,
  SubjectKind,
  Submission,
  SubmissionStatus,
  Trend,
  TrendDetail,
  TrendSignal,
  ApiError,
} from "../types";

const BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000/api";

export class ApiClientError extends Error {
  envelope: ApiError["error"];
  status: number;
  constructor(status: number, envelope: ApiError["error"]) {
    super(envelope.message);
    this.status = status;
    this.envelope = envelope;
  }
}

/**
 * Safe human-readable message from ANY query/mutation error.
 * React Query surfaces whatever the queryFn threw: contract ApiClientErrors
 * carry `.envelope`, but network/DNS failures surface as plain TypeErrors
 * (e.g. "Failed to fetch") with no envelope. Never access `.envelope`
 * unguarded — it crashes the render (full-page "Application error").
 */
export function errorMessage(err: unknown): string {
  if (err instanceof ApiClientError) return err.envelope.message;
  const envelope = (err as { envelope?: unknown } | null | undefined)?.envelope as
    | { message?: unknown }
    | undefined;
  if (typeof envelope?.message === "string" && envelope.message.length > 0) {
    return envelope.message;
  }
  if (err instanceof Error && err.message.length > 0) return err.message;
  return "Request failed";
}

/** Safe trace id from a contract envelope, if the error carries one. */
export function errorTraceId(err: unknown): string | undefined {
  const envelope = (err as { envelope?: unknown } | null | undefined)?.envelope as
    | { trace_id?: unknown }
    | undefined;
  return typeof envelope?.trace_id === "string" ? envelope.trace_id : undefined;
}

function idempotencyKey(): string {
  // Crypto-random idempotency key for mutating POSTs (CONTRACT §2.6).
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `idem-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
  });
  if (res.status === 204) return undefined as T;
  if (!res.ok) {
    const body = (await res.json().catch(() => null)) as ApiError | null;
    throw new ApiClientError(
      res.status,
      body?.error ?? {
        code: "INTERNAL_ERROR",
        message: `Request failed (${res.status})`,
        severity: "error",
        retryable: res.status >= 500,
        details: {},
      },
    );
  }
  return (await res.json()) as T;
}

function qs(params: Record<string, string | number | boolean | undefined | null>): string {
  const parts: string[] = [];
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") continue;
    parts.push(`${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`);
  }
  return parts.length ? `?${parts.join("&")}` : "";
}

export interface ListParams {
  page?: number;
  page_size?: number;
  sort?: string;
  [key: string]: string | number | boolean | undefined | null;
}

const get = <T,>(path: string) => request<T>(path);
const post = <T,>(path: string, body?: unknown, idempotent = false) =>
  request<T>(path, {
    method: "POST",
    body: body === undefined ? undefined : JSON.stringify(body),
    headers: idempotent ? { "Idempotency-Key": idempotencyKey() } : undefined,
  });
const patch = <T,>(path: string, body: unknown) =>
  request<T>(path, { method: "PATCH", body: JSON.stringify(body) });
const put = <T,>(path: string, body: unknown) =>
  request<T>(path, { method: "PUT", body: JSON.stringify(body) });
const del = <T,>(path: string) => request<T>(path, { method: "DELETE" });

export const api = {
  get,
  post,
  patch,
  del,
  health: () => get<HealthResponse>("/health"),

  // §5.2 Trends
  trends: {
    list: (p: ListParams & { category?: string; window?: "7d" | "30d" | "90d"; min_score?: number } = {}) =>
      get<Page<Trend>>(`/trends${qs(p)}`),
    detail: (id: string) => get<TrendDetail>(`/trends/${id}`),
    signals: (id: string) => get<Page<TrendSignal> | TrendSignal[]>(`/trends/${id}/signals`),
    refresh: () => post<JobAccepted>("/trends/refresh", undefined, true),
  },

  // §5.3 Categories
  categories: {
    // Backend returns the standard Page envelope {data, pagination}; unwrap to Category[].
    list: async (): Promise<Category[]> => {
      const r = await get<Page<Category> | Category[]>(`/categories`);
      return Array.isArray(r) ? r : r.data;
    },
    detail: (id: string) => get<Category>(`/categories/${id}`),
  },

  // §5.4 Opportunities
  opportunities: {
    list: (
      p: ListParams & { status?: OpportunityStatus | string; category?: string; min_score?: number } = {},
    ) => get<Page<Opportunity>>(`/opportunities${qs(p)}`),
    detail: (id: string) => get<Opportunity>(`/opportunities/${id}`),
    create: (body: { title: string; summary: string; micro_niche_id?: string; project_id?: string; priority?: number }) =>
      post<Opportunity>("/opportunities", body),
    update: (id: string, body: Partial<Opportunity>) => patch<Opportunity>(`/opportunities/${id}`, body),
    approve: (id: string, body?: { priority?: "high" | "normal" | "low"; note?: string }) =>
      post<{ id: string; status: string; approved_at: string }>(`/opportunities/${id}/approve`, body ?? {}, true),
    reject: (id: string, reason: string) => post<Opportunity>(`/opportunities/${id}/reject`, { reason }),
    archive: (id: string) => post<Opportunity>(`/opportunities/${id}/archive`, {}),
    remove: (id: string) => del<void>(`/opportunities/${id}`),
  },

  // §5.5 Ideas
  ideas: {
    list: (
      p: ListParams & { kind?: IdeaKind; opportunity_id?: string; status?: IdeaStatus | string } = {},
    ) => get<Page<Idea>>(`/ideas${qs(p)}`),
    detail: (id: string) => get<Idea>(`/ideas/${id}`),
    create: (body: {
      kind: IdeaKind;
      title: string;
      concept: string;
      originality_notes: string;
      opportunity_id?: string;
      micro_niche_id?: string;
      reference_mood?: string[];
      duration_target_seconds?: number;
      shot_list?: { shot: string; camera_move?: string; duration_s?: number; notes?: string }[];
    }) => post<Idea>("/ideas", body),
    update: (id: string, body: Partial<Idea>) => patch<Idea>(`/ideas/${id}`, body),
    generateConcepts: (opportunity_id?: string | null) =>
      post<JobAccepted>(
        `/ideas/generate-concepts${opportunity_id ? `?opportunity_id=${encodeURIComponent(opportunity_id)}` : ""}`,
        {},
        true,
      ),
    archive: (id: string) => post<Idea>(`/ideas/${id}/archive`, {}),
  },

  // §5.6 Prompts
  prompts: {
    list: (p: ListParams & { idea_id?: string; status?: PromptStatus | string; asset_type?: AssetType } = {}) =>
      get<Page<Prompt>>(`/prompts${qs(p)}`),
    detail: (id: string) => get<Prompt>(`/prompts/${id}`),
    generate: (body: { idea_id: string; asset_type: AssetType; tool?: string }) =>
      post<JobAccepted>("/prompts", body, true),
    versions: (id: string) => get<PromptVersion[]>(`/prompts/${id}/versions`),
    saveVersion: (
      id: string,
      body: {
        prompt_text: string;
        negative_prompt_text?: string;
        alternative_prompt_text?: string;
        technical_notes?: string;
        originality_notes?: string;
        compliance_notes?: string;
        parameters?: Record<string, unknown>;
        change_summary: string;
      },
    ) => post<PromptVersion>(`/prompts/${id}/versions`, body),
    regenerate: (id: string, feedback: string) =>
      post<JobAccepted>(`/prompts/${id}/regenerate`, { feedback }, true),
    update: (id: string, body: { name?: string; status?: PromptStatus }) =>
      patch<Prompt>(`/prompts/${id}`, body),
  },

  // §5.7 Compliance
  compliance: {
    runCheck: (body: {
      check_type: ComplianceCheckType;
      subject_kind: SubjectKind;
      subject_id: string;
      subject_version_id?: string;
    }) => post<JobAccepted | ComplianceCheck>("/compliance/checks", body, true),
    list: (
      p: ListParams & {
        result?: ComplianceResult | string;
        check_type?: ComplianceCheckType | string;
        subject_kind?: SubjectKind | string;
        pending_review?: boolean;
      } = {},
    ) => get<Page<ComplianceCheck>>(`/compliance/checks${qs(p)}`),
    detail: (id: string) => get<ComplianceCheck>(`/compliance/checks/${id}`),
    review: (id: string, body: { decision: ReviewDecision; note?: string }) =>
      post<ComplianceCheck>(`/compliance/checks/${id}/review`, body),
  },

  // §5.8 Similarity
  similarity: {
    runCheck: (body: {
      subject_kind: "image_idea" | "video_idea" | "prompt" | "asset";
      subject_id: string;
    }) => post<JobAccepted>("/similarity/checks", body, true),
    get: (id: string) => get<SimilarityCheckResult>(`/similarity/checks/${id}`),
  },

  // §5.9 Assets
  assets: {
    list: (
      p: ListParams & { asset_type?: AssetType | string; status?: string; idea_id?: string; queue_id?: string } = {},
    ) => get<Page<Asset>>(`/assets${qs(p)}`),
    register: (body: {
      title: string;
      asset_type: AssetType;
      mime_type: string;
      production_queue_id?: string;
      idea_id?: string;
      prompt_id?: string;
    }) => post<AssetRegistration>("/assets", body),
    detail: (id: string) => get<Asset>(`/assets/${id}`),
    addVersion: (id: string, body: Record<string, unknown>) => post<AssetVersion>(`/assets/${id}/versions`, body),
    remove: (id: string) => del<void>(`/assets/${id}`),
  },

  // §5.10 Metadata
  metadata: {
    list: (p: ListParams & { asset_id?: string; is_current?: boolean } = {}) =>
      get<Page<MetadataBundle>>(`/metadata${qs(p)}`),
    generate: (asset_id: string) => post<JobAccepted>("/metadata", { asset_id }, true),
    detail: (id: string) => get<MetadataBundle>(`/metadata/${id}`),
    update: (
      id: string,
      body: { title?: string; description?: string; keywords?: string[]; adobe_category?: string },
    ) => patch<MetadataBundle>(`/metadata/${id}`, body),
    validate: (id: string) => post<MetadataValidation>(`/metadata/${id}/validate`, {}),
  },

  // §5.11 Production queue
  production: {
    queue: (
      p: ListParams & {
        status?: string;
        project_id?: string;
        paused?: boolean;
        overdue?: boolean;
      } = {},
    ) => get<Page<QueueItem>>(`/production/queue${qs(p)}`),
    enqueue: (body: {
      title: string;
      asset_type: AssetType;
      opportunity_id?: string;
      image_idea_id?: string;
      video_idea_id?: string;
      prompt_id?: string;
      priority_band?: string;
      target_date?: string;
      target_quantity?: number;
      generation_tool?: string;
      notes?: string;
    }) => post<QueueItem>("/production/queue", body, true),
    detail: (id: string) => get<QueueItemDetail>(`/production/queue/${id}`),
    transition: (id: string, body: { to: QueueStatus; note?: string }) =>
      post<QueueItem>(`/production/queue/${id}/transition`, body, true),
    assign: (id: string, body: Record<string, unknown>) =>
      post<QueueItem>(`/production/queue/${id}/assign`, body),
    pause: (id: string, body: { paused: boolean; reason?: string }) =>
      post<QueueItem>(`/production/queue/${id}/pause`, body),
  },

  // §5.12 Submissions
  submissions: {
    list: (p: ListParams & { status?: SubmissionStatus | string; from?: string; to?: string } = {}) =>
      get<Page<Submission>>(`/submissions${qs(p)}`),
    create: (body: { queue_ids: string[]; week_start: string }) =>
      post<Page<Submission> | Submission[]>(`/submissions`, body, true),
    detail: (id: string) => get<Submission>(`/submissions/${id}`),
    markSubmitted: (id: string, body?: { submitted_at?: string; adobe_reference?: string }) =>
      post<Submission>(`/submissions/${id}/mark-submitted`, body ?? {}, true),
    recordOutcome: (id: string, body: { items: { queue_id: string; outcome: "accepted" | "rejected"; reason?: string }[] }) =>
      post<Submission>(`/submissions/${id}/record-outcome`, body),
  },

  // §5.13 Analytics
  analytics: {
    overview: (from: string, to: string) =>
      get<AnalyticsOverview>(`/analytics/overview${qs({ from, to })}`),
    funnel: () => get<AnalyticsFunnel>("/analytics/funnel"),
    opportunityPerformance: (id: string) =>
      get<Record<string, unknown>>(`/analytics/opportunities/${id}/performance`),
    ingestEvents: (events: { name: string; entity_id?: string; route?: string; at?: string }[]) =>
      post<{ accepted: number }>("/analytics/events", { events }),
QQQ
      // Backend returns the standard Page envelope {data, pagination}; unwrap.
      const r = await get<Page<AnalyticsExport> | AnalyticsExport[]>("/analytics/exports");
      return Array.isArray(r) ? r : r.data;
    },
    requestExport: (body: { kind: string; from?: string; to?: string }) =>
      post<JobAccepted>("/analytics/exports", body, true),
  },

  // §5.14 Agents
  agents: {
    list: () => get<AgentDefinition[]>("/agents"),
    jobs: (
      p: ListParams & { status?: JobStatus | string; agent?: AgentName | string; run_kind?: AgentRunKind | string } = {},
    ) => get<Page<AgentJob>>(`/agents/jobs${qs(p)}`),
    job: (jobId: string) => get<AgentJob>(`/agents/jobs/${jobId}`),
    cancel: (jobId: string) => post<AgentJob>(`/agents/jobs/${jobId}/cancel`, {}),
    deadLetters: () => get<Page<AgentJob> | AgentJob[]>("/agents/dead-letters"),
    retry: (id: string) => post<AgentJob>(`/agents/dead-letters/${id}/retry`, {}, true),
    // NOTE: CONTRACT defines no dedicated logs endpoint; run output/errors
    // on the job payload are the full record (see Agents page).
  },

  // §5.15 Settings
  settings: {
    public: () => get<{ app_env: string; api_version: string; feature_flags: Record<string, boolean> }>("/settings/public"),
    get: () => get<SettingsMap>("/settings"),
    patch: (body: Record<string, unknown> | { settings: { key: string; value: unknown }[] }) =>
      patch<SettingsMap>("/settings", body),
    flags: () => get<Record<string, boolean>>("/settings/feature-flags"),
  },

  // §5.16 Notifications (ext)
  notifications: {
    list: (p: ListParams & { unread?: boolean; type?: NotificationType | string } = {}) =>
      get<NotificationList | Page<Notification>>(`/notifications${qs(p)}`),
    markRead: (id: string) => post<Notification>(`/notifications/${id}/read`, {}),
    markAllRead: () => post<{ marked: number }>("/notifications/read-all", {}),
  },

  // §5.17 Library (ext)
  library: {
    list: (p: ListParams & { kind?: SavedItemKind | string; q?: string } = {}) =>
      get<Page<SavedItem>>(`/library${qs(p)}`),
    save: (body: { item_kind: SavedItemKind; item_id: string; note?: string }) =>
      post<SavedItem>("/library", body),
    unsave: (id: string) => del<void>(`/library/${id}`),
  },

  // Phase 2 — Data sources (PHASE2_DESIGN.md §5)
  sources: {
    /** GET /api/sources — list sources with health summary + provenance. */
    list: () => get<Page<SourceSummary> | SourceSummary[]>("/sources"),
    /** GET /api/sources/{id} — detail + recent runs. */
    detail: (id: string) => get<SourceDetail>(`/sources/${id}`),
    /** GET /api/sources/health — all SourceHealth rows. */
    health: () => get<Page<SourceHealth> | SourceHealth[]>("/sources/health"),
    /** POST /api/sources/{id}/collect — manual collection → 202 + run id. */
    collect: (id: string) => post<CollectionRunAccepted>(`/sources/${id}/collect`, {}, true),
    /** GET /api/sources/runs — collection runs. */
    runs: (p: ListParams & { source_id?: string; status?: string; trigger?: string } = {}) =>
      get<Page<CollectionRun> | CollectionRun[]>(`/sources/runs${qs(p)}`),
    /** GET /api/sources/runs/{id} — one run. */
    run: (id: string) => get<CollectionRun>(`/sources/runs/${id}`),
  },

  // Phase 2 — Private performance (PHASE2_DESIGN.md §5)
  private: {
    /** GET /api/private/connection — honest NOT_CONFIGURED default; never carries secrets. */
    connection: () => get<AdobeConnection>("/private/connection"),
    /** PUT /api/private/connection — store session config server-side only. */
    saveConnection: (body: AdobeConnectionConfig) =>
      put<AdobeConnection>("/private/connection", body),
    /** POST /api/private/connection/test — validates config presence/format only. */
    testConnection: () => post<{ ok?: boolean; valid?: boolean; missing?: string[]; message?: string; detail?: string }>("/private/connection/test", {}),
    /** GET /api/private/performance/summary — empty-state when no data. */
    performanceSummary: () => get<PrivatePerformanceSummary>("/private/performance/summary"),
    /** GET /api/private/performance/categories */
    performanceCategories: () =>
      get<Page<PrivateCategoryPerformance> | PrivateCategoryPerformance[]>("/private/performance/categories"),
    /** GET /api/private/performance/keywords */
    performanceKeywords: () =>
      get<Page<PrivateKeywordPerformance> | PrivateKeywordPerformance[]>("/private/performance/keywords"),
  },

  // Phase 3 — Personal intelligence (PERSONAL INTELLIGENCE module)
  // CONTRACT: backend sibling implements these. Honest "not_configured" state
  // is a normal response — never treated as an error.
  personal: {
    /** GET /api/personal-performance?period=7d|30d|90d */
    performance: (period: PersonalPeriod) =>
      get<PersonalPerformanceSummary3>(`/personal-performance${qs({ period })}`),
    /** GET /api/personal-performance/categories?period= */
    categories: (period: PersonalPeriod) =>
      get<PersonalCategoriesResponse>(`/personal-performance/categories${qs({ period })}`),
    /** GET /api/personal-performance/content-types */
    contentTypes: () => get<ContentTypesResponse>("/personal-performance/content-types"),
    /** GET /api/personal-performance/themes */
    themes: () => get<PersonalThemesResponse>("/personal-performance/themes"),
  },

  // Phase 3 — Opportunity fusion (OPPORTUNITY FUSION module)
  fusion: {
    /** POST /api/opportunity-fusion/compute {opportunity_id} → fused score. */
    compute: (opportunity_id: string) =>
      post<FusionScore>("/opportunity-fusion/compute", { opportunity_id }, true),
    /** GET /api/opportunity-fusion/{opportunity_id} → latest fusion score. */
    latest: (opportunity_id: string) => get<FusionScore>(`/opportunity-fusion/${opportunity_id}`),
  },

  // Phase 3 — Daily production planner (DAILY PRODUCTION PLANNER module)
  daily: {
    /**
     * GET /api/daily-production/today → plan detail (or 404 when none built).
     * A 404 is the honest "no plan yet" state — returned as { plan: null, ... }
     * so the UI shows the Build call-to-action instead of an error.
     */
    plan: async (_date: string): Promise<DailyProductionResponse> => {
      try {
        const detail = await get<PlanDetail>(`/daily-production/today`);
        return { plan: detail, recommendations: detail.recommendations ?? [] };
      } catch (e) {
        if (e instanceof ApiClientError && e.status === 404) {
          return { plan: null, recommendations: [] };
        }
        throw e;
      }
    },
    /** POST /api/daily-production/build {plan_date} */
    build: async (date: string): Promise<DailyProductionResponse> => {
      const detail = await post<PlanDetail>("/daily-production/build", { plan_date: date }, true);
      return { plan: detail, recommendations: detail.recommendations ?? [] };
    },
    /** PUT /api/daily-production/settings */
    settings: () => get<CapacitySettings>("/daily-production/settings"),
    saveSettings: (body: Partial<CapacitySettings>) => put<CapacitySettings>("/daily-production/settings", body),
  },

  // Phase 3 — Production recommendations
  recommendations: {
    /** GET /api/production-recommendations */
    list: () => get<Page<ProductionRecommendation> | ProductionRecommendation[]>("/production-recommendations"),
    /** POST /api/production-recommendations/{id}/approve */
    approve: (id: string) =>
      post<ProductionRecommendation>(`/production-recommendations/${id}/approve`, {}, true),
    /** POST /api/production-recommendations/{id}/reject */
    reject: (id: string, reason?: string) =>
      post<ProductionRecommendation>(`/production-recommendations/${id}/reject`, { reason }),
    /** POST /api/production-recommendations/{id}/archive */
    archive: (id: string) => post<ProductionRecommendation>(`/production-recommendations/${id}/archive`, {}),
    /** PATCH /api/production-recommendations/{id} — edit/prioritize. */
    update: (id: string, body: Partial<ProductionRecommendation>) =>
      patch<ProductionRecommendation>(`/production-recommendations/${id}`, body),
    /** POST /api/production-recommendations/{id}/concepts — generate screened concepts. */
    generateConcepts: (id: string, count = 3) =>
      post<ConceptVariation[]>(`/production-recommendations/${id}/concepts`, { count }, true),
    /** GET /api/production-recommendations/{id}/concepts */
    concepts: (id: string) =>
      get<ConceptVariation[]>(`/production-recommendations/${id}/concepts`),
    /** PATCH /api/production-recommendations/concepts/{concept_id} — status + AI-disclosure decision. */
    updateConcept: (conceptId: string, body: { status: ConceptVariation["status"]; ai_disclosure?: boolean | null }) =>
      patch<ConceptVariation>(`/production-recommendations/concepts/${conceptId}`, body),
  },

  // Phase 3 — Prompt packs
  promptPacks: {
    /** POST /api/prompt-packs?concept_id= — build a deterministic pack from a concept. */
    create: (concept_id: string, target_tool = "muse") =>
      post<PromptPack>(`/prompt-packs${qs({ concept_id })}`, { target_tool }, true),
    /** GET /api/prompt-packs */
    list: () => get<Page<PromptPack> | PromptPack[]>("/prompt-packs"),
    /** GET /api/prompt-packs/{id} */
    detail: (id: string) => get<PromptPack>(`/prompt-packs/${id}`),
    /** POST /api/prompt-packs/{id}/export → download payload. */
    exportPack: (id: string) =>
      post<{ id: string; name: string; content: string; mime_type?: string }>(`/prompt-packs/${id}/export`, {}, true),
  },
};

export { idempotencyKey };
