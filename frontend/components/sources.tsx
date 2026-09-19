"use client";
/**
 * Phase-2 data-source badges + freshness helpers (PHASE2_DESIGN.md §7).
 *
 * Provenance honesty rules (binding):
 * - LIVE (green) renders ONLY when the source's health row is genuinely
 *   healthy AND fresh (status AVAILABLE + recent last_success_at).
 * - REAL / MOCK ("Demo data") / ESTIMATED / PREDICTED badges come from the
 *   record's data_provenance — mock is never presented as real.
 */
import { Activity } from "lucide-react";
import { Badge, Tooltip, cx } from "./ui";
import { timeAgo } from "../lib/format";
import type {
  AdobeConnectionStatus,
  CollectionRunStatus,
  SourceHealth,
  SourceStatus,
  SourceSummary,
} from "../types";

/** Freshness window for "live" data: daily scheduler jobs + slack. */
export const FRESHNESS_WINDOW_MS = 26 * 60 * 60 * 1000;

export function isFresh(iso: string | null | undefined): boolean {
  if (!iso) return false;
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return false;
  return Date.now() - t <= FRESHNESS_WINDOW_MS;
}

/** Last successful collection timestamp, from either shape (incl. legacy last_fetched_at). */
export function lastSuccessOf(h: SourceHealth | SourceSummary | null | undefined): string | null | undefined {
  if (!h) return null;
  return (
    h.last_success_at ??
    (h as SourceSummary).health?.last_success_at ??
    (h as SourceSummary).last_fetched_at ??
    null
  );
}

/** LIVE only when genuinely healthy AND fresh — never guess. */
export function isLiveHealth(h: SourceHealth | SourceSummary | null | undefined): boolean {
  if (!h) return false;
  const asSummary = h as SourceSummary;
  const asHealth = h as SourceHealth;
  const status = asSummary.health_status ?? asSummary.health?.status ?? asHealth.status ?? null;
  return status === "AVAILABLE" && isFresh(lastSuccessOf(h));
}

const STATUS_TONE: Record<SourceStatus, "success" | "info" | "warning" | "muted" | "danger"> = {
  NOT_CHECKED: "muted",
  AVAILABLE: "success",
  CONFIGURED: "info",
  NEEDS_AUTH: "warning",
  UNAVAILABLE: "muted",
  TEMP_FAILING: "danger",
};

export function sourceStatusLabel(status: SourceStatus | string | null | undefined): string {
  switch (status) {
    case "NOT_CHECKED":
      return "Not checked";
    case "AVAILABLE":
      return "Available";
    case "CONFIGURED":
      return "Configured";
    case "NEEDS_AUTH":
      return "Needs auth";
    case "UNAVAILABLE":
      return "Unavailable";
    case "TEMP_FAILING":
      return "Failing";
    default:
      return status ? String(status).replace(/_/g, " ").toLowerCase() : "Unknown";
  }
}

export function SourceStatusChip({ status }: { status: SourceStatus | string | null | undefined }) {
  const tone = status && status in STATUS_TONE ? STATUS_TONE[status as SourceStatus] : "muted";
  return (
    <Tooltip label={`Source status: ${sourceStatusLabel(status)}. Honest state from the source health check — never assumed.`}>
      <span>
        <Badge tone={tone}>{sourceStatusLabel(status)}</Badge>
      </span>
    </Tooltip>
  );
}

/** Green LIVE badge — rendered only when isLiveHealth() is true. */
export function LiveBadge({ health }: { health: SourceHealth | SourceSummary | null | undefined }) {
  if (!isLiveHealth(health)) return null;
  return (
    <Tooltip label={`Live: healthy source, successful collection ${timeAgo(lastSuccessOf(health))}.`}>
      <span>
        <Badge tone="success">
          <Activity size={11} aria-hidden /> Live
        </Badge>
      </span>
    </Tooltip>
  );
}

/** One-line freshness description: "Last success 3h ago" / "Never succeeded". */
export function FreshnessLine({ health, className }: { health: SourceHealth | SourceSummary | null | undefined; className?: string }) {
  if (!health) return <span className={cx("text-xs text-text-muted", className)}>No health data</span>;
  const lastSuccess = lastSuccessOf(health);
  const fresh = isFresh(lastSuccess);
  return (
    <span className={cx("text-xs", className, fresh ? "text-text-secondary" : "text-text-muted")}>
      {lastSuccess ? `Last success ${timeAgo(lastSuccess)}` : "Never succeeded"}
      {!fresh && lastSuccess ? " · stale" : ""}
    </span>
  );
}

const RUN_TONE: Record<CollectionRunStatus, "muted" | "info" | "success" | "warning" | "danger" | "neutral"> = {
  QUEUED: "muted",
  RUNNING: "info",
  SUCCESS: "success",
  PARTIAL: "warning",
  FAILED: "danger",
  SKIPPED: "neutral",
};

export function RunStatusChip({ status }: { status: CollectionRunStatus | string }) {
  const tone = status in RUN_TONE ? RUN_TONE[status as CollectionRunStatus] : "muted";
  return <Badge tone={tone}>{String(status).replace(/_/g, " ").toLowerCase()}</Badge>;
}

export function AdobeConnectionChip({ status }: { status: AdobeConnectionStatus | string | null | undefined }) {
  const s = String(status ?? "NOT_CONFIGURED");
  const tone =
    s === "ACTIVE" ? "success" : s === "CONFIGURED" ? "info" : s === "AUTH_ERROR" ? "danger" : "muted";
  return (
    <Tooltip label="Adobe Contributor connection state. Secrets are stored server-side only and never displayed.">
      <span>
        <Badge tone={tone}>{s.replace(/_/g, " ").toLowerCase()}</Badge>
      </span>
    </Tooltip>
  );
}

/** Real-data badge for VERIFIED / THIRD_PARTY / USER_PROVIDED provenance. */
export function RealDataBadge() {
  return (
    <Tooltip label="Real data from a live source — not demo, not invented.">
      <span>
        <Badge tone="info">Real data</Badge>
      </span>
    </Tooltip>
  );
}

/** Personal Fit Score (0–100, nullable) — Phase 2 §6. Null = no private data yet. */
export function PersonalFitScore({ value, compact }: { value: number | null | undefined; compact?: boolean }) {
  if (value === null || value === undefined || Number.isNaN(value))
    return (
      <Tooltip label="No private performance data yet — connect your Adobe Contributor account to get a personal fit score.">
        <span className={cx("text-xs text-text-muted", compact && "text-[11px]")}>Personal fit —</span>
      </Tooltip>
    );
  return (
    <Tooltip label="Personal Fit Score: how well this matches YOUR Adobe Stock performance history. Probabilistic — not a sales guarantee.">
      <span className="inline-flex items-center gap-1.5">
        <span className="text-[11px] font-semibold uppercase tracking-[0.06em] text-text-muted">Personal fit</span>
        <span className="text-[13px] font-semibold text-text-primary" style={{ fontVariantNumeric: "tabular-nums" }}>
          {Math.round(value)}
        </span>
      </span>
    </Tooltip>
  );
}
