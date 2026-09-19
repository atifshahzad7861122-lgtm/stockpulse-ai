"use client";
/**
 * Compliance Center (docs/05 screen 11) — PASS / REVIEW / HIGH RISK summary,
 * screening runner, manual human review with reason, run history.
 */
import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { ShieldAlert, ShieldCheck, Play } from "lucide-react";
import {
  Badge,
  Button,
  Drawer,
  EmptyState,
  Field,
  Input,
  PageHeader,
  Pagination,
  Panel,
  QueryView,
  Select,
  Skeleton,
  Textarea,
  WhyThis,
  cx,
} from "../../components/ui";
import { ComplianceChip, RiskChip } from "../../components/scores";
import { useToast } from "../../components/toast";
import {
  useComplianceChecks,
  useComplianceCheck,
  useComplianceMutations,
} from "../../hooks/useApi";
import { useJobPoll } from "../../hooks/useJobPoll";
import { enumLabel, timeAgo } from "../../lib/format";
import type { ComplianceCheck, ComplianceCheckType, ComplianceResult, ReviewDecision, SubjectKind } from "../../types";

const SUBJECT_LINKS: Record<SubjectKind, (id: string) => string> = {
  image_idea: (id) => `/image-ideas?idea=${id}`,
  video_idea: (id) => `/video-ideas?idea=${id}`,
  prompt: (id) => `/prompt-studio/${id}`,
  asset: (id) => `/metadata?asset=${id}`,
  metadata: (id) => `/metadata?bundle=${id}`,
  production_queue: (id) => `/queue?item=${id}`,
};

function CompliancePage() {
  const router = useRouter();
  const params = useSearchParams();
  const reviewId = params.get("review");
  const [page, setPage] = useState(1);
  const [runOpen, setRunOpen] = useState(false);

  const all = useComplianceChecks({ page, page_size: 20 });
  const recent = useComplianceChecks({ page_size: 100 });
  const pending = useComplianceChecks({ pending_review: true, page_size: 1 });

  const setParam = (k: string, v: string) => {
    const p = new URLSearchParams(params.toString());
    if (v) p.set(k, v); else p.delete(k);
    router.replace(`/compliance?${p.toString()}`);
  };

  return (
    <div className="space-y-4">
      <PageHeader
        title="Compliance Center"
        description="Property releases, trademarks, sensitive content. A PASS is required before an item can leave compliance review (T18); HIGH RISK blocks the queue until remediated."
        actions={<Button size="sm" variant="primary" icon={<Play size={13} />} onClick={() => setRunOpen(true)}>Run screening</Button>}
      />

      {/* Summary counters (last 100 screenings) */}
      <div className="grid grid-cols-3 gap-3">
        <CounterCard tone="success" label="PASS" value={countOf(recent.data?.data, "PASS")} hint="Cleared — can leave compliance review" />
        <CounterCard tone="warning" label="REVIEW" value={countOf(recent.data?.data, "REVIEW")} hint="Needs your judgment" />
        <CounterCard tone="danger" label="HIGH RISK" value={countOf(recent.data?.data, "HIGH_RISK")} hint="Blocked until remediated" />
      </div>

      {(pending.data?.pagination.total ?? 0) > 0 && (
        <div className="flex items-center gap-2 rounded-lg border border-status-warning/30 bg-status-warning/[0.06] px-4 py-3 text-[13px] text-text-secondary">
          <ShieldAlert size={15} className="text-status-warning" aria-hidden />
          <span><strong className="text-text-primary">{pending.data!.pagination.total}</strong> item{pending.data!.pagination.total === 1 ? "" : "s"} waiting for human review.</span>
          <Button size="sm" variant="outline" className="ml-auto" onClick={() => document.getElementById("review-list")?.scrollIntoView()}>Review now</Button>
        </div>
      )}

      {/* Pending review list */}
      <Panel title="Needs review">
        <div id="review-list">
          <ReviewList onOpen={(id) => setParam("review", id)} />
        </div>
      </Panel>

      {/* History */}
      <Panel title="Screening history">
        <QueryView
          query={all}
          loading={<Skeleton lines={5} />}
          empty={<EmptyState compact title="No screenings yet" description="Run a screening from an idea, prompt, or the button above." />}
          errorTitle="Screening history unavailable"
        >
          {(p) => (
            <>
              <ul className="space-y-2">
                {p.data.map((c) => <CheckRow key={c.id} check={c} onOpen={() => setParam("review", c.id)} />)}
              </ul>
              <Pagination page={page} totalPages={p.pagination.total_pages} onChange={setPage} />
            </>
          )}
        </QueryView>
      </Panel>

      <ScreeningRunner open={runOpen} onClose={() => setRunOpen(false)} />
      <ReviewDrawer id={reviewId} onClose={() => setParam("review", "")} />
    </div>
  );
}

function countOf(checks: ComplianceCheck[] | undefined, result: ComplianceResult) {
  return checks?.filter((c) => c.result === result).length ?? 0;
}

function CounterCard({ tone, label, value, hint }: { tone: "success" | "warning" | "danger"; label: string; value: number; hint: string }) {
  const color = tone === "success" ? "text-status-success" : tone === "warning" ? "text-status-warning" : "text-status-danger";
  return (
    <Panel>
      <div className="flex items-center gap-2">
        {tone === "success" ? <ShieldCheck size={16} className="text-status-success" aria-hidden /> : <ShieldAlert size={16} className={color} aria-hidden />}
        <p className={cx("font-display text-2xl font-semibold", color)}>{value}</p>
      </div>
      <p className="mt-1 text-xs font-semibold text-text-primary">{label}</p>
      <p className="text-[11px] text-text-muted">{hint}</p>
    </Panel>
  );
}

function CheckRow({ check, onOpen }: { check: ComplianceCheck; onOpen: () => void }) {
  return (
    <li className="flex items-center gap-3 rounded-md border border-border bg-bg-secondary px-3 py-2.5">
      <ComplianceChip result={check.result} />
      <button onClick={onOpen} className="min-w-0 flex-1 text-left">
        <span className="block truncate text-[13px] font-medium text-text-primary hover:text-accent-secondary">
          {enumLabel(check.subject.kind)} · {check.subject.id.slice(0, 8)}… · {enumLabel(check.check_type)}
        </span>
        <span className="text-[11px] text-text-muted">{check.findings.filter((f) => f.triggered).length} triggered findings · {timeAgo(check.created_at)}</span>
      </button>
      {check.review_decision ? (
        <span className="shrink-0 text-[11px] text-text-muted">reviewed: {enumLabel(check.review_decision)}</span>
      ) : check.result === "REVIEW" ? (
        <Button size="sm" variant="outline" onClick={onOpen}>Review</Button>
      ) : null}
    </li>
  );
}

function ReviewList({ onOpen }: { onOpen: (id: string) => void }) {
  const pending = useComplianceChecks({ pending_review: true, page_size: 10 });
  return (
    <QueryView
      query={pending}
      loading={<Skeleton lines={3} />}
      empty={<EmptyState compact icon={<ShieldCheck size={18} />} title="All clear" description="Nothing is waiting for compliance review." />}
      errorTitle="Review list unavailable"
    >
      {(p) => (
        <ul className="space-y-2">
          {p.data.map((c) => (
            <li key={c.id} className="flex items-center gap-3 rounded-md border border-status-warning/30 bg-status-warning/[0.04] px-3 py-2.5">
              <ComplianceChip result={c.result} />
              <button onClick={() => onOpen(c.id)} className="min-w-0 flex-1 text-left">
                <span className="block truncate text-[13px] font-medium text-text-primary hover:text-accent-secondary">
                  {enumLabel(c.subject.kind)} · {c.subject.id.slice(0, 8)}… · {enumLabel(c.check_type)}
                </span>
                <span className="text-[11px] text-text-muted">{c.findings.filter((f) => f.triggered).length} triggered findings · {timeAgo(c.created_at)}</span>
              </button>
              <Button size="sm" variant="outline" onClick={() => onOpen(c.id)}>Review</Button>
            </li>
          ))}
        </ul>
      )}
    </QueryView>
  );
}

// ---------------------------------------------------------------------------
// Screening runner
// ---------------------------------------------------------------------------

const CHECK_TYPES: { value: ComplianceCheckType; label: string }[] = [
  { value: "PROMPT_SCREEN", label: "Prompt screen" },
  { value: "ASSET_SCREEN", label: "Asset screen" },
  { value: "SIMILARITY_SCAN", label: "Similarity scan" },
  { value: "METADATA_SCREEN", label: "Metadata screen" },
];

const SUBJECT_KINDS: SubjectKind[] = ["prompt", "asset", "image_idea", "video_idea", "metadata", "production_queue"];

function ScreeningRunner({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { toast } = useToast();
  const qc = useQueryClient();
  const muts = useComplianceMutations();
  const [checkType, setCheckType] = useState<ComplianceCheckType>("PROMPT_SCREEN");
  const [subjectKind, setSubjectKind] = useState<SubjectKind>("prompt");
  const [subjectId, setSubjectId] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);

  const poll = useJobPoll(jobId, {
    onDone: (job) => {
      setJobId(null);
      if (job.status === "succeeded") {
        toast({ title: "Screening complete", description: "Findings are in the history below.", tone: "success" });
        qc.invalidateQueries({ queryKey: ["compliance"] });
        onClose();
      } else toast({ title: "Screening failed", description: job.error?.message ?? "Try again.", tone: "warning" });
    },
  });

  const run = () => {
    if (!subjectId.trim()) return;
    muts.runCheck.mutate(
      { check_type: checkType, subject_kind: subjectKind, subject_id: subjectId.trim() },
      {
        onSuccess: (r) => {
          if ("job_id" in r) {
            setJobId(r.job_id);
          } else {
            toast({ title: "Screening complete", description: `Result: ${r.result}`, tone: r.result === "PASS" ? "success" : "warning" });
            qc.invalidateQueries({ queryKey: ["compliance"] });
            setSubjectId("");
            onClose();
          }
        },
      },
    );
  };

  return (
    <Drawer open={open} onClose={onClose} title="Run compliance screening"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button variant="primary" icon={<Play size={13} />} loading={muts.runCheck.isPending || poll.isPolling} disabled={!subjectId.trim()} onClick={run} data-testid="compliance-run">
            {poll.isPolling ? `Screening… ${Math.round((poll.job?.progress ?? 0) * 100)}%` : "Start screening"}
          </Button>
        </>
      }>
      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <Field label="Check type">
            <Select value={checkType} onChange={(e) => setCheckType(e.target.value as ComplianceCheckType)}>
              {CHECK_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
            </Select>
          </Field>
          <Field label="Subject type">
            <Select value={subjectKind} onChange={(e) => setSubjectKind(e.target.value as SubjectKind)}>
              {SUBJECT_KINDS.map((k) => <option key={k} value={k}>{enumLabel(k)}</option>)}
            </Select>
          </Field>
        </div>
        <Field label="Subject ID" required hint="The UUID of the prompt, asset, idea, metadata bundle, or queue item to screen.">
          <Input value={subjectId} onChange={(e) => setSubjectId(e.target.value)} placeholder="e.g. 3f2a1b4c-…" data-testid="compliance-subject-id" />
        </Field>
        <WhyThis label="What screening checks">
          <p>Trademark and logo detection, recognizable people and release requirements, disallowed or sensitive content, and editorial framing. Results: PASS (clear), REVIEW (human judgment), HIGH RISK (blocked until remediated).</p>
        </WhyThis>
      </div>
    </Drawer>
  );
}

// ---------------------------------------------------------------------------
// Manual human review drawer
// ---------------------------------------------------------------------------

function ReviewDrawer({ id, onClose }: { id: string | null; onClose: () => void }) {
  const check = useComplianceCheck(id);
  return (
    <Drawer open={!!id} onClose={onClose} title="Compliance review" wide>
      {!id ? null : check.isLoading ? (
        <div className="space-y-3"><div className="skeleton h-8 rounded" /><div className="skeleton h-40 rounded" /></div>
      ) : check.isError || !check.data ? (
        <EmptyState title="Screening not found" action={<Button size="sm" onClick={onClose}>Close</Button>} />
      ) : (
        <ReviewBody check={check.data} onClose={onClose} />
      )}
    </Drawer>
  );
}

function ReviewBody({ check, onClose }: { check: ComplianceCheck; onClose: () => void }) {
  const { toast } = useToast();
  const muts = useComplianceMutations();
  const [note, setNote] = useState("");
  const [decision, setDecision] = useState<ReviewDecision | null>(null);

  const submit = () => {
    if (!decision) return;
    muts.review.mutate(
      { id: check.id, decision, note: note.trim() || undefined },
      {
        onSuccess: () => {
          toast({ title: `Review recorded: ${enumLabel(decision)}`, description: "Your decision was stored on the check.", tone: decision === "rejected" ? "info" : "success" });
          onClose();
        },
      },
    );
  };

  const triggered = check.findings.filter((f) => f.triggered);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-2">
        <ComplianceChip result={check.result} />
        <RiskChip risk={check.risk_level} />
        <a href={SUBJECT_LINKS[check.subject.kind](check.subject.id)} className="text-xs text-accent-secondary hover:underline">
          {enumLabel(check.subject.kind)} {check.subject.id.slice(0, 8)}…
        </a>
        <span className="text-xs text-text-muted">· screened {timeAgo(check.created_at)} · rules {check.rules_version}</span>
      </div>

      {check.explanation && <p className="text-[13px] text-text-secondary">{check.explanation}</p>}

      <section>
        <p className="micro-label mb-2">Findings — {triggered.length} triggered</p>
        {triggered.length ? (
          <ul className="space-y-2">
            {triggered.map((f) => (
              <li key={f.rule_key} className="rounded-md border border-status-warning/40 bg-status-warning/[0.05] px-3 py-2.5 text-[13px]">
                <div className="flex items-center gap-2">
                  <Badge tone={f.severity === "BLOCK" ? "danger" : f.severity === "WARN" ? "warning" : "muted"}>{f.severity}</Badge>
                  <strong className="font-mono text-xs text-text-primary">{f.rule_key}</strong>
                  <span className="text-[11px] text-text-muted">rules {f.rule_version}</span>
                </div>
                <p className="mt-1 text-text-secondary">{f.explanation}</p>
                {f.matched_excerpt && <p className="mt-1 font-mono text-[11px] text-text-muted">“{f.matched_excerpt}”</p>}
                {f.remediation && <p className="mt-1 text-xs text-text-muted"><strong className="text-text-primary">Fix:</strong> {f.remediation}</p>}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-text-muted">No findings triggered — every rule passed.</p>
        )}
      </section>

      <section className="rounded-lg border border-border p-3.5">
        <p className="micro-label mb-2.5">Your decision (manual human review)</p>
        <div className="flex flex-wrap gap-2">
          {(["accepted", "accepted_with_changes", "rejected"] as ReviewDecision[]).map((d) => (
            <Button key={d} size="sm" variant={decision === d ? "primary" : "outline"} onClick={() => setDecision(d)}>
              {enumLabel(d)}
            </Button>
          ))}
        </div>
        <div className="mt-3">
          <Field label="Note (optional)" hint="Stored with the decision — explain accepted risk or the rejection reason.">
            <Textarea value={note} onChange={(e) => setNote(e.target.value)} rows={3}
              placeholder="Why this decision?…"/>
          </Field>
        </div>
        <Button size="sm" variant="primary" loading={muts.review.isPending} disabled={!decision} onClick={submit} data-testid="compliance-review-submit">
          Record decision
        </Button>
        <p className="mt-2 text-[11px] text-text-muted">The decision gates queue transitions (T18) — only a PASS may leave compliance review toward READY TO UPLOAD.</p>
      </section>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Suspense wrapper — useSearchParams() requires a Suspense boundary during
// prerender (Next.js missing-suspense-with-csr-bailout).
// ---------------------------------------------------------------------------

export default function PageWrapper() {
  return (
    <Suspense fallback={<div className="skeleton h-64 rounded" />}>
      <CompliancePage />
    </Suspense>
  );
}
