"use client";
/**
 * Similarity Lab (docs/05 screen 12) — originality verification.
 * Point at an existing record (idea, prompt, asset), run the embedding
 * similarity scan against the library + external index, threshold-flagged
 * matches (0.60 review, 0.80 high risk), per-record differentiators.
 */
import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AlertTriangle, CheckCircle2, Play, XCircle } from "lucide-react";
import {
  Button,
  EmptyState,
  Field,
  Input,
  PageHeader,
  Panel,
  QueryView,
  Select,
  Skeleton,
  WhyThis,
  cx,
} from "../../components/ui";
import { ProvenanceBadge, RiskChip, isMock } from "../../components/scores";
import { useToast } from "../../components/toast";
import { useSimilarityCheck, useRunSimilarity } from "../../hooks/useApi";
import { useJobPoll } from "../../hooks/useJobPoll";
import { enumLabel, timeAgo } from "../../lib/format";
import type { RiskLevel, SimilarityCheckResult, SimilarityRecord } from "../../types";

const REVIEW_AT = 0.6;
const HIGH_RISK_AT = 0.8;

type SubjectKind = "image_idea" | "video_idea" | "prompt" | "asset";

function SimilarityPage() {
  const params = useSearchParams();
  const [kind, setKind] = useState<SubjectKind>("image_idea");
  const [subjectId, setSubjectId] = useState(params.get("idea") ?? params.get("subject") ?? "");
  const [checkId, setCheckId] = useState<string | null>(params.get("check"));

  const { toast } = useToast();
  const runSim = useRunSimilarity();
  const [jobId, setJobId] = useState<string | null>(null);
  const poll = useJobPoll(jobId, {
    onDone: (job) => {
      setJobId(null);
      if (job.status === "succeeded") {
        const id = (job.output_summary as { check_id?: string } | null)?.check_id ?? null;
        if (id) {
          setCheckId(id);
          toast({ title: "Similarity scan complete", description: "Matches are shown below.", tone: "success" });
        } else {
          toast({ title: "Scan finished", description: "The check record was not returned inline — ask the backend team to include check_id in the job output.", tone: "warning" });
        }
      } else {
        toast({ title: "Scan failed", description: job.error?.message ?? "Try again.", tone: "warning" });
      }
    },
  });

  const run = () => {
    if (!subjectId.trim()) {
      toast({ title: "Nothing to scan", description: "Enter a record ID first.", tone: "warning" });
      return;
    }
    runSim.mutate(
      { subject_kind: kind, subject_id: subjectId.trim() },
      { onSuccess: (r) => setJobId(r.job_id) },
    );
  };

  const busy = runSim.isPending || poll.isPolling;

  return (
    <div className="space-y-4">
      <PageHeader
        title="Similarity Lab"
        description="Originality verification before production. Matches ≥ 60% need review; ≥ 80% is high risk and blocks the queue until remediated (GATE-05)."
      />

      {/* Input panel */}
      <Panel title="What to check">
        <div className="grid gap-3 md:grid-cols-[180px_1fr_auto] md:items-end">
          <Field label="Record type">
            <Select value={kind} onChange={(e) => setKind(e.target.value as SubjectKind)}>
              <option value="image_idea">Image idea</option>
              <option value="video_idea">Video idea</option>
              <option value="prompt">Prompt</option>
              <option value="asset">Asset</option>
            </Select>
          </Field>
          <Field label="Record ID" hint="The UUID of the idea, prompt, or asset to scan.">
            <Input value={subjectId} onChange={(e) => setSubjectId(e.target.value)} placeholder="e.g. 3f2a1b4c-…" data-testid="similarity-subject-id" />
          </Field>
          <Button variant="primary" icon={<Play size={13} />} loading={busy} onClick={run} data-testid="similarity-run">
            {poll.isPolling ? `Scanning… ${Math.round((poll.job?.progress ?? 0) * 100)}%` : "Run similarity scan"}
          </Button>
        </div>
        <WhyThis label="Why record IDs">
          <p>The contract scans existing records — the backend computes embeddings server-side. To scan a new image, save it as an idea first.</p>
        </WhyThis>
      </Panel>

      {/* Results */}
      <Panel title="Results">
        {!checkId ? (
          <EmptyState title="No scan yet" description="Point at a record above and run the scan. Flagged matches need review before production." />
        ) : (
          <ResultView checkId={checkId} />
        )}
      </Panel>
    </div>
  );
}

function ResultView({ checkId }: { checkId: string }) {
  const check = useSimilarityCheck(checkId);
  return (
    <QueryView
      query={check}
      loading={<Skeleton lines={5} />}
      empty={<EmptyState title="Check not found" description="The scan record could not be loaded." />}
      errorTitle="Scan results unavailable"
    >
      {(c: SimilarityCheckResult) => <ResultBody result={c} />}
    </QueryView>
  );
}

function ResultBody({ result }: { result: SimilarityCheckResult }) {
  const flagged = result.records.filter((r) => r.similarity_score >= REVIEW_AT);
  const high = result.records.filter((r) => r.similarity_score >= HIGH_RISK_AT);
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <RiskChip risk={result.risk_level} />
        <span className="text-xs text-text-muted">
          {enumLabel(result.subject.kind)} {result.subject.id.slice(0, 8)}… · scanned {timeAgo(result.created_at)}
        </span>
        {isMock(result) && <ProvenanceBadge mock />}
      </div>

      <div className={cx(
        "flex items-center gap-2 rounded-lg border px-4 py-3 text-[13px]",
        high.length ? "border-status-danger/40 bg-status-danger/[0.06]" : flagged.length ? "border-status-warning/40 bg-status-warning/[0.06]" : "border-status-success/30 bg-status-success/[0.05]",
      )}>
        {high.length ? <XCircle size={15} className="shrink-0 text-status-danger" aria-hidden />
          : flagged.length ? <AlertTriangle size={15} className="shrink-0 text-status-warning" aria-hidden />
          : <CheckCircle2 size={15} className="shrink-0 text-status-success" aria-hidden />}
        <span className="text-text-secondary">
          {high.length ? (
            <><strong className="text-text-primary">{high.length} high-risk</strong> match{high.length === 1 ? "" : "es"} ≥ 80% — this concept is blocked from queueing until differentiated or an accept-risk decision is recorded (GATE-05).</>
          ) : flagged.length ? (
            <><strong className="text-text-primary">{flagged.length} match{flagged.length === 1 ? "" : "es"}</strong> above the 60% review threshold — review the differentiators below before producing.</>
          ) : (
            <><strong className="text-text-primary">No matches</strong> above the review threshold. This reads as original — keep the evidence anyway.</>
          )}
        </span>
      </div>

      <ThresholdLegend />

      {result.records.length ? (
        <ul className="space-y-2.5">
          {result.records.map((m, i) => <MatchRow key={i} match={m} rank={i + 1} />)}
        </ul>
      ) : (
        <p className="text-xs text-text-muted">The scan returned no comparison records.</p>
      )}
    </div>
  );
}

function ThresholdLegend() {
  return (
    <WhyThis label="How to read thresholds">
      <p>Score ≥ <strong className="text-text-primary">60%</strong> → flagged for review. Score ≥ <strong className="text-text-primary">80%</strong> → high risk; queueing is blocked until the concept is differentiated or an accept-risk decision is recorded (GATE-05).</p>
    </WhyThis>
  );
}

function MatchRow({ match, rank }: { match: SimilarityRecord; rank: number }) {
  const pct = match.similarity_score * 100;
  const high = match.similarity_score >= HIGH_RISK_AT;
  const review = match.similarity_score >= REVIEW_AT;
  const risk: RiskLevel = high ? "HIGH" : review ? "MEDIUM" : "LOW";
  return (
    <li className={cx("rounded-lg border p-3.5",
      high ? "border-status-danger/40 bg-status-danger/[0.05]" : review ? "border-status-warning/40 bg-status-warning/[0.04]" : "border-border bg-bg-secondary")}>
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-md border border-border bg-surface-elevated" aria-hidden>
          <span className="font-display text-lg font-semibold text-text-muted">#{rank}</span>
        </div>
        <div className="min-w-0 flex-1 basis-48">
          <p className="truncate text-[13px] font-semibold text-text-primary">{match.compared_cluster_label}</p>
          <p className="text-[11px] text-text-muted">
            Cluster sample: {match.cluster_sample_count} item{match.cluster_sample_count === 1 ? "" : "s"}
          </p>
          {match.differentiators.length > 0 && (
            <ul className="mt-1.5 space-y-0.5">
              {match.differentiators.map((d, i) => (
                <li key={i} className="flex items-start gap-1.5 text-[11px] text-text-secondary">
                  <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-text-muted" aria-hidden />
                  <span>{d}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="flex items-center gap-2">
          <div className="h-1.5 w-24 overflow-hidden rounded-full bg-border" role="img" aria-label={`Similarity ${Math.round(pct)} percent`}>
            <div className={cx("h-full rounded-full", high ? "bg-status-danger" : review ? "bg-status-warning" : "bg-status-success")} style={{ width: `${Math.min(100, pct)}%` }} />
          </div>
          <span className={cx("w-12 text-right font-display text-sm font-semibold", high ? "text-status-danger" : review ? "text-status-warning" : "text-text-primary")}>
            {Math.round(pct)}%
          </span>
        </div>
        <RiskChip risk={risk} />
      </div>
    </li>
  );
}

// ---------------------------------------------------------------------------
// Suspense wrapper — useSearchParams() requires a Suspense boundary during
// prerender (Next.js missing-suspense-with-csr-bailout).
// ---------------------------------------------------------------------------

export default function PageWrapper() {
  return (
    <Suspense fallback={<div className="skeleton h-64 rounded" />}>
      <SimilarityPage />
    </Suspense>
  );
}
