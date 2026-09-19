"use client";
/**
 * Collection Runs — Phase 2 (PHASE2_DESIGN.md §5).
 * GET /api/sources/runs — every collection attempt: started, source, status,
 * trigger, records collected/stored, duration, error. Failures stay visible;
 * nothing is silently dropped.
 */
import { useState } from "react";
import Link from "next/link";
import { History } from "lucide-react";
import {
  Badge,
  DataTable,
  EmptyState,
  PageHeader,
  Pagination,
  QueryView,
  Select,
  Skeleton,
  Tooltip,
  type Column,
} from "../../components/ui";
import { RunStatusChip } from "../../components/sources";
import { useCollectionRuns } from "../../hooks/useApi";
import type { CollectionRun, CollectionRunStatus } from "../../types";
import { enumLabel, fmtDateTime, fmtInt } from "../../lib/format";

const PAGE_SIZE = 15;

function fmtDuration(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return "—";
  if (ms < 1000) return `${Math.round(ms)}ms`;
  const s = ms / 1000;
  if (s < 60) return `${s.toFixed(1)}s`;
  return `${(s / 60).toFixed(1)}m`;
}

export default function RunsPage() {
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("");
  const [trigger, setTrigger] = useState("");

  const runs = useCollectionRuns(
    {
      page,
      page_size: PAGE_SIZE,
      status: status || undefined,
      trigger: trigger || undefined,
    },
    { retry: false },
  );

  const columns: Column<CollectionRun>[] = [
    {
      key: "started",
      header: "Started",
      render: (r) => <span className="whitespace-nowrap text-text-secondary">{fmtDateTime(r.started_at)}</span>,
    },
    {
      key: "source",
      header: "Source",
      render: (r) => (
        <div className="min-w-[140px]">
          <p className="font-medium text-text-primary">{r.source_name ?? "Unknown source"}</p>
          {r.source_type && <p className="font-mono text-[11px] text-text-muted">{r.source_type}</p>}
        </div>
      ),
    },
    {
      key: "status",
      header: "Status",
      render: (r) => <RunStatusChip status={r.status} />,
    },
    {
      key: "trigger",
      header: "Trigger",
      render: (r) => (
        <Badge tone={r.trigger === "MANUAL" ? "accent" : "neutral"}>{enumLabel(r.trigger)}</Badge>
      ),
    },
    {
      key: "collected",
      header: "Collected",
      render: (r) => (
        <span className="text-text-secondary" style={{ fontVariantNumeric: "tabular-nums" }}>
          {fmtInt(r.records_collected)}
        </span>
      ),
    },
    {
      key: "stored",
      header: "Stored",
      render: (r) => (
        <span className="text-text-secondary" style={{ fontVariantNumeric: "tabular-nums" }}>
          {fmtInt(r.records_stored)}
        </span>
      ),
    },
    {
      key: "duration",
      header: "Duration",
      render: (r) => <span className="text-text-secondary">{fmtDuration(r.duration_ms)}</span>,
    },
    {
      key: "error",
      header: "Error",
      render: (r) =>
        r.error ? (
          <Tooltip label={r.error}>
            <span className="block max-w-[240px] truncate text-status-danger">
              {r.error.length > 80 ? `${r.error.slice(0, 80)}…` : r.error}
            </span>
          </Tooltip>
        ) : (
          <span className="text-text-muted">—</span>
        ),
    },
  ];

  const statuses: (CollectionRunStatus | "")[] = ["", "QUEUED", "RUNNING", "SUCCESS", "PARTIAL", "FAILED", "SKIPPED"];

  return (
    <div>
      <PageHeader
        title="Collection Runs"
        description="Every collection attempt by every source adapter — scheduled and manual. Failed and skipped runs are shown, not hidden; their sources carry the failure in Source Health."
        actions={
          <Link href="/sources/health">
            <Badge tone="info">Source Health</Badge>
          </Link>
        }
      />

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <label className="text-xs text-text-muted" htmlFor="runs-status">Status</label>
        <Select
          id="runs-status"
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            setPage(1);
          }}
          className="w-auto"
        >
          {statuses.map((s) => (
            <option key={s || "all"} value={s}>{s ? enumLabel(s) : "All"}</option>
          ))}
        </Select>
        <label className="text-xs text-text-muted" htmlFor="runs-trigger">Trigger</label>
        <Select
          id="runs-trigger"
          value={trigger}
          onChange={(e) => {
            setTrigger(e.target.value);
            setPage(1);
          }}
          className="w-auto"
        >
          {["", "SCHEDULED", "MANUAL", "API"].map((t) => (
            <option key={t || "all"} value={t}>{t ? enumLabel(t) : "All"}</option>
          ))}
        </Select>
      </div>

      <QueryView
        query={runs}
        loading={<Skeleton lines={8} />}
        empty={
          <EmptyState
            icon={<History size={18} />}
            title="No collection runs yet"
            description="Runs appear here once the scheduler or a manual Collect triggers a collection."
          />
        }
        errorTitle="Runs unavailable"
      >
        {(pageData) => (
          <div>
            <div className="rounded-lg border border-border bg-surface-base">
              <DataTable<CollectionRun>
                columns={columns}
                rows={pageData.data}
                rowKey={(r) => r.id}
                empty={
                  <EmptyState
                    compact
                    icon={<History size={18} />}
                    title="No runs match the filters"
                    description="Try widening the status or trigger filter."
                  />
                }
              />
            </div>
            <Pagination
              page={pageData.pagination.page}
              totalPages={pageData.pagination.total_pages}
              onChange={setPage}
            />
          </div>
        )}
      </QueryView>
    </div>
  );
}
