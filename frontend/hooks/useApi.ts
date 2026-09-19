"use client";
/**
 * TanStack Query hooks per domain — docs/11 §5.
 * Stale times follow docs/11 §5.1. Components consume these hooks, never `api` directly.
 */
import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryOptions,
} from "@tanstack/react-query";
import { useCallback, useRef, useState } from "react";
import { api, ApiClientError, errorMessage, type ListParams } from "../services/api";
import { qk } from "../services/queryKeys";
import { useJobPoll } from "./useJobPoll";
import type {
  AdobeConnection,
  AgentDefinition,
  AgentJob,
  AgentLog,
  AgentName,
  AgentRunKind,
  AnalyticsExport,
  AnalyticsFunnel,
  AnalyticsOverview,
  Asset,
  AssetType,
  CapacitySettings,
  Category,
  CollectionRun,
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
  JobStatus,
  MetadataBundle,
  Notification,
  NotificationList,
  NotificationType,
  Opportunity,
  OpportunityPerformance,
  OpportunityStatus,
  Page,
  PersonalCategoriesResponse,
  PersonalPerformanceSummary3,
  PersonalPeriod,
  PersonalThemesResponse,
  PrivateCategoryPerformance,
  PrivateKeywordPerformance,
  PrivatePerformanceSummary,
  ProductionRecommendation,
  Prompt,
  PromptPack,
  PromptStatus,
  QueueItem,
  QueueItemDetail,
  QueueStatus,
  ReviewDecision,
  SavedItem,
  SavedItemKind,
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
} from "../types";
import { useToast } from "../components/toast";

type QueryOpts<T> = Omit<UseQueryOptions<T, ApiClientError>, "queryKey" | "queryFn">;

const LIST = { staleTime: 2 * 60_000, gcTime: 15 * 60_000, placeholderData: keepPreviousData };
const DETAIL = { staleTime: 5 * 60_000, gcTime: 30 * 60_000 };
const QUEUE = { staleTime: 30_000, gcTime: 5 * 60_000 };
const REF = { staleTime: 24 * 60 * 60_000, gcTime: 7 * 24 * 60 * 60_000 };
const ANALYTICS_Q = { staleTime: 10 * 60_000, gcTime: 60 * 60_000 };

function toastOnError(toast: ReturnType<typeof useToast>["toast"]) {
  return (err: unknown) => {
    toast({ title: "Request failed", description: errorMessage(err), tone: "danger" });
  };
}

// ---------------------------------------------------------------- Health

export function useHealth(opts?: QueryOpts<HealthResponse>) {
  return useQuery<HealthResponse, ApiClientError>({
    queryKey: qk.health,
    queryFn: api.health,
    retry: false,
    ...opts,
  });
}

// ---------------------------------------------------------------- Trends

export function useTrends(
  params: { category?: string; window?: "7d" | "30d" | "90d"; min_score?: number } & ListParams = {},
  opts?: QueryOpts<Page<Trend>>,
) {
  return useQuery<Page<Trend>, ApiClientError>({
    queryKey: qk.trends.list(params),
    queryFn: () => api.trends.list(params),
    ...LIST,
    ...opts,
  });
}

export function useTrend(id: string | null, opts?: QueryOpts<TrendDetail>) {
  return useQuery<TrendDetail, ApiClientError>({
    queryKey: qk.trends.detail(id ?? ""),
    queryFn: () => api.trends.detail(id as string),
    enabled: !!id,
    ...DETAIL,
    ...opts,
  });
}

export function useTrendSignals(id: string | null, opts?: QueryOpts<TrendSignal[]>) {
  return useQuery<TrendSignal[], ApiClientError>({
    queryKey: qk.trends.signals(id ?? ""),
    queryFn: async () => {
      const r = await api.trends.signals(id as string);
      return Array.isArray(r) ? r : r.data;
    },
    enabled: !!id,
    ...DETAIL,
    ...opts,
  });
}

export function useRefreshTrends() {
  const { toast } = useToast();
  const qc = useQueryClient();
  const [jobId, setJobId] = useState<string | null>(null);
  const doneRef = useRef(false);

  // Invalidate every panel the analysis can change, so badges/cards cannot
  // disagree after the job finishes (queue depth, opportunities, capacity).
  const invalidateAnalysisOutputs = useCallback(() => {
    qc.invalidateQueries({ queryKey: ["trends"] });
    qc.invalidateQueries({ queryKey: ["opportunities"] });
    qc.invalidateQueries({ queryKey: ["production"] });
    qc.invalidateQueries({ queryKey: ["daily"] });
    qc.invalidateQueries({ queryKey: ["ideas"] });
    qc.invalidateQueries({ queryKey: ["agents"] });
  }, [qc]);

  const poll = useJobPoll(jobId, {
    onDone: (job) => {
      setJobId(null);
      if (doneRef.current) return;
      doneRef.current = true;
      if (job.status === "succeeded") {
        toast({ title: "Analysis complete", description: "Trend data refreshed — all panels updated.", tone: "success" });
      } else {
        toast({
          title: "Analysis failed",
          description: job.error?.message ?? `The analysis job ended as ${job.status}. No data was fabricated.`,
          tone: "danger",
        });
      }
      invalidateAnalysisOutputs();
    },
  });

  const mutation = useMutation({
    mutationFn: api.trends.refresh,
    onSuccess: (r) => {
      doneRef.current = false;
      setJobId(r.job_id);
      toast({ title: "Analysis started", description: `Job ${r.job_id.slice(0, 8)}… — progress is tracked until it finishes.`, tone: "info" });
    },
    onError: toastOnError(toast),
    onSettled: () => qc.invalidateQueries({ queryKey: ["trends"] }),
  });

  return {
    ...mutation,
    /** Latest polled job (null when idle). */
    analysisJob: poll.job,
    /** queued | running | succeeded | failed | cancelled | dead_letter | idle */
    analysisStatus: poll.status,
    /** True while a job is in flight — callers should disable re-triggering. */
    isAnalysisRunning: poll.isPolling || mutation.isPending,
  };
}

// ---------------------------------------------------------------- Categories

export function useCategories(opts?: QueryOpts<Category[]>) {
  return useQuery<Category[], ApiClientError>({
    queryKey: qk.categories.list,
    queryFn: api.categories.list,
    ...REF,
    ...opts,
  });
}

export function useCategory(id: string | null, opts?: QueryOpts<Category>) {
  return useQuery<Category, ApiClientError>({
    queryKey: qk.categories.detail(id ?? ""),
    queryFn: () => api.categories.detail(id as string),
    enabled: !!id,
    ...REF,
    ...opts,
  });
}

// ---------------------------------------------------------------- Opportunities

export function useOpportunities(
  params: { status?: OpportunityStatus | string; category?: string; min_score?: number } & ListParams = {},
  opts?: QueryOpts<Page<Opportunity>>,
) {
  return useQuery<Page<Opportunity>, ApiClientError>({
    queryKey: qk.opportunities.list(params),
    queryFn: () => api.opportunities.list(params),
    ...LIST,
    ...opts,
  });
}

export function useOpportunity(id: string | null, opts?: QueryOpts<Opportunity>) {
  return useQuery<Opportunity, ApiClientError>({
    queryKey: qk.opportunities.detail(id ?? ""),
    queryFn: () => api.opportunities.detail(id as string),
    enabled: !!id,
    ...DETAIL,
    ...opts,
  });
}

function invalidateOpportunities(qc: ReturnType<typeof useQueryClient>, id?: string) {
  qc.invalidateQueries({ queryKey: ["opportunities"] });
  if (id) qc.invalidateQueries({ queryKey: qk.opportunities.detail(id) });
}

export function useOpportunityMutations() {
  const { toast } = useToast();
  const qc = useQueryClient();
  const onErr = toastOnError(toast);
  return {
    approve: useMutation({
      mutationFn: (v: { id: string; priority?: "high" | "normal" | "low"; note?: string }) =>
        api.opportunities.approve(v.id, { priority: v.priority, note: v.note }),
      onSuccess: (_, v) => {
        toast({ title: "Opportunity approved", description: "It is now eligible for ideation.", tone: "success" });
        invalidateOpportunities(qc, v.id);
      },
      onError: onErr,
    }),
    reject: useMutation({
      mutationFn: (v: { id: string; reason: string }) => api.opportunities.reject(v.id, v.reason),
      onSuccess: (_, v) => {
        toast({ title: "Opportunity rejected", tone: "info" });
        invalidateOpportunities(qc, v.id);
      },
      onError: onErr,
    }),
    archive: useMutation({
      mutationFn: (id: string) => api.opportunities.archive(id),
      onSuccess: (_, id) => {
        toast({ title: "Opportunity archived", tone: "info" });
        invalidateOpportunities(qc, id);
      },
      onError: onErr,
    }),
    create: useMutation({
      mutationFn: api.opportunities.create,
      onSuccess: () => {
        toast({ title: "Opportunity created", tone: "success" });
        invalidateOpportunities(qc);
      },
      onError: onErr,
    }),
  };
}

// ---------------------------------------------------------------- Ideas

export function useIdeas(
  params: { kind?: IdeaKind; opportunity_id?: string; status?: IdeaStatus | string } & ListParams = {},
  opts?: QueryOpts<Page<Idea>>,
) {
  return useQuery<Page<Idea>, ApiClientError>({
    queryKey: qk.ideas.list(params),
    queryFn: () => api.ideas.list(params),
    ...LIST,
    ...opts,
  });
}

export function useIdea(id: string | null, opts?: QueryOpts<Idea>) {
  return useQuery<Idea, ApiClientError>({
    queryKey: qk.ideas.detail(id ?? ""),
    queryFn: () => api.ideas.detail(id as string),
    enabled: !!id,
    ...DETAIL,
    ...opts,
  });
}

export function useIdeaMutations() {
  const { toast } = useToast();
  const qc = useQueryClient();
  const onErr = toastOnError(toast);
  const inv = (id?: string) => {
    qc.invalidateQueries({ queryKey: ["ideas"] });
    if (id) qc.invalidateQueries({ queryKey: qk.ideas.detail(id) });
  };
  return {
    create: useMutation({
      mutationFn: api.ideas.create,
      onSuccess: (idea) => {
        toast({ title: "Idea saved", description: "Review it, then send it to Prompt Studio.", tone: "success" });
        inv(idea.id);
      },
      onError: onErr,
    }),
    update: useMutation({
      mutationFn: (v: { id: string; body: Partial<Idea> }) => api.ideas.update(v.id, v.body),
      onSuccess: (_, v) => {
        toast({ title: "Idea updated", tone: "success" });
        inv(v.id);
      },
      onError: onErr,
    }),
    generateConcepts: useMutation({
      mutationFn: (opportunityId: string | null) =>
        api.ideas.generateConcepts(opportunityId ?? undefined),
      onSuccess: (r) => {
        toast({ title: "Ideation started", description: `Job ${r.job_id.slice(0, 8)}…`, tone: "info" });
      },
      onError: onErr,
    }),
    archive: useMutation({
      mutationFn: (id: string) => api.ideas.archive(id),
      onSuccess: (_, id) => {
        toast({ title: "Idea archived", tone: "info" });
        inv(id);
      },
      onError: onErr,
    }),
  };
}

// ---------------------------------------------------------------- Prompts

export function usePrompts(
  params: { idea_id?: string; status?: PromptStatus | string; asset_type?: AssetType } & ListParams = {},
  opts?: QueryOpts<Page<Prompt>>,
) {
  return useQuery<Page<Prompt>, ApiClientError>({
    queryKey: qk.prompts.list(params),
    queryFn: () => api.prompts.list(params),
    ...LIST,
    ...opts,
  });
}

export function usePrompt(id: string | null, opts?: QueryOpts<Prompt>) {
  return useQuery<Prompt, ApiClientError>({
    queryKey: qk.prompts.detail(id ?? ""),
    queryFn: () => api.prompts.detail(id as string),
    enabled: !!id,
    ...DETAIL,
    ...opts,
  });
}

export function usePromptVersions(id: string | null) {
  return useQuery({
    queryKey: qk.prompts.versions(id ?? ""),
    queryFn: () => api.prompts.versions(id as string),
    enabled: !!id,
    ...DETAIL,
  });
}

export function usePromptMutations() {
  const { toast } = useToast();
  const qc = useQueryClient();
  const onErr = toastOnError(toast);
  const inv = (id?: string) => {
    qc.invalidateQueries({ queryKey: ["prompts"] });
    if (id) {
      qc.invalidateQueries({ queryKey: qk.prompts.detail(id) });
      qc.invalidateQueries({ queryKey: qk.prompts.versions(id) });
    }
  };
  return {
    generate: useMutation({
      mutationFn: (v: { idea_id: string; asset_type: AssetType; tool?: string }) => api.prompts.generate(v),
      onSuccess: (r) => {
        toast({ title: "Prompt generation started", description: `Job ${r.job_id.slice(0, 8)}…`, tone: "info" });
        return r;
      },
      onError: onErr,
    }),
    saveVersion: useMutation({
      mutationFn: (v: { id: string; body: Parameters<typeof api.prompts.saveVersion>[1] }) =>
        api.prompts.saveVersion(v.id, v.body),
      onSuccess: (_, v) => {
        toast({ title: "Version saved", tone: "success" });
        inv(v.id);
      },
      onError: onErr,
    }),
    regenerate: useMutation({
      mutationFn: (v: { id: string; feedback: string }) => api.prompts.regenerate(v.id, v.feedback),
      onSuccess: (r) => {
        toast({ title: "Regeneration started", description: `Job ${r.job_id.slice(0, 8)}…`, tone: "info" });
        return r;
      },
      onError: onErr,
    }),
    update: useMutation({
      mutationFn: (v: { id: string; body: { name?: string; status?: PromptStatus } }) =>
        api.prompts.update(v.id, v.body),
      onSuccess: (_, v) => {
        toast({ title: "Prompt updated", tone: "success" });
        inv(v.id);
      },
      onError: onErr,
    }),
  };
}

// ---------------------------------------------------------------- Compliance

export function useComplianceChecks(
  params: {
    result?: ComplianceResult | string;
    check_type?: ComplianceCheckType | string;
    subject_kind?: SubjectKind | string;
    pending_review?: boolean;
  } & ListParams = {},
  opts?: QueryOpts<Page<ComplianceCheck>>,
) {
  return useQuery<Page<ComplianceCheck>, ApiClientError>({
    queryKey: qk.compliance.list(params),
    queryFn: () => api.compliance.list(params),
    ...QUEUE,
    ...opts,
  });
}

export function useComplianceCheck(id: string | null, opts?: QueryOpts<ComplianceCheck>) {
  return useQuery<ComplianceCheck, ApiClientError>({
    queryKey: qk.compliance.detail(id ?? ""),
    queryFn: () => api.compliance.detail(id as string),
    enabled: !!id,
    ...DETAIL,
    ...opts,
  });
}

export function useComplianceMutations() {
  const { toast } = useToast();
  const qc = useQueryClient();
  const onErr = toastOnError(toast);
  return {
    runCheck: useMutation({
      mutationFn: api.compliance.runCheck,
      onSuccess: (r) => {
        const id = "job_id" in r ? r.job_id.slice(0, 8) : r.id.slice(0, 8);
        toast({ title: "Compliance check started", description: `Ref ${id}…`, tone: "info" });
        qc.invalidateQueries({ queryKey: ["compliance"] });
        return r;
      },
      onError: onErr,
    }),
    review: useMutation({
      mutationFn: (v: { id: string; decision: ReviewDecision; note?: string }) =>
        api.compliance.review(v.id, { decision: v.decision, note: v.note }),
      onSuccess: (c) => {
        toast({ title: "Review recorded", description: `Decision: ${c.review_decision}`, tone: "success" });
        qc.invalidateQueries({ queryKey: ["compliance"] });
        qc.invalidateQueries({ queryKey: ["production"] });
      },
      onError: onErr,
    }),
  };
}

// ---------------------------------------------------------------- Similarity

export function useSimilarityCheck(id: string | null, opts?: QueryOpts<SimilarityCheckResult>) {
  return useQuery<SimilarityCheckResult, ApiClientError>({
    queryKey: qk.similarity.detail(id ?? ""),
    queryFn: () => api.similarity.get(id as string),
    enabled: !!id,
    ...DETAIL,
    ...opts,
  });
}

export function useRunSimilarity() {
  const { toast } = useToast();
  return useMutation({
    mutationFn: api.similarity.runCheck,
    onSuccess: (r) => {
      toast({ title: "Similarity scan started", description: `Job ${r.job_id.slice(0, 8)}…`, tone: "info" });
      return r;
    },
    onError: toastOnError(toast),
  });
}

// ---------------------------------------------------------------- Assets

export function useAssets(
  params: { asset_type?: AssetType | string; status?: string; idea_id?: string; queue_id?: string } & ListParams = {},
  opts?: QueryOpts<Page<Asset>>,
) {
  return useQuery<Page<Asset>, ApiClientError>({
    queryKey: qk.assets.list(params),
    queryFn: () => api.assets.list(params),
    ...LIST,
    ...opts,
  });
}

export function useAsset(id: string | null, opts?: QueryOpts<Asset>) {
  return useQuery<Asset, ApiClientError>({
    queryKey: qk.assets.detail(id ?? ""),
    queryFn: () => api.assets.detail(id as string),
    enabled: !!id,
    ...DETAIL,
    ...opts,
  });
}

// ---------------------------------------------------------------- Metadata

export function useMetadataBundles(
  params: { asset_id?: string; is_current?: boolean } & ListParams = {},
  opts?: QueryOpts<Page<MetadataBundle>>,
) {
  return useQuery<Page<MetadataBundle>, ApiClientError>({
    queryKey: qk.metadata.list(params),
    queryFn: () => api.metadata.list(params),
    ...LIST,
    ...opts,
  });
}

export function useMetadataMutations() {
  const { toast } = useToast();
  const qc = useQueryClient();
  const onErr = toastOnError(toast);
  return {
    generate: useMutation({
      mutationFn: (asset_id: string) => api.metadata.generate(asset_id),
      onSuccess: (r) => {
        toast({ title: "Metadata draft started", description: `Job ${r.job_id.slice(0, 8)}…`, tone: "info" });
        return r;
      },
      onError: onErr,
    }),
    update: useMutation({
      mutationFn: (v: {
        id: string;
        body: { title?: string; description?: string; keywords?: string[]; adobe_category?: string };
      }) => api.metadata.update(v.id, v.body),
      onSuccess: () => {
        toast({ title: "Metadata saved", description: "A new version was created.", tone: "success" });
        qc.invalidateQueries({ queryKey: ["metadata"] });
      },
      onError: onErr,
    }),
    validate: useMutation({
      mutationFn: (id: string) => api.metadata.validate(id),
      onError: onErr,
    }),
  };
}

// ---------------------------------------------------------------- Production queue

export function useQueue(
  params: { status?: string; project_id?: string; paused?: boolean; overdue?: boolean } & ListParams = {},
  opts?: QueryOpts<Page<QueueItem>>,
) {
  return useQuery<Page<QueueItem>, ApiClientError>({
    queryKey: qk.production.queue(params),
    queryFn: () => api.production.queue(params),
    ...QUEUE,
    ...opts,
  });
}

export function useQueueItem(id: string | null, opts?: QueryOpts<QueueItemDetail>) {
  return useQuery<QueueItemDetail, ApiClientError>({
    queryKey: qk.production.detail(id ?? ""),
    queryFn: () => api.production.detail(id as string),
    enabled: !!id,
    ...DETAIL,
    ...opts,
  });
}

export function useQueueMutations() {
  const { toast } = useToast();
  const qc = useQueryClient();
  const onErr = toastOnError(toast);
  const inv = (id?: string) => {
    qc.invalidateQueries({ queryKey: ["production"] });
    if (id) qc.invalidateQueries({ queryKey: qk.production.detail(id) });
  };
  return {
    enqueue: useMutation({
      mutationFn: api.production.enqueue,
      onSuccess: (item) => {
        toast({ title: "Added to queue", description: item.title, tone: "success" });
        inv(item.id);
      },
      onError: onErr,
    }),
    transition: useMutation({
      mutationFn: (v: { id: string; to: QueueStatus; note?: string }) =>
        api.production.transition(v.id, { to: v.to, note: v.note }),
      onSuccess: (_, v) => {
        toast({ title: "Queue updated", description: `Moved to ${v.to.replace(/_/g, " ").toLowerCase()}.`, tone: "success" });
        inv(v.id);
      },
      onError: (err: unknown, v) => {
        // Surface the contract's allowed-list hint from INVALID_TRANSITION details.
        const envelope = (err as { envelope?: unknown } | null | undefined)?.envelope as
          | { details?: unknown; message?: unknown }
          | undefined;
        const allowedRaw = (envelope?.details as { allowed?: unknown } | undefined)?.allowed;
        const allowed = Array.isArray(allowedRaw)
          ? allowedRaw.filter((x): x is string => typeof x === "string")
          : [];
        toast({
          title: "Transition not allowed",
          description: allowed.length
            ? `Allowed from here: ${allowed.join(", ")}.`
            : errorMessage(err),
          tone: "danger",
        });
        inv(v.id);
      },
    }),
    pause: useMutation({
      mutationFn: (v: { id: string; paused: boolean; reason?: string }) =>
        api.production.pause(v.id, { paused: v.paused, reason: v.reason }),
      onSuccess: (_, v) => {
        toast({ title: v.paused ? "Item paused" : "Item resumed", tone: "info" });
        inv(v.id);
      },
      onError: onErr,
    }),
  };
}

// ---------------------------------------------------------------- Submissions

export function useSubmissions(
  params: { status?: SubmissionStatus | string; from?: string; to?: string } & ListParams = {},
  opts?: QueryOpts<Page<Submission>>,
) {
  return useQuery<Page<Submission>, ApiClientError>({
    queryKey: qk.submissions.list(params),
    queryFn: () => api.submissions.list(params),
    ...LIST,
    ...opts,
  });
}

export function useSubmissionMutations() {
  const { toast } = useToast();
  const qc = useQueryClient();
  const onErr = toastOnError(toast);
  return {
    createPlan: useMutation({
      mutationFn: (v: { queue_ids: string[]; week_start: string }) => api.submissions.create(v),
      onSuccess: () => {
        toast({ title: "Submission plan created", tone: "success" });
        qc.invalidateQueries({ queryKey: ["submissions"] });
      },
      onError: onErr,
    }),
    markSubmitted: useMutation({
      mutationFn: (v: { id: string; submitted_at?: string; adobe_reference?: string }) =>
        api.submissions.markSubmitted(v.id, { submitted_at: v.submitted_at, adobe_reference: v.adobe_reference }),
      onSuccess: () => {
        toast({ title: "Marked as submitted", description: "Recorded as your manual upload.", tone: "success" });
        qc.invalidateQueries({ queryKey: ["submissions"] });
        qc.invalidateQueries({ queryKey: ["production"] });
      },
      onError: onErr,
    }),
    recordOutcome: useMutation({
      mutationFn: (v: {
        id: string;
        items: { queue_id: string; outcome: "accepted" | "rejected"; reason?: string }[];
      }) => api.submissions.recordOutcome(v.id, { items: v.items }),
      onSuccess: () => {
        toast({ title: "Outcome recorded", description: "Feeds your analytics.", tone: "success" });
        qc.invalidateQueries({ queryKey: ["submissions"] });
        qc.invalidateQueries({ queryKey: ["analytics"] });
      },
      onError: onErr,
    }),
  };
}

// ---------------------------------------------------------------- Analytics

export function useAnalyticsOverview(from: string, to: string, opts?: QueryOpts<AnalyticsOverview>) {
  return useQuery<AnalyticsOverview, ApiClientError>({
    queryKey: qk.analytics.overview(from, to),
    queryFn: () => api.analytics.overview(from, to),
    ...ANALYTICS_Q,
    ...opts,
  });
}

export function useAnalyticsFunnel(opts?: QueryOpts<AnalyticsFunnel>) {
  return useQuery<AnalyticsFunnel, ApiClientError>({
    queryKey: qk.analytics.funnel,
    queryFn: api.analytics.funnel,
    ...ANALYTICS_Q,
    ...opts,
  });
}

export function useOpportunityPerformance(id: string | null, opts?: QueryOpts<OpportunityPerformance>) {
  return useQuery<OpportunityPerformance, ApiClientError>({
    queryKey: qk.analytics.opportunityPerformance(id ?? ""),
    queryFn: async () => api.analytics.opportunityPerformance(id as string) as unknown as OpportunityPerformance,
    enabled: !!id,
    ...ANALYTICS_Q,
    ...opts,
  });
}

export function useAnalyticsExports(opts?: QueryOpts<AnalyticsExport[]>) {
  return useQuery<AnalyticsExport[], ApiClientError>({
    queryKey: qk.analytics.exports,
    queryFn: api.analytics.exports,
    ...ANALYTICS_Q,
    ...opts,
  });
}

export function useRequestExport() {
  const { toast } = useToast();
  return useMutation({
    mutationFn: api.analytics.requestExport,
    onSuccess: (r) => {
      toast({ title: "Export requested", description: `Job ${r.job_id.slice(0, 8)}…`, tone: "info" });
      return r;
    },
    onError: toastOnError(toast),
  });
}

// ---------------------------------------------------------------- Agents

export function useAgents(opts?: QueryOpts<AgentDefinition[]>) {
  return useQuery<AgentDefinition[], ApiClientError>({
    queryKey: qk.agents.list,
    queryFn: api.agents.list,
    ...QUEUE,
    ...opts,
  });
}

export function useAgentJobs(
  params: { status?: JobStatus | string; agent?: AgentName | string; run_kind?: AgentRunKind | string } & ListParams = {},
  opts?: QueryOpts<Page<AgentJob>>,
) {
  return useQuery<Page<AgentJob>, ApiClientError>({
    queryKey: qk.agents.jobs(params),
    queryFn: () => api.agents.jobs(params),
    ...QUEUE,
    ...opts,
  });
}

export function useAgentJob(jobId: string | null, opts?: QueryOpts<AgentJob>) {
  return useQuery<AgentJob, ApiClientError>({
    queryKey: qk.agents.job(jobId ?? ""),
    queryFn: () => api.agents.job(jobId as string),
    enabled: !!jobId,
    ...opts,
  });
}

/**
 * Agent run logs — CONTRACT defines no dedicated logs endpoint; logs ride on
 * the job payload (AgentJob.logs), so this derives them from the job detail.
 */
export function useAgentLogs(jobId: string | null, opts?: QueryOpts<AgentLog[]>) {
  return useQuery<AgentLog[], ApiClientError>({
    queryKey: ["agents", "logs", jobId ?? ""],
    queryFn: async () => (await api.agents.job(jobId as string)).logs ?? [],
    enabled: !!jobId,
    ...QUEUE,
    ...opts,
  });
}

export function useDeadLetters(opts?: QueryOpts<AgentJob[]>) {
  return useQuery<AgentJob[], ApiClientError>({
    queryKey: qk.agents.deadLetters,
    queryFn: async () => {
      const r = await api.agents.deadLetters();
      return Array.isArray(r) ? r : r.data;
    },
    ...QUEUE,
    ...opts,
  });
}

export function useRetryDeadLetter() {
  const { toast } = useToast();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.agents.retry(id),
    onSuccess: () => {
      toast({ title: "Job requeued", description: "The dead-letter job was sent back to the queue.", tone: "success" });
      qc.invalidateQueries({ queryKey: ["agents"] });
    },
    onError: toastOnError(toast),
  });
}

export function useCancelJob() {
  const { toast } = useToast();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (jobId: string) => api.agents.cancel(jobId),
    onSuccess: () => {
      toast({ title: "Job cancelled", tone: "info" });
      qc.invalidateQueries({ queryKey: ["agents"] });
    },
    onError: toastOnError(toast),
  });
}

// ---------------------------------------------------------------- Settings

export function useSettings(opts?: QueryOpts<Record<string, unknown>>) {
  return useQuery<Record<string, unknown>, ApiClientError>({
    queryKey: qk.settings.all,
    queryFn: api.settings.get,
    staleTime: 5 * 60_000,
    ...opts,
  });
}

export function useSettingsMutations() {
  const { toast } = useToast();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.settings.patch(body),
    onSuccess: () => {
      toast({ title: "Settings saved", tone: "success" });
      qc.invalidateQueries({ queryKey: ["settings"] });
    },
    onError: toastOnError(toast),
  });
}

// ---------------------------------------------------------------- Notifications

export function useNotifications(
  params: { unread?: boolean; type?: NotificationType | string } & ListParams = {},
  opts?: QueryOpts<{ data: Notification[]; unread_count: number }>,
) {
  return useQuery<{ data: Notification[]; unread_count: number }, ApiClientError>({
    queryKey: qk.notifications.list(params),
    queryFn: async () => {
      const r = await api.notifications.list(params);
      if ("unread_count" in r) return { data: r.data, unread_count: r.unread_count };
      const total = (r as Page<Notification>).pagination?.total ?? r.data.length;
      const unread = r.data.filter((n) => !n.is_read).length;
      return { data: r.data, unread_count: params.unread ? total : unread };
    },
    ...QUEUE,
    ...opts,
  });
}

export function useNotificationMutations() {
  const qc = useQueryClient();
  return {
    markRead: useMutation({
      mutationFn: (id: string) => api.notifications.markRead(id),
      onSettled: () => qc.invalidateQueries({ queryKey: ["notifications"] }),
    }),
    markAllRead: useMutation({
      mutationFn: api.notifications.markAllRead,
      onSettled: () => qc.invalidateQueries({ queryKey: ["notifications"] }),
    }),
  };
}

// ---------------------------------------------------------------- Library

export function useLibrary(
  params: { kind?: SavedItemKind | string; q?: string } & ListParams = {},
  opts?: QueryOpts<Page<SavedItem>>,
) {
  return useQuery<Page<SavedItem>, ApiClientError>({
    queryKey: qk.library.list(params),
    queryFn: () => api.library.list(params),
    ...LIST,
    ...opts,
  });
}

export function useLibraryMutations() {
  const { toast } = useToast();
  const qc = useQueryClient();
  return {
    save: useMutation({
      mutationFn: (v: { item_kind: SavedItemKind; item_id: string; note?: string }) => api.library.save(v),
      onSuccess: () => {
        toast({ title: "Saved to library", tone: "success" });
        qc.invalidateQueries({ queryKey: ["library"] });
      },
      onError: toastOnError(toast),
    }),
    unsave: useMutation({
      mutationFn: (id: string) => api.library.unsave(id),
      onSuccess: () => {
        toast({ title: "Removed from library", tone: "info" });
        qc.invalidateQueries({ queryKey: ["library"] });
      },
      onError: toastOnError(toast),
    }),
  };
}

// ---------------------------------------------------------------- Phase 2: data sources (PHASE2_DESIGN.md §5)

const SOURCE_Q = { staleTime: 60_000, gcTime: 5 * 60_000 };

/** Normalize a list response that may be a paginated Page or a bare array. */
function asPage<T>(r: Page<T> | T[], fallback: Page<T>): Page<T> {
  if (Array.isArray(r)) {
    return { data: r, pagination: { page: 1, page_size: r.length, total: r.length, total_pages: 1 } };
  }
  return r ?? fallback;
}

function asArray<T>(r: Page<T> | T[] | undefined | null): T[] {
  if (!r) return [];
  return Array.isArray(r) ? r : (r.data ?? []);
}

export function useSources(opts?: QueryOpts<SourceSummary[]>) {
  return useQuery<SourceSummary[], ApiClientError>({
    queryKey: qk.sources.list,
    queryFn: async () => asArray(await api.sources.list()),
    ...SOURCE_Q,
    ...opts,
  });
}

export function useSource(id: string | null, opts?: QueryOpts<SourceDetail>) {
  return useQuery<SourceDetail, ApiClientError>({
    queryKey: qk.sources.detail(id ?? ""),
    queryFn: () => api.sources.detail(id as string),
    enabled: !!id,
    ...DETAIL,
    ...opts,
  });
}

export function useSourceHealth(opts?: QueryOpts<SourceHealth[]>) {
  return useQuery<SourceHealth[], ApiClientError>({
    queryKey: qk.sources.health,
    queryFn: async () => asArray(await api.sources.health()),
    ...SOURCE_Q,
    ...opts,
  });
}

export function useCollectionRuns(
  params: { page?: number; page_size?: number; source_id?: string; status?: string; trigger?: string } = {},
  opts?: QueryOpts<Page<CollectionRun>>,
) {
  return useQuery<Page<CollectionRun>, ApiClientError>({
    queryKey: qk.sources.runs(params),
    queryFn: async () => asPage(await api.sources.runs(params), {
      data: [], pagination: { page: 1, page_size: 20, total: 0, total_pages: 0 },
    }),
    ...SOURCE_Q,
    ...opts,
  });
}

export function useCollectionRun(id: string | null, opts?: QueryOpts<CollectionRun>) {
  return useQuery<CollectionRun, ApiClientError>({
    queryKey: qk.sources.run(id ?? ""),
    queryFn: () => api.sources.run(id as string),
    enabled: !!id,
    ...DETAIL,
    ...opts,
  });
}

/** POST /api/sources/{id}/collect — manual collection (rate-limited server-side). */
export function useCollectSource() {
  const { toast } = useToast();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.sources.collect(id),
    onSuccess: (r, id) => {
      toast({
        title: "Collection started",
        description: `Run ${(r.run_id ?? r.job_id ?? "").slice(0, 8)}… — the run row will update as it finishes.`,
        tone: "info",
      });
      qc.invalidateQueries({ queryKey: ["sources"] });
      return id;
    },
    onError: toastOnError(toast),
  });
}

// ---------------------------------------------------------------- Phase 2: private performance (PHASE2_DESIGN.md §5)

export function useAdobeConnection(opts?: QueryOpts<AdobeConnection>) {
  return useQuery<AdobeConnection, ApiClientError>({
    queryKey: qk.private.connection,
    queryFn: api.private.connection,
    ...SOURCE_Q,
    ...opts,
  });
}

export function useAdobeConnectionMutations() {
  const { toast } = useToast();
  const qc = useQueryClient();
  const onErr = toastOnError(toast);
  return {
    save: useMutation({
      // PUT /api/private/connection — secrets stay server-side, never echoed.
      mutationFn: api.private.saveConnection,
      onSuccess: (conn) => {
        toast({ title: "Connection saved", description: `Status: ${String(conn.status).replace(/_/g, " ").toLowerCase()}.`, tone: "success" });
        qc.invalidateQueries({ queryKey: ["private"] });
      },
      onError: onErr,
    }),
    test: useMutation({
      // POST /api/private/connection/test — validates config presence/format only.
      mutationFn: () => api.private.testConnection(),
      onSuccess: (r) => {
        const ok = r.ok ?? r.valid ?? false;
        const missing = r.missing?.length ? ` Missing: ${r.missing.join("; ")}` : "";
        toast({
          title: ok ? "Connection test passed" : "Connection test failed",
          description: `${r.message ?? ""}${missing}`.trim() || undefined,
          tone: ok ? "success" : "danger",
        });
        qc.invalidateQueries({ queryKey: ["private"] });
        return r;
      },
      onError: onErr,
    }),
  };
}

export function usePrivatePerformanceSummary(opts?: QueryOpts<PrivatePerformanceSummary>) {
  return useQuery<PrivatePerformanceSummary, ApiClientError>({
    queryKey: qk.private.performanceSummary,
    queryFn: api.private.performanceSummary,
    staleTime: 10 * 60_000,
    gcTime: 60 * 60_000,
    ...opts,
  });
}

export function usePrivateCategories(opts?: QueryOpts<PrivateCategoryPerformance[]>) {
  return useQuery<PrivateCategoryPerformance[], ApiClientError>({
    queryKey: qk.private.performanceCategories({}),
    queryFn: async () => asArray(await api.private.performanceCategories()),
    staleTime: 10 * 60_000,
    ...opts,
  });
}

export function usePrivateKeywords(opts?: QueryOpts<PrivateKeywordPerformance[]>) {
  return useQuery<PrivateKeywordPerformance[], ApiClientError>({
    queryKey: qk.private.performanceKeywords({}),
    queryFn: async () => asArray(await api.private.performanceKeywords()),
    staleTime: 10 * 60_000,
    ...opts,
  });
}

// ---------------------------------------------------------------- Phase 3: personal intelligence (PERSONAL INTELLIGENCE module)
// ----------------------------------------------------------------

const PERSONAL_Q = { staleTime: 10 * 60_000, gcTime: 30 * 60_000 };

/**
 * Personal performance summary for a period. The backend returns
 * {status:"not_configured", ...} when no private data is connected — that is a
 * normal response, not an error; callers render the honest empty state.
 */
export function usePersonalPerformance(
  period: PersonalPeriod = "30d",
  opts?: QueryOpts<PersonalPerformanceSummary3>,
) {
  return useQuery<PersonalPerformanceSummary3, ApiClientError>({
    queryKey: qk.personal.performance(period),
    queryFn: () => api.personal.performance(period),
    retry: false,
    ...PERSONAL_Q,
    ...opts,
  });
}

export function usePersonalCategories(
  period: PersonalPeriod = "30d",
  opts?: QueryOpts<PersonalCategoriesResponse>,
) {
  return useQuery<PersonalCategoriesResponse, ApiClientError>({
    queryKey: qk.personal.categories(period),
    queryFn: () => api.personal.categories(period),
    retry: false,
    ...PERSONAL_Q,
    ...opts,
  });
}

export function useContentTypes(opts?: QueryOpts<ContentTypesResponse>) {
  return useQuery<ContentTypesResponse, ApiClientError>({
    queryKey: qk.personal.contentTypes,
    queryFn: api.personal.contentTypes,
    retry: false,
    ...PERSONAL_Q,
    ...opts,
  });
}

export function usePersonalThemes(opts?: QueryOpts<PersonalThemesResponse>) {
  return useQuery<PersonalThemesResponse, ApiClientError>({
    queryKey: qk.personal.themes,
    queryFn: api.personal.themes,
    retry: false,
    ...PERSONAL_Q,
    ...opts,
  });
}

// ---------------------------------------------------------------- Phase 3: opportunity fusion (OPPORTUNITY FUSION module)
// ----------------------------------------------------------------

const FUSION_Q = { staleTime: 5 * 60_000, gcTime: 30 * 60_000 };

/** Latest fusion score for an opportunity (404/missing = not computed yet). */
export function useFusionScore(opportunityId: string | null, opts?: QueryOpts<FusionScore>) {
  return useQuery<FusionScore, ApiClientError>({
    queryKey: qk.fusion.score(opportunityId ?? ""),
    queryFn: () => api.fusion.latest(opportunityId as string),
    enabled: !!opportunityId,
    retry: false,
    ...FUSION_Q,
    ...opts,
  });
}

export function useFusionMutations() {
  const { toast } = useToast();
  const qc = useQueryClient();
  return {
    compute: useMutation({
      mutationFn: (opportunity_id: string) => api.fusion.compute(opportunity_id),
      onSuccess: (r) => {
        toast({
          title: "Fusion score computed",
          description: `${r.label} · unified ${Math.round(r.unified_score)} · confidence ${Math.round((r.confidence_score <= 1 ? r.confidence_score * 100 : r.confidence_score))}%`,
          tone: "success",
        });
        qc.invalidateQueries({ queryKey: qk.fusion.score(r.opportunity_id) });
        qc.invalidateQueries({ queryKey: ["daily"] });
        qc.invalidateQueries({ queryKey: ["recommendations"] });
      },
      onError: toastOnError(toast),
    }),
  };
}

// ---------------------------------------------------------------- Phase 3: daily production planner (DAILY PRODUCTION PLANNER module)
// ----------------------------------------------------------------

const DAILY_Q = { staleTime: 2 * 60_000, gcTime: 10 * 60_000 };

export function useDailyPlan(date: string, opts?: QueryOpts<DailyProductionResponse>) {
  return useQuery<DailyProductionResponse, ApiClientError>({
    queryKey: qk.daily.plan(date),
    queryFn: () => api.daily.plan(date),
    retry: false,
    ...DAILY_Q,
    ...opts,
  });
}

export function useDailySettings(opts?: QueryOpts<CapacitySettings>) {
  return useQuery<CapacitySettings, ApiClientError>({
    queryKey: ["daily", "settings"] as const,
    queryFn: api.daily.settings,
    retry: false,
    staleTime: 5 * 60_000,
    ...opts,
  });
}

export function useDailyMutations() {
  const { toast } = useToast();
  const qc = useQueryClient();
  const onErr = toastOnError(toast);
  const inv = (date?: string) => {
    qc.invalidateQueries({ queryKey: ["daily"] });
    if (date) qc.invalidateQueries({ queryKey: qk.daily.plan(date) });
  };
  return {
    build: useMutation({
      mutationFn: (date: string) => api.daily.build(date),
      onSuccess: (_, date) => {
        toast({ title: "Production plan built", description: `Plan for ${date} is ready.`, tone: "success" });
        inv(date);
        qc.invalidateQueries({ queryKey: ["recommendations"] });
      },
      onError: onErr,
    }),
    saveSettings: useMutation({
      mutationFn: (body: Partial<CapacitySettings>) => api.daily.saveSettings(body),
      onSuccess: () => {
        toast({ title: "Capacity settings saved", tone: "success" });
        qc.invalidateQueries({ queryKey: ["daily"] });
      },
      onError: onErr,
    }),
  };
}

// ---------------------------------------------------------------- Phase 3: production recommendations
// ----------------------------------------------------------------

export function useProductionRecommendations(opts?: QueryOpts<ProductionRecommendation[]>) {
  return useQuery<ProductionRecommendation[], ApiClientError>({
    queryKey: qk.recommendations.list,
    queryFn: async () => asArray(await api.recommendations.list()),
    retry: false,
    ...DAILY_Q,
    ...opts,
  });
}

export function useProductionRecommendationMutations() {
  const { toast } = useToast();
  const qc = useQueryClient();
  const onErr = toastOnError(toast);
  const inv = () => {
    qc.invalidateQueries({ queryKey: ["recommendations"] });
    qc.invalidateQueries({ queryKey: ["daily"] });
  };
  return {
    approve: useMutation({
      mutationFn: (id: string) => api.recommendations.approve(id),
      onSuccess: () => {
        toast({ title: "Recommendation approved", tone: "success" });
        inv();
      },
      onError: onErr,
    }),
    reject: useMutation({
      mutationFn: (v: { id: string; reason?: string }) => api.recommendations.reject(v.id, v.reason),
      onSuccess: () => {
        toast({ title: "Recommendation rejected", tone: "info" });
        inv();
      },
      onError: onErr,
    }),
    archive: useMutation({
      mutationFn: (id: string) => api.recommendations.archive(id),
      onSuccess: () => {
        toast({ title: "Recommendation archived", tone: "info" });
        inv();
      },
      onError: onErr,
    }),
    update: useMutation({
      mutationFn: (v: { id: string; body: Partial<ProductionRecommendation> }) =>
        api.recommendations.update(v.id, v.body),
      onSuccess: () => {
        toast({ title: "Recommendation updated", tone: "success" });
        inv();
      },
      onError: onErr,
    }),
  };
}

// ---------------------------------------------------------------- Phase 3: prompt packs
// ----------------------------------------------------------------

export function usePromptPacks(opts?: QueryOpts<PromptPack[]>) {
  return useQuery<PromptPack[], ApiClientError>({
    queryKey: qk.promptPacks.list,
    queryFn: async () => asArray(await api.promptPacks.list()),
    retry: false,
    ...DETAIL,
    ...opts,
  });
}

export function usePromptPack(id: string | null, opts?: QueryOpts<PromptPack>) {
  return useQuery<PromptPack, ApiClientError>({
    queryKey: qk.promptPacks.detail(id ?? ""),
    queryFn: () => api.promptPacks.detail(id as string),
    enabled: !!id,
    retry: false,
    ...DETAIL,
    ...opts,
  });
}

export function usePromptPackExport() {
  const { toast } = useToast();
  return useMutation({
    mutationFn: (id: string) => api.promptPacks.exportPack(id),
    onSuccess: (r) => {
      // Export payload is a file — download it, never paste it into a chat.
      const blob = new Blob([r.content], { type: r.mime_type ?? "text/markdown" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${r.name.replace(/[^\w\-]+/g, "-").toLowerCase() || "prompt-pack"}.md`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 5000);
      toast({ title: "Prompt pack exported", description: `Downloaded “${r.name}”.`, tone: "success" });
    },
    onError: toastOnError(toast),
  });
}

// ---------------------------------------------------------------- Phase 3: concept variations
// ----------------------------------------------------------------

export function useConcepts(recId: string | null, opts?: QueryOpts<ConceptVariation[]>) {
  return useQuery<ConceptVariation[], ApiClientError>({
    queryKey: ["recommendations", recId ?? "", "concepts"] as const,
    queryFn: () => api.recommendations.concepts(recId as string),
    enabled: !!recId,
    retry: false,
    ...DETAIL,
    ...opts,
  });
}

export function useConceptMutations() {
  const { toast } = useToast();
  const qc = useQueryClient();
  const inv = (recId: string) => {
    qc.invalidateQueries({ queryKey: ["recommendations", recId, "concepts"] });
    qc.invalidateQueries({ queryKey: ["recommendations"] });
    qc.invalidateQueries({ queryKey: ["daily"] });
  };
  return {
    generate: useMutation({
      mutationFn: (v: { recId: string; count?: number }) =>
        api.recommendations.generateConcepts(v.recId, v.count ?? 3),
      onSuccess: (_r, v) => {
        toast({ title: "Concepts generated", description: "Screened for originality and compliance.", tone: "success" });
        inv(v.recId);
      },
      onError: toastOnError(toast),
    }),
    update: useMutation({
      mutationFn: (v: { recId: string; conceptId: string; body: { status: ConceptVariation["status"]; ai_disclosure?: boolean | null } }) =>
        api.recommendations.updateConcept(v.conceptId, v.body),
      onSuccess: (_r, v) => {
        toast({ title: "Concept updated", tone: "success" });
        inv(v.recId);
      },
      onError: toastOnError(toast),
    }),
  };
}

// ---------------------------------------------------------------- Phase 3: prompt-pack creation
// ----------------------------------------------------------------

export function usePromptPackCreate() {
  const { toast } = useToast();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { conceptId: string; target_tool?: string }) =>
      api.promptPacks.create(v.conceptId, v.target_tool ?? "muse"),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.promptPacks.list });
      toast({ title: "Prompt pack created", description: "Export it and paste into your generation tool — nothing auto-generates.", tone: "success" });
    },
    onError: toastOnError(toast),
  });
}
