"use client";
/**
 * Analytics (docs/05 screen 17) — KPI cards with provenance, pipeline funnel,
 * opportunity performance, submission outcomes, what-to-do-next, CSV export.
 * Never fabricates sales data: empty states say "connect your data".
 */
import { useState } from "react";
import { Download, Lightbulb } from "lucide-react";
import {
  Button,
  EmptyState,
  KpiCard,
  PageHeader,
  Panel,
  QueryView,
  Skeleton,
  Tabs,
  WhyThis,
} from "../../components/ui";
import { ProvenanceBadge, isMock } from "../../components/scores";
import { TrendBarChart } from "../../components/charts";
import { useToast } from "../../components/toast";
import {
  useAnalyticsExports,
  useAnalyticsFunnel,
  useAnalyticsOverview,
  useComplianceChecks,
  useOpportunities,
  useOpportunityPerformance,
  useQueue,
  useRequestExport,
  useSubmissions,
} from "../../hooks/useApi";
import { daysAgoISO, enumLabel, fmtInt, fmtPct01, todayISO, timeAgo } from "../../lib/format";

const RANGES = [
  { value: "7", label: "7 days" },
  { value: "30", label: "30 days" },
  { value: "90", label: "90 days" },
] as const;

export default function AnalyticsPage() {
  const [range, setRange] = useState<(typeof RANGES)[number]["value"]>("30");
  const from = daysAgoISO(Number(range));
  const to = todayISO();

  return (
    <div className="space-y-4">
      <PageHeader
        title="Analytics"
        description="What is working, in numbers with provenance. Empty means unconnected — never invented."
        actions={
          <div className="flex items-center gap-2">
            <Tabs tabs={RANGES.map((r) => ({ value: r.value, label: r.label }))} value={range} onChange={(v) => setRange(v as never)} />
            <ExportButton from={from} to={to} />
          </div>
        }
      />

      <KpiSection from={from} to={to} />

      <div className="grid gap-4 lg:grid-cols-2">
        <FunnelPanel />
        <SubmissionsPanel />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <OpportunityPerformancePanel />
        <WhatToDoNextPanel />
      </div>

      <ExportsPanel />
    </div>
  );
}

// ---------------------------------------------------------------------------
// KPI cards
// ---------------------------------------------------------------------------

function KpiSection({ from, to }: { from: string; to: string }) {
  const overview = useAnalyticsOverview(from, to);
  return (
    <QueryView query={overview}
      loading={<div className="grid grid-cols-2 gap-3 xl:grid-cols-4">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-24" />)}</div>}
      empty={<EmptyState title="No analytics data" description="Connect your Adobe Stock dashboard data to see KPIs here. We never invent sales numbers." />}
      errorTitle="Analytics unavailable">
      {(o) => (
        <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
          <KpiCard label="Submitted" value={o.kpis.submitted.value === null ? "—" : fmtInt(o.kpis.submitted.value)}
            delta={<ProvenanceBadge provenance={o.kpis.submitted.provenance} mock={o.mock} />} />
          <KpiCard label="Accepted" value={o.kpis.accepted.value === null ? "—" : fmtInt(o.kpis.accepted.value)}
            delta={<ProvenanceBadge provenance={o.kpis.accepted.provenance} mock={o.mock} />} />
          <KpiCard label="Acceptance rate" value={o.kpis.acceptance_rate.value === null ? "—" : fmtPct01(o.kpis.acceptance_rate.value)}
            delta={<ProvenanceBadge provenance={o.kpis.acceptance_rate.provenance} mock={o.mock} />} />
          {o.kpis.views && (
            <KpiCard label="Views" value={o.kpis.views.value === null ? "—" : fmtInt(o.kpis.views.value)}
              delta={<ProvenanceBadge provenance={o.kpis.views.provenance} mock={o.mock} />} />
          )}
          {o.kpis.downloads && (
            <KpiCard label="Downloads" value={o.kpis.downloads.value === null ? "—" : fmtInt(o.kpis.downloads.value)}
              delta={<ProvenanceBadge provenance={o.kpis.downloads.provenance} mock={o.mock} />} />
          )}
          {o.kpis.revenue && (
            <KpiCard label="Revenue" value={o.kpis.revenue.value === null ? "—" : `$${fmtInt(o.kpis.revenue.value)}`}
              delta={<ProvenanceBadge provenance={o.kpis.revenue.provenance} mock={o.mock} />} />
          )}
        </div>
      )}
    </QueryView>
  );
}

// ---------------------------------------------------------------------------
// Funnel — from the server funnel endpoint
// ---------------------------------------------------------------------------

function FunnelPanel() {
  const funnel = useAnalyticsFunnel();
  return (
    <Panel title="Pipeline funnel">
      <QueryView query={funnel} loading={<Skeleton className="h-56" />}
        empty={<EmptyState compact title="No funnel data" description="The backend has no funnel stages yet." />}
        errorTitle="Funnel unavailable">
        {(f) => f.stages.length ? (
          <>
            <TrendBarChart
              data={f.stages.map((s) => ({ label: s.stage, count: s.count }))}
              series={[{ key: "count", name: "Records", accent: true }]}
              horizontal
              ariaLabel="Pipeline funnel by stage"
              formatter={(v) => `${fmtInt(v)}`}
            />
            {f.mock && <ProvenanceBadge mock />}
            <WhyThis label="What this funnel shows">
              <p>Record counts per pipeline stage from the backend. Stage-to-stage drops highlight where work stalls — e.g. many ideas but few prompts means the bottleneck is prompt writing.</p>
            </WhyThis>
          </>
        ) : (
          <EmptyState compact title="Funnel is empty" description="No stages returned by the backend." />
        )}
      </QueryView>
    </Panel>
  );
}

// ---------------------------------------------------------------------------
// Submission outcomes — from recorded submissions
// ---------------------------------------------------------------------------

function SubmissionsPanel() {
  const subs = useSubmissions({ page_size: 10, sort: "-submitted_at" });
  return (
    <Panel title="Submission outcomes" action={<a href="/planner" className="text-xs text-accent-secondary hover:underline">Open planner</a>}>
      <QueryView query={subs} loading={<Skeleton className="h-48" />}
        empty={<EmptyState compact title="No submissions" description="Record submissions in the queue and their Adobe outcomes — they appear here and feed the KPIs." />}
        errorTitle="Submission data unavailable">
        {(p) => (
          <ul className="space-y-2">
            {p.data.map((s) => (
              <li key={s.id} className="flex items-center gap-3 rounded-md border border-border bg-bg-secondary px-3 py-2.5 text-[13px]">
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-text-primary">Asset {s.asset_id.slice(0, 8)}…</span>
                  <span className="text-[11px] text-text-muted">
                    {s.submitted_at ? `submitted ${timeAgo(s.submitted_at)}` : "not yet submitted"}
                    {s.adobe_reference ? ` · ref ${s.adobe_reference}` : ""}
                    {s.rejection_reason ? ` · ${s.rejection_reason}` : ""}
                  </span>
                </span>
                <span className="shrink-0 rounded bg-surface-elevated px-2 py-0.5 text-[11px] text-text-secondary">{enumLabel(s.status)}</span>
              </li>
            ))}
          </ul>
        )}
      </QueryView>
    </Panel>
  );
}

// ---------------------------------------------------------------------------
// Opportunity performance — predictions vs real outcomes per opportunity
// ---------------------------------------------------------------------------

function OpportunityPerformancePanel() {
  const opps = useOpportunities({ page_size: 5, sort: "-opportunity_score" });
  return (
    <Panel title="Opportunity performance">
      <QueryView query={opps} loading={<Skeleton className="h-40" />}
        empty={<EmptyState compact title="No opportunities" />}
        errorTitle="Performance data unavailable">
        {(p) => p.data.length ? (
          <ul className="space-y-2.5">
            {p.data.map((o) => <PerformanceRow key={o.id} opportunityId={o.id} title={o.title} />)}
          </ul>
        ) : (
          <EmptyState compact title="Nothing to compare yet" description="Once opportunities and real outcomes both exist, performance appears here." />
        )}
      </QueryView>
      <p className="mt-2 text-[11px] text-text-muted">
        Predictions are estimates, not guarantees — this panel compares them against recorded outcomes. Small samples are noisy.
      </p>
    </Panel>
  );
}

function PerformanceRow({ opportunityId, title }: { opportunityId: string; title: string }) {
  const perf = useOpportunityPerformance(opportunityId);
  if (perf.isLoading) return <li className="skeleton h-10 rounded" aria-hidden />;
  if (perf.isError || !perf.data) return null;
  const p = perf.data;
  return (
    <li className="rounded-md border border-border bg-bg-secondary px-3 py-2.5">
      <p className="truncate text-[13px] font-medium text-text-primary">{title}</p>
      <p className="mt-0.5 text-[11px] text-text-muted">
        {p.sample_size} samples · {p.submitted} submitted · {p.accepted} accepted ·{" "}
        acceptance {p.acceptance_rate === null ? "—" : fmtPct01(p.acceptance_rate)}
        {p.mock && " · Demo data"}
      </p>
      {p.note && <p className="text-[11px] text-text-muted">{p.note}</p>}
    </li>
  );
}

// ---------------------------------------------------------------------------
// What to do next — derived guidance, never fabricated numbers
// ---------------------------------------------------------------------------

function WhatToDoNextPanel() {
  const opps = useOpportunities({ page_size: 5, sort: "-opportunity_score" });
  const queue = useQueue({ page_size: 5 });
  const checks = useComplianceChecks({ pending_review: true, page_size: 1 });

  const tips: string[] = [];
  const actionable = (opps.data?.data ?? []).filter((o) => o.opportunity_score >= 55 && o.confidence >= 0.5).length;
  if (actionable > 0) tips.push(`${actionable} opportunities clear the action bar — approve the best and save your first idea.`);
  const qn = queue.data?.pagination.total ?? 0;
  if (qn === 0) tips.push("The queue is empty: nothing converts. Enqueue one READY idea today.");
  const pending = checks.data?.pagination.total ?? 0;
  if (pending > 0) tips.push(`${pending} item${pending === 1 ? "" : "s"} waiting on compliance review — blocked work is invisible work.`);
  if (!tips.length) tips.push("Pipeline is healthy. Keep the daily analysis running and review new opportunities each morning.");

  return (
    <Panel title="What to do next">
      <ul className="space-y-2.5">
        {tips.map((t, i) => (
          <li key={i} className="flex items-start gap-2.5 rounded-md border border-border bg-bg-secondary px-3 py-2.5 text-[13px] text-text-secondary">
            <Lightbulb size={14} className="mt-0.5 shrink-0 text-accent-primary" aria-hidden />
            {t}
          </li>
        ))}
      </ul>
      <p className="mt-2 text-[11px] text-text-muted">Guidance derived from your live counts — not from invented benchmarks.</p>
    </Panel>
  );
}

// ---------------------------------------------------------------------------
// Export — request a job, download when ready
// ---------------------------------------------------------------------------

function ExportButton({ from, to }: { from: string; to: string }) {
  const req = useRequestExport();
  return (
    <Button size="sm" variant="outline" icon={<Download size={13} />} loading={req.isPending}
      onClick={() => req.mutate({ kind: "analytics_csv", from, to })} data-testid="analytics-export">
      Export CSV
    </Button>
  );
}

function ExportsPanel() {
  const exports = useAnalyticsExports();
  return (
    <Panel title="Export jobs">
      <QueryView query={exports} loading={<Skeleton lines={3} />}
        empty={<EmptyState compact title="No exports yet" description="Request a CSV export above — the file appears here when the job finishes." />}
        errorTitle="Exports unavailable">
        {(exportsList) => (
          <ul className="space-y-2">
            {(exportsList?.data ?? exportsList?.items ?? []).map((e) => (
              <li key={e.id} className="flex items-center gap-3 rounded-md border border-border bg-bg-secondary px-3 py-2.5 text-[13px]">
                <span className="min-w-0 flex-1 text-text-secondary">
                  <span className="font-medium text-text-primary">{e.kind}</span> · requested {timeAgo(e.created_at)}
                </span>
                <span className="shrink-0 rounded bg-surface-elevated px-2 py-0.5 text-[11px] text-text-secondary">{enumLabel(e.status)}</span>
                {e.status === "succeeded" && e.download_url ? (
                  <a href={e.download_url} className="shrink-0 text-xs text-accent-secondary hover:underline" download>Download</a>
                ) : e.status === "succeeded" ? (
                  <span className="shrink-0 text-[11px] text-text-muted">no file attached</span>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </QueryView>
    </Panel>
  );
}
