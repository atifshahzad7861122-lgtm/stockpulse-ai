"use client";
/**
 * Trend Explorer — 7-day analysis view (docs/05 screen 4).
 * Category selector, current-7d vs previous-7d vs baseline charts,
 * score cards with factor breakdowns, provenance + timestamp on every insight.
 */
import {useMemo, Suspense, useState} from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowDown, ArrowUp, Bookmark, Minus, RefreshCw } from "lucide-react";
import {
  Badge,
  Button,
  Drawer,
  EmptyState,
  PageHeader,
  Panel,
  QueryView,
  Select,
  Skeleton,
  Tabs,
  WhyThis,
  cx,
} from "../../components/ui";
import { ConfidenceMeter, ProvenanceBadge, ScoreBar, ScoreInline, SaturationBadge, isMock } from "../../components/scores";
import { TrendBarChart, TrendLineChart } from "../../components/charts";
import { TrendTerrainScene, type TerrainRidge } from "../../components/three/scenes";
import { GOLD, STEEL } from "../../components/palette";
import {
  useCategories,
  useLibraryMutations,
  useRefreshTrends,
  useTrend,
  useTrendSignals,
  useTrends,
} from "../../hooks/useApi";
import { useToast } from "../../components/toast";
import { fmtDate, fmtDateTime, timeAgo } from "../../lib/format";
import type { Trend, TrendSignal } from "../../types";

const WINDOWS = [
  { value: "7d", label: "7 days" },
  { value: "30d", label: "30 days" },
  { value: "90d", label: "90 days" },
] as const;

type Window = (typeof WINDOWS)[number]["value"];

function TrendsPage() {
  const router = useRouter();
  const params = useSearchParams();
  const category = params.get("category") ?? "";
  const window = ((params.get("window") as Window) || "7d") as Window;
  const [minScore, setMinScore] = useState(0);
  const drawerId = params.get("trend");

  const categories = useCategories();
  const trends = useTrends({ window, category: category || undefined, min_score: minScore || undefined, sort: "-score", page_size: 24 });
  const refresh = useRefreshTrends();
  const running = refresh.isAnalysisRunning;
  const pct = refresh.analysisJob ? Math.round((refresh.analysisJob.progress ?? 0) * 100) : 0;

  const setParam = (k: string, v: string) => {
    const p = new URLSearchParams(params.toString());
    if (v) p.set(k, v);
    else p.delete(k);
    router.replace(`/trends?${p.toString()}`);
  };

  return (
    <div className="space-y-4">
      <PageHeader
        title="Trend Explorer"
        description="What is rising, in which category, and why. Every insight carries provenance and a timestamp."
        actions={
          <Button
            size="sm"
            variant="primary"
            icon={<RefreshCw size={13} />}
            loading={refresh.isPending || running}
            disabled={running}
            onClick={() => refresh.mutate()}
            title="Trigger on-demand aggregation (rate-limited: 5/hr)"
          >
            {running ? `Aggregating… ${pct}%` : "Refresh trends"}
          </Button>
        }
      />

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <Tabs
          tabs={WINDOWS.map((w) => ({ value: w.value, label: w.label }))}
          value={window}
          onChange={(v) => setParam("window", v)}
        />
        <div className="w-56">
          <Select value={category} onChange={(e) => setParam("category", e.target.value)} aria-label="Filter by category">
            <option value="">All categories</option>
            {(categories.data ?? []).map((c) => (
              <option key={c.id} value={c.slug}>{c.name}</option>
            ))}
          </Select>
        </div>
        <div className="flex items-center gap-2 text-xs text-text-muted">
          <label htmlFor="min-score">Min score</label>
          <input
            id="min-score"
            type="range"
            min={0}
            max={100}
            step={5}
            value={minScore}
            onChange={(e) => setMinScore(Number(e.target.value))}
            className="w-28"
            aria-label="Minimum trend score"
          />
          <span className="w-8 text-text-primary">{minScore}</span>
        </div>
        {(category || minScore > 0) && (
          <Button size="sm" variant="ghost" onClick={() => { setParam("category", ""); setMinScore(0); }}>
            Clear filters
          </Button>
        )}
      </div>

      {/* Trend table */}
      <Panel title={`Trends · ${window}`}>
        <QueryView
          query={trends}
          loading={<div className="space-y-2">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-14" />)}</div>}
          empty={
            <EmptyState
              title="No trends match these filters"
              description="Try lowering the minimum score or clearing the category filter."
              action={<Button size="sm" onClick={() => { setParam("category", ""); setMinScore(0); }}>Clear filters</Button>}
            />
          }
          errorTitle="Trend data unavailable"
        >
          {(page) => (
            <div className="grid gap-2.5 md:grid-cols-2 xl:grid-cols-3">
              {page.data.map((t) => <TrendCard key={t.id} trend={t} onOpen={() => setParam("trend", t.id)} />)}
            </div>
          )}
        </QueryView>
      </Panel>

      <TrendDrawer id={drawerId} onClose={() => setParam("trend", "")} />
    </div>
  );
}

function TrendCard({ trend, onOpen }: { trend: Trend; onOpen: () => void }) {
  return (
    <button
      onClick={onOpen}
      className="rounded-lg border border-border bg-surface-base p-3.5 text-left transition-colors hover:border-text-muted"
      data-testid="trends-card"
    >
      <div className="flex items-start justify-between gap-2">
        <p className="text-[13.5px] font-semibold text-text-primary">{trend.title}</p>
        <ScoreInline value={trend.score} />
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        {trend.categories.slice(0, 3).map((c) => <Badge key={c} tone="neutral">{c}</Badge>)}
        <Badge tone="muted">{trend.signal_count} signals</Badge>
        {isMock(trend) ? <ProvenanceBadge mock /> : <ProvenanceBadge provenance={trend.provenance} />}
      </div>
      <p className="mt-2 text-[11px] text-text-muted">Updated {timeAgo(trend.updated_at)} · window {trend.window}</p>
    </button>
  );
}

// ---------------------------------------------------------------------------
// Detail drawer: evidence, charts, score cards with factor breakdowns
// ---------------------------------------------------------------------------

function TrendDrawer({ id, onClose }: { id: string | null; onClose: () => void }) {
  const detail = useTrend(id);
  const signals = useTrendSignals(id);
  const lib = useLibraryMutations();

  return (
    <Drawer open={!!id} onClose={onClose} title={detail.data?.title ?? "Trend"} wide
      footer={detail.data ? (
        <div className="flex gap-2">
          <Button size="sm" variant="outline" icon={<Bookmark size={13} />}
            onClick={() => id && lib.save.mutate({ item_kind: "TREND_SIGNAL", item_id: id })}>
            Save to library
          </Button>
          <Button size="sm" variant="ghost" onClick={onClose}>Close</Button>
        </div>
      ) : undefined}>
      {!id ? null : detail.isLoading ? (
        <div className="space-y-3"><div className="skeleton h-8 rounded" /><div className="skeleton h-40 rounded" /><div className="skeleton h-24 rounded" /></div>
      ) : detail.isError || !detail.data ? (
        <EmptyState title="Trend not found" description="It may have been removed." action={<Button size="sm" onClick={onClose}>Close</Button>} />
      ) : (
        <TrendDetailBody trend={detail.data} signals={signals.data ?? []} signalsLoading={signals.isLoading} />
      )}
    </Drawer>
  );
}

function buildSeries(signals: TrendSignal[]) {
  // Group signal values by day; compute current-7d, previous-7d, and baseline series.
  const byDay = new Map<string, number[]>();
  for (const s of signals) {
    if (s.metric_value === undefined || s.metric_value === null) continue;
    const day = new Date(s.observed_at).toISOString().slice(0, 10);
    const arr = byDay.get(day) ?? [];
    arr.push(s.metric_value);
    byDay.set(day, arr);
  }
  const days = Array.from(byDay.entries()).sort(([a]: [string, number[]], [b]: [string, number[]]) => (a < b ? -1 : 1));
  if (!days.length) return null;
  const means = days.map(([d, vals]) => ({ day: d, value: vals.reduce((a, v) => a + v, 0) / vals.length }));
  const overall = means.reduce((a, m) => a + m.value, 0) / means.length;
  const lastDay = days[days.length - 1][0];
  const cutoff = new Date(lastDay);
  cutoff.setDate(cutoff.getDate() - 7);
  const cutoff2 = new Date(lastDay);
  cutoff2.setDate(cutoff2.getDate() - 14);
  const hasPrevious = days.some(([d]) => d < cutoff.toISOString().slice(0, 10)) && days.some(([d]) => d >= cutoff2.toISOString().slice(0, 10));
  const rows = means.map((m) => ({
    label: m.day.slice(5),
    current: m.day >= cutoff.toISOString().slice(0, 10) ? Number(m.value.toFixed(1)) : null,
    previous: hasPrevious && m.day < cutoff.toISOString().slice(0, 10) ? Number(m.value.toFixed(1)) : null,
    baseline: Number(overall.toFixed(1)),
  }));
  return { rows, hasPrevious };
}

function TrendDetailBody({ trend, signals, signalsLoading }: { trend: NonNullable<ReturnType<typeof useTrend>["data"]>; signals: TrendSignal[]; signalsLoading: boolean }) {
  const series = useMemo(() => buildSeries(signals), [signals]);
  // Terrain ridges use only days where every ridge has a real value — no invented points.
  const terrainRidges: TerrainRidge[] = useMemo(() => {
    if (!series) return [];
    const rows = series.rows.filter((r) => r.current !== null && r.baseline !== null);
    if (rows.length < 2) return [];
    return [
      { name: "Current 7d", values: rows.map((r) => r.current as number), color: GOLD },
      { name: "Baseline (mean)", values: rows.map((r) => r.baseline as number), color: STEEL },
    ];
  }, [series]);
  const scores = trend.scores;
  const lib = useLibraryMutations();

  return (
    <div className="space-y-5">
      {/* Provenance + timestamp header */}
      <div className="flex flex-wrap items-center gap-1.5 text-xs text-text-muted">
        {isMock(trend) ? <ProvenanceBadge mock /> : <ProvenanceBadge provenance={trend.provenance} />}
        <span>·</span><span>Window {trend.window}</span>
        <span>·</span><span>Created {fmtDateTime(trend.created_at)}</span>
        <span>·</span><span>Updated {timeAgo(trend.updated_at)}</span>
      </div>

      {/* Score cards */}
      <section>
        <p className="micro-label mb-2.5">Scores</p>
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">
          <ScoreCard label="Trend score" value={scores?.trend_score ?? trend.score}
            explainer="How hot is this trend right now. TS = 0.30·TV + 0.25·SG + 0.20·KM + 0.15·EG + 0.10·SE (CONTRACT §8.1)." />
          <ScoreCard label="Opportunity score" value={scores?.opportunity_score}
            explainer="Should we act. OS = 0.35·TS + 0.25·CR + 0.20·CD + 0.20·(100−saturation) (CONTRACT §8.2)." />
          <ScoreCard label="Commercial score" value={scores?.commercial_score}
            explainer="How sellable. CPS = 0.35·CR + 0.25·CD + 0.15·SE + 0.15·(100−CO) + 0.10·format_fit (CONTRACT §8.3)." />
          <div className="rounded-lg border border-border bg-bg-secondary p-3">
            <p className="micro-label mb-2">Saturation</p>
            <SaturationBadge value={scores?.saturation_score ?? null} />
            <WhyThis label="How saturation is computed">
              <p>CSS = 100 × (0.55·CS + 0.45·CO). Open (0–30) → up to 8 assets; Saturated (76–100) → at most 2 (CONTRACT §8.4).</p>
            </WhyThis>
          </div>
          <div className="rounded-lg border border-border bg-bg-secondary p-3">
            <p className="micro-label mb-2">Confidence</p>
            <ConfidenceMeter value={scores?.confidence ?? null} />
            <p className="mt-1.5 text-[11px] italic text-text-muted">Estimate, not a guarantee — directional hints only.</p>
            <WhyThis label="How confidence is computed">
              <p>PC = 0.30·coverage + 0.25·freshness + 0.20·source count + 0.15·stability + 0.10·your agreement (CONTRACT §8.5). Below 50 the outputs are marked degraded.</p>
            </WhyThis>
          </div>
          {scores?.factors && scores.factors.length > 0 && (
            <div className="col-span-full rounded-lg border border-border bg-bg-secondary p-3">
              <p className="micro-label mb-2">Factor breakdown</p>
              <div className="space-y-1.5">
                {scores.factors.map((f, i) => (
                  <div key={i} className="flex items-center gap-2 text-xs">
                    <span className="w-40 shrink-0 text-text-secondary">{f.name}</span>
                    <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-border">
                      <div className="h-full rounded-full bg-info" style={{ width: `${Math.min(100, Math.max(0, f.value))}%` }} />
                    </div>
                    <span className="w-12 text-right text-text-primary">{Math.round(f.value)}{f.weight !== undefined && <span className="text-text-muted"> ·×{f.weight}</span>}</span>
                  </div>
                ))}
                {scores.factors.every((f) => !f.note) ? null : (
                  <p className="pt-1 text-[11px] text-text-muted">{scores.factors.map((f) => f.note).filter(Boolean).join(" ")}</p>
                )}
              </div>
            </div>
          )}
        </div>
      </section>

      {/* Time series */}
      <section>
        <p className="micro-label mb-2.5">Signal velocity — current 7d vs previous 7d vs baseline</p>
        {signalsLoading ? (
          <Skeleton className="h-56" />
        ) : !series ? (
          <EmptyState compact title="No signal series" description="This trend has no dated signal values to chart yet." />
        ) : (
          <>
            <TrendLineChart
              data={series.rows}
              ariaLabel={`Signal velocity for ${trend.title}: current 7 days versus previous 7 days versus baseline`}
              series={[
                { key: "current", name: "Current 7d", accent: true },
                ...(series.hasPrevious ? [{ key: "previous", name: "Previous 7d" }] : []),
                { key: "baseline", name: "Baseline (mean)", color: STEEL },
              ]}
              formatter={(v) => `${v}`}
            />
            {!series.hasPrevious && (
              <p className="mt-1.5 text-[11px] text-text-muted">Previous-7d series unavailable — signals span less than 14 days. Missing intervals are shown as gaps, never interpolated.</p>
            )}
            {terrainRidges.length > 0 && (
              <div className="mt-3 overflow-hidden rounded-lg border border-border bg-bg-primary">
                <TrendTerrainScene
                  ridges={terrainRidges}
                  height={280}
                  label={`3D momentum terrain for ${trend.title}: current 7 days versus baseline`}
                  fallback={null}
                />
              </div>
            )}
          </>
        )}
      </section>

      {/* Evidence */}
      <section>
        <p className="micro-label mb-2.5">Evidence ({signals.length})</p>
        {signalsLoading ? (
          <Skeleton lines={4} />
        ) : !signals.length ? (
          <EmptyState compact title="No raw signals" description="Signal-level evidence has not been exposed for this trend yet." />
        ) : (
          <ul className="space-y-2">
            {signals.slice(0, 12).map((s, i) => (
              <li key={`${s.signal_name}-${i}`} className="rounded-md border border-border bg-bg-secondary p-2.5 text-[12.5px]">
                <div className="flex flex-wrap items-center gap-1.5">
                  {s.source_name && <Badge tone="neutral">{s.source_name}</Badge>}
                  <span className="font-medium text-text-primary">{s.signal_name}</span>
                  <span className="ml-auto text-[11px] text-text-muted">{fmtDate(s.observed_at)}</span>
                  {isMock(s) ? <ProvenanceBadge mock /> : <ProvenanceBadge provenance={s.provenance} />}
                </div>
                {(s.metric_name || s.metric_value !== undefined && s.metric_value !== null) && (
                  <p className="mt-1 text-text-secondary">
                    {s.metric_name}{s.metric_value !== undefined && s.metric_value !== null ? `: ${s.metric_value}${s.metric_unit ? ` ${s.metric_unit}` : ""}` : ""}
                    {s.confidence !== undefined && s.confidence !== null ? <span className="text-text-muted"> · conf {Math.round(s.confidence * 100)}%</span> : null}
                  </p>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function ScoreCard({ label, value, explainer }: { label: string; value: number | null | undefined; explainer: string }) {
  return (
    <div className="rounded-lg border border-border bg-bg-secondary p-3">
      <p className="micro-label mb-2">{label}</p>
      <ScoreBar value={value ?? null} />
      <WhyThis label="How this is computed"><p>{explainer}</p></WhyThis>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Suspense wrapper — useSearchParams() requires a Suspense boundary during
// prerender (Next.js missing-suspense-with-csr-bailout).
// ---------------------------------------------------------------------------

export default function PageWrapper() {
  return (
    <Suspense fallback={<div className="skeleton h-64 rounded" />}>
      <TrendsPage />
    </Suspense>
  );
}
