/**
 * Centralized TanStack Query key factory — docs/11 §5.1.
 * Keys are the only source of truth for cache identity + invalidation.
 */
export const qk = {
  health: ["health"] as const,
  trends: {
    list: (params: Record<string, unknown>) => ["trends", "list", params] as const,
    detail: (id: string) => ["trends", "detail", id] as const,
    signals: (id: string) => ["trends", "signals", id] as const,
  },
  categories: {
    list: ["categories", "list"] as const,
    detail: (id: string) => ["categories", "detail", id] as const,
  },
  opportunities: {
    list: (params: Record<string, unknown>) => ["opportunities", "list", params] as const,
    detail: (id: string) => ["opportunities", "detail", id] as const,
  },
  ideas: {
    list: (params: Record<string, unknown>) => ["ideas", "list", params] as const,
    detail: (id: string) => ["ideas", "detail", id] as const,
  },
  prompts: {
    list: (params: Record<string, unknown>) => ["prompts", "list", params] as const,
    detail: (id: string) => ["prompts", "detail", id] as const,
    versions: (id: string) => ["prompts", "versions", id] as const,
  },
  compliance: {
    list: (params: Record<string, unknown>) => ["compliance", "list", params] as const,
    detail: (id: string) => ["compliance", "detail", id] as const,
  },
  similarity: {
    detail: (id: string) => ["similarity", "detail", id] as const,
  },
  assets: {
    list: (params: Record<string, unknown>) => ["assets", "list", params] as const,
    detail: (id: string) => ["assets", "detail", id] as const,
  },
  metadata: {
    list: (params: Record<string, unknown>) => ["metadata", "list", params] as const,
    detail: (id: string) => ["metadata", "detail", id] as const,
  },
  production: {
    queue: (params: Record<string, unknown>) => ["production", "queue", params] as const,
    detail: (id: string) => ["production", "detail", id] as const,
  },
  submissions: {
    list: (params: Record<string, unknown>) => ["submissions", "list", params] as const,
    detail: (id: string) => ["submissions", "detail", id] as const,
  },
  analytics: {
    overview: (from: string, to: string) => ["analytics", "overview", from, to] as const,
    funnel: ["analytics", "funnel"] as const,
    opportunityPerformance: (id: string) => ["analytics", "opportunity", id] as const,
    exports: ["analytics", "exports"] as const,
  },
  agents: {
    list: ["agents", "list"] as const,
    jobs: (params: Record<string, unknown>) => ["agents", "jobs", params] as const,
    job: (jobId: string) => ["agents", "job", jobId] as const,
    deadLetters: ["agents", "dead-letters"] as const,
  },
  settings: {
    all: ["settings", "all"] as const,
    public: ["settings", "public"] as const,
    flags: ["settings", "flags"] as const,
  },
  notifications: {
    list: (params: Record<string, unknown>) => ["notifications", "list", params] as const,
  },
  library: {
    list: (params: Record<string, unknown>) => ["library", "list", params] as const,
  },
  // Phase 2 — data sources + private performance (PHASE2_DESIGN.md §5)
  sources: {
    list: ["sources", "list"] as const,
    detail: (id: string) => ["sources", "detail", id] as const,
    health: ["sources", "health"] as const,
    runs: (params: Record<string, unknown>) => ["sources", "runs", params] as const,
    run: (id: string) => ["sources", "run", id] as const,
  },
  private: {
    connection: ["private", "connection"] as const,
    performanceSummary: ["private", "performance", "summary"] as const,
    performanceCategories: (params: Record<string, unknown>) =>
      ["private", "performance", "categories", params] as const,
    performanceKeywords: (params: Record<string, unknown>) =>
      ["private", "performance", "keywords", params] as const,
  },
  // Phase 3 — personal intelligence (PERSONAL INTELLIGENCE module)
  personal: {
    performance: (period: string) => ["personal", "performance", period] as const,
    categories: (period: string) => ["personal", "categories", period] as const,
    contentTypes: ["personal", "content-types"] as const,
    themes: ["personal", "themes"] as const,
  },
  // Phase 3 — opportunity fusion (OPPORTUNITY FUSION module)
  fusion: {
    score: (opportunityId: string) => ["fusion", "score", opportunityId] as const,
  },
  // Phase 3 — daily production planner (DAILY PRODUCTION PLANNER module)
  daily: {
    plan: (date: string) => ["daily", "plan", date] as const,
  },
  recommendations: {
    list: ["recommendations", "list"] as const,
    detail: (id: string) => ["recommendations", "detail", id] as const,
  },
  promptPacks: {
    list: ["prompt-packs", "list"] as const,
    detail: (id: string) => ["prompt-packs", "detail", id] as const,
  },
  // Product simplification — market intelligence + asset analysis
  marketIntelligence: {
    overview: ["market-intelligence", "overview"] as const,
  },
  assetAnalysis: {
    byOpportunity: (opportunityId: string, assetType: string) =>
      ["asset-analysis", "by-opportunity", opportunityId, assetType] as const,
  },
};