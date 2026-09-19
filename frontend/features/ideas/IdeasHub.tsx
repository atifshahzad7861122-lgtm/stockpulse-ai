"use client";
/**
 * Ideas hub shared by /image-ideas and /video-ideas (docs/05 screens 7–8).
 * Cards with status filter, detail drawer (?idea=) with
 * edit/regenerate/prompt-studio/queue/archive/library actions,
 * shot lists, originality notes, compliance & similarity chips.
 */
import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Plus } from "lucide-react";
import {
  Button,
  DataTable,
  EmptyState,
  Field,
  PageHeader,
  Pagination,
  QueryView,
  Select,
  Skeleton,
  cx,
} from "../../components/ui";
import { IdeaCard, IdeaDrawer } from "./IdeaCard";
import { IdeaStatusChip } from "../../components/scores";
import { Stagger, StaggerItem } from "../../components/motion/motion";
import { useIdeas } from "../../hooks/useApi";
import { timeAgo } from "../../lib/format";
import type { Idea, IdeaKind, IdeaStatus } from "../../types";

const STATUSES: IdeaStatus[] = ["DRAFT", "READY", "IN_QUEUE", "ARCHIVED", "DISCARDED"];

export function IdeasHub({ kind }: { kind: IdeaKind }) {
  const router = useRouter();
  const params = useSearchParams();
  const [status, setStatus] = useState(params.get("status") ?? "");
  const [sort, setSort] = useState("-updated_at");
  const [page, setPage] = useState(1);
  const [view, setView] = useState<"grid" | "table">("grid");

  const ideas = useIdeas({ kind, status: status || undefined, sort, page, page_size: 18 });

  const setParam = (k: string, v: string) => {
    const p = new URLSearchParams(params.toString());
    if (v) p.set(k, v); else p.delete(k);
    router.replace(`/${kind}-ideas?${p.toString()}`);
  };

  const title = kind === "image" ? "Image Ideas" : "Video Ideas";

  return (
    <div className="space-y-4">
      <PageHeader
        title={title}
        description={`${kind === "image" ? "Concepts for Adobe Stock image submissions" : "Concepts with duration and motion notes for video submissions"}. Ideas are human-created — the pipeline refines and screens them.`}
        actions={
          <>
            <div className="flex rounded-md border border-border p-0.5" role="tablist" aria-label="View">
              {(["grid", "table"] as const).map((v) => (
                <button key={v} role="tab" aria-selected={view === v} onClick={() => setView(v)}
                  className={cx("rounded px-2.5 py-1 text-xs capitalize", view === v ? "bg-surface-elevated text-text-primary" : "text-text-muted hover:text-text-primary")}>
                  {v}
                </button>
              ))}
            </div>
            <Button size="sm" variant="primary" icon={<Plus size={13} />} onClick={() => router.push("/opportunities")}>
              New idea
            </Button>
          </>
        }
      />

      <div className="flex flex-wrap items-end gap-3">
        <div className="w-44">
          <Field label="Status">
            <Select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }} aria-label="Filter by status">
              <option value="">All statuses</option>
              {STATUSES.map((s) => (
                <option key={s} value={s} className="capitalize">{s.replace(/_/g, " ").toLowerCase()}</option>
              ))}
            </Select>
          </Field>
        </div>
        {status && (
          <Button size="sm" variant="ghost" onClick={() => { setStatus(""); setPage(1); }}>Clear</Button>
        )}
        <span className="pb-2 text-xs text-text-muted" aria-live="polite">
          {ideas.data ? `${ideas.data.pagination.total} ${kind} ideas` : ""}
        </span>
      </div>

      <QueryView
        query={ideas}
        loading={<Skeleton className="h-56" />}
        empty={
          <EmptyState
            title={`No ${kind} ideas yet`}
            description={`Save an idea from an approved opportunity — you write the concept, StockPulse AI refines it for ${kind} generation.`}
            action={<Button size="sm" variant="primary" onClick={() => router.push("/opportunities")}>Browse opportunities</Button>}
          />
        }
        errorTitle={`${kind === "image" ? "Image" : "Video"} ideas unavailable`}
      >
        {(pageData) => view === "grid" ? (
          <Stagger className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {pageData.data.map((i) => (
              <StaggerItem key={i.id} className="h-full">
                <IdeaCard idea={i} onOpen={() => setParam("idea", i.id)} />
              </StaggerItem>
            ))}
          </Stagger>
        ) : (
          <IdeasTable ideas={pageData.data} sort={sort} onSort={setSort} onOpen={(id) => setParam("idea", id)} />
        )}
      </QueryView>

      {ideas.data && ideas.data.pagination.total_pages > 1 && (
        <Pagination page={page} totalPages={ideas.data.pagination.total_pages} onChange={setPage} />
      )}

      <IdeaDrawer kind={kind} onClose={() => setParam("idea", "")} />
    </div>
  );
}

function IdeasTable({ ideas, sort, onSort, onOpen }: { ideas: Idea[]; sort: string; onSort: (s: string) => void; onOpen: (id: string) => void }) {
  return (
    <DataTable
      columns={[
        {
          key: "title", header: "Idea",
          render: (i) => (
            <button onClick={() => onOpen(i.id)} className="text-left text-[13px] font-semibold text-text-primary hover:text-accent-secondary">
              {i.title}
            </button>
          ),
        },
        { key: "status", header: "Status", render: (i) => <IdeaStatusChip status={i.status} /> },
        {
          key: "updated", header: "Updated",
          render: (i) => <span className="text-xs text-text-muted">{timeAgo(i.updated_at)}</span>,
        },
      ]}
      rows={ideas}
      rowKey={(i) => i.id}
      sort={sort}
      onSort={onSort}
    />
  );
}
