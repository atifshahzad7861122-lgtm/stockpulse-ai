"use client";
/**
 * Phase 3 shared UI: fusion score display, personal-fit honesty chips,
 * component breakdown with visible saturation subtraction, evidence
 * provenance rows, and the capacity settings form.
 *
 * Binding rules:
 * - personal_fit === null → "N/A — private data not connected", NEVER a number.
 * - MARKET-ONLY badge whenever label is MARKET-ONLY (personal_fit is null).
 * - No "will sell / guaranteed" copy anywhere.
 */
import { useEffect, useState } from "react";
import { Badge, Button, Field, Input, Panel, Select, WhyThis, cx } from "./ui";
import { ConfidenceMeter, ProvenanceBadge } from "./scores";
import { GOLD, RACING_RED, SUCCESS, STEEL } from "./palette";
import { fmtDateTime, fmtPct01 } from "../lib/format";
import { useDailyMutations, useDailySettings } from "../hooks/useApi";
import type {
  FusionComponents,
  FusionEvidence,
  FusionLabel,
  FusionScore,
  PersonalTrendLabel,
} from "../types";

// ---------------------------------------------------------------------------
// Fusion label — FUSED (personal data included) vs MARKET-ONLY (no private data)
// ---------------------------------------------------------------------------

export function FusionLabelBadge({ label }: { label: FusionLabel | null | undefined }) {
  if (!label) return <Badge tone="muted">Score pending</Badge>;
  if (label === "FUSED") return <Badge tone="accent">Fused</Badge>;
  return (
    <Badge tone="info" title="Personal performance data is not connected, so this score blends market signals only.">
      Market-only
    </Badge>
  );
}

// ---------------------------------------------------------------------------
// Personal Fit — a real number, or the honest N/A state (never a fake number)
// ---------------------------------------------------------------------------

export function PersonalFitChip({ value, compact }: { value: number | null | undefined; compact?: boolean }) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return (
      <Badge tone="muted" title="Personal Fit needs your own Adobe Stock performance history — connect it on the Private page.">
        Personal fit N/A — private data not connected
      </Badge>
    );
  }
  return (
    <span className={cx("inline-flex items-center gap-1.5", compact && "text-xs")}>
      <span
        className="h-1.5 w-12 overflow-hidden rounded-full bg-border"
        role="img"
        aria-label={`Personal fit ${Math.round(value)} out of 100`}
      >
        <span className="block h-full rounded-full" style={{ background: SUCCESS, width: `${Math.min(100, value)}%` }} />
      </span>
      <span className="font-semibold text-text-primary" style={{ fontVariantNumeric: "tabular-nums" }}>
        {Math.round(value)}
      </span>
      <span className="text-[11px] text-text-muted">Personal fit</span>
    </span>
  );
}

// ---------------------------------------------------------------------------
// Component breakdown — every component named, saturation subtracted visibly
// ---------------------------------------------------------------------------

const COMPONENT_LABELS: [keyof FusionComponents, string][] = [
  ["market_opportunity", "Market opportunity"],
  ["personal_fit", "Personal fit"],
  ["trend_momentum", "Trend momentum"],
  ["commercial_potential", "Commercial potential"],
  ["seasonality", "Seasonality"],
  ["saturation_risk", "Saturation risk"],
  ["prediction_confidence", "Prediction confidence"],
  ["personal_momentum", "Personal momentum"],
  ["historical_performance", "Historical performance"],
];

export function FusionBreakdown({ fusion }: { fusion: FusionScore }) {
  const c = fusion.components;
  return (
    <div>
      <div className="flex items-baseline justify-between">
        <p className="micro-label">Unified score</p>
        <p className="font-display text-2xl font-semibold text-text-primary" style={{ fontVariantNumeric: "tabular-nums" }}>
          {Math.round(fusion.unified_score)}
        </p>
      </div>
      <div className="mt-3 space-y-2">
        {COMPONENT_LABELS.map(([key, label]) => {
          const v = c[key];
          const isSaturation = key === "saturation_risk";
          if (v === null || v === undefined || Number.isNaN(v)) {
            return (
              <div key={key} className="flex items-center gap-2.5">
                <span className="w-44 shrink-0 text-xs text-text-muted">{label}</span>
                <span className="text-xs text-text-muted">— not available</span>
              </div>
            );
          }
          const barValue = isSaturation ? v : Math.max(0, Math.min(100, v));
          const color = isSaturation ? RACING_RED : GOLD;
          return (
            <div key={key} className="flex items-center gap-2.5" title={isSaturation ? "Saturation risk is subtracted from the unified score — higher saturation lowers it." : undefined}>
              <span className="w-44 shrink-0 text-xs text-text-secondary">
                {label}
                {isSaturation && <span className="text-status-danger"> (−)</span>}
              </span>
              <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-border" aria-hidden>
                <span className="block h-full rounded-full" style={{ width: `${barValue}%`, background: color }} />
              </span>
              <span className="w-12 shrink-0 text-right text-xs font-semibold text-text-primary" style={{ fontVariantNumeric: "tabular-nums" }}>
                {isSaturation ? `−${Math.round(v)}` : Math.round(v)}
              </span>
            </div>
          );
        })}
      </div>
      {fusion.explanation && (
        <p className="mt-3 rounded-md border border-border bg-bg-secondary p-2.5 text-[12.5px] leading-relaxed text-text-secondary">
          {fusion.explanation}
        </p>
      )}
      <div className="mt-2.5 flex flex-wrap items-center gap-2">
        <FusionLabelBadge label={fusion.label} />
        <ConfidenceMeter value={fusion.confidence_score} />
        <ProvenanceBadge provenance={fusion.data_provenance} mock={fusion.mock} />
        {fusion.computed_at && <span className="text-[11px] text-text-muted">Computed {fmtDateTime(fusion.computed_at)}</span>}
      </div>
      <WhyThis label="Why this score">
        <p>
          The unified score blends market opportunity, trend momentum, commercial potential and seasonality,
          then subtracts saturation risk. When your private performance is connected, personal fit, personal
          momentum and historical performance are folded in as well (label: <strong>FUSED</strong>). Without
          private data the score is <strong>MARKET-ONLY</strong> — still honest, just less personalized.
        </p>
        <p className="mt-1.5">Every component above is shown; a missing component contributes nothing, not a guess.</p>
      </WhyThis>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Evidence provenance — every recommendation shows where its evidence came
// from: source, timestamp, signal, private/public, prediction version.
// ---------------------------------------------------------------------------

export function EvidenceList({ evidence }: { evidence?: FusionEvidence[] | null }) {
  if (!evidence || !evidence.length) {
    return <p className="text-xs text-text-muted">No evidence rows recorded for this recommendation.</p>;
  }
  return (
    <ul className="space-y-1.5">
      {evidence.map((e, i) => (
        <li key={i} className="rounded-md border border-border bg-bg-secondary px-2.5 py-2">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-[12px] font-medium text-text-primary">{e.signal}</span>
            {e.private ? <Badge tone="warning">Private data</Badge> : <Badge tone="info">Public signal</Badge>}
            {e.prediction_version && <Badge tone="neutral" title="Prediction model version">v{e.prediction_version}</Badge>}
            <span className="ml-auto text-[11px] text-text-muted">
              {e.source} · {fmtDateTime(e.observed_at)}
            </span>
          </div>
        </li>
      ))}
    </ul>
  );
}

// ---------------------------------------------------------------------------
// Trend label (growing / stable / declining) — text + color, never color alone
// ---------------------------------------------------------------------------

export function TrendLabelBadge({ label }: { label: PersonalTrendLabel | string | null | undefined }) {
  if (!label) return <Badge tone="muted">—</Badge>;
  const l = String(label).toLowerCase();
  const tone = l === "growing" ? "success" : l === "declining" ? "danger" : "neutral";
  return <Badge tone={tone}>{l}</Badge>;
}

// ---------------------------------------------------------------------------
// Capacity settings — writes PUT /daily-production/settings
// ---------------------------------------------------------------------------

const PRIORITY_OPTIONS = [
  { value: "balanced", label: "Balanced (market + personal)" },
  { value: "market_first", label: "Market first (chase rising niches)" },
  { value: "personal_first", label: "Personal first (play to my strengths)" },
  { value: "low_saturation", label: "Low saturation first (open niches)" },
];

export function CapacitySettingsForm() {
  const settings = useDailySettings();
  const muts = useDailyMutations();
  const [weekly, setWeekly] = useState("");
  const [daily, setDaily] = useState("");
  const [images, setImages] = useState("");
  const [videos, setVideos] = useState("");
  const [maxGen, setMaxGen] = useState("");
  const [priority, setPriority] = useState("balanced");
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    const s = settings.data;
    if (s && !dirty) {
      setWeekly(String(s.weekly_capacity ?? ""));
      setDaily(String(s.daily_target ?? ""));
      setImages(String(s.image_target ?? ""));
      setVideos(String(s.video_target ?? ""));
      setMaxGen(String(s.max_daily_generation ?? ""));
      setPriority(s.priority_preference ?? "balanced");
    }
  }, [settings.data, dirty]);

  const num = (v: string): number | undefined => {
    if (v.trim() === "") return undefined;
    const n = Number(v);
    return Number.isFinite(n) && n >= 0 ? Math.floor(n) : undefined;
  };

  const save = () => {
    muts.saveSettings.mutate(
      {
        weekly_capacity: num(weekly) ?? 20,
        daily_target: num(daily) ?? 4,
        image_target: num(images) ?? 3,
        video_target: num(videos) ?? 1,
        max_daily_generation: num(maxGen) ?? 10,
        priority_preference: priority,
      },
      { onSuccess: () => setDirty(false) },
    );
  };

  if (settings.isLoading) return <Panel title="Capacity settings"><p className="text-xs text-text-muted">Loading current settings…</p></Panel>;
  if (settings.isError) {
    return (
      <Panel title="Capacity settings">
        <p className="text-[13px] text-text-secondary">
          Capacity settings are not available yet — the backend for <span className="font-mono">PUT /daily-production/settings</span> is still being built.
          The planner will use defaults (4/day: 3 images, 1 video) until then.
        </p>
      </Panel>
    );
  }

  return (
    <Panel title="Capacity settings" action={<Button size="sm" variant="primary" loading={muts.saveSettings.isPending} disabled={!dirty} onClick={save}>Save</Button>}>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <Field label="Weekly capacity" hint="Assets you can realistically produce per week.">
          <Input type="number" min={0} value={weekly} onChange={(e) => { setWeekly(e.target.value); setDirty(true); }} />
        </Field>
        <Field label="Daily target" hint="Planned assets per day.">
          <Input type="number" min={0} value={daily} onChange={(e) => { setDaily(e.target.value); setDirty(true); }} />
        </Field>
        <Field label="Images per day" hint="Split of the daily target for still images.">
          <Input type="number" min={0} value={images} onChange={(e) => { setImages(e.target.value); setDirty(true); }} />
        </Field>
        <Field label="Videos per day" hint="Split of the daily target for video.">
          <Input type="number" min={0} value={videos} onChange={(e) => { setVideos(e.target.value); setDirty(true); }} />
        </Field>
        <Field label="Max daily generation" hint="Hard ceiling the planner never exceeds.">
          <Input type="number" min={0} value={maxGen} onChange={(e) => { setMaxGen(e.target.value); setDirty(true); }} />
        </Field>
        <Field label="Priority preference" hint="How the planner ranks recommendations.">
          <Select value={priority} onChange={(e) => { setPriority(e.target.value); setDirty(true); }}>
            {PRIORITY_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </Select>
        </Field>
      </div>
      <WhyThis label="How capacity is used">
        <p>The daily planner fills up to your daily target with ranked recommendations (market opportunity × personal fit, minus saturation), preferring open niches when you choose that priority. Nothing is auto-queued — you approve each recommendation first.</p>
      </WhyThis>
    </Panel>
  );
}
