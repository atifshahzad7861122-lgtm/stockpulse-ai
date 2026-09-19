"use client";
/**
 * Planner (docs/05 screen 14) — weekly capacity, submission calendar,
 * compliance gate list, asset tracking with acceptance/rejection outcomes.
 * CONTRACT notes: QueueItem carries no compliance/similarity summary, so the
 * gate list combines queue items awaiting review with pending compliance
 * checks. Submission records are never invented — only manual uploads
 * recorded in the queue appear here.
 */
import { useMemo, useState } from "react";
import Link from "next/link";
import { CalendarDays, ChevronLeft, ChevronRight } from "lucide-react";
import {
  Badge,
  Button,
  EmptyState,
  Field,
  Input,
  Modal,
  PageHeader,
  Panel,
  QueryView,
  Skeleton,
  Textarea,
  WhyThis,
  cx,
} from "../../components/ui";
import { ComplianceChip, QueueStatusChip } from "../../components/scores";
import { Stagger, StaggerItem } from "../../components/motion/motion";
import { useToast } from "../../components/toast";
import { useComplianceChecks, useQueue, useSettings, useSettingsMutations, useSubmissionMutations, useSubmissions } from "../../hooks/useApi";
import { enumLabel, fmtDate, timeAgo } from "../../lib/format";
import type { QueueItem, Submission } from "../../types";

export default function PlannerPage() {
  const [month, setMonth] = useState(() => {
    const d = new Date();
    return { y: d.getFullYear(), m: d.getMonth() };
  });

  return (
    <div className="space-y-4">
      <PageHeader
        title="Planner"
        description="Capacity, calendar, and asset tracking. Plan the week against what the queue can actually hold."
      />

      <div className="grid gap-4 xl:grid-cols-[1fr_1.5fr]">
        <div className="space-y-4">
          <CapacityPanel />
          <GateListPanel />
        </div>
        <div className="space-y-4">
          <CalendarPanel month={month} onMonth={setMonth} />
          <AssetTrackingPanel />
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Capacity settings
// ---------------------------------------------------------------------------

function CapacityPanel() {
  const { toast } = useToast();
  const settings = useSettings();
  const muts = useSettingsMutations();
  const queue = useQueue({ page_size: 200 });

  const weekly = Number(settings.data?.["planner.weekly_capacity"] ?? 0);
  const [draft, setDraft] = useState<string | null>(null);

  const weekStart = new Date();
  weekStart.setDate(weekStart.getDate() - ((weekStart.getDay() + 6) % 7));
  const ws = weekStart.toISOString().slice(0, 10);
  const planned = (queue.data?.data ?? []).filter((i) => i.target_date && i.target_date >= ws && !["ARCHIVED"].includes(i.status)).length;
  const over = weekly > 0 && planned > weekly;

  const save = () => {
    const v = Number(draft);
    if (!Number.isFinite(v) || v < 0) return;
    muts.mutate({ "planner.weekly_capacity": v }, {
      onSuccess: () => { toast({ title: "Capacity saved", description: `Weekly capacity set to ${v} assets.`, tone: "success" }); setDraft(null); },
    });
  };

  return (
    <Panel title="Weekly capacity">
      <QueryView query={settings} loading={<Skeleton className="h-20" />} empty={<EmptyState compact title="No settings" />} errorTitle="Settings unavailable">
        {() => (
          <div className="space-y-3">
            <div className="flex items-baseline justify-between">
              <span className="text-xs text-text-secondary">Planned this week</span>
              <span className={cx("font-display text-xl font-semibold", over ? "text-status-danger" : "text-text-primary")}>
                {planned}<span className="text-text-muted"> / {weekly > 0 ? weekly : "—"}</span>
              </span>
            </div>
            {weekly > 0 && (
              <div className="h-2 overflow-hidden rounded-full bg-border" role="img" aria-label={`${planned} of ${weekly} slots planned`}>
                <div className={cx("h-full rounded-full", over ? "bg-status-danger" : "bg-accent-primary")} style={{ width: `${Math.min(100, (planned / weekly) * 100)}%` }} />
              </div>
            )}
            {over && <p className="text-xs text-status-danger">Over capacity — move items to later dates or raise capacity.</p>}
            <div className="flex items-end gap-2">
              <div className="w-32">
                <Field label="Assets / week">
                  <Input type="number" min={0} value={draft ?? String(weekly)} onChange={(e) => setDraft(e.target.value)} aria-label="Weekly capacity" />
                </Field>
              </div>
              <Button size="sm" variant="primary" loading={muts.isPending} onClick={save} disabled={draft === null || draft === String(weekly)}>Save</Button>
            </div>
            <WhyThis label="Why capacity matters">
              <p>The dashboard capacity indicator is computed against this number. Set what you can realistically produce and upload in a week.</p>
            </WhyThis>
          </div>
        )}
      </QueryView>
    </Panel>
  );
}

// ---------------------------------------------------------------------------
// Gate list — items awaiting compliance review + pending compliance checks
// ---------------------------------------------------------------------------

const GATE_STATES = ["QUALITY_CHECK", "COMPLIANCE_REVIEW"] as const;

function GateListPanel() {
  const queue = useQueue({ page_size: 100 });
  const pending = useComplianceChecks({ pending_review: true, page_size: 20 });
  const gated = useMemo(() => {
    return (queue.data?.data ?? []).filter((i) => (GATE_STATES as readonly string[]).includes(i.status));
  }, [queue.data]);

  const none = !gated.length && !(pending.data?.data?.length);

  return (
    <Panel title="Compliance gates" action={<Link href="/compliance" className="text-xs text-accent-secondary hover:underline">Compliance Center</Link>}>
      {queue.isLoading || pending.isLoading ? (
        <Skeleton lines={3} />
      ) : queue.isError ? (
        <EmptyState compact title="Gate list unavailable" />
      ) : none ? (
        <EmptyState compact title="No gated items" description="Nothing is waiting in review states and no compliance checks are pending your decision." />
      ) : (
        <div className="space-y-3">
          {gated.length > 0 && (
            <Stagger as="ul" className="space-y-2" gap={0.03}>
              {gated.map((i) => (
                <StaggerItem as="li" layout key={i.id} className="flex items-center gap-2.5 rounded-md border border-status-warning/30 bg-status-warning/[0.04] px-3 py-2">
                  <Link href={`/queue?item=${i.id}`} className="min-w-0 flex-1 truncate text-[13px] font-medium text-text-primary hover:text-accent-secondary">
                    {i.title}
                  </Link>
                  <QueueStatusChip status={i.status} />
                </StaggerItem>
              ))}
            </Stagger>
          )}
          {(pending.data?.data ?? []).length > 0 && (
            <div>
              <p className="micro-label mb-1.5">Checks awaiting decision</p>
              <Stagger as="ul" className="space-y-2" gap={0.03}>
                {(pending.data?.data ?? []).map((c) => (
                  <StaggerItem as="li" layout key={c.id} className="flex items-center gap-2.5 rounded-md border border-border bg-bg-secondary px-3 py-2">
                    <ComplianceChip result={c.result} />
                    <Link href={`/compliance?review=${c.id}`} className="min-w-0 flex-1 truncate text-[13px] font-medium text-text-primary hover:text-accent-secondary">
                      {enumLabel(c.subject.kind)} · {c.subject.id.slice(0, 8)}
                    </Link>
                  </StaggerItem>
                ))}
              </Stagger>
            </div>
          )}
        </div>
      )}
    </Panel>
  );
}

// ---------------------------------------------------------------------------
// Calendar
// ---------------------------------------------------------------------------

function CalendarPanel({ month, onMonth }: { month: { y: number; m: number }; onMonth: (v: { y: number; m: number }) => void }) {
  const queue = useQueue({ page_size: 300 });

  const cells = useMemo(() => {
    const first = new Date(month.y, month.m, 1);
    const startPad = (first.getDay() + 6) % 7; // Monday-first
    const daysIn = new Date(month.y, month.m + 1, 0).getDate();
    const arr: (Date | null)[] = [];
    for (let i = 0; i < startPad; i++) arr.push(null);
    for (let d = 1; d <= daysIn; d++) arr.push(new Date(month.y, month.m, d));
    while (arr.length % 7) arr.push(null);
    return arr;
  }, [month]);

  const byDay = useMemo(() => {
    const map = new Map<string, QueueItem[]>();
    for (const i of queue.data?.data ?? []) {
      if (!i.target_date) continue;
      const arr = map.get(i.target_date) ?? [];
      arr.push(i);
      map.set(i.target_date, arr);
    }
    return map;
  }, [queue.data]);

  const todayISO = new Date().toISOString().slice(0, 10);
  const label = new Date(month.y, month.m, 1).toLocaleDateString(undefined, { month: "long", year: "numeric" });

  const shift = (delta: number) => {
    const d = new Date(month.y, month.m + delta, 1);
    onMonth({ y: d.getFullYear(), m: d.getMonth() });
  };

  return (
    <Panel
      title={
        <div className="flex items-center gap-2">
          <CalendarDays size={15} className="text-accent-primary" aria-hidden />
          Submission calendar
        </div>
      }
      action={
        <div className="flex items-center gap-1">
          <Button size="sm" variant="ghost" icon={<ChevronLeft size={14} />} onClick={() => shift(-1)} aria-label="Previous month" />
          <span className="min-w-32 text-center text-[13px] font-semibold text-text-primary">{label}</span>
          <Button size="sm" variant="ghost" icon={<ChevronRight size={14} />} onClick={() => shift(1)} aria-label="Next month" />
        </div>
      }
    >
      <QueryView query={queue} loading={<Skeleton className="h-64" />} empty={<EmptyState compact title="Nothing scheduled" />} errorTitle="Calendar unavailable">
        {() => (
          <div>
            <div className="grid grid-cols-7 gap-px overflow-hidden rounded-lg border border-border bg-border">
              {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d) => (
                <div key={d} className="bg-bg-secondary px-1 py-1.5 text-center text-[10px] font-semibold uppercase tracking-wide text-text-muted">{d}</div>
              ))}
              {cells.map((date, i) => {
                if (!date) return <div key={i} className="min-h-16 bg-surface-base" aria-hidden />;
                const iso = date.toISOString().slice(0, 10);
                const rows = (byDay.get(iso) ?? []).slice(0, 3);
                const extra = (byDay.get(iso) ?? []).length - rows.length;
                const isToday = iso === todayISO;
                return (
                  <div key={i} className={cx("min-h-16 bg-surface-base p-1", isToday && "ring-1 ring-inset ring-accent-primary")}>
                    <p className={cx("text-[11px] font-semibold", isToday ? "text-accent-primary" : "text-text-muted")}>{date.getDate()}</p>
                    {rows.map((r) => (
                      <Link key={r.id} href={`/queue?item=${r.id}`} title={r.title}
                        className="mt-0.5 block truncate rounded bg-surface-elevated px-1 py-0.5 text-[10px] text-text-secondary hover:text-text-primary">
                        {r.title}
                      </Link>
                    ))}
                    {extra > 0 && <p className="mt-0.5 text-[10px] text-text-muted">+{extra} more</p>}
                  </div>
                );
              })}
            </div>
            <p className="mt-2 text-[11px] text-text-muted">Target dates come from queue items. Click a day item to open it in the queue.</p>
          </div>
        )}
      </QueryView>
    </Panel>
  );
}

// ---------------------------------------------------------------------------
// Asset tracking
// ---------------------------------------------------------------------------

const OUTCOME_TONE: Record<string, "success" | "danger" | "warning" | "muted"> = {
  ACCEPTED: "success",
  REJECTED: "danger",
  UNDER_REVIEW: "warning",
  SUBMITTED: "warning",
  PLANNED: "muted",
};

function AssetTrackingPanel() {
  const subs = useSubmissions({ page_size: 10 });

  return (
    <Panel title="Asset tracking" action={<Link href="/queue" className="text-xs text-accent-secondary hover:underline">Queue</Link>}>
      <QueryView
        query={subs}
        loading={<Skeleton lines={4} />}
        empty={<EmptyState compact title="No submissions recorded" description="When you manually upload to Adobe and record the submission in the queue, outcomes are tracked here. We never invent sales data." />}
        errorTitle="Submissions unavailable"
      >
        {(page) => (
          <ul className="divide-y divide-border">
            {page.data.map((s) => (
              <SubmissionRow key={s.id} submission={s} />
            ))}
          </ul>
        )}
      </QueryView>
    </Panel>
  );
}

function SubmissionRow({ submission: s }: { submission: Submission }) {
  const [outcomeOpen, setOutcomeOpen] = useState(false);
  const actionable = s.status === "SUBMITTED" || s.status === "UNDER_REVIEW";
  return (
    <>
      <li className="flex items-center gap-3 py-2.5">
        <div className="min-w-0 flex-1">
          <p className="truncate text-[13px] font-medium text-text-primary">
            {s.production_queue_id ? (
              <Link href={`/queue?item=${s.production_queue_id}`} className="hover:text-accent-secondary">
                Asset · {s.asset_id.slice(0, 8)}
              </Link>
            ) : (
              <>Asset · {s.asset_id.slice(0, 8)}</>
            )}
          </p>
          <p className="text-[11px] text-text-muted">
            {s.submitted_at ? `Submitted ${fmtDate(s.submitted_at)}` : timeAgo(s.created_at)}
            {s.adobe_reference ? ` · Adobe ref ${s.adobe_reference}` : ""}
          </p>
          {s.rejection_reason && (
            <p className="mt-0.5 text-[11px] text-status-danger">Rejected: {s.rejection_reason}</p>
          )}
          {s.notes && !s.rejection_reason && (
            <p className="mt-0.5 line-clamp-1 text-[11px] text-text-muted">{s.notes}</p>
          )}
        </div>
        <Badge tone={OUTCOME_TONE[s.status] ?? "muted"}>{enumLabel(s.status)}</Badge>
        {actionable && (
          <Button size="sm" variant="outline" onClick={() => setOutcomeOpen(true)}>Record outcome</Button>
        )}
      </li>
      {outcomeOpen && <OutcomeModal submission={s} onClose={() => setOutcomeOpen(false)} />}
    </>
  );
}

function OutcomeModal({ submission: s, onClose }: { submission: Submission; onClose: () => void }) {
  const sub = useSubmissionMutations();
  const [outcome, setOutcome] = useState<"accepted" | "rejected">("accepted");
  const [reason, setReason] = useState("");

  const save = () => {
    sub.recordOutcome.mutate(
      {
        id: s.id,
        items: [{ queue_id: s.production_queue_id ?? "", outcome, reason: outcome === "rejected" ? reason.trim() : undefined }],
      },
      { onSuccess: onClose },
    );
  };

  return (
    <Modal open onClose={onClose} title="Record outcome"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button variant="primary" loading={sub.recordOutcome.isPending}
            disabled={outcome === "rejected" && !reason.trim()}
            title={outcome === "rejected" && !reason.trim() ? "Rejection requires a reason" : undefined}
            onClick={save}>
            Record {outcome}
          </Button>
        </>
      }>
      <div className="space-y-3">
        <p className="text-[13px] text-text-secondary">
          Record what Adobe decided about this submission. Outcomes feed your analytics — only record real decisions, never estimates.
        </p>
        <div className="flex gap-2">
          {(["accepted", "rejected"] as const).map((o) => (
            <Button key={o} size="sm" variant={outcome === o ? "primary" : "outline"} onClick={() => setOutcome(o)}>
              {enumLabel(o.toUpperCase())}
            </Button>
          ))}
        </div>
        {outcome === "rejected" && (
          <Field label="Reason" required hint="Recorded for your review — required by the API.">
            <Textarea value={reason} onChange={(e) => setReason(e.target.value)} rows={3} placeholder="e.g. Similar content already in the collection" />
          </Field>
        )}
      </div>
    </Modal>
  );
}
