"use client";
/**
 * Opportunity Explorer — ranked, filterable opportunities (docs/05 screen 6).
 */
import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Plus } from "lucide-react";
import {
  Badge,
  Button,
  DataTable,
  EmptyState,
  Field,
  Input,
  Modal,
  PageHeader,
  Pagination,
  Panel,
  QueryView,
  Select,
  Skeleton,
  Textarea,
  type Column,
} from "../../components/ui";
import { ConfidenceMeter, FormatBadge, ProvenanceBadge, ScoreInline, isMock } from "../../components/scores";
import { OpportunitySpaceScene, type SpacePoint } from "../../components/three/scenes";
import { Tilt } from "../../components/three/Tilt";
import { GOLD, STEEL, TEXT_MUTED, WARNING, RACING_RED } from "../../components/palette";
import { useCategories, useOpportunities, useOpportunityMutations } from "../../hooks/useApi";
import type { Opportunity, OpportunityStatus } from "../../types";
import { enumLabel, timeAgo } from "../../lib/format";

const PAGE_SIZE = 15;

function OpportunitiesPage() {
  const router = useRouter();
  const params = useSearchParams();
  const [status, setStatus] = useState(params.get("status") ?? "");
  const [category, setCategory] = useState(params.get("category") ?? "");
  const [minScore, setMinScore] = useState(Number(params.get("min_score") ?? 0));
  const [sort, setSort] = useState("-opportunity_score");
  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const [createOpen, setCreateOpen] = useState(false);

  const categories = useCategories();
  const opps = useOpportunities({
    status: status || undefined,
    category: category || undefined,
    min_score: minScore || undefined,
    sort,
    page,
    page_size: PAGE_SIZE,
  });

  const filtered = (opps.data?.data ?? []).filter((o) =>
    q.trim() ? o.title.toLowerCase().includes(q.trim().toLowerCase()) : true,
  );

  const columns: Column<Opportunity>[] = [
    {
      key: "title",
      header: "Opportunity",
      render: (o) => (
        <div className="min-w-[220px]">
          <button onClick={() => router.push(`/opportunities/${o.id}`)} className="text-left text-[13px] font-semibold text-text-primary hover:text-accent-secondary">
            {o.title}
          </button>
          <p className="mt-0.5 line-clamp-1 text-xs text-text-muted">{o.summary}</p>
          <div className="mt-1 flex flex-wrap gap-1">
            {o.category && <Badge tone="neutral">{o.category}</Badge>}
            {(o.formats ?? []).map((f) => <FormatBadge key={f} format={f} />)}
            {isMock(o) || isMock({ provenance: o.data_provenance }) ? <ProvenanceBadge mock /> : <ProvenanceBadge provenance={o.data_provenance} />}
          </div>
        </div>
      ),
    },
    { key: "score", header: "Score", sortKey: "opportunity_score", render: (o) => <ScoreInline value={o.opportunity_score} /> },
    { key: "conf", header: "Confidence", render: (o) => <ConfidenceMeter value={o.confidence} compact /> },
    {
      key: "status",
      header: "Status",
      render: (o) => (
        <Badge tone={o.status === "approved" ? "success" : o.status === "new" ? "info" : "muted"}>{enumLabel(o.status)}</Badge>
      ),
    },
    { key: "priority", header: "Priority", sortKey: "priority", render: (o) => <span className="text-text-primary">{o.priority}</span> },
    { key: "updated", header: "Updated", render: (o) => <span className="text-xs">{timeAgo(o.updated_at)}</span> },
  ];

  const hasFilters = status || category || minScore > 0 || q.trim();

  const spacePoints: SpacePoint[] = (opps.data?.data ?? []).map((o) => ({
    id: o.id,
    title: o.title,
    x: o.opportunity_score,
    y: o.personal_fit_score ?? null,
    z: o.scores?.commercial_score ?? o.scores?.trend_score ?? null,
    size: o.confidence,
    saturation: o.scores?.saturation_score ?? null,
  }));

  return (
    <div className="space-y-4">
      <PageHeader
        title="Opportunities"
        description="Where is the best opportunity right now? Ranked by opportunity score; only score ≥ 55 with confidence ≥ 50% is actionable."
        actions={
          <Button size="sm" variant="primary" icon={<Plus size={13} />} onClick={() => setCreateOpen(true)}>
            New opportunity
          </Button>
        }
      />

      {/* Filter bar */}
      <div className="flex flex-wrap items-end gap-3">
        <div className="w-48">
          <Field label="Status">
            <Select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }} aria-label="Filter by status">
              <option value="">All statuses</option>
              {(["new", "approved", "rejected", "in_progress", "archived"] as OpportunityStatus[]).map((s) => (
                <option key={s} value={s}>{enumLabel(s)}</option>
              ))}
            </Select>
          </Field>
        </div>
        <div className="w-56">
          <Field label="Category">
            <Select value={category} onChange={(e) => { setCategory(e.target.value); setPage(1); }} aria-label="Filter by category">
              <option value="">All categories</option>
              {(categories.data ?? []).map((c) => (
                <option key={c.id} value={c.slug}>{c.name}</option>
              ))}
            </Select>
          </Field>
        </div>
        <div>
          <Field label={`Min score · ${minScore}`}>
            <input type="range" min={0} max={100} step={5} value={minScore}
              onChange={(e) => { setMinScore(Number(e.target.value)); setPage(1); }}
              className="w-32" aria-label="Minimum opportunity score" />
          </Field>
        </div>
        <div className="w-52">
          <Field label="Search">
            <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter titles…" aria-label="Search opportunities" />
          </Field>
        </div>
        {hasFilters && (
          <Button size="sm" variant="ghost" onClick={() => { setStatus(""); setCategory(""); setMinScore(0); setQ(""); setPage(1); }}>
            Clear filters
          </Button>
        )}
        <span className="pb-2 text-xs text-text-muted" aria-live="polite">
          {opps.data ? `${filtered.length} of ${opps.data.pagination.total} shown` : ""}
        </span>
      </div>

      {/* Opportunity space — 3D positioning overview (2D list follows below) */}
      {spacePoints.length > 0 && (
        <Panel
          className="mb-6"
          title="Opportunity space"
          subtitle="Market opportunity × personal fit × commercial potential — size by confidence, color by saturation risk"
          pad={false}
        >
          <OpportunitySpaceScene
            points={spacePoints}
            onSelect={(id) => router.push(`/opportunities/${id}`)}
            height={380}
            label="3D scatter of opportunities by market opportunity, personal fit and commercial potential"
            fallback={
              <div className="flex h-[380px] items-center justify-center px-6 text-center text-sm text-text-muted">
                3D view unavailable on this device — the full ranked list below shows every opportunity with the same scores.
              </div>
            }
          />
          <div className="flex flex-wrap items-center gap-x-5 gap-y-1.5 border-t border-border px-4 py-3 text-[11px] font-semibold uppercase tracking-[0.08em]">
            <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full" style={{ background: GOLD }} /> Open</span>
            <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full" style={{ background: STEEL }} /> Moderate</span>
            <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full" style={{ background: WARNING }} /> Crowded</span>
            <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full" style={{ background: RACING_RED }} /> Saturated</span>
            <span className="text-text-muted normal-case tracking-normal">Hollow markers sit on the N/A shelf — private data not connected.</span>
          </div>
        </Panel>
      )}

      <Panel>
        <QueryView
          query={opps}
          loading={<Skeleton className="h-64" />}
          empty={
            <EmptyState
              title="No opportunities match"
              description="Adjust or clear the filters — or run the daily analysis to surface new ones."
              action={hasFilters ? <Button size="sm" onClick={() => { setStatus(""); setCategory(""); setMinScore(0); setQ(""); }}>Clear filters</Button> : undefined}
            />
          }
          errorTitle="Opportunities unavailable"
        >
          {() => (
            <>
              <DataTable
                columns={columns}
                rows={filtered}
                rowKey={(o) => o.id}
                sort={sort}
                onSort={(s) => { setSort(s); setPage(1); }}
                testId="opportunities-table"
              />
              <Pagination page={page} totalPages={opps.data?.pagination.total_pages ?? 1} onChange={setPage} />
            </>
          )}
        </QueryView>
      </Panel>

      <CreateOpportunityModal open={createOpen} onClose={() => setCreateOpen(false)} />
    </div>
  );
}

function CreateOpportunityModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const muts = useOpportunityMutations();
  const [title, setTitle] = useState("");
  const [summary, setSummary] = useState("");
  const [priority, setPriority] = useState(50);

  const save = () => {
    if (!title.trim() || !summary.trim()) return;
    muts.create.mutate(
      { title: title.trim(), summary: summary.trim(), priority },
      { onSuccess: () => { setTitle(""); setSummary(""); onClose(); } },
    );
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="New opportunity"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button variant="primary" loading={muts.create.isPending} disabled={!title.trim() || !summary.trim()} onClick={save}>
            Create
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        <Field label="Title" required><Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. AI-generated corporate wellness videos" /></Field>
        <Field label="Summary" required><Textarea value={summary} onChange={(e) => setSummary(e.target.value)} placeholder="What is the opportunity and why now?" rows={4} /></Field>
        <Field label={`Priority · ${priority}`}>
          <input type="range" min={0} max={100} value={priority} onChange={(e) => setPriority(Number(e.target.value))} className="w-full" />
        </Field>
        <p className="text-xs text-text-muted">Manually created opportunities are scored when the analysis pipeline next runs. Approval remains a human gate.</p>
      </div>
    </Modal>
  );
}

// ---------------------------------------------------------------------------
// Suspense wrapper — useSearchParams() requires a Suspense boundary during
// prerender (Next.js missing-suspense-with-csr-bailout).
// ---------------------------------------------------------------------------

export default function PageWrapper() {
  return (
    <Suspense fallback={<div className="skeleton h-64 rounded" />}>
      <OpportunitiesPage />
    </Suspense>
  );
}
