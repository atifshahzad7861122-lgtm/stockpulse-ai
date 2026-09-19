"use client";
/**
 * Score indicators + badges — precision-instrument restyle (2026-09-19).
 * High band = champagne gold; semantic colors only for meaning (saturation
 * risk, pass/fail). Scores render as numeric + label + color, never color
 * alone. No blue anywhere in the system.
 */
import { ShieldAlert, ShieldCheck, ShieldQuestion } from "lucide-react";
import { Badge, Tooltip, cx } from "./ui";
import { confidenceBand, provenanceLabel, saturationBand, scoreBand } from "../lib/scores";
import { GOLD, SCORE_TRACK, scoreBandColor } from "./palette";
import { CountUp } from "./motion/motion";
import type {
  ComplianceResult,
  DataProvenance,
  IdeaStatus,
  PriorityBand,
  PromptStatus,
  QueueStatus,
  RiskLevel,
} from "../types";
import { stateLabel } from "../lib/transitions";

// ---------------------------------------------------------------------------
// Score ring (detail pages) — number + ring + band label
// ---------------------------------------------------------------------------

export function ScoreRing({
  value,
  size = 84,
  label,
  inverted,
  serif,
}: {
  value: number | null | undefined;
  size?: number;
  label?: string;
  /** Saturation-style: meaning inverted, color follows meaning. */
  inverted?: boolean;
  /** Render the numeral in the Didone serif — hero moments only. */
  serif?: boolean;
}) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return (
      <span className="inline-flex items-center gap-2 text-text-muted">
        <span
          className="inline-flex items-center justify-center rounded-full border border-border bg-surface-elevated text-xs"
          style={{ width: size, height: size }}
          aria-label="Score unavailable"
        >
          —
        </span>
        {label && <span className="text-xs text-text-muted">{label}</span>}
      </span>
    );
  }
  const band = scoreBand(value);
  const color = scoreBandColor(band);
  const r = (size - 10) / 2;
  const c = 2 * Math.PI * r;
  const bandName = band === "high" ? "High" : band === "medium" ? "Medium" : "Low";
  return (
    <span className="inline-flex items-center gap-2.5">
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        role="img"
        aria-label={`Score ${Math.round(value)} out of 100, band ${bandName}`}
      >
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={SCORE_TRACK} strokeWidth="6" />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth="6"
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - Math.min(100, Math.max(0, value)) / 100)}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
        <text
          x="50%"
          y="50%"
          dy="0.36em"
          textAnchor="middle"
          fill="#F5F3EE"
          fontSize={size * (serif ? 0.26 : 0.24)}
          fontWeight={serif ? 500 : 700}
          fontFamily={serif ? "var(--font-display), Georgia, serif" : "var(--font-sans), Inter, sans-serif"}
          style={{ fontVariantNumeric: "tabular-nums" }}
        >
          {Math.round(value)}
        </text>
      </svg>
      <span className="flex flex-col">
        {label && <span className="text-[11px] font-semibold uppercase tracking-[0.08em] text-text-muted">{label}</span>}
        <span className="text-xs font-semibold" style={{ color }}>
          {bandName}
        </span>
      </span>
    </span>
  );
  void inverted;
}

// ---------------------------------------------------------------------------
// Score bar (compact horizontal)
// ---------------------------------------------------------------------------

export function ScoreBar({
  value,
  label,
  color,
  showBand = true,
}: {
  value: number | null | undefined;
  label?: string;
  color?: string;
  showBand?: boolean;
}) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return (
      <span className="text-xs text-text-muted">
        {label && <span className="mr-1.5 text-text-muted">{label}</span>}—
      </span>
    );
  }
  const band = scoreBand(value);
  const bandName = band === "high" ? "High" : band === "medium" ? "Medium" : "Low";
  const barColor = color ?? scoreBandColor(band);
  return (
    <span className="inline-flex min-w-[120px] flex-col gap-1" role="img" aria-label={`${label ?? "Score"} ${Math.round(value)} out of 100, ${bandName}`}>
      <span className="flex items-baseline justify-between gap-2">
        {label && <span className="text-[11px] text-text-muted">{label}</span>}
        <span className="tnum text-xs font-bold text-text-primary">
          {Math.round(value)}
          {showBand && <span className="ml-1 font-semibold" style={{ color: barColor }}>{bandName}</span>}
        </span>
      </span>
      <span className="h-1.5 w-full overflow-hidden rounded-full" style={{ background: SCORE_TRACK }} aria-hidden>
        <span className="block h-full rounded-full" style={{ width: `${value}%`, background: barColor }} />
      </span>
    </span>
  );
}

// ---------------------------------------------------------------------------
// Compact score for table cells: number + 3-segment band
// ---------------------------------------------------------------------------

export function ScoreInline({ value }: { value: number | null | undefined }) {
  if (value === null || value === undefined || Number.isNaN(value)) return <span className="text-text-muted">—</span>;
  const band = scoreBand(value);
  const color = scoreBandColor(band);
  return (
    <span className="inline-flex items-center gap-1.5" role="img" aria-label={`Score ${Math.round(value)}, ${band}`}>
      <span className="tnum text-[13px] font-bold text-text-primary">
        <CountUp value={value} duration={0.5} />
      </span>
      <span className="flex gap-[2px]" aria-hidden>
        {[0, 1, 2].map((i) => {
          const filled = band === "high" ? i < 3 : band === "medium" ? i < 2 : i < 1;
          return (
            <span key={i} className="h-1 w-3 rounded-sm" style={{ background: filled ? color : SCORE_TRACK }} />
          );
        })}
      </span>
    </span>
  );
}

// ---------------------------------------------------------------------------
// Confidence meter (champagne-gold bar — certainty is valuable, not colored
// by desirability; semantic red/green stay reserved)
// ---------------------------------------------------------------------------

export function ConfidenceMeter({ value, compact }: { value: number | null | undefined; compact?: boolean }) {
  if (value === null || value === undefined || Number.isNaN(value))
    return <span className="text-xs text-text-muted">No confidence data</span>;
  const pct = value <= 1 ? value * 100 : value;
  const band = confidenceBand(pct);
  return (
    <Tooltip label={`Prediction confidence ${Math.round(pct)}% (${band}). Probabilistic — not a guarantee.`}>
      <span className={cx("inline-flex items-center gap-1.5", compact && "gap-1")}>
        <span className={cx("overflow-hidden rounded-full", compact ? "h-1 w-10" : "h-1.5 w-16")} style={{ background: SCORE_TRACK }} aria-hidden>
          <span className="block h-full rounded-full" style={{ width: `${pct}%`, background: GOLD }} />
        </span>
        <span className="tnum text-[11px] font-semibold text-text-secondary">
          {Math.round(pct)}%
        </span>
      </span>
    </Tooltip>
  );
}

// ---------------------------------------------------------------------------
// Saturation (meaning-inverted, semantic risk colors)
// ---------------------------------------------------------------------------

export function SaturationBadge({ value }: { value: number | null | undefined }) {
  if (value === null || value === undefined || Number.isNaN(value))
    return <Badge tone="muted">Saturation —</Badge>;
  const band = saturationBand(value);
  const tone = band === "Open" ? "success" : band === "Saturated" ? "danger" : "warning";
  return (
    <Tooltip label={`Saturation ${Math.round(value)}/100. ${band === "Open" ? "Room for up to ~8 assets." : band === "Saturated" ? "Crowded — at most 2 assets advised." : "Some competition."}`}>
      <span>
        <Badge tone={tone}>{band} · {Math.round(value)}</Badge>
      </span>
    </Tooltip>
  );
}

// ---------------------------------------------------------------------------
// Provenance badge — Mock gets the Demo-data chip.
// ---------------------------------------------------------------------------

export function ProvenanceBadge({ provenance, mock }: { provenance?: DataProvenance | null; mock?: boolean }) {
  if (!provenance && !mock) return null;
  if (provenance === "MOCK" || mock) {
    return (
      <Tooltip label="Demo/placeholder data — not real Adobe Stock data.">
        <span>
          <Badge tone="warning">Demo data</Badge>
        </span>
      </Tooltip>
    );
  }
  const label = provenanceLabel(provenance as string);
  return (
    <Tooltip label={`Data provenance: ${label}.`}>
      <span>
        <Badge tone="muted">{label}</Badge>
      </span>
    </Tooltip>
  );
}

/** Does this record carry demo data? */
export function isMock(p: { provenance?: DataProvenance | null; mock?: boolean } | undefined | null): boolean {
  return !!p && (p.provenance === "MOCK" || p.mock === true);
}

// ---------------------------------------------------------------------------
// Compliance / risk / status chips — always text + color
// ---------------------------------------------------------------------------

export function ComplianceChip({ result }: { result: ComplianceResult }) {
  const tone = result === "PASS" ? "success" : result === "REVIEW" ? "warning" : "danger";
  const Icon = result === "PASS" ? ShieldCheck : result === "REVIEW" ? ShieldQuestion : ShieldAlert;
  const text = result === "PASS" ? "PASS" : result === "REVIEW" ? "REVIEW" : "HIGH RISK";
  return (
    <Badge tone={tone}>
      <Icon size={11} aria-hidden /> {text}
    </Badge>
  );
}

export function RiskChip({ risk }: { risk: RiskLevel }) {
  const tone = risk === "LOW" ? "success" : risk === "MEDIUM" ? "warning" : "danger";
  return <Badge tone={tone}>{risk === "MEDIUM" ? "Moderate" : risk.charAt(0) + risk.slice(1).toLowerCase()}</Badge>;
}

const IDEA_TONE: Record<IdeaStatus, "muted" | "info" | "accent" | "neutral" | "success"> = {
  DRAFT: "muted",
  READY: "info",
  IN_QUEUE: "accent",
  ARCHIVED: "neutral",
  DISCARDED: "neutral",
};

export function IdeaStatusChip({ status }: { status: IdeaStatus }) {
  return <Badge tone={IDEA_TONE[status]}>{status.replace("_", " ")}</Badge>;
}

const PROMPT_TONE: Record<PromptStatus, "muted" | "info" | "success" | "neutral"> = {
  DRAFT: "muted",
  READY: "info",
  APPROVED: "success",
  ARCHIVED: "neutral",
};

export function PromptStatusChip({ status }: { status: PromptStatus }) {
  return <Badge tone={PROMPT_TONE[status]}>{status}</Badge>;
}

export function QueueStatusChip({ status }: { status: QueueStatus }) {
  const tone =
    status === "ACCEPTED"
      ? "success"
      : status === "REJECTED" || status === "ARCHIVED"
        ? "muted"
        : status === "SUBMITTED"
          ? "success"
          : status === "IN_PRODUCTION"
            ? "accent"
            : status === "QUALITY_CHECK" || status === "COMPLIANCE_REVIEW"
              ? "warning"
              : status === "READY_TO_UPLOAD" || status === "APPROVED"
                ? "info"
                : "neutral";
  return <Badge tone={tone}>{stateLabel(status)}</Badge>;
}

export function PriorityBandChip({ band }: { band: PriorityBand }) {
  const tone = band === "P0" ? "danger" : band === "P1" ? "accent" : band === "P2" ? "warning" : "neutral";
  return <Badge tone={tone}>{band}</Badge>;
}

export function FormatBadge({ format }: { format: "image" | "video" | "IMAGE" | "VIDEO" }) {
  const f = format.toLowerCase();
  return <Badge tone="neutral">{f === "image" ? "IMG" : "VID"}</Badge>;
}
