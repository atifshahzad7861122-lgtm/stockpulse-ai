"use client";
/**
 * Library (docs/05 screen 16) — saved items across the app: search,
 * kind filter, remove. CONTRACT notes: library has no collections API —
 * note/title lookups are not exposed, so cards show kind + item id.
 */
import { useState } from "react";
import Link from "next/link";
import { BookmarkX, FolderOpen, Search } from "lucide-react";
import {
  Badge,
  Button,
  EmptyState,
  Field,
  Input,
  PageHeader,
  Pagination,
  Panel,
  QueryView,
  Select,
  Skeleton,
} from "../../components/ui";
import { useLibrary, useLibraryMutations } from "../../hooks/useApi";
import { enumLabel, timeAgo } from "../../lib/format";
import type { SavedItem, SavedItemKind } from "../../types";

const KINDS: SavedItemKind[] = ["TREND_SIGNAL", "OPPORTUNITY", "IMAGE_IDEA", "VIDEO_IDEA", "PROMPT", "PREDICTION"];

const KIND_LINKS: Record<SavedItemKind, (id: string) => string> = {
  TREND_SIGNAL: (id) => `/trends?trend=${id}`,
  OPPORTUNITY: (id) => `/opportunities/${id}`,
  IMAGE_IDEA: (id) => `/image-ideas?idea=${id}`,
  VIDEO_IDEA: (id) => `/video-ideas?idea=${id}`,
  PROMPT: (id) => `/prompt-studio/${id}`,
  PREDICTION: () => "/trends",
};

export default function LibraryPage() {
  const [q, setQ] = useState("");
  const [kind, setKind] = useState("");
  const [page, setPage] = useState(1);

  const lib = useLibrary({ q: q || undefined, kind: kind || undefined, page, page_size: 24 });

  return (
    <div className="space-y-4">
      <PageHeader
        title="Library"
        description="Everything you saved: trends, opportunities, ideas, prompts. Your personal reference shelf."
      />

      <div className="flex flex-wrap items-end gap-3">
        <div className="w-64">
          <Field label="Search">
            <div className="relative">
              <Search size={14} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-text-muted" aria-hidden />
              <Input value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} placeholder="Search saved items…" className="pl-8" aria-label="Search library" />
            </div>
          </Field>
        </div>
        <div className="w-44">
          <Field label="Kind">
            <Select value={kind} onChange={(e) => { setKind(e.target.value); setPage(1); }} aria-label="Filter by kind">
              <option value="">All kinds</option>
              {KINDS.map((k) => <option key={k} value={k}>{enumLabel(k)}</option>)}
            </Select>
          </Field>
        </div>
        {(q || kind) && (
          <Button size="sm" variant="ghost" onClick={() => { setQ(""); setKind(""); setPage(1); }}>Clear</Button>
        )}
        <span className="pb-2 text-xs text-text-muted" aria-live="polite">
          {lib.data ? `${lib.data.pagination.total} saved` : ""}
        </span>
      </div>

      <Panel title="Saved items">
        <QueryView
          query={lib}
          loading={<Skeleton className="h-56" />}
          empty={
            <EmptyState
              icon={<FolderOpen size={18} />}
              title="Library is empty"
              description="Save trends, opportunities, ideas, and prompts from anywhere — the bookmark action lands them here."
            />
          }
          errorTitle="Library unavailable"
        >
          {(pageData) => (
            <>
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {pageData.data.map((item) => <LibraryCard key={item.id} item={item} />)}
              </div>
              <Pagination page={page} totalPages={pageData.pagination.total_pages} onChange={setPage} />
            </>
          )}
        </QueryView>
      </Panel>
    </div>
  );
}

function LibraryCard({ item }: { item: SavedItem }) {
  const muts = useLibraryMutations();
  const href = KIND_LINKS[item.item_kind](item.item_id);
  return (
    <div className="rounded-lg border border-border bg-surface-base p-3.5">
      <div className="flex items-start gap-2">
        <Badge tone="neutral">{enumLabel(item.item_kind)}</Badge>
        <Button size="sm" variant="ghost" className="ml-auto" icon={<BookmarkX size={13} />}
          title="Remove from library" aria-label={`Remove ${item.item_id.slice(0, 8)} from library`}
          loading={muts.unsave.isPending}
          onClick={() => muts.unsave.mutate(item.id)} />
      </div>
      <Link href={href} className="mt-2 block truncate text-[13px] font-semibold text-text-primary hover:text-accent-secondary">
        {enumLabel(item.item_kind)} · {item.item_id.slice(0, 8)}
      </Link>
      {item.note && <p className="mt-1 line-clamp-2 text-xs text-text-muted">{item.note}</p>}
      <p className="mt-2 text-[11px] text-text-muted">Saved {timeAgo(item.created_at)}</p>
    </div>
  );
}
