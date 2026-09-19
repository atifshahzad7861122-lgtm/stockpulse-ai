"use client";
/**
 * Private Performance — Phase 2 connection + Phase 3 personal intelligence
 * (PHASE2_DESIGN.md §5, §7).
 *
 * Adobe Contributor connection panel + performance charts/summaries +
 * Phase 3 time-filtered intelligence: earnings/downloads trends,
 * category performance table with trend labels, image-vs-video comparison,
 * top assets, growing/declining lists, themes, momentum.
 *
 * Binding honesty rules:
 * - Default state is NOT CONFIGURED; no collection is attempted until the
 *   user configures. Never mark connected without real data retrieved.
 * - NEVER display secret values — the API never returns them and neither do we.
 * - No invented earnings/downloads. Empty states stay empty until real
 *   private data exists. Phase 3 endpoints return {status:"not_configured"}
 *   as a normal response, not an error.
 */
import { useMemo, useState } from "react";
import Link from "next/link";
import { AlertTriangle, ArrowDownRight, ArrowUpRight, CheckCircle2, Minus, PlugZap, RefreshCw, TrendingDown, TrendingUp, Wallet } from "lucide-react";
import {
  Badge,
  Banner,
  Button,
  DataTable,
  EmptyState,
  Field,
  Modal,
  PageHeader,
  Panel,
  QueryView,
  Select,
  Skeleton,
  Tabs,
  Textarea,
  type Column,
} from "../../components/ui";
import { MiniBars, TrendLineChart } from "../../components/charts";
import { ConfidenceMeter, ProvenanceBadge } from "../../components/scores";
import { AdobeConnectionChip } from "../../components/sources";
import { TrendLabelBadge } from "../../components/fusion";
import {
  useAdobeConnection,
  useAdobeConnectionMutations,
  useCollectSource,
  useContentTypes,
  usePersonalCategories,
  usePersonalPerformance,
  usePersonalThemes,
  usePrivateCategories,
  usePrivatePerformanceSummary,
  useSources,
} from "../../hooks/useApi";
import type {
  AdobeConnection,
  PersonalCategoryPerformance3,
  PersonalPeriod,
  PersonalThemesResponse,
  PrivateCategoryPerformance,
  PrivatePerformanceSummary,
} from "../../types";
import { compact, enumLabel, fmtDateTime, fmtInt, fmtPct01, timeAgo } from "../../lib/format";

/** Honest fallback steps when the backend does not ship required_config. */
const FALLBACK_STEPS: { title: string; detail: string }[] = [
  {
    title: "Open your Adobe Stock Contributor dashboard",
    detail:
      "In your own browser, sign in to the Adobe Stock Contributor portal (contributor.stock.adobe.com) with the account you want tracked.",
  },
  {
    title: "Export the session from your browser",
    detail:
      "Use a cookie-export extension (e.g. Cookie-Editor) on the contributor dashboard tab and copy the session export. This proves to the collector that it may read pages you are already authorized to see.",
  },
  {
    title: "Paste it into the configuration below",
    detail:
      "The session data is stored server-side only. It is never displayed back, never logged, and never leaves this machine. You can revoke it at any time by clearing the configuration.",
  },
  {
    title: "Test, then sync",
    detail:
      "Use “Test connection” to validate the config format, then “Sync now” to run the first collection. Until a successful sync, every performance panel shows an honest empty state.",
  },
];

function configSteps(conn: AdobeConnection | undefined): { title: string; detail?: string }[] {
  const rc = conn?.required_config;
  if (Array.isArray(rc) && rc.length) {
    return rc.map((s) => (typeof s === "string" ? { title: s } : s));
  }
  return FALLBACK_STEPS;
}

function isConfigured(conn: AdobeConnection | undefined): boolean {
  if (!conn) return false;
  if (conn.configured === true) return true;
  return conn.status !== "NOT_CONFIGURED";
}

// ---------------------------------------------------------------------------
// Connection panel (setup screen when NOT CONFIGURED)
// ---------------------------------------------------------------------------

function ConnectionPanel() {
  const conn = useAdobeConnection({ retry: false });
  const mutations = useAdobeConnectionMutations();
  const collect = useCollectSource();
  const sources = useSources({ retry: false });
  const [formOpen, setFormOpen] = useState(false);

  const adobeSource = (sources.data ?? []).find((s) =>
    s.source_type === "adobe_contributor" || s.name.toLowerCase().includes("adobe"),
  );

  const syncNow = () => {
    if (adobeSource) collect.mutate(adobeSource.id);
  };

  return (
    <Panel
      title="Adobe Contributor connection"
      action={
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="outline" loading={mutations.test.isPending} onClick={() => mutations.test.mutate()}>
            Test connection
          </Button>
          <Button
            size="sm"
            variant="secondary"
            icon={<RefreshCw size={13} />}
            loading={collect.isPending}
            disabled={!adobeSource || !isConfigured(conn.data)}
            title={
              !adobeSource
                ? "The adobe_contributor source is not registered on the backend yet"
                : !isConfigured(conn.data)
                  ? "Configure the connection first"
                  : `Run a collection on ${adobeSource.name}`
            }
            onClick={syncNow}
          >
            Sync now
          </Button>
        </div>
      }
    >
      <QueryView
        query={conn}
        loading={<Skeleton lines={6} />}
        empty={
          <SetupScreen
            conn={undefined}
            formOpen={formOpen}
            setFormOpen={setFormOpen}
            saving={mutations.save.isPending}
            onSave={(body) => mutations.save.mutate(body)}
          />
        }
        errorTitle="Connection status unavailable"
      >
        {(c) =>
          isConfigured(c) ? (
            <ConfiguredState conn={c} onReconfigure={() => setFormOpen(true)} />
          ) : (
            <SetupScreen
              conn={c}
              formOpen={formOpen}
              setFormOpen={setFormOpen}
              saving={mutations.save.isPending}
              onSave={(body) => mutations.save.mutate(body, { onSuccess: () => setFormOpen(false) })}
            />
          )
        }
      </QueryView>
    </Panel>
  );
}

function ConfiguredState({ conn, onReconfigure }: { conn: AdobeConnection; onReconfigure: () => void }) {
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <AdobeConnectionChip status={conn.status} />
        <span className="inline-flex items-center gap-1.5 text-[13px] text-status-success">
          <CheckCircle2 size={14} aria-hidden /> Session stored server-side
        </span>
        {conn.session_type && (
          <span className="text-xs text-text-muted">Type: <span className="font-mono">{conn.session_type}</span></span>
        )}
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        <div className="rounded-lg border border-border bg-bg-secondary p-3">
          <p className="text-[10px] font-semibold uppercase tracking-[0.08em] text-text-muted">Last sync</p>
          <p className="mt-1 text-sm text-text-primary">{conn.last_sync ? timeAgo(conn.last_sync) : "Never — run “Sync now” above"}</p>
        </div>
        <div className="rounded-lg border border-border bg-bg-secondary p-3">
          <p className="text-[10px] font-semibold uppercase tracking-[0.08em] text-text-muted">Session value</p>
          <p className="mt-1 text-sm text-text-muted">Hidden — never displayed or logged</p>
        </div>
        <div className="rounded-lg border border-border bg-bg-secondary p-3">
          <p className="text-[10px] font-semibold uppercase tracking-[0.08em] text-text-muted">Manage</p>
          <Button size="sm" variant="ghost" className="mt-1 px-0" onClick={onReconfigure}>
            Replace session…
          </Button>
        </div>
      </div>
      {conn.error && (
        <div className="flex items-start gap-2 rounded-lg border border-status-danger/30 bg-status-danger/[0.06] px-3 py-2.5 text-[13px]">
          <AlertTriangle size={14} className="mt-0.5 shrink-0 text-status-danger" aria-hidden />
          <div>
            <p className="font-semibold text-text-primary">Last collection error</p>
            <p className="mt-0.5 text-text-secondary">{conn.error}</p>
          </div>
        </div>
      )}
      <p className="text-xs text-text-muted">
        Collection runs against only your own contributor-dashboard pages. Nothing is fabricated —
        if a sync fails, the failure is recorded and shown here.
      </p>
    </div>
  );
}

function SetupScreen({
  conn,
  formOpen,
  setFormOpen,
  saving,
  onSave,
}: {
  conn: AdobeConnection | undefined;
  formOpen: boolean;
  setFormOpen: (v: boolean) => void;
  saving: boolean;
  onSave: (body: { session_type: string; session_data?: string; notes?: string }) => void;
}) {
  const steps = configSteps(conn);
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <AdobeConnectionChip status={conn?.status ?? "NOT_CONFIGURED"} />
        <p className="text-[13px] text-text-secondary">
          Not configured — no collection has been attempted and no private data exists. That is the honest state, not an error.
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-lg border border-border bg-bg-secondary p-3">
          <p className="text-[10px] font-semibold uppercase tracking-[0.08em] text-text-muted">Last sync</p>
          <p className="mt-1 text-sm text-text-muted">{conn?.last_sync ? fmtDateTime(conn.last_sync) : "—"}</p>
        </div>
        <div className="rounded-lg border border-border bg-bg-secondary p-3">
          <p className="text-[10px] font-semibold uppercase tracking-[0.08em] text-text-muted">Required configuration</p>
          <p className="mt-1 text-sm text-text-secondary">{steps.length} steps below</p>
        </div>
      </div>

      {conn?.error && (
        <div className="flex items-start gap-2 rounded-lg border border-status-danger/30 bg-status-danger/[0.06] px-3 py-2.5 text-[13px]" role="alert">
          <AlertTriangle size={14} className="mt-0.5 shrink-0 text-status-danger" aria-hidden />
          <div>
            <p className="font-semibold text-text-primary">Configuration error</p>
            <p className="mt-0.5 text-text-secondary">{conn.error}</p>
          </div>
        </div>
      )}

      <ol className="space-y-3">
        {steps.map((s, i) => (
          <li key={i} className="flex gap-3 rounded-lg border border-border bg-bg-secondary p-3.5">
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accent-primary/15 font-display text-xs font-bold text-accent-primary">
              {i + 1}
            </span>
            <div>
              <p className="text-[13.5px] font-semibold text-text-primary">{s.title}</p>
              {s.detail && <p className="mt-1 text-[13px] leading-relaxed text-text-secondary">{s.detail}</p>}
            </div>
          </li>
        ))}
      </ol>

      <div className="flex flex-wrap items-center gap-3 rounded-lg border border-status-warning/30 bg-status-warning/[0.06] px-3.5 py-3">
        <PlugZap size={15} className="shrink-0 text-status-warning" aria-hidden />
        <p className="flex-1 text-[13px] text-text-secondary">
          Ready when you are — paste your own browser session and the collector can start reading your dashboard.
        </p>
        <Button size="sm" variant="primary" onClick={() => setFormOpen(true)}>
          Configure connection
        </Button>
      </div>

      <ConnectionFormModal
        open={formOpen}
        onClose={() => setFormOpen(false)}
        saving={saving}
        onSave={onSave}
      />
    </div>
  );
}

function ConnectionFormModal({
  open,
  onClose,
  saving,
  onSave,
}: {
  open: boolean;
  onClose: () => void;
  saving: boolean;
  onSave: (body: { session_type: string; session_data?: string; notes?: string }) => void;
}) {
  const [sessionType, setSessionType] = useState("browser_session_export");
  const [sessionData, setSessionData] = useState("");
  const [notes, setNotes] = useState("");

  const submit = () => {
    onSave({ session_type: sessionType, session_data: sessionData || undefined, notes: notes || undefined });
    // Never retain secret material in component state after submit.
    setSessionData("");
    setNotes("");
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Configure Adobe Contributor connection"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button variant="primary" loading={saving} disabled={!sessionData.trim()} onClick={submit}>
            Save configuration
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Banner id="private-secret" tone="warning">
          <strong className="text-text-primary">Session data is secret.</strong> It is stored
          server-side only, never displayed back, never logged, and never committed. Only paste a
          session from <em>your own</em> browser.
        </Banner>
        <Field label="Session type" hint="How the session was obtained.">
          <Select value={sessionType} onChange={(e) => setSessionType(e.target.value)}>
            <option value="browser_session_export">Browser session export (cookie extension)</option>
            <option value="manual">Manual entry</option>
          </Select>
        </Field>
        <Field
          label="Session export"
          required
          hint="Paste the exported session here. It will not be shown again after saving."
        >
          <Textarea
            value={sessionData}
            onChange={(e) => setSessionData(e.target.value)}
            placeholder="Paste session export…"
            rows={5}
            className="font-mono text-xs"
            autoComplete="off"
            spellCheck={false}
          />
        </Field>
        <Field label="Notes" hint="Optional reminder for yourself (e.g. which browser profile). Never a secret.">
          <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} />
        </Field>
      </div>
    </Modal>
  );
}

// ---------------------------------------------------------------------------
// Performance summaries (honest empty states until real data exists)
// ---------------------------------------------------------------------------

function Kpi({
  label,
  value,
  provenance,
  mock,
  suffix,
}: {
  label: string;
  value: number | null | undefined;
  provenance?: PrivatePerformanceSummary["provenance"];
  mock?: boolean;
  suffix?: string;
}) {
  return (
    <div className="rounded-lg border border-border bg-bg-secondary p-3.5 text-center">
      <p className="font-display text-2xl font-semibold text-text-primary" style={{ fontVariantNumeric: "tabular-nums" }}>
        {value === null || value === undefined ? "—" : fmtInt(value)}
        {suffix && value !== null && value !== undefined && <span className="text-sm font-normal text-text-muted"> {suffix}</span>}
      </p>
      <p className="mt-0.5 text-[11px] text-text-muted">{label}</p>
      <div className="mt-1.5 flex justify-center">
        <ProvenanceBadge provenance={provenance} mock={mock} />
      </div>
    </div>
  );
}

function PerformancePanel() {
  const summary = usePrivatePerformanceSummary({ retry: false });
  const categories = usePrivateCategories({ retry: false });

  const catColumns: Column<PrivateCategoryPerformance>[] = [
    { key: "category", header: "Category", render: (c) => <span className="font-medium text-text-primary">{c.category}</span> },
    {
      key: "downloads",
      header: "Downloads",
      render: (c) => <span style={{ fontVariantNumeric: "tabular-nums" }}>{fmtInt(c.downloads)}</span>,
    },
    {
      key: "earnings",
      header: "Earnings",
      render: (c) => <span style={{ fontVariantNumeric: "tabular-nums" }}>${fmtInt(c.earnings)}</span>,
    },
    {
      key: "assets",
      header: "Assets",
      render: (c) => <span style={{ fontVariantNumeric: "tabular-nums" }}>{fmtInt(c.asset_count)}</span>,
    },
  ];

  return (
    <div className="space-y-4">
      <Panel title="Performance summary" action={<ProvenanceHint />}>
        <QueryView
          query={summary}
          loading={<Skeleton lines={5} />}
          empty={<PerformanceEmpty />}
          errorTitle="Performance data unavailable"
        >
          {(s) => {
            const t = s.totals;
            if (!s.has_data || !t) return <PerformanceEmpty message={s.message} />;
            const hasNumbers =
              (t.earnings ?? 0) > 0 ||
              (t.downloads ?? 0) > 0 ||
              (t.asset_count ?? 0) > 0 ||
              (s.by_category?.length ?? 0) > 0;
            if (!hasNumbers) return <PerformanceEmpty message={s.message} />;
            const range =
              t.date_from || t.date_to ? `${t.date_from ?? "…"} → ${t.date_to ?? "…"}` : null;
            const series = mergeTrend(s.earnings_trend, s.downloads_trend);
            const acceptance = s.acceptance_rate;
            return (
              <div className="space-y-4">
                {range && <p className="text-xs text-text-muted">Range: {range}</p>}
                <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                  <Kpi label="Earnings" value={t.earnings} suffix={t.currency} provenance={s.provenance} mock={s.mock} />
                  <Kpi label="Downloads" value={t.downloads} provenance={s.provenance} mock={s.mock} />
                  <Kpi label="Assets tracked" value={t.asset_count} provenance={s.provenance} mock={s.mock} />
                  <Kpi
                    label="Acceptance rate"
                    value={acceptance === null || acceptance === undefined ? null : Math.round((acceptance <= 1 ? acceptance * 100 : acceptance))}
                    suffix={acceptance !== null && acceptance !== undefined ? "%" : undefined}
                    provenance={s.provenance}
                    mock={s.mock}
                  />
                </div>
                {series.length > 0 && (
                  <div>
                    <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.06em] text-text-muted">
                      Earnings & downloads over time
                    </p>
                    <TrendLineChart
                      data={series.slice(-30).map((p) => ({ label: p.date.slice(5), earnings: p.earnings, downloads: p.downloads }))}
                      series={[
                        { key: "earnings", name: "Earnings", accent: true },
                        { key: "downloads", name: "Downloads" },
                      ]}
                      ariaLabel="Earnings and downloads over time"
                      height={200}
                      formatter={(v, name) => (name === "Earnings" ? `$${fmtInt(v)}` : fmtInt(v))}
                    />
                    <p className="mt-1 text-[11px] text-text-muted">
                      Daily earnings and downloads (last {Math.min(30, series.length)} days). From your own data — never a guarantee.
                    </p>
                  </div>
                )}
                {(s.by_category?.length ?? 0) > 0 && (
                  <div>
                    <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.06em] text-text-muted">
                      By category
                    </p>
                    <div className="overflow-hidden rounded-lg border border-border">
                      <DataTable<PrivateCategoryPerformance>
                        columns={catColumns}
                        rows={s.by_category}
                        rowKey={(c) => c.category}
                      />
                    </div>
                  </div>
                )}
              </div>
            );
          }}
        </QueryView>
      </Panel>

      <Panel title="Category performance" action={<ProvenanceHint />}>
        <QueryView
          query={categories}
          loading={<Skeleton lines={4} />}
          empty={<PerformanceEmpty compact />}
          errorTitle="Category performance unavailable"
        >
          {(rows) =>
            rows.length ? (
              <div className="overflow-hidden rounded-lg border border-border">
                <DataTable<PrivateCategoryPerformance>
                  columns={catColumns}
                  rows={rows}
                  rowKey={(c) => `${c.category}-${c.snapshot_date ?? "latest"}`}
                />
              </div>
            ) : (
              <PerformanceEmpty compact />
            )
          }
        </QueryView>
      </Panel>
    </div>
  );
}

function ProvenanceHint() {
  return (
    <span className="text-[11px] text-text-muted">
      Real numbers only from <span className="font-mono">USER_PROVIDED</span> rows — your own dashboard.
    </span>
  );
}

function PerformanceEmpty({ compact, message }: { compact?: boolean; message?: string | null } = {}) {
  return (
    <EmptyState
      compact={compact}
      icon={<Wallet size={18} />}
      title="No private performance data yet"
      description={
        message ??
        "Connect your Adobe Contributor account above and run a sync. We never invent earnings or downloads — these panels stay empty until real data arrives."
      }
    />
  );
}

/** Merge the backend's earnings/downloads trend arrays by date. */
function mergeTrend(
  earnings?: { date: string; earnings: number }[],
  downloads?: { date: string; downloads: number }[],
): { date: string; earnings: number; downloads: number }[] {
  const map = new Map<string, { date: string; earnings: number; downloads: number }>();
  for (const p of earnings ?? [])
    map.set(p.date, { date: p.date, earnings: p.earnings, downloads: map.get(p.date)?.downloads ?? 0 });
  for (const p of downloads ?? [])
    map.set(p.date, { date: p.date, earnings: map.get(p.date)?.earnings ?? 0, downloads: p.downloads });
  return Array.from(map.values()).sort((a, b) => a.date.localeCompare(b.date));
}

// ---------------------------------------------------------------------------
// Phase 3 — personal intelligence panels (PERSONAL INTELLIGENCE module)
// Time filters 7D/30D/90D/1Y/ALL, TrendLineChart earnings+downloads,
// category table with trend labels, content-type comparison, top assets,
// growing/declining lists, themes, momentum.
// ---------------------------------------------------------------------------

const PERSONAL_PERIODS: { value: PersonalPeriod; label: string }[] = [
  { value: "7d", label: "7D" },
  { value: "30d", label: "30D" },
  { value: "90d", label: "90D" },
  { value: "1y", label: "1Y" },
  { value: "all", label: "All" },
];

function MomentumPill({ value, label }: { value: number | null | undefined; label: string }) {
  if (value === null || value === undefined || Number.isNaN(value)) return <span className="text-xs text-text-muted">{label}: —</span>;
  const up = value > 0;
  const flat = value === 0;
  const Icon = up ? ArrowUpRight : flat ? Minus : ArrowDownRight;
  return (
    <span className={`inline-flex items-center gap-1 text-xs font-medium ${up ? "text-status-success" : flat ? "text-text-muted" : "text-status-danger"}`}>
      <Icon size={13} aria-hidden />
      {label}: {up ? "+" : ""}{Math.round(value)}%
    </span>
  );
}

function NotConfiguredNote() {
  return (
    <EmptyState
      compact
      icon={<Wallet size={18} />}
      title="Private performance not connected"
      description={
        <span>
          This panel activates once your Adobe Stock data is connected above. Until then it shows nothing —
          we never invent earnings or downloads.
        </span>
      }
    />
  );
}

function PersonalIntelligencePanel() {
  const [period, setPeriod] = useState<PersonalPeriod>("30d");
  const perf = usePersonalPerformance(period, { retry: false });
  const cats = usePersonalCategories(period, { retry: false });
  const types = useContentTypes({ retry: false });
  const themes = usePersonalThemes({ retry: false });

  const categoryColumns: Column<PersonalCategoryPerformance3>[] = useMemo(
    () => [
      { key: "category", header: "Category", render: (c) => <span className="font-medium text-text-primary">{c.category}</span> },
      { key: "trend", header: "Trend", render: (c) => <TrendLabelBadge label={c.trend_label} /> },
      { key: "downloads", header: "Downloads", render: (c) => <span style={{ fontVariantNumeric: "tabular-nums" }}>{fmtInt(c.downloads)}</span> },
      { key: "earnings", header: "Earnings", render: (c) => <span style={{ fontVariantNumeric: "tabular-nums" }}>${fmtInt(c.earnings)}</span> },
      { key: "avg_dl", header: "Avg downloads/asset", render: (c) => <span style={{ fontVariantNumeric: "tabular-nums" }}>{c.avg_downloads_per_asset !== null ? c.avg_downloads_per_asset.toFixed(1) : "—"}</span> },
      { key: "avg_e", header: "Avg earnings/asset", render: (c) => <span style={{ fontVariantNumeric: "tabular-nums" }}>{c.avg_earnings_per_asset !== null ? `$${c.avg_earnings_per_asset.toFixed(2)}` : "—"}</span> },
      { key: "acceptance", header: "Acceptance", render: (c) => fmtPct01(c.acceptance_rate) },
      { key: "mom7", header: "Momentum 7d", render: (c) => <MomentumPill value={c.momentum_7d} label="7d" /> },
      { key: "mom30", header: "Momentum 30d", render: (c) => <MomentumPill value={c.momentum_30d} label="30d" /> },
    ],
    [],
  );

  const catsData = cats.data;
  const { growing, declining } = useMemo(() => {
    const rows = catsData?.status === "available" ? catsData.categories : [];
    return {
      growing: rows.filter((c) => c.trend_label === "growing").sort((a, b) => b.momentum_30d! - a.momentum_30d!).slice(0, 5),
      declining: rows.filter((c) => c.trend_label === "declining").sort((a, b) => a.momentum_30d! - b.momentum_30d!).slice(0, 5),
    };
  }, [catsData]);

  return (
    <Panel
      title="Personal intelligence"
      action={<ProvenanceHint />}
    >
      <Tabs
        tabs={PERSONAL_PERIODS.map((p) => ({ value: p.value, label: p.label }))}
        value={period}
        onChange={(v) => setPeriod(v as PersonalPeriod)}
        className="mb-4"
      />

      {/* KPI row + trends */}
      <QueryView query={perf} loading={<Skeleton lines={6} />} errorTitle="Personal intelligence unavailable">
        {(p) => {
          if (p.status !== "available") return <NotConfiguredNote />;
          return (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                {[
                  { label: "Earnings", value: p.earnings_total !== null ? `$${fmtInt(p.earnings_total)}` : "—" },
                  { label: "Downloads", value: fmtInt(p.downloads_total) },
                  { label: "Acceptance rate", value: fmtPct01(p.acceptance_rate) },
                  { label: "Assets tracked", value: fmtInt(p.assets_tracked) },
                ].map((k) => (
                  <div key={k.label} className="rounded-lg border border-border bg-bg-secondary p-3.5 text-center">
                    <p className="font-display text-2xl font-semibold text-text-primary" style={{ fontVariantNumeric: "tabular-nums" }}>{k.value}</p>
                    <p className="mt-0.5 text-[11px] text-text-muted">{k.label}</p>
                  </div>
                ))}
              </div>
              <div className="flex flex-wrap gap-4">
                <MomentumPill value={p.earnings_momentum} label="Earnings momentum" />
                <MomentumPill value={p.downloads_momentum} label="Downloads momentum" />
                {p.updated_at && <span className="text-xs text-text-muted">Updated {timeAgo(p.updated_at)}</span>}
              </div>
              {(p.top_categories?.length ?? 0) > 0 && (
                <div>
                  <p className="micro-label mb-2">Top categories — your download totals</p>
                  <MiniBars rows={p.top_categories.slice(0, 8).map((c) => ({ label: c.category, value: c.downloads, color: "#FF5C35" }))} />
                  <p className="mt-1 text-[11px] text-text-muted">
                    Totals for this period from your own data. Earnings/downloads time-series charts appear here once the backend ships per-day points.
                  </p>
                </div>
              )}
            </div>
          );
        }}
      </QueryView>

      {/* Image vs video */}
      <div className="mt-6">
        <p className="micro-label mb-2">Image vs video — your own results</p>
        <QueryView query={types} loading={<Skeleton lines={3} />} errorTitle="Content-type comparison unavailable">
          {(t) => {
            if (t.status !== "available" || !t.types.length) return <NotConfiguredNote />;
            const img = t.types.find((x) => x.content_type === "image");
            const vid = t.types.find((x) => x.content_type === "video");
            const better = img && vid ? (img.avg_earnings_per_asset !== null && vid.avg_earnings_per_asset !== null
              ? (img.avg_earnings_per_asset >= vid.avg_earnings_per_asset ? "image" : "video") : null) : null;
            return (
              <div className="grid gap-3 sm:grid-cols-2">
                {[img, vid].map((x) =>
                  x ? (
                    <div key={x.content_type} className={`rounded-lg border p-4 ${better === x.content_type ? "border-status-success/50 bg-bg-secondary" : "border-border bg-bg-secondary"}`}>
                      <div className="flex items-center gap-2">
                        <p className="text-xs font-semibold uppercase tracking-[0.06em] text-text-secondary">{x.content_type}</p>
                        {better === x.content_type && <Badge tone="success">Better $/asset</Badge>}
                        <TrendLabelBadge label={x.trend_label} />
                      </div>
                      <p className="mt-2 font-display text-xl font-semibold text-text-primary" style={{ fontVariantNumeric: "tabular-nums" }}>
                        ${fmtInt(x.earnings)} <span className="text-xs font-normal text-text-muted">· {fmtInt(x.downloads)} downloads</span>
                      </p>
                      <p className="mt-1 text-[12px] text-text-muted">
                        {fmtInt(x.assets_total)} assets · {fmtPct01(x.acceptance_rate)} acceptance ·{" "}
                        {x.avg_earnings_per_asset !== null ? `$${x.avg_earnings_per_asset.toFixed(2)}/asset` : "—/asset"}
                      </p>
                      <div className="mt-2 flex gap-3">
                        <MomentumPill value={x.momentum_7d} label="7d" />
                        <MomentumPill value={x.momentum_30d} label="30d" />
                      </div>
                    </div>
                  ) : null,
                )}
              </div>
            );
          }}
        </QueryView>
      </div>

      {/* Category table */}
      <div className="mt-6">
        <p className="micro-label mb-2">Category performance ({enumLabel(period)})</p>
        <QueryView query={cats} loading={<Skeleton lines={5} />} errorTitle="Category performance unavailable">
          {(r) => {
            if (r.status !== "available" || !r.categories.length) return <NotConfiguredNote />;
            return (
              <div className="overflow-hidden rounded-lg border border-border">
                <DataTable<PersonalCategoryPerformance3>
                  columns={categoryColumns}
                  rows={[...r.categories].sort((a, b) => b.earnings - a.earnings)}
                  rowKey={(c) => c.category}
                />
              </div>
            );
          }}
        </QueryView>
      </div>

      {/* Growing vs declining */}
      <div className="mt-6 grid gap-4 md:grid-cols-2">
        <div>
          <p className="micro-label mb-2 flex items-center gap-1.5"><TrendingUp size={12} className="text-status-success" /> Growing for you</p>
          <QueryView query={cats} loading={<Skeleton lines={3} />} errorTitle="Unavailable">
            {(r) => {
              if (r.status !== "available") return <NotConfiguredNote />;
              if (!growing.length) return <EmptyState compact title="No growing categories" description="Nothing is tagged “growing” in this window." />;
              return (
                <ul className="space-y-1.5">
                  {growing.map((c) => (
                    <li key={c.category} className="flex items-center gap-2 rounded-md border border-border bg-bg-secondary px-3 py-2 text-[13px]">
                      <span className="flex-1 font-medium text-text-primary">{c.category}</span>
                      <MomentumPill value={c.momentum_30d} label="30d" />
                    </li>
                  ))}
                </ul>
              );
            }}
          </QueryView>
        </div>
        <div>
          <p className="micro-label mb-2 flex items-center gap-1.5"><TrendingDown size={12} className="text-status-danger" /> Declining for you</p>
          <QueryView query={cats} loading={<Skeleton lines={3} />} errorTitle="Unavailable">
            {(r) => {
              if (r.status !== "available") return <NotConfiguredNote />;
              if (!declining.length) return <EmptyState compact title="No declining categories" description="Nothing is tagged “declining” in this window." />;
              return (
                <ul className="space-y-1.5">
                  {declining.map((c) => (
                    <li key={c.category} className="flex items-center gap-2 rounded-md border border-border bg-bg-secondary px-3 py-2 text-[13px]">
                      <span className="flex-1 font-medium text-text-primary">{c.category}</span>
                      <MomentumPill value={c.momentum_30d} label="30d" />
                    </li>
                  ))}
                </ul>
              );
            }}
          </QueryView>
        </div>
      </div>

      {/* Themes */}
      <div className="mt-6">
        <p className="micro-label mb-2">Themes in your portfolio</p>
        <QueryView query={themes} loading={<Skeleton lines={3} />} errorTitle="Themes unavailable">
          {(t: PersonalThemesResponse) => {
            if (t.status !== "available" || !t.themes.length) return <NotConfiguredNote />;
            return (
              <div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
                {t.themes.map((th) => (
                  <div key={th.theme} className="rounded-lg border border-border bg-bg-secondary p-3">
                    <div className="flex items-center gap-2">
                      <p className="flex-1 text-[13px] font-semibold text-text-primary">{th.theme}</p>
                      {th.trend && <TrendLabelBadge label={th.trend} />}
                    </div>
                    <p className="mt-1.5 text-[12px] text-text-muted" style={{ fontVariantNumeric: "tabular-nums" }}>
                      {fmtInt(th.assets)} assets · {fmtInt(th.downloads)} downloads · ${fmtInt(th.earnings)}
                    </p>
                    {th.keywords.length > 0 && (
                      <p className="mt-1.5 text-[11px] leading-relaxed text-text-muted">{th.keywords.slice(0, 6).join(", ")}</p>
                    )}
                  </div>
                ))}
              </div>
            );
          }}
        </QueryView>
      </div>
    </Panel>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function PrivatePage() {
  return (
    <div className="space-y-4">
      <PageHeader
        title="Private Performance"
        description="Your own Adobe Stock contributor performance — earnings, downloads, and per-category results. Single-user: this data never leaves your machine and is never mixed with public trend data."
        badge={<Badge tone="info">Private · append-only</Badge>}
      />
      <ConnectionPanel />
      <PersonalIntelligencePanel />
      <PerformancePanel />
      <p className="text-xs text-text-muted">
        Private rows are time-series snapshots (never updated in place). Related:{" "}
        <Link href="/analytics" className="text-accent-secondary hover:underline">Analytics</Link> ·{" "}
        <Link href="/runs" className="text-accent-secondary hover:underline">Collection runs</Link> ·{" "}
        <Link href="/daily" className="text-accent-secondary hover:underline">Daily Intelligence</Link>
      </p>
    </div>
  );
}
