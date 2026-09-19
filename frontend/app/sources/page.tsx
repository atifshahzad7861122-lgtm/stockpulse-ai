"use client";
/**
 * Data Sources — Phase 2 (PHASE2_DESIGN.md §7).
 * One card per source: status chip, LIVE badge (only when genuinely
 * healthy+fresh), last sync, records count, provenance, Collect button.
 */
import Link from "next/link";
import { Database, RefreshCw } from "lucide-react";
import {
  Button,
  Card,
  EmptyState,
  PageHeader,
  QueryView,
  Skeleton,
} from "../../components/ui";
import { ProvenanceBadge } from "../../components/scores";
import {
  FreshnessLine,
  LiveBadge,
  SourceStatusChip,
  lastSuccessOf,
  sourceStatusLabel,
} from "../../components/sources";
import { useCollectSource, useSources } from "../../hooks/useApi";
import type { SourceSummary } from "../../types";
import { fmtInt, timeAgo } from "../../lib/format";

function SourceCard({ source }: { source: SourceSummary }) {
  const collect = useCollectSource();
  const status = source.health_status ?? source.health?.status ?? null;
  const records = source.records_collected ?? source.health?.records_collected ?? null;
  const lastSync = lastSuccessOf(source);

  return (
    <Card className="flex flex-col p-4">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h2 className="truncate text-[15px] font-semibold text-text-primary">{source.name}</h2>
          <p className="mt-0.5 font-mono text-[11px] text-text-muted">{source.source_type}</p>
        </div>
        <div className="flex shrink-0 flex-wrap justify-end gap-1">
          <SourceStatusChip status={status} />
          <LiveBadge health={source} />
        </div>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2 text-[13px]">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.06em] text-text-muted">Last sync</p>
          <p className="mt-0.5 text-text-secondary">{lastSync ? timeAgo(lastSync) : "—"}</p>
        </div>
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.06em] text-text-muted">Records</p>
          <p className="mt-0.5 text-text-secondary">{records === null ? "—" : fmtInt(records)}</p>
        </div>
      </div>

      <div className="mt-2">
        <FreshnessLine health={source} />
      </div>

      <div className="mt-2 flex flex-wrap gap-1">
        {source.is_active ? (
          <span className="inline-flex items-center rounded bg-status-success/10 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-[0.06em] text-status-success">
            Active
          </span>
        ) : (
          <span className="inline-flex items-center rounded bg-surface-elevated px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-[0.06em] text-text-muted">
            Inactive
          </span>
        )}
        {source.data_provenance ? (
          <ProvenanceBadge provenance={source.data_provenance} />
        ) : (
          <span className="inline-flex items-center rounded bg-surface-elevated px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-[0.06em] text-text-muted">
            Provenance unknown
          </span>
        )}
      </div>

      <div className="mt-4 flex items-center justify-between gap-2 border-t border-border pt-3">
        <Link href="/sources/health" className="text-xs text-accent-secondary hover:underline">
          Health details
        </Link>
        <Button
          size="sm"
          variant="secondary"
          icon={<RefreshCw size={13} />}
          loading={collect.isPending}
          disabled={!source.is_active}
          title={
            source.is_active
              ? `Collect now from ${source.name}`
              : "Source is inactive — collection is disabled until it is configured"
          }
          onClick={() => collect.mutate(source.id)}
        >
          Collect
        </Button>
      </div>
    </Card>
  );
}

export default function SourcesPage() {
  const sources = useSources({ retry: false });

  return (
    <div>
      <PageHeader
        title="Data Sources"
        description="Every feed that powers StockPulse AI. Status chips are honest runtime states — a source is never marked connected without real data retrieved."
        actions={
          <Link href="/runs">
            <Button size="sm" variant="outline">Collection runs</Button>
          </Link>
        }
      />
      <QueryView
        query={sources}
        loading={
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {[0, 1, 2, 3, 4, 5].map((i) => <Skeleton key={i} className="h-52" />)}
          </div>
        }
        empty={
          <EmptyState
            icon={<Database size={18} />}
            title="No data sources configured"
            description="The backend has not seeded any trend sources yet. When the Phase-2 backend is live, adapters (RSS, GitHub, YouTube RSS, ScrapeGraph, Agent-Reach channels) appear here."
          />
        }
        errorTitle="Sources unavailable"
      >
        {(rows) => {
          if (!rows.length)
            return (
              <EmptyState
                icon={<Database size={18} />}
                title="No data sources configured"
                description="The backend has not seeded any trend sources yet."
              />
            );
          const counts = new Map<string, number>();
          for (const s of rows) counts.set(sourceStatusLabel(s.health_status ?? s.health?.status), (counts.get(sourceStatusLabel(s.health_status ?? s.health?.status)) ?? 0) + 1);
          return (
            <div>
              <p className="mb-3 text-xs text-text-muted">
                {rows.length} sources · {Array.from(counts.entries()).map(([k, v]) => `${v} ${k}`).join(" · ")}
              </p>
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {rows.map((s) => <SourceCard key={s.id} source={s} />)}
              </div>
            </div>
          );
        }}
      </QueryView>
    </div>
  );
}
