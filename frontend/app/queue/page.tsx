"use client";
/**
 * Production Queue (docs/05 screen 13) — Kanban + list views, legal transitions
 * (T01–T29, CONTRACT §10), gate indicators, capacity + stale alerts, bulk moves,
 * manual submission recording.
 */
import {useMemo, useState, Suspense} from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { AlertTriangle, CalendarClock, CheckSquare, ChevronRight, Pause, Play, Plus, Send, Square } from "lucide-react";
import {
  Badge,
  Button,
  ConfirmModal,
  Drawer,
  EmptyState,
  Field,
  Input,
  Modal,
  PageHeader,
  Panel,
  QueryView,
  Select,
  Skeleton,
  Textarea,
  WhyThis,
  cx,
} from "../../components/ui";
import {
  ComplianceChip,
  FormatBadge,
  PriorityBandChip,
  QueueStatusChip,
} from "../../components/scores";
import { useToast } from "../../components/toast";
import {
  useAssets,
  useIdeas,
  useQueue,
  useQueueItem,
  useQueueMutations,
  useSettings,
  useSubmissionMutations,
} from "../../hooks/useApi";
import { api } from "../../services/api";
import { enumLabel, fmtDate, timeAgo } from "../../lib/format";
import { legalTargets, QUIESCENT_STATES, stateLabel, STATE_GROUPS, type QueueState } from "../../lib/transitions";
import type { Idea, PriorityBand, QueueItem, QueueItemDetail, QueueStatus } from "../../types";

type View = "board" | "list";

function isStale(i: QueueItem) {
  const age = (Date.now() - new Date(i.status_changed_at).getTime()) / 86400000;
  return age > 14 && !QUIESCENT_STATES.includes(i.status);
}

const BANDS: PriorityBand[] = ["P0", "P1", "P2", "P3", "P4"];

function QueuePage() {
  const router = useRouter();
  const params = useSearchParams();
  const [view, setView] = useState<View>("board");
  const [q, setQ] = useState("");
  const [band, setBand] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [detailId, setDetailId] = useState<string | null>(params.get("item"));
  const [addOpen, setAddOpen] = useState(false);

  const queue = useQueue({ page_size: 100, sort: "-priority_score" });
  const settings = useSettings();

  const items = useMemo(() => {
    const list = queue.data?.data ?? [];
    return list.filter((i) => {
      if (band && i.priority_band !== band) return false;
      if (q.trim()) {
        const hay = `${i.title} ${i.status}`.toLowerCase();
        if (!hay.includes(q.trim().toLowerCase())) return false;
      }
      return true;
    });
  }, [queue.data, q, band]);

  const weekly = Number(settings.data?.["planner.weekly_capacity"] ?? 0);
  const weekStart = new Date();
  weekStart.setDate(weekStart.getDate() - ((weekStart.getDay() + 6) % 7));
  const weekStartISO = weekStart.toISOString().slice(0, 10);
  const planned = items.filter(
    (i) => i.target_date && i.target_date >= weekStartISO && !QUIESCENT_STATES.includes(i.status),
  ).length;
  const staleCount = items.filter(isStale).length;

  const toggle = (id: string) => {
    setSelected((s) => {
      const next = new Set(s);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const setParam = (k: string, v: string | null) => {
    const p = new URLSearchParams(params.toString());
    if (v) p.set(k, v); else p.delete(k);
    router.replace(`/queue?${p.toString()}`);
  };

  return (
    <div className="space-y-4">
      <PageHeader
        title="Production Queue"
        description="Every idea flows through gated pipeline states (T01–T29). Blocked gates are explained, never silent."
        actions={
          <div className="flex gap-2">
            <div className="flex rounded-md border border-border p-0.5" role="tablist" aria-label="View">
              {(["board", "list"] as View[]).map((v) => (
                <button key={v} role="tab" aria-selected={view === v} onClick={() => setView(v)}
                  className={cx("rounded px-2.5 py-1 text-xs capitalize", view === v ? "bg-surface-elevated text-text-primary" : "text-text-muted hover:text-text-primary")}>
                  {v}
                </button>
              ))}
            </div>
            <Button size="sm" variant="primary" icon={<Plus size={13} />} onClick={() => setAddOpen(true)}>Add item</Button>
          </div>
        }
      />

      {/* Capacity + stale strip */}
      <div className="flex flex-wrap items-center gap-3 text-xs">
        <span className={cx("inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1",
          weekly > 0 && planned > weekly ? "border-status-danger/40 text-status-danger" : "border-border text-text-secondary")}>
          <CalendarClock size={12} aria-hidden />
          {weekly > 0 ? `${planned}/${weekly} weekly slots` : "No weekly capacity set"}
        </span>
        {staleCount > 0 && (
          <span className="inline-flex items-center gap-1.5 rounded-full border border-status-warning/40 px-2.5 py-1 text-status-warning">
            <AlertTriangle size={12} aria-hidden /> {staleCount} stalled &gt; 14 days
          </span>
        )}
        {selected.size > 0 && <BulkBar count={selected.size} ids={Array.from(selected)} onClear={() => setSelected(new Set())} />}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-end gap-3">
        <div className="w-64">
          <Field label="Search">
            <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Title, status…" aria-label="Search queue" />
          </Field>
        </div>
        <div className="w-36">
          <Field label="Priority band">
            <Select value={band} onChange={(e) => setBand(e.target.value)} aria-label="Filter by priority band">
              <option value="">All</option>
              {BANDS.map((b) => <option key={b} value={b}>{b}</option>)}
            </Select>
          </Field>
        </div>
        {(q || band) && <Button size="sm" variant="ghost" onClick={() => { setQ(""); setBand(""); }}>Clear</Button>}
        <span className="pb-2 text-xs text-text-muted" aria-live="polite">{queue.data ? `${items.length} items` : ""}</span>
      </div>

      <QueryView
        query={queue}
        loading={<Skeleton className="h-72" />}
        empty={
          <EmptyState
            title="Queue is empty"
            description="Enqueue ideas to move them through the gated pipeline toward submission."
            action={<Button size="sm" variant="primary" onClick={() => setAddOpen(true)}>Add item</Button>}
          />
        }
        errorTitle="Queue unavailable"
      >
        {() => view === "board" ? (
          <BoardView items={items} selected={selected} onToggle={toggle} onOpen={(id) => { setDetailId(id); setParam("item", id); }} />
        ) : (
          <ListView items={items} selected={selected} onToggle={toggle} onOpen={(id) => { setDetailId(id); setParam("item", id); }} />
        )}
      </QueryView>

      <AddItemModal open={addOpen} onClose={() => setAddOpen(false)} />
      <ItemDrawer id={detailId} onClose={() => { setDetailId(null); setParam("item", null); }} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Board
// ---------------------------------------------------------------------------

function BoardView({ items, selected, onToggle, onOpen }: { items: QueueItem[]; selected: Set<string>; onToggle: (id: string) => void; onOpen: (id: string) => void }) {
  return (
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6">
      {STATE_GROUPS.map((g) => {
        const rows = items.filter((i) => g.states.includes(i.status));
        return (
          <div key={g.label} className="rounded-lg border border-border bg-bg-secondary/50 p-2.5" data-testid={`queue-column-${g.label}`}>
            <p className="mb-2 flex items-center justify-between px-1">
              <span className="text-xs font-semibold uppercase tracking-wide text-text-secondary">{g.label}</span>
              <Badge tone="muted">{rows.length}</Badge>
            </p>
            <div className="space-y-2">
              {rows.map((i) => <QueueCard key={i.id} item={i} selected={selected.has(i.id)} onToggle={onToggle} onOpen={onOpen} />)}
              {!rows.length && <p className="px-1 py-3 text-center text-[11px] text-text-muted">Empty</p>}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function QueueCard({ item, selected, onToggle, onOpen }: { item: QueueItem; selected: boolean; onToggle: (id: string) => void; onOpen: (id: string) => void }) {
  const stale = isStale(item);
  return (
    <div className={cx("group rounded-lg border p-3 transition-colors",
      selected ? "border-accent-primary bg-bg-secondary" : "border-border bg-surface-base hover:border-text-muted")}
      data-testid="queue-card">
      <div className="flex items-start gap-2">
        <button onClick={() => onToggle(item.id)} aria-label={selected ? `Deselect ${item.title}` : `Select ${item.title}`}
          className="mt-0.5 text-text-muted hover:text-text-primary">
          {selected ? <CheckSquare size={14} className="text-accent-primary" /> : <Square size={14} />}
        </button>
        <button onClick={() => onOpen(item.id)} className="min-w-0 flex-1 text-left">
          <p className="line-clamp-2 text-[13px] font-semibold text-text-primary">{item.title}</p>
        </button>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        <QueueStatusChip status={item.status} />
        <PriorityBandChip band={item.priority_band} />
        {item.paused && <Badge tone="warning">paused</Badge>}
        {stale && <Badge tone="warning">stalled</Badge>}
      </div>
      <div className="mt-1.5 flex items-center justify-between text-[11px] text-text-muted">
        <span>{item.target_date ? `Due ${fmtDate(item.target_date)}` : "No target date"}</span>
        <GateDots item={item} />
      </div>
    </div>
  );
}

/** Compact gate indicators: compliance dot + blocked/paused flags. */
function GateDots({ item }: { item: QueueItem }) {
  const c = item.compliance;
  return (
    <span className="flex items-center gap-1" title="Gate status">
      <span className={cx("h-1.5 w-1.5 rounded-full",
        !c ? "bg-text-muted" : c.result === "PASS" ? "bg-status-success" : c.result === "REVIEW" ? "bg-status-warning" : "bg-status-danger")}
        aria-label={c ? `Compliance ${c.result}` : "Compliance not screened"} />
      {item.blocked_reason && (
        <Badge tone="danger" title={item.blocked_reason}>blocked</Badge>
      )}
    </span>
  );
}

function ListView({ items, selected, onToggle, onOpen }: { items: QueueItem[]; selected: Set<string>; onToggle: (id: string) => void; onOpen: (id: string) => void }) {
  return (
    <Panel>
      <ul className="divide-y divide-border">
        {items.map((i) => (
          <li key={i.id} className="flex items-center gap-3 py-2.5">
            <button onClick={() => onToggle(i.id)} aria-label={selected.has(i.id) ? `Deselect ${i.title}` : `Select ${i.title}`} className="text-text-muted hover:text-text-primary">
              {selected.has(i.id) ? <CheckSquare size={14} className="text-accent-primary" /> : <Square size={14} />}
            </button>
            <button onClick={() => onOpen(i.id)} className="min-w-0 flex-1 text-left">
              <span className="block truncate text-[13px] font-semibold text-text-primary hover:text-accent-secondary">{i.title}</span>
              <span className="text-[11px] text-text-muted">{i.target_date ? `due ${fmtDate(i.target_date)}` : "no target date"}</span>
            </button>
            <GateDots item={i} />
            <PriorityBandChip band={i.priority_band} />
            <QueueStatusChip status={i.status} />
          </li>
        ))}
      </ul>
    </Panel>
  );
}

// ---------------------------------------------------------------------------
// Move modal — only legal transitions, gates explained
// ---------------------------------------------------------------------------

function MoveModal({ item, onClose }: { item: QueueItem; onClose: () => void }) {
  const { toast } = useToast();
  const muts = useQueueMutations();
  const targets = legalTargets(item.status as QueueState);
  const [target, setTarget] = useState<QueueState | "">(targets[0] ?? "");
  const [note, setNote] = useState("");
  const [confirmGate, setConfirmGate] = useState(false);

  const complianceHigh = item.compliance?.result === "HIGH_RISK";
  // T18 gate: only PASS leaves COMPLIANCE_REVIEW toward READY_TO_UPLOAD.
  const gated = target === "READY_TO_UPLOAD" && item.compliance?.result !== "PASS";

  const submit = () => {
    if (!target) return;
    muts.transition.mutate(
      { id: item.id, to: target, note: note.trim() || undefined },
      {
        onSuccess: () => { toast({ title: "Moved", description: `${item.title} → ${stateLabel(target)}.`, tone: "success" }); onClose(); },
      },
    );
  };

  return (
    <Modal open onClose={onClose} title={`Move: ${item.title}`}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button variant="primary" loading={muts.transition.isPending} disabled={!target || (gated && !confirmGate)}
            onClick={submit} data-testid="queue-move-confirm">
            Move to {target ? stateLabel(target) : "…"}
          </Button>
        </>
      }>
      <div className="space-y-3">
        <div className="flex items-center gap-2 text-sm">
          <QueueStatusChip status={item.status} />
          <ChevronRight size={14} className="text-text-muted" aria-hidden />
          <span className="text-text-secondary">{targets.length ? "Choose next state" : "No legal moves from here"}</span>
        </div>
        {targets.length ? (
          <Field label="Target state">
            <Select value={target} onChange={(e) => setTarget(e.target.value as QueueState)} data-testid="queue-move-target">
              {targets.map((t) => <option key={t} value={t}>{stateLabel(t)}</option>)}
            </Select>
          </Field>
        ) : (
          <p className="text-xs text-text-muted">This is a terminal state. Archive it or start a new item.</p>
        )}
        {gated && (
          <div className="rounded-md border border-status-danger/40 bg-status-danger/[0.06] p-3 text-[13px]">
            <p className="font-semibold text-status-danger">Gate likely blocked (T18)</p>
            <p className="mt-1 text-text-secondary">
              {complianceHigh
                ? <>Compliance is <strong>HIGH RISK</strong> — only a PASS may leave compliance review toward READY TO UPLOAD. </>
                : <>Compliance result is <strong className="text-text-primary">{item.compliance?.result ?? "missing"}</strong>, not PASS — T18 requires a PASS. </>}
              The backend enforces this; attempting the move will be rejected and logged.
            </p>
            <label className="mt-2 flex items-start gap-2 text-xs text-text-secondary">
              <input type="checkbox" checked={confirmGate} onChange={(e) => setConfirmGate(e.target.checked)} className="mt-0.5" />
              I understand — attempt the move anyway (the backend will reject it).
            </label>
          </div>
        )}
        <Field label="Note (optional)" hint="Recorded on the item timeline.">
          <Input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Why is this moving?" />
        </Field>
        <WhyThis label="Why only these states">
          <p>The queue contract allows only transitions T01–T29 (§10). Illegal jumps (e.g. DISCOVERED → SUBMITTED) are rejected by the backend.</p>
        </WhyThis>
      </div>
    </Modal>
  );
}

// ---------------------------------------------------------------------------
// Bulk bar
// ---------------------------------------------------------------------------

function BulkBar({ count, ids, onClear }: { count: number; ids: string[]; onClear: () => void }) {
  const { toast } = useToast();
  const muts = useQueueMutations();
  const [target, setTarget] = useState("");

  const run = async () => {
    if (!target) return;
    let ok = 0, fail = 0;
    for (const id of ids) {
      try {
        await muts.transition.mutateAsync({ id, to: target as QueueStatus });
        ok++;
      } catch { fail++; }
    }
    onClear();
    toast({
      title: "Bulk move finished",
      description: `${ok} moved, ${fail} rejected (illegal or gated transitions are skipped, not forced).`,
      tone: fail ? "warning" : "success",
    });
  };

  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-accent-primary/50 bg-accent-primary/10 px-3 py-1">
      {count} selected
      <select value={target} onChange={(e) => setTarget(e.target.value)} className="rounded bg-bg-secondary px-1.5 py-0.5 text-xs text-text-primary" aria-label="Bulk move target">
        <option value="">Move to…</option>
        {(["ARCHIVED", "IN_PRODUCTION", "READY_TO_UPLOAD"] as QueueStatus[]).map((s) => (
          <option key={s} value={s}>{stateLabel(s)}</option>
        ))}
      </select>
      <Button size="sm" variant="primary" loading={muts.transition.isPending} disabled={!target} onClick={run}>Apply</Button>
      <Button size="sm" variant="ghost" onClick={onClear}>Clear</Button>
    </span>
  );
}

// ---------------------------------------------------------------------------
// Add item modal — enqueue
// ---------------------------------------------------------------------------

function AddItemModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const muts = useQueueMutations();
  const ideas = useIdeas({ status: "READY", page_size: 50 });
  const [ideaId, setIdeaId] = useState("");
  const [title, setTitle] = useState("");
  const [band, setBand] = useState<PriorityBand>("P2");
  const [targetDate, setTargetDate] = useState("");
  const [notes, setNotes] = useState("");

  const idea: Idea | undefined = (ideas.data?.data ?? []).find((i) => i.id === ideaId);
  const assetType = idea?.kind === "video" ? "VIDEO" : "IMAGE";

  const save = () => {
    if (!idea) return;
    muts.enqueue.mutate(
      {
        title: title.trim() || idea.title,
        asset_type: assetType,
        image_idea_id: idea.kind === "image" ? idea.id : undefined,
        video_idea_id: idea.kind === "video" ? idea.id : undefined,
        opportunity_id: idea.opportunity_id ?? undefined,
        priority_band: band,
        target_date: targetDate || undefined,
        notes: notes.trim() || undefined,
      },
      {
        onSuccess: () => {
          setIdeaId(""); setTitle(""); setTargetDate(""); setNotes("");
          onClose();
        },
      },
    );
  };

  return (
    <Modal open={open} onClose={onClose} title="Add to queue"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button variant="primary" loading={muts.enqueue.isPending} disabled={!idea} onClick={save}>Enqueue</Button>
        </>
      }>
      <div className="space-y-3">
        <Field label="Idea" required hint="READY ideas enter the queue at DISCOVERED (T01).">
          <Select value={ideaId} onChange={(e) => { setIdeaId(e.target.value); if (!title) { const f = (ideas.data?.data ?? []).find((i) => i.id === e.target.value); if (f) setTitle(f.title); } }}>
            <option value="">Select a READY idea…</option>
            {(ideas.data?.data ?? []).map((i) => <option key={i.id} value={i.id}>{i.title}</option>)}
          </Select>
        </Field>
        {idea && (
          <div className="flex flex-wrap items-center gap-1.5 text-xs">
            <FormatBadge format={idea.kind} />
            {idea.compliance && <ComplianceChip result={idea.compliance.result} />}
          </div>
        )}
        <Field label="Queue title"><Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Defaults to the idea title" /></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Target date"><Input type="date" value={targetDate} onChange={(e) => setTargetDate(e.target.value)} /></Field>
          <Field label="Priority band">
            <Select value={band} onChange={(e) => setBand(e.target.value as PriorityBand)}>
              {BANDS.map((b) => <option key={b} value={b}>{b}</option>)}
            </Select>
          </Field>
        </div>
        <Field label="Notes (optional)"><Textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} /></Field>
      </div>
    </Modal>
  );
}

// ---------------------------------------------------------------------------
// Detail drawer
// ---------------------------------------------------------------------------

function ItemDrawer({ id, onClose }: { id: string | null; onClose: () => void }) {
  const item = useQueueItem(id);
  return (
    <Drawer open={!!id} onClose={onClose} title={item.data?.title ?? "Queue item"} wide>
      {!id ? null : item.isLoading ? (
        <div className="space-y-3"><div className="skeleton h-8 rounded" /><div className="skeleton h-40 rounded" /></div>
      ) : item.isError || !item.data ? (
        <EmptyState title="Queue item not found" action={<Button size="sm" onClick={onClose}>Close</Button>} />
      ) : (
        <ItemDetail item={item.data} onClose={onClose} />
      )}
    </Drawer>
  );
}

function ItemDetail({ item, onClose }: { item: QueueItemDetail; onClose: () => void }) {
  const { toast } = useToast();
  const muts = useQueueMutations();
  const assets = useAssets({ queue_id: item.id, page_size: 10 });
  const [moveOpen, setMoveOpen] = useState(false);
  const [submitOpen, setSubmitOpen] = useState(false);
  const [confirmArchive, setConfirmArchive] = useState(false);

  const ideaKind = item.image_idea_id ? "image" : item.video_idea_id ? "video" : null;
  const ideaId = item.image_idea_id ?? item.video_idea_id;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-1.5">
        <QueueStatusChip status={item.status} />
        <PriorityBandChip band={item.priority_band} />
        <FormatBadge format={item.asset_type} />
        {item.compliance && <ComplianceChip result={item.compliance.result} />}
        {item.paused && <Badge tone="warning">paused</Badge>}
        <span className="text-xs text-text-muted">· changed {timeAgo(item.status_changed_at)}</span>
      </div>

      {/* Idea link */}
      {ideaId && (
        <p className="text-[13px] text-text-secondary">
          Idea: <a href={`/${ideaKind}-ideas?idea=${ideaId}`} className="text-accent-secondary hover:underline">
            {ideaId.slice(0, 8)}… ({ideaKind})
          </a>
        </p>
      )}

      {/* Scheduling facts */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Fact label="Target date" value={item.target_date ? fmtDate(item.target_date) : "—"} />
        <Fact label="Deadline" value={item.deadline_state ? enumLabel(item.deadline_state) : "—"} />
        <Fact label="Produced" value={`${item.produced_count}/${item.target_quantity}`} />
        <Fact label="Rework" value={String(item.rework_count)} />
      </div>
      {item.generation_tool && <p className="text-[13px] text-text-secondary">Generation tool: <span className="text-text-primary">{item.generation_tool}</span></p>}
      {item.notes && <p className="text-[13px] text-text-secondary">Notes: <span className="text-text-primary">{item.notes}</span></p>}
      {item.blocked_reason && (
        <div className="rounded-md border border-status-danger/40 bg-status-danger/[0.06] p-3 text-[13px] text-status-danger">
          Blocked: {item.blocked_reason}
        </div>
      )}

      {/* Gate status */}
      <section className="rounded-lg border border-border p-3.5">
        <p className="micro-label mb-2">Gate status</p>
        {item.compliance ? (
          <div className="flex items-center gap-2 text-[13px]">
            <ComplianceChip result={item.compliance.result} />
            <a href={`/compliance?check=${item.compliance.check_id}`} className="text-accent-secondary hover:underline">
              Open screening {item.compliance.check_id.slice(0, 8)}…
            </a>
          </div>
        ) : (
          <p className="text-[13px] text-text-muted">Not screened yet — compliance gates (T16/T18) will request a screen at COMPLIANCE REVIEW.</p>
        )}
        <p className="mt-2 text-[11px] text-text-muted">
          Gates are enforced by the backend at move time. Similarity screening lives on the idea/prompt records, not the queue row.
        </p>
      </section>

      {/* Assets */}
      <section>
        <p className="micro-label mb-2">Assets ({assets.data?.data.length ?? 0})</p>
        {(assets.data?.data ?? []).map((a) => (
          <div key={a.id} className="flex items-center gap-2 rounded-md border border-border bg-bg-secondary px-3 py-2 text-[13px]">
            <span className="font-display font-semibold text-text-primary">v{a.current_version?.version_number ?? 1}</span>
            <span className="min-w-0 flex-1 truncate text-text-secondary">{a.title}</span>
            <Badge tone="muted">{enumLabel(a.status)}</Badge>
          </div>
        ))}
        {!(assets.data?.data ?? []).length && <p className="text-xs text-text-muted">No registered assets yet.</p>}
      </section>

      {/* Timeline */}
      <section>
        <p className="micro-label mb-2">Timeline</p>
        <ul className="space-y-2">
          {(item.history ?? []).map((t) => (
            <li key={t.id} className="flex items-start gap-2.5 text-[13px]">
              <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-text-muted" aria-hidden />
              <div>
                <p className="flex flex-wrap items-center gap-1.5 text-text-primary">
                  {t.from ? <QueueStatusChip status={t.from} /> : <Badge tone="muted">created</Badge>}
                  <ChevronRight size={12} className="text-text-muted" aria-hidden />
                  <QueueStatusChip status={t.to} />
                </p>
                <p className="text-[11px] text-text-muted">{timeAgo(t.at)} · {t.actor}{t.note ? ` · ${t.note}` : ""}</p>
              </div>
            </li>
          ))}
          {!(item.history ?? []).length && <li className="text-xs text-text-muted">No timeline events recorded.</li>}
        </ul>
      </section>

      {/* Actions */}
      <section className="rounded-lg border border-border p-3.5">
        <p className="micro-label mb-2.5">Actions</p>
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="primary" onClick={() => setMoveOpen(true)}>Move state</Button>
          {item.status !== "SUBMITTED" && (
            <Button size="sm" variant="outline" icon={<Send size={13} />} onClick={() => setSubmitOpen(true)}>
              Record submission
            </Button>
          )}
          <Button
            size="sm" variant="ghost"
            icon={item.paused ? <Play size={13} /> : <Pause size={13} />}
            loading={muts.pause.isPending}
            onClick={() => muts.pause.mutate({ id: item.id, paused: !item.paused })}
          >
            {item.paused ? "Resume" : "Pause"}
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setConfirmArchive(true)}>Archive</Button>
        </div>
      </section>

      {moveOpen && <MoveModal item={item} onClose={() => setMoveOpen(false)} />}
      {submitOpen && <SubmissionModal item={item} onClose={() => setSubmitOpen(false)} />}
      <ConfirmModal
        open={confirmArchive}
        onClose={() => setConfirmArchive(false)}
        title="Archive queue item"
        description="The item leaves active views but stays in history."
        confirmLabel="Archive"
        onConfirm={() => { muts.transition.mutate({ id: item.id, to: "ARCHIVED" }); setConfirmArchive(false); onClose(); }}
      />
    </div>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-border bg-bg-secondary p-2.5">
      <p className="text-[11px] uppercase tracking-wide text-text-muted">{label}</p>
      <p className="mt-0.5 font-display text-sm font-semibold text-text-primary">{value}</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// ---------------------------------------------------------------------------
// Submission modal — records the user's manual upload via the contract's
// documented flow: POST /submissions (plan) -> POST /submissions/{id}/
// mark-submitted. (StockPulse never uploads; these endpoints only record.)
// ---------------------------------------------------------------------------

function SubmissionModal({ item, onClose }: { item: QueueItemDetail; onClose: () => void }) {
  const { toast } = useToast();
  const sub = useSubmissionMutations();
  const [adobeRef, setAdobeRef] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true);
    try {
      const weekStart = new Date();
      weekStart.setDate(weekStart.getDate() - ((weekStart.getDay() + 6) % 7));
      const plan = await sub.createPlan.mutateAsync({ queue_ids: [item.id], week_start: weekStart.toISOString().slice(0, 10) });
      const first = Array.isArray(plan) ? plan[0] : plan.data?.[0];
      if (!first?.id) throw new Error("Plan created but no submission record was returned.");
      await sub.markSubmitted.mutateAsync({ id: first.id, adobe_reference: adobeRef.trim() || undefined });
      toast({
        title: "Submission recorded",
        description: `Recorded as your manual upload${notes.trim() ? " — note kept with this session only." : "."} StockPulse never uploads on your behalf.`,
        tone: "success",
      });
      onClose();
    } catch (e) {
      toast({ title: "Could not record submission", description: e instanceof Error ? e.message : "The item may not be in a ready state.", tone: "danger" });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal open onClose={onClose} title={`Record submission: ${item.title}`}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button variant="primary" icon={<Send size={13} />} loading={busy} onClick={submit} data-testid="queue-submit-confirm">
            Record as submitted
          </Button>
        </>
      }>
      <div className="space-y-3">
        <div className="rounded-md border border-border bg-bg-secondary p-3 text-[13px] text-text-secondary">
          This creates a submission plan for this item and records that <strong className="text-text-primary">you manually uploaded</strong> it to Adobe Stock
          (plan → mark-submitted). The backend moves the queue item to SUBMITTED. StockPulse never uploads on your behalf.
        </div>
        <Field label="Adobe reference (optional)" hint="The reference Adobe assigned after your manual upload.">
          <Input value={adobeRef} onChange={(e) => setAdobeRef(e.target.value)} placeholder="e.g. 123456789" />
        </Field>
        <Field label="Notes (optional)" hint="For your own reference — not stored on the submission record.">
          <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={3} placeholder="Anything worth remembering about this submission…" />
        </Field>
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
      <QueuePage />
    </Suspense>
  );
}
