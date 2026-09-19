"use client";
/**
 * Source Health — Phase 2 (PHASE2_DESIGN.md §7).
 * Full SourceHealth table: source, status, last success/failure, records,
 * freshness, auth state, fallback, error. Honest failure display: on failure
 * we mark the source, show the last success, and never fabricate replacements.
 */
import { useMemo } from "react";
import Link from "next/link";
import { Activity } from "lucide-react";
import {
  Badge,
  Button,
  DataTable,
  EmptyState,
  PageHeader,
  QueryView,
  Skeleton,
  Tooltip,
  type Column,
} from "../../../components/ui";
import {
  LiveBadge,
  SourceStatusChip,
} from "../../../components/sources";
import { useCollectSource, useSourceHealth } from "../../../hooks/useApi";
import type { SourceHealth } from "../../../types";
import { fmtDateTime, fmtInt, timeAgo } from "../../../lib/format";

function truncate(s: string | null | undefined, n = 90): string {
  if (!s) return "—";
  return s.length > n ? `${s.slice(0, n)}…` : s;
}

export default function SourceHealthPage() {
  const health = useSourceHealth({ retry: false });
  const collect = useCollectSource();

  const rows = useMemo(() => health.data ?? [], [health.data]);

  const columns: Column<SourceHealth>[] = [
    {
      key: "source",
      header: "Source",
      render: (h) => (
        <div className="min-w-[160px]">
          <p className="font-semibold text-text-primary">{h.source_name ?? "Unnamed source"}</p>
          <p className="font-mono text-[11px] text-text-muted">{h.source_type ?? h.trend_source_id.slice(0, 8)}</p>
        </div>
      ),
    },
    {
      key: "status",
      header: "Status",
      render: (h) => (
        <div className="flex flex-wrap gap-1">
          <SourceStatusChip status={h.status} />
          <LiveBadge health={h} />
        </div>
      ),
    },
    {
      key: "last_success",
      header: "Last success",
      render: (h) => (
        <span className="text-text-secondary">{h.last_success_at ? timeAgo(h.last_success_at) : "—"}</span>
      ),
    },
    {
      key: "last_failure",
      header: "Last failure",
      render: (h) =>
        h.last_failure_at ? (
          <span className="text-status-danger">{timeAgo(h.last_failure_at)}</span>
        ) : (
          <span className="text-text-muted">—</span>
        ),
    },
    {
      key: "records",
      header: "Records",
      render: (h) => (
        <span className="text-text-secondary" style={{ fontVariantNumeric: "tabular-nums" }}>
          {fmtInt(h.records_collected)}
        </span>
      ),
    },
    {
      key: "failures",
      header: "Consec. failures",
      render: (h) => (
        <Badge tone={h.consecutive_failures > 0 ? "danger" : "muted"}>{h.consecutive_failures}</Badge>
      ),
    },
    {
      key: "auth",
      header: "Auth state",
      render: (h) => (
        <Tooltip label="Authorization state of the source adapter.">
          <span className="text-text-secondary">{h.auth_state ?? "—"}</span>
        </Tooltip>
      ),
    },
    {
      key: "fallback",
      header: "Fallback",
      render: (h) => <span className="text-text-secondary">{h.fallback_status ?? "—"}</span>,
    },
    {
      key: "error",
      header: "Last error",
      render: (h) =>
        h.last_error ? (
          <Tooltip label={h.last_error}>
            <span className="block max-w-[220px] truncate text-status-danger">{truncate(h.last_error)}</span>
          </Tooltip>
        ) : (
          <span className="text-text-muted">—</span>
        ),
    },
    {
      key: "checked",
      header: "Checked",
      render: (h) => <span className="text-text-muted">{h.checked_at ? timeAgo(h.checked_at) : "—"}</span>,
    },
    {
      key: "actions",
      header: "Actions",
      render: (h) => (
        <Button
          size="sm"
          variant="outline"
          loading={collect.isPending}
          onClick={() => collect.mutate(h.trend_source_id)}
        >
          Collect
        </Button>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="Source Health"
        description="Runtime health of every data source adapter. Failing sources are marked with their last success and error — confidence is lowered downstream, never padded with invented data."
        badge={<Badge tone="info">{rows.length} sources</Badge>}
        actions={
          <Link href="/sources">
            <Button size="sm" variant="outline">All sources</Button>
          </Link>
        }
      />
      <QueryView
        query={health}
        loading={<Skeleton lines={8} />}
        empty={
          <EmptyState
            icon={<Activity size={18} />}
            title="No health records yet"
            description="Health rows appear once the Phase-2 backend runs its first 15-minute source health check."
          />
        }
        errorTitle="Health data unavailable"
      >
        {() => (
          <div className="rounded-lg border border-border bg-surface-base">
            <DataTable<SourceHealth>
              columns={columns}
              rows={rows}
              rowKey={(h) => h.id}
              empty={
                <EmptyState
                  compact
                  icon={<Activity size={18} />}
                  title="No health records yet"
                  description="Health rows appear once the Phase-2 backend runs its first source health check."
                />
              }
            />
          </div>
        )}
      </QueryView>
      <p className="mt-3 text-xs text-text-muted">
        Checked-at timestamps are produced by the backend scheduler (every 15 min). Full history:{" "}
        <Link href="/runs" className="text-accent-secondary hover:underline">Collection runs</Link>
        {rows.length > 0 && rows[0].checked_at && <> · Last check {fmtDateTime(rows[0].checked_at)}</>}.
      </p>
    </div>
  );
}
