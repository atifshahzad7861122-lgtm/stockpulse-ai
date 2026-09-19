"use client";
/**
 * Dashboard — answers "WHAT SHOULD I CREATE TODAY?" (docs/05 §3).
 * Panels load independently; a failed panel shows its own error card (docs/05 §3.3).
 */
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  AlertTriangle,
  ArrowRight,
  ArrowUpRight,
  Bot,
  Play,
  TrendingUp,
  Wallet,
} from "lucide-react";
import {
  Badge,
  Banner,
  Button,
  EmptyState,
  KpiCard,
  PageHeader,
  Panel,
  QueryView,
  Skeleton,
  WhyThis,
  cx,
} from "../components/ui";
import {
  ComplianceChip,
  ConfidenceMeter,
  ProvenanceBadge,
  ScoreInline,
  isMock,
} from "../components/scores";
import { MiniBars } from "../components/charts";
import { Stagger, StaggerItem } from "../components/motion/motion";
import {
  useAgentJobs,
  useAnalyticsOverview,
  useComplianceChecks,
  useOpportunities,
  useQueue,
  useRefreshTrends,
  useSettings,
  useTrends,
  useSources,
  useAdobeConnection,
  usePrivatePerformanceSummary,
  useCollectionRuns,
} from "../hooks/useApi";
import { OpportunityCard, isActionable } from "../features/opportunities/OpportunityCard";
import {
  LiveBadge,
  SourceStatusChip,
  isLiveHealth,
  lastSuccessOf,
} from "../components/sources";
import type { Opportunity, QueueStatus } from "../types";
import { daysAgoISO, fmtInt, fmtPct01, timeAgo, todayISO } from "../lib/format";
import { stateLabel } from "../lib/transitions";

// ---------------------------------------------------------------- Hero strip

function CreateTodayHero() {
  const router = useRouter();
  const opps = useOpportunities({ sort: "-opportunity_score", page_size: 10, status: "approved" });

  return (
    <Panel
      title={<span className="font-display text-base">What should I create today?</span>}
      action={
        <Button size="sm" variant="ghost" onClick={() => router.push("/opportunities")}>
          All opportunities <ArrowRight size={13} />
        </Button>
      }
      className="border-l-2 border-l-accent-primary"
    >
      <QueryView
        query={opps}
        loading={<div className="space-y-3">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-16" />)}</div>}
        empty={
          <EmptyState
            compact
            title="No strong recommendations today"
            description="Nothing clears the quality bar (opportunity score ≥ 55 with confidence ≥ 50%). Check back after the next daily analysis."
            action={<RunAnalysisButton />}
          />
        }
        errorTitle="Could not load recommendations"
      >
        {(page) => {
          const actionable = page.data.filter(isActionable).slice(0, 3);
          if (!actionable.length)
            return (
              <EmptyState
                compact
                title="No strong recommendations today"
                description={`${page.data.length} opportunities scanned — none clear the quality bar (score ≥ 55, confidence ≥ 50%). Honest selectivity beats padded lists.`}
                action={<RunAnalysisButton />}
              />
            );
          return (
            <Stagger className="space-y-2.5" gap={0.05}>
              {actionable.map((o, i) => (
                <StaggerItem key={o.id}>
                  <HeroRow opp={o} rank={i + 1} />
                </StaggerItem>
              ))}
            </Stagger>
          );
        }}
      </QueryView>
    </Panel>
  );
}

function HeroRow({ opp, rank }: { opp: Opportunity; rank: number }) {
  const router = useRouter();
  const demo = isMock(opp) || isMock({ provenance: opp.data_provenance });
  const reason = `${opp.category ?? "Market"} · score ${Math.round(opp.opportunity_score)}, confidence ${fmtPct01(opp.confidence)}${opp.micro_niche ? ` · ${opp.micro_niche}` : ""}.`;
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-bg-secondary px-4 py-3">
      <span className="font-display text-2xl font-semibold text-accent-primary" aria-hidden>{rank}</span>
      <div className="min-w-0 flex-1 basis-64">
        <div className="flex flex-wrap items-center gap-2">
          <Link href={`/opportunities/${opp.id}`} className="truncate text-[14px] font-semibold text-text-primary hover:text-accent-secondary">
            {opp.title}
          </Link>
          {demo && <ProvenanceBadge mock />}
        </div>
        <p className="mt-0.5 truncate text-xs text-text-muted">{reason}</p>
        <WhyThis>
          <p>Opportunity score <strong className="text-text-primary">{Math.round(opp.opportunity_score)}</strong> with {fmtPct01(opp.confidence)} confidence (CONTRACT §8.2).</p>
          {opp.risk_notes && <p className="mt-1">Watch-outs: {opp.risk_notes}</p>}
          <p className="mt-1">Estimates are probabilistic — never a sales guarantee.</p>
        </WhyThis>
      </div>
      <div className="flex items-center gap-2">
        <ScoreInline value={opp.opportunity_score} />
        <ConfidenceMeter value={opp.confidence} />
        <Button size="sm" variant="primary" onClick={() => router.push(`/opportunities/${opp.id}?create=idea`)} data-testid="dashboard-hero-create">
          Start creating
        </Button>
      </div>
    </div>
  );
}

function RunAnalysisButton() {
  const run = useRefreshTrends();
  return (
    <Button size="sm" variant="primary" icon={<Play size={13} />} loading={run.isPending} onClick={() => run.mutate()}>
      Run daily analysis
    </Button>
  );
}

// ---------------------------------------------------------------- KPI strip

function KpiStrip() {
  const opps = useOpportunities({ page_size: 50 });
  const queue = useQueue({ page_size: 1 });
  const settings = useSettings();
  const weeklyCapacity = Number(settings.data?.["planner.weekly_capacity"] ?? 0);

  const oppList = opps.data?.data ?? [];
  const avgConf = oppList.length ? oppList.reduce((a, o) => a + o.confidence, 0) / oppList.length : null;

  return (
    <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
      <KpiCard
        label="Opportunities today"
        value={fmtInt(opps.data?.pagination.total)}
        countTo={opps.data?.pagination.total ?? null}
        countFormat={(n) => fmtInt(Math.round(n))}
        delta={opps.data && opps.data.data[0] ? <ProvenanceBadge provenance={opps.data.data[0].data_provenance} /> : undefined}
        loading={opps.isLoading}
      />
      <KpiCard
        label="Avg confidence"
        value={fmtPct01(avgConf)}
        countTo={avgConf !== null ? avgConf * 100 : null}
        countFormat={(n) => `${Math.round(n)}%`}
        hint="Across listed opportunities"
        loading={opps.isLoading}
      />
      <KpiCard
        label="Queue depth"
        value={fmtInt(queue.data?.pagination.total)}
        countTo={queue.data?.pagination.total ?? null}
        countFormat={(n) => fmtInt(Math.round(n))}
        delta={
          queue.data ? (
            <Link href="/queue" className="text-accent-secondary hover:underline">Open queue</Link>
          ) : undefined
        }
        loading={queue.isLoading}
      />
      <KpiCard
        label="Capacity left (week)"
        value={weeklyCapacity > 0 ? fmtInt(weeklyCapacity) : "—"}
        countTo={weeklyCapacity > 0 ? weeklyCapacity : null}
        countFormat={(n) => fmtInt(Math.round(n))}
        delta={
          settings.data ? (
            <Link href="/planner" className="text-accent-secondary hover:underline">Planner</Link>
          ) : undefined
        }
        hint={weeklyCapacity > 0 ? "assets/week configured" : "Set capacity in Planner"}
        loading={settings.isLoading}
      />
    </div>
  );
}

// ---------------------------------------------------------------- Panels

function RisingCategoriesPanel() {
  const trends = useTrends({ window: "7d", page_size: 8, sort: "-score" });
  return (
    <Panel title="Rising categories" action={<Link href="/trends" className="text-xs text-accent-secondary hover:underline">Trend Explorer</Link>}>
      <QueryView
        query={trends}
        loading={<Skeleton lines={5} />}
        empty={<EmptyState compact title="No rising categories" description="No trends in the 7-day window yet." />}
        errorTitle="Trends unavailable"
      >
        {(page) => (
          <div className="flex flex-wrap gap-2">
            {page.data.map((t) => (
              <Link key={t.id} href={`/trends?trend=${t.id}`}
                className="inline-flex items-center gap-1.5 rounded-full border border-border bg-bg-secondary px-3 py-1.5 text-xs text-text-secondary hover:border-text-muted hover:text-text-primary">
                <ArrowUpRight size={12} className="text-accent-primary" aria-hidden />
                {t.title}
                <span className="font-semibold text-text-primary">{Math.round(t.score)}</span>
                {isMock(t) && <ProvenanceBadge mock />}
              </Link>
            ))}
          </div>
        )}
      </QueryView>
    </Panel>
  );
}

function OpportunityListPanel({ title, href, formats }: { title: string; href: string; formats?: ("image" | "video")[] }) {
  const opps = useOpportunities({ sort: "-opportunity_score", page_size: 5 });
  return (
    <Panel title={title} action={<Link href={href} className="text-xs text-accent-secondary hover:underline">View all</Link>}>
      <QueryView
        query={opps}
        loading={<div className="space-y-2">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-14" />)}</div>}
        empty={<EmptyState compact title="No opportunities" description="Run the daily analysis to surface opportunities." action={<RunAnalysisButton />} />}
        errorTitle="Opportunities unavailable"
      >
        {(page) => {
          const rows = formats ? page.data.filter((o) => !o.formats?.length || o.formats.some((f) => formats.includes(f))) : page.data;
          return (
            <div className="space-y-2">
              {rows.slice(0, 5).map((o, i) => <OpportunityCard key={o.id} opp={o} rank={i + 1} />)}
              {!rows.length && <EmptyState compact title="Nothing here yet" />}
            </div>
          );
        }}
      </QueryView>
    </Panel>
  );
}

function PredictionSignalsPanel() {
  const trends = useTrends({ window: "7d", page_size: 6, min_score: 70 });
  return (
    <Panel title="Prediction signals" action={<Link href="/trends" className="text-xs text-accent-secondary hover:underline">All signals</Link>}>
      <QueryView
        query={trends}
        loading={<Skeleton lines={4} />}
        empty={<EmptyState compact title="No high-confidence signals" description="Signals below the confidence bar are shown as speculative in Trend Explorer." />}
        errorTitle="Signals unavailable"
      >
        {(page) => (
          <ul className="space-y-2.5">
            {page.data.map((t) => (
              <li key={t.id} className="flex items-start gap-2.5">
                <TrendingUp size={14} className="mt-0.5 shrink-0 text-status-info" aria-hidden />
                <div className="min-w-0 flex-1">
                  <Link href={`/trends?trend=${t.id}`} className="text-[13px] font-medium text-text-primary hover:text-accent-secondary">
                    {t.title}
                  </Link>
                  <p className="text-[11px] text-text-muted">
                    {t.signal_count} signals · updated {timeAgo(t.updated_at)} · <span className="italic">estimate, not a guarantee</span>
                    {isMock(t) && <> · <ProvenanceBadge mock /></>}
                  </p>
                </div>
                <ScoreInline value={t.score} />
              </li>
            ))}
          </ul>
        )}
      </QueryView>
    </Panel>
  );
}

function QueueSnapshotPanel() {
  const queue = useQueue({ page_size: 100 });
  return (
    <Panel title="Production queue" action={<Link href="/queue" className="text-xs text-accent-secondary hover:underline">Open board</Link>}>
      <QueryView
        query={queue}
        loading={<Skeleton lines={4} />}
        empty={<EmptyState compact title="Queue is empty" description="Approved ideas land here, in pipeline order." action={<Link href="/opportunities"><Button size="sm">Find opportunities</Button></Link>} />}
        errorTitle="Queue unavailable"
      >
        {(page) => {
          const counts = new Map<string, number>();
          for (const i of page.data) counts.set(i.status, (counts.get(i.status) ?? 0) + 1);
          const rows = Array.from(counts.entries()).map(([s, c]) => ({ label: stateLabel(s as QueueStatus), value: c }));
          const stalled = page.data.filter((i) => {
            const age = (Date.now() - new Date(i.status_changed_at).getTime()) / 86400000;
            return age > 14 && !["ACCEPTED", "REJECTED", "ARCHIVED", "SUBMITTED"].includes(i.status);
          }).length;
          return (
            <div>
              <MiniBars rows={rows.slice(0, 8)} />
              {stalled > 0 && (
                <p className="mt-2.5 flex items-center gap-1.5 text-xs text-status-warning">
                  <AlertTriangle size={12} aria-hidden /> {stalled} item{stalled === 1 ? "" : "s"} stalled &gt; 14 days
                </p>
              )}
            </div>
          );
        }}
      </QueryView>
    </Panel>
  );
}

function ComplianceAlertsPanel() {
  const checks = useComplianceChecks({ pending_review: true, page_size: 6 });
  return (
    <Panel title="Compliance alerts" action={<Link href="/compliance" className="text-xs text-accent-secondary hover:underline">Compliance Center</Link>}>
      <QueryView
        query={checks}
        loading={<Skeleton lines={3} />}
        empty={<EmptyState compact title="No items need compliance review" description="Healthy state — nothing is blocked or awaiting your judgment." />}
        errorTitle="Compliance data unavailable"
      >
        {(page) => (
          <ul className="space-y-2">
            {page.data.map((c) => (
              <li key={c.id} className="flex items-center gap-2.5 rounded-md border border-border bg-bg-secondary px-3 py-2">
                <ComplianceChip result={c.result} />
                <div className="min-w-0 flex-1">
                  <Link href={`/compliance?review=${c.id}`} className="block truncate text-[13px] font-medium text-text-primary hover:text-accent-secondary">
                    {c.subject.kind.replace(/_/g, " ")} · {c.subject.id.slice(0, 8)}
                  </Link>
                  <p className="text-[11px] text-text-muted">{c.findings.filter((f) => f.triggered).length} findings · {timeAgo(c.created_at)}</p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </QueryView>
    </Panel>
  );
}

function RecentRunsPanel() {
  const jobs = useAgentJobs({ page_size: 5, sort: "-created_at" });
  return (
    <Panel title="Recent agent runs" action={<Link href="/agents" className="text-xs text-accent-secondary hover:underline">Agent Center</Link>}>
      <QueryView
        query={jobs}
        loading={<Skeleton lines={4} />}
        empty={<EmptyState compact icon={<Bot size={18} />} title="No agent runs yet" description="Run the daily analysis to start the pipeline." action={<RunAnalysisButton />} />}
        errorTitle="Agent runs unavailable"
      >
        {(page) => (
          <ul className="space-y-2">
            {page.data.map((j) => (
              <li key={j.job_id} className="flex items-center gap-2.5 text-[13px]">
                <Badge tone={j.status === "succeeded" ? "success" : j.status === "failed" ? "danger" : j.status === "running" ? "warning" : "muted"}>
                  {j.status}
                </Badge>
                <Link href={`/agents/runs/${j.job_id}`} className="min-w-0 flex-1 truncate text-text-secondary hover:text-text-primary">
                  {j.agent.replace(/_/g, " ")} · {j.run_kind.replace(/_/g, " ").toLowerCase()}
                </Link>
                <span className="shrink-0 text-[11px] text-text-muted">{timeAgo(j.created_at)}</span>
              </li>
            ))}
          </ul>
        )}
      </QueryView>
    </Panel>
  );
}

function PerformancePanel() {
  const perf = useAnalyticsOverview(daysAgoISO(30), todayISO());
  return (
    <Panel title="Performance (30d)" action={<Link href="/analytics" className="text-xs text-accent-secondary hover:underline">Analytics</Link>}>
      <QueryView
        query={perf}
        loading={<Skeleton lines={3} />}
        empty={<EmptyState compact title="No performance data" description="Connect your Adobe Stock dashboard data to see performance here. We never invent sales numbers." />}
        errorTitle="Performance unavailable"
      >
        {(o) => {
          const k = o.kpis;
          const hasAny = [k.submitted.value, k.accepted.value].some((v) => v !== null && v !== 0);
          if (!hasAny)
            return (
              <EmptyState
                compact
                title="No sales data connected"
                description="Performance KPIs appear here once you record submissions and outcomes. Guidance, never fabricated numbers."
                action={<Link href="/planner"><Button size="sm">Open planner</Button></Link>}
              />
            );
          return (
            <div className="grid grid-cols-3 gap-3 text-center">
              {[
                { label: "Submitted", v: k.submitted, pct: false },
                { label: "Accepted", v: k.accepted, pct: false },
                { label: "Accept rate", v: k.acceptance_rate, pct: true },
              ].map((r) => (
                <div key={r.label}>
                  <p className="font-display text-xl font-semibold text-text-primary" style={{ fontVariantNumeric: "tabular-nums" }}>
                    {r.v.value === null ? "—" : r.pct ? `${Math.round(r.v.value * 100)}%` : fmtInt(r.v.value)}
                  </p>
                  <p className="text-[11px] text-text-muted">{r.label}</p>
                  <ProvenanceBadge provenance={r.v.provenance} mock={o.mock} />
                </div>
              ))}
            </div>
          );
        }}
      </QueryView>
    </Panel>
  );
}

function CapacityPanel() {
  const settings = useSettings();
  const queue = useQueue({ page_size: 100 });
  const weekly = Number(settings.data?.["planner.weekly_capacity"] ?? 0);
  const weekStart = daysAgoISO(new Date().getDay());
  const planned = (queue.data?.data ?? []).filter((i) => i.target_date && i.target_date >= weekStart && !["ARCHIVED", "REJECTED"].includes(i.status)).length;
  const pct = weekly > 0 ? Math.min(100, (planned / weekly) * 100) : 0;
  const over = weekly > 0 && planned > weekly;
  return (
    <Panel title="Submission capacity" action={<Link href="/planner" className="text-xs text-accent-secondary hover:underline">Planner</Link>}>
      {settings.isLoading || queue.isLoading ? (
        <Skeleton className="h-10" />
      ) : weekly <= 0 ? (
        <EmptyState compact title="No capacity set" description="Enter your weekly submission capacity in the Planner — the queue is planned against it." action={<Link href="/planner"><Button size="sm">Set capacity</Button></Link>} />
      ) : (
        <div>
          <div className="flex items-baseline justify-between text-xs">
            <span className="text-text-secondary">{planned} planned of {weekly} slots</span>
            <span className={cx("font-semibold", over ? "text-status-danger" : "text-text-primary")}>{over ? "Over capacity" : `${weekly - planned} left`}</span>
          </div>
          <div className="mt-2 h-2 overflow-hidden rounded-full bg-border" role="img" aria-label={`${planned} of ${weekly} weekly slots used`}>
            <div className={cx("h-full rounded-full", over ? "bg-status-danger" : "bg-accent-primary")} style={{ width: `${pct}%` }} />
          </div>
        </div>
      )}
    </Panel>
  );
}

// ---------------------------------------------------------------- Phase 2: data-layer widgets

/** Source status chips row + "last data update" freshness line (PHASE2_DESIGN.md §7). */
function DataLayerStatusPanel() {
  const sources = useSources({ retry: false });
  return (
    <Panel
      title="Data layer status"
      action={<Link href="/sources" className="text-xs text-accent-secondary hover:underline">All sources</Link>}
    >
      <QueryView
        query={sources}
        loading={<Skeleton lines={2} />}
        empty={<EmptyState compact title="No sources" description="Data sources appear here once the Phase-2 backend registers them." />}
        errorTitle="Source status unavailable"
      >
        {(rows) => {
          if (!rows.length)
            return <EmptyState compact title="No sources" description="Data sources appear here once the Phase-2 backend registers them." />;
          const live = rows.filter(isLiveHealth).length;
          const lastUpdate = rows.map(lastSuccessOf).filter(Boolean).sort().pop();
          return (
            <div>
              <div className="flex flex-wrap gap-2">
                {rows.map((s) => (
                  <Link
                    key={s.id}
                    href="/sources"
                    className="inline-flex items-center gap-1.5 rounded-full border border-border bg-bg-secondary px-2.5 py-1 text-xs text-text-secondary hover:border-text-muted hover:text-text-primary"
                    title={s.name}
                  >
                    <span className="max-w-[140px] truncate font-medium">{s.name}</span>
                    <SourceStatusChip status={s.health_status ?? s.health?.status} />
                    <LiveBadge health={s} />
                  </Link>
                ))}
              </div>
              <p className="mt-2.5 text-xs text-text-muted">
                {live} of {rows.length} sources live · Last data update:{" "}
                <span className="font-medium text-text-secondary">
                  {lastUpdate ? timeAgo(lastUpdate) : "never"}
                </span>
              </p>
            </div>
          );
        }}
      </QueryView>
    </Panel>
  );
}

/** Private performance mini-summary — or an honest setup CTA when not configured. */
function PrivateMiniPanel() {
  const conn = useAdobeConnection({ retry: false });
  const summary = usePrivatePerformanceSummary({ retry: false });
  const configured = !!conn.data && (conn.data.configured === true || conn.data.status !== "NOT_CONFIGURED");

  return (
    <Panel
      title="Your Adobe performance"
      action={<Link href="/private" className="text-xs text-accent-secondary hover:underline">Open</Link>}
    >
      {conn.isLoading ? (
        <Skeleton lines={3} />
      ) : !configured ? (
        <EmptyState
          compact
          icon={<Wallet size={18} />}
          title="Adobe Contributor not connected"
          description="Connect your contributor account to see your real earnings, downloads, and per-category performance here. No demo numbers, ever."
          action={<Link href="/private"><Button size="sm">Set up connection</Button></Link>}
        />
      ) : (
        <QueryView
          query={summary}
          loading={<Skeleton lines={3} />}
          empty={
            <EmptyState
              compact
              title="Connected — no data yet"
              description="The connection is configured. Run a sync from the Private Performance page to pull your first snapshot."
              action={<Link href="/private"><Button size="sm">Sync now</Button></Link>}
            />
          }
          errorTitle="Performance unavailable"
        >
          {(s) => {
            const t = s.totals;
            if (!s.has_data || !t) {
              return (
                <EmptyState
                  compact
                  title="Connected — no data yet"
                  description={s.message ?? "The connection is configured. Run a sync from the Private Performance page to pull your first snapshot."}
                  action={<Link href="/private"><Button size="sm">Sync now</Button></Link>}
                />
              );
            }
            const hasData = (t.earnings ?? 0) > 0 || (t.downloads ?? 0) > 0;
            if (!hasData)
              return (
                <EmptyState
                  compact
                  title="Connected — no data yet"
                  description="The connection is configured. Run a sync from the Private Performance page to pull your first snapshot."
                  action={<Link href="/private"><Button size="sm">Sync now</Button></Link>}
                />
              );
            return (
              <div className="grid grid-cols-2 gap-3 text-center">
                <div>
                  <p className="font-display text-xl font-semibold text-text-primary" style={{ fontVariantNumeric: "tabular-nums" }}>
                    {t.earnings === null ? "—" : `$${fmtInt(t.earnings)}`}
                  </p>
                  <p className="text-[11px] text-text-muted">Earnings</p>
                </div>
                <div>
                  <p className="font-display text-xl font-semibold text-text-primary" style={{ fontVariantNumeric: "tabular-nums" }}>
                    {t.downloads === null ? "—" : fmtInt(t.downloads)}
                  </p>
                  <p className="text-[11px] text-text-muted">Downloads</p>
                </div>
                <div className="col-span-2">
                  <ProvenanceBadge provenance={s.provenance} mock={s.mock} />
                  <p className="mt-1 text-[11px] text-text-muted">
                    {conn.data?.last_sync ? `Synced ${timeAgo(conn.data.last_sync)}` : "Never synced"} · your data only
                  </p>
                </div>
              </div>
            );
          }}
        </QueryView>
      )}
    </Panel>
  );
}

/** Market summary — what the public data layer knows right now. */
function MarketSummaryPanel() {
  const sources = useSources({ retry: false });
  const runs = useCollectionRuns({ page: 1, page_size: 50 }, { retry: false });
  return (
    <Panel
      title="Market data summary"
      action={<Link href="/runs" className="text-xs text-accent-secondary hover:underline">Runs</Link>}
    >
      {sources.isLoading || runs.isLoading ? (
        <Skeleton lines={3} />
      ) : sources.isError || runs.isError ? (
        <EmptyState compact title="Market data unavailable" description="The data layer could not be reached." />
      ) : (
        (() => {
          const rows = sources.data ?? [];
          const live = rows.filter(isLiveHealth).length;
          const records = rows.reduce((a, s) => a + (s.records_collected ?? s.health?.records_collected ?? 0), 0);
          const runRows = runs.data?.data ?? [];
          const ok24h = runRows.filter((r) => {
            const age = Date.now() - new Date(r.started_at).getTime();
            return age < 24 * 3600_000 && (r.status === "SUCCESS" || r.status === "PARTIAL");
          }).length;
          return (
            <div className="grid grid-cols-3 gap-3 text-center">
              {[
                { label: "Sources live", value: `${live}/${rows.length}` },
                { label: "Records collected", value: fmtInt(records) },
                { label: "Successful runs (24h)", value: fmtInt(ok24h) },
              ].map((k) => (
                <div key={k.label}>
                  <p className="font-display text-xl font-semibold text-text-primary" style={{ fontVariantNumeric: "tabular-nums" }}>
                    {k.value}
                  </p>
                  <p className="mt-0.5 text-[11px] text-text-muted">{k.label}</p>
                </div>
              ))}
            </div>
          );
        })()
      )}
    </Panel>
  );
}

// ---------------------------------------------------------------- Page

export default function DashboardPage() {
  return (
    <div className="space-y-4">
      <PageHeader
        title="Dashboard"
        description="Your daily command view. Every number carries its provenance; demo data is always badged."
        actions={<RunAnalysisButton />}
      />

      <Banner id="provider" tone="warning">
        <strong className="text-text-primary">Demo data provider.</strong> Figures shown are illustrative placeholders
        until live sources connect — never treat them as real Adobe Stock data.
      </Banner>

      <CreateTodayHero />
      <KpiStrip />

      <DataLayerStatusPanel />

      <div className="grid gap-4 lg:grid-cols-2">
        <PrivateMiniPanel />
        <MarketSummaryPanel />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <OpportunityListPanel title="Today's opportunities" href="/opportunities" />
        <RisingCategoriesPanel />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <OpportunityListPanel title="Top image opportunities" href="/opportunities" formats={["image"]} />
        <OpportunityListPanel title="Top video opportunities" href="/opportunities" formats={["video"]} />
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <PredictionSignalsPanel />
        <CapacityPanel />
        <QueueSnapshotPanel />
        <ComplianceAlertsPanel />
        <RecentRunsPanel />
        <PerformancePanel />
      </div>
    </div>
  );
}
