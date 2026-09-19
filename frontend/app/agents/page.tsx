"use client";
/**
 * Agents (docs/05 screen 18) — the 13 supervised agents: status grid,
 * per-agent detail, run history, manual triggers, dead letters,
 * run detail with output/errors/logs. (No dedicated logs endpoint in CONTRACT —
 * logs ride on the job payload and are shown instead.)
 */
import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Bot, Play, RotateCcw, Square, Terminal } from "lucide-react";
import {
  Badge,
  Button,
  ConfirmModal,
  Drawer,
  EmptyState,
  Field,
  Modal,
  PageHeader,
  Pagination,
  Panel,
  QueryView,
  Select,
  Skeleton,
  WhyThis,
  cx,
} from "../../components/ui";
import { useToast } from "../../components/toast";
import {
  useAgentJob,
  useAgentJobs,
  useAgents,
  useCancelJob,
  useDeadLetters,
  useRefreshTrends,
  useRetryDeadLetter,
} from "../../hooks/useApi";
import { useJobPoll } from "../../hooks/useJobPoll";
import { enumLabel, fmtDateTime, timeAgo } from "../../lib/format";
import { AGENT_NAMES, type AgentDefinition, type AgentJob, type AgentName, type AgentRunKind, type JobStatus } from "../../types";

function AgentsPage() {
  const router = useRouter();
  const params = useSearchParams();
  const [agentSel, setAgentSel] = useState(params.get("agent") ?? "");
  const [runId, setRunId] = useState<string | null>(params.get("run"));
  const [triggerOpen, setTriggerOpen] = useState(false);
  const [stopId, setStopId] = useState<string | null>(null);
  const cancel = useCancelJob();

  const agents = useAgents();

  const setParam = (k: string, v: string | null) => {
    const p = new URLSearchParams(params.toString());
    if (v) p.set(k, v); else p.delete(k);
    router.replace(`/agents?${p.toString()}`);
  };

  return (
    <div className="space-y-4">
      <PageHeader
        title="Agents"
        description="13 supervised agents run the pipeline. Every run is logged, every output reviewable — nothing acts on its own."
        actions={<Button size="sm" variant="primary" icon={<Play size={13} />} onClick={() => setTriggerOpen(true)}>Start run</Button>}
      />

      <div className="grid gap-4 xl:grid-cols-[1fr_1.5fr]">
        {/* Status grid */}
        <Panel title="Agent status">
          <QueryView query={agents} loading={<div className="grid grid-cols-2 gap-2">{[0,1,2,3,4,5].map((i) => <Skeleton key={i} className="h-16" />)}</div>}
            empty={<EmptyState compact title="No agents registered" description="The backend should expose the 13 canonical agents." />}
            errorTitle="Agent status unavailable">
            {(list) => (
              <div className="grid grid-cols-2 gap-2">
                {AGENT_NAMES.map((name) => {
                  const a = list.find((x) => x.name === name);
                  const active = agentSel === name;
                  return (
                    <button key={name} onClick={() => { setAgentSel(active ? "" : name); setParam("agent", active ? null : name); }}
                      className={cx("rounded-lg border p-2.5 text-left transition-colors",
                        active ? "border-accent-primary bg-bg-secondary" : "border-border hover:border-text-muted")}
                      data-testid={`agent-${name}`}>
                      <div className="flex items-center gap-1.5">
                        <span className={cx("h-1.5 w-1.5 rounded-full", statusDot(a?.status))} aria-hidden />
                        <span className="min-w-0 flex-1 truncate text-xs font-semibold text-text-primary">{pretty(name)}</span>
                      </div>
                      <p className="mt-1 truncate text-[10px] text-text-muted">
                        {a?.last_run_at ? `last run ${timeAgo(a.last_run_at)}` : "never run"}
                      </p>
                    </button>
                  );
                })}
              </div>
            )}
          </QueryView>
        </Panel>

        {/* Detail or run history */}
        <div>
          {agentSel ? (
            <AgentDetail name={agentSel} onOpenRun={(id) => { setRunId(id); setParam("run", id); }} onTrigger={() => setTriggerOpen(true)} />
          ) : (
            <RunHistory agent="" onOpenRun={(id) => { setRunId(id); setParam("run", id); }} onStop={setStopId} />
          )}
        </div>
      </div>

      <DeadLetterPanel />

      <TriggerModal open={triggerOpen} onClose={() => setTriggerOpen(false)} presetAgent={agentSel || undefined} />
      <RunDrawer id={runId} onClose={() => { setRunId(null); setParam("run", null); }} />
      <ConfirmModal
        open={stopId !== null}
        onClose={() => setStopId(null)}
        title="Stop this run?"
        description="The job is cancelled; partial output, if any, stays on the job record."
        confirmLabel="Stop run"
        onConfirm={() => stopId && cancel.mutate(stopId, { onSuccess: () => setStopId(null) })}
      />
    </div>
  );
}

function statusDot(status?: string) {
  switch (status) {
    case "COMPLETED": return "bg-status-success";
    case "RUNNING": return "bg-status-warning animate-pulse";
    case "FAILED": return "bg-status-danger";
    case "CANCELLED": return "bg-text-muted";
    default: return "bg-text-muted";
  }
}

function pretty(name: string) {
  return name.toLowerCase().replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

// ---------------------------------------------------------------------------
// Agent detail
// ---------------------------------------------------------------------------

function AgentDetail({ name, onOpenRun, onTrigger }: { name: string; onOpenRun: (id: string) => void; onTrigger: () => void }) {
  const agents = useAgents();
  return (
    <Panel title={pretty(name)} action={<Button size="sm" variant="primary" icon={<Play size={13} />} onClick={onTrigger}>Start run</Button>}>
      <QueryView query={agents} loading={<Skeleton className="h-40" />} empty={<EmptyState compact title="Agent not found" />} errorTitle="Agent detail unavailable">
        {(list) => {
          const a: AgentDefinition | undefined = list.find((x) => x.name === name);
          if (!a) return <EmptyState compact title="Agent not registered" description="The backend did not list this agent." />;
          return (
            <div className="space-y-4">
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <Badge tone={a.status === "COMPLETED" ? "success" : a.status === "FAILED" ? "danger" : a.status === "RUNNING" ? "warning" : "muted"}>
                  {a.status ? enumLabel(a.status) : "unknown"}
                </Badge>
                <Badge tone={a.enabled ? "success" : "muted"}>{a.enabled ? "enabled" : "disabled"}</Badge>
                {a.confidence !== undefined && a.confidence !== null && (
                  <span className="text-text-muted">confidence {Math.round(a.confidence * 100)}%</span>
                )}
                {a.last_run_at && <span className="text-text-muted">last run {timeAgo(a.last_run_at)}</span>}
              </div>
              {a.display_name && <p className="text-[13px] font-semibold text-text-primary">{a.display_name}</p>}
              {a.description && <p className="text-[13px] text-text-secondary">{a.description}</p>}
              {a.capabilities && a.capabilities.length > 0 && (
                <div className="rounded-lg border border-border bg-bg-secondary p-3">
                  <p className="micro-label mb-2">Capabilities</p>
                  <ul className="list-disc space-y-0.5 pl-4 text-xs text-text-secondary">
                    {a.capabilities.map((c) => <li key={c}>{c}</li>)}
                  </ul>
                </div>
              )}
              <RunHistory agent={name} onOpenRun={onOpenRun} onStop={() => {}} compact />
            </div>
          );
        }}
      </QueryView>
    </Panel>
  );
}

// ---------------------------------------------------------------------------
// Run history
// ---------------------------------------------------------------------------

function RunHistory({ agent, onOpenRun, onStop, compact }: { agent: string; onOpenRun: (id: string) => void; onStop: (id: string) => void; compact?: boolean }) {
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("");
  const jobs = useAgentJobs({ agent: agent || undefined, status: status || undefined, page, page_size: compact ? 5 : 12, sort: "-created_at" });

  return (
    <Panel title={agent ? `Runs — ${pretty(agent)}` : "Run history"}
      action={!compact ? (
        <div className="w-32">
          <Select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }} aria-label="Filter by job status">
            <option value="">All statuses</option>
            {(["queued", "running", "succeeded", "failed", "cancelled", "dead_letter"] as JobStatus[]).map((s) => (
              <option key={s} value={s}>{enumLabel(s)}</option>
            ))}
          </Select>
        </div>
      ) : undefined}>
      <QueryView query={jobs} loading={<Skeleton lines={4} />}
        empty={<EmptyState compact icon={<Bot size={18} />} title="No runs yet" description="Start a run to see it here." />}
        errorTitle="Run history unavailable">
        {(p) => (
          <>
            <ul className="space-y-2">
              {p.data.map((j) => (
                <li key={j.job_id} className="flex items-center gap-2.5 rounded-md border border-border bg-bg-secondary px-3 py-2">
                  <JobBadge status={j.status} />
                  <button onClick={() => onOpenRun(j.job_id)} className="min-w-0 flex-1 text-left">
                    <span className="block truncate text-[13px] font-medium text-text-primary hover:text-accent-secondary">
                      {pretty(j.agent)} · {enumLabel(j.run_kind)}
                    </span>
                    <span className="text-[11px] text-text-muted">{fmtDateTime(j.created_at)}{duration(j) ? ` · ${duration(j)}` : ""}</span>
                  </button>
                  {(j.status === "queued" || j.status === "running") && (
                    <Button size="sm" variant="ghost" icon={<Square size={12} />} onClick={() => onStop(j.job_id)} aria-label="Stop run">Stop</Button>
                  )}
                </li>
              ))}
            </ul>
            {!compact && <Pagination page={page} totalPages={p.pagination.total_pages} onChange={setPage} />}
          </>
        )}
      </QueryView>
    </Panel>
  );
}

function duration(j: AgentJob) {
  if (!j.started_at || !j.finished_at) return null;
  const s = (new Date(j.finished_at).getTime() - new Date(j.started_at).getTime()) / 1000;
  return s < 60 ? `${s.toFixed(1)}s` : `${Math.round(s / 60)}m`;
}

function JobBadge({ status }: { status: JobStatus }) {
  return (
    <Badge tone={status === "succeeded" ? "success" : status === "failed" || status === "dead_letter" ? "danger" : status === "running" ? "warning" : "muted"}>
      {enumLabel(status)}
    </Badge>
  );
}

// ---------------------------------------------------------------------------
// Dead letters
// ---------------------------------------------------------------------------

function DeadLetterPanel() {
  const dl = useDeadLetters();
  const retry = useRetryDeadLetter();
  return (
    <Panel title="Dead letters" action={<span className="text-[11px] text-text-muted">Jobs that failed beyond retry</span>}>
      <QueryView query={dl} loading={<Skeleton lines={3} />}
        empty={<EmptyState compact title="No dead letters" description="Failed jobs that exhaust retries land here for manual requeue." />}
        errorTitle="Dead letters unavailable">
        {(list) => list.length ? (
          <ul className="space-y-2">
            {list.map((j) => (
              <li key={j.job_id} className="flex items-center gap-3 rounded-md border border-status-danger/30 bg-status-danger/[0.04] px-3 py-2.5 text-[13px]">
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-text-primary">{pretty(j.agent)} · {enumLabel(j.run_kind)}</span>
                  <span className="text-[11px] text-text-muted">{j.error ? `${j.error.code}: ${j.error.message}` : "no error recorded"}</span>
                </span>
                <Button size="sm" variant="outline" icon={<RotateCcw size={12} />} loading={retry.isPending} onClick={() => retry.mutate(j.job_id)}>
                  Requeue
                </Button>
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState compact title="No dead letters" description="Failed jobs that exhaust retries land here for manual requeue." />
        )}
      </QueryView>
    </Panel>
  );
}

// ---------------------------------------------------------------------------
// Manual trigger — maps run kinds to the contract's real triggers
// ---------------------------------------------------------------------------

const REFRESH_KINDS: AgentRunKind[] = ["TREND_INGEST", "MARKET_ANALYSIS", "OPPORTUNITY_SCAN", "BRIEFING_BUILD"];
const SUBJECT_KINDS: { kind: AgentRunKind; label: string; href: string; hint: string }[] = [
  { kind: "IDEA_GENERATION", label: "Idea generation", href: "/image-ideas", hint: "Runs from an idea — open the Ideas pages." },
  { kind: "PROMPT_GENERATION", label: "Prompt generation", href: "/prompt-studio", hint: "Runs from an idea — open Prompt Studio." },
  { kind: "COMPLIANCE_SCREEN", label: "Compliance screen", href: "/compliance", hint: "Runs on a subject — open the Compliance Center." },
  { kind: "METADATA_DRAFT", label: "Metadata draft", href: "/metadata", hint: "Runs on an asset — open the Metadata page." },
  { kind: "PERFORMANCE_DIGEST", label: "Performance digest", href: "/analytics", hint: "Runs over analytics — open Analytics." },
];

function TriggerModal({ open, onClose, presetAgent }: { open: boolean; onClose: () => void; presetAgent?: string }) {
  const { toast } = useToast();
  const refresh = useRefreshTrends();
  const [agent, setAgent] = useState<AgentName>((presetAgent as AgentName) ?? AGENT_NAMES[0]);
  const [kind, setKind] = useState<AgentRunKind>("TREND_INGEST");
  const [jobId, setJobId] = useState<string | null>(null);

  const poll = useJobPoll(jobId, {
    onDone: (job) => {
      setJobId(null);
      if (job.status === "succeeded") toast({ title: "Run complete", description: `${pretty(job.agent)} finished.`, tone: "success" });
      else toast({ title: "Run ended", description: `Status: ${job.status}. ${job.error?.message ?? ""}`, tone: "warning" });
      onClose();
    },
  });

  const subject = SUBJECT_KINDS.find((s) => s.kind === kind);
  const canStart = REFRESH_KINDS.includes(kind);

  const start = () => {
    if (!canStart) return;
    refresh.mutate(undefined, { onSuccess: (r) => setJobId(r.job_id) });
  };

  return (
    <Modal open={open} onClose={onClose} title="Start agent run"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          {canStart ? (
            <Button variant="primary" icon={<Play size={13} />} loading={refresh.isPending || poll.isPolling} disabled={poll.isPolling} onClick={start} data-testid="agent-trigger-start">
              {poll.isPolling ? `Running… ${Math.round((poll.job?.progress ?? 0) * 100)}%` : "Start"}
            </Button>
          ) : (
            <Button variant="primary" onClick={() => { onClose(); window.location.href = subject!.href; }}>
              Open {subject?.label.toLowerCase()}
            </Button>
          )}
        </>
      }>
      <div className="space-y-3">
        <Field label="Agent">
          <Select value={agent} onChange={(e) => setAgent(e.target.value as AgentName)}>
            {AGENT_NAMES.map((n) => <option key={n} value={n}>{pretty(n)}</option>)}
          </Select>
        </Field>
        <Field label="Run kind">
          <Select value={kind} onChange={(e) => setKind(e.target.value as AgentRunKind)}>
            {[...REFRESH_KINDS, ...SUBJECT_KINDS.map((s) => s.kind)].map((k) => (
              <option key={k} value={k}>{k.replace(/_/g, " ")}</option>
            ))}
          </Select>
        </Field>
        {canStart ? (
          <WhyThis label="What this does">
            <p>This triggers <strong className="text-text-primary">POST /trends/refresh</strong> — the contract’s documented trigger for trend ingestion, market analysis, and briefing builds. Runs are supervised and pollable; stopping keeps partial output.</p>
          </WhyThis>
        ) : (
          <div className="rounded-md border border-border bg-bg-secondary p-3 text-[13px] text-text-secondary">
            <p className="font-semibold text-text-primary">Needs a subject</p>
            <p className="mt-1">{subject?.hint}</p>
            <p className="mt-1 text-[11px] text-text-muted">The contract has no generic “start run” endpoint — subject-bound runs start from their owning page.</p>
          </div>
        )}
      </div>
    </Modal>
  );
}

// ---------------------------------------------------------------------------
// Run detail drawer — output, errors, logs from the job payload
// ---------------------------------------------------------------------------

function RunDrawer({ id, onClose }: { id: string | null; onClose: () => void }) {
  const job = useAgentJob(id);
  return (
    <Drawer open={!!id} onClose={onClose} title="Agent run" wide>
      {!id ? null : job.isLoading ? (
        <div className="space-y-3"><div className="skeleton h-8 rounded" /><div className="skeleton h-40 rounded" /></div>
      ) : job.isError || !job.data ? (
        <EmptyState title="Run not found" action={<Button size="sm" onClick={onClose}>Close</Button>} />
      ) : (
        <RunDetail job={job.data} onClose={onClose} />
      )}
    </Drawer>
  );
}

function RunDetail({ job, onClose }: { job: AgentJob; onClose: () => void }) {
  const { toast } = useToast();
  const cancel = useCancelJob();
  const [tab, setTab] = useState<"output" | "logs">("output");
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <JobBadge status={job.status} />
        <span className="text-[13px] font-semibold text-text-primary">{pretty(job.agent)}</span>
        <span className="text-xs text-text-muted">{enumLabel(job.run_kind)} · started {fmtDateTime(job.created_at)}</span>
        {(job.status === "queued" || job.status === "running") && (
          <Button size="sm" variant="outline" icon={<Square size={12} />} loading={cancel.isPending}
            onClick={() => cancel.mutate(job.job_id, { onSuccess: () => { toast({ title: "Run cancelled", tone: "info" }); onClose(); } })}>
            Stop
          </Button>
        )}
      </div>

      {job.status === "running" && (
        <div>
          <div className="flex justify-between text-xs text-text-muted"><span>Progress</span><span>{Math.round((job.progress ?? 0) * 100)}%</span></div>
          <div className="mt-1 h-2 overflow-hidden rounded-full bg-border">
            <div className="h-full rounded-full bg-accent-primary transition-all" style={{ width: `${Math.round((job.progress ?? 0) * 100)}%` }} />
          </div>
        </div>
      )}

      {job.error && (
        <div className="rounded-lg border border-status-danger/40 bg-status-danger/[0.06] p-3.5">
          <p className="text-[13px] font-semibold text-status-danger">Error</p>
          <p className="mt-1 font-mono text-xs text-text-secondary">{job.error.code}: {job.error.message}</p>
        </div>
      )}

      <div className="flex rounded-md border border-border p-0.5" role="tablist" aria-label="Run detail">
        {(["output", "logs"] as const).map((t) => (
          <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)}
            className={cx("rounded px-2.5 py-1 text-xs capitalize", tab === t ? "bg-surface-elevated text-text-primary" : "text-text-muted hover:text-text-primary")}>
            {t}{t === "logs" && job.logs ? ` (${job.logs.length})` : ""}
          </button>
        ))}
      </div>

      {tab === "output" ? (
        <section>
          <p className="micro-label mb-2 flex items-center gap-1.5"><Terminal size={12} aria-hidden /> Output summary</p>
          {job.output_summary ? (
            <pre className="max-h-96 overflow-auto rounded-lg border border-border bg-bg-secondary p-3 font-mono text-[11.5px] leading-relaxed text-text-secondary">
              {JSON.stringify(job.output_summary, null, 2)}
            </pre>
          ) : (
            <p className="text-xs text-text-muted">
              No output yet{job.status === "running" || job.status === "queued" ? " — the run is still going." : "."}
            </p>
          )}
          {Object.keys(job.input_summary ?? {}).length > 0 && (
            <details className="mt-3">
              <summary className="cursor-pointer text-xs text-text-muted hover:text-text-primary">Input summary</summary>
              <pre className="mt-2 max-h-48 overflow-auto rounded-lg border border-border bg-bg-secondary p-3 font-mono text-[11.5px] text-text-secondary">
                {JSON.stringify(job.input_summary, null, 2)}
              </pre>
            </details>
          )}
        </section>
      ) : (
        <section>
          <p className="micro-label mb-2">Logs</p>
          {(job.logs ?? []).length ? (
            <ul className="max-h-96 space-y-1 overflow-auto rounded-lg border border-border bg-bg-secondary p-3 font-mono text-[11.5px]">
              {(job.logs ?? []).map((l) => (
                <li key={l.id} className="flex gap-2">
                  <span className={cx("shrink-0", l.level === "ERROR" ? "text-status-danger" : l.level === "WARNING" ? "text-status-warning" : "text-text-muted")}>
                    {l.level}
                  </span>
                  <span className="min-w-0 flex-1 text-text-secondary">{l.message}</span>
                  <span className="shrink-0 text-text-muted">{timeAgo(l.timestamp)}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-text-muted">No logs attached to this run — the contract exposes no separate logs endpoint, so output and errors above are the full record.</p>
          )}
        </section>
      )}

      <p className="text-[11px] text-text-muted">Instructions version: {job.instructions_version}{job.run_id ? ` · run ${job.run_id.slice(0, 8)}…` : ""}</p>
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
      <AgentsPage />
    </Suspense>
  );
}
