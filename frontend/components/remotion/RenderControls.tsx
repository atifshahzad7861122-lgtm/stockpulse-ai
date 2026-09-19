"use client";
/**
 * RenderVideoButton — on-demand Remotion render controls.
 *
 * Renders NEVER start automatically: the user clicks "Render video",
 * the job is POSTed to /api/renders, and this component polls
 * /api/renders/[id] until it reaches ready/failed, then offers the MP4
 * download. One render runs at a time server-side; extra jobs queue.
 */
import { useEffect, useRef, useState } from "react";
import { CheckCircle2, Clapperboard, Download, Loader2, RotateCcw, XCircle } from "lucide-react";
import { Button } from "../ui";
import type { RenderJob, RenderKind } from "../../lib/renders/queue";

export function RenderVideoButton({
  kind,
  label,
  props,
  idleLabel = "Render video",
}: {
  kind: RenderKind;
  label: string;
  /** JSON-serializable composition input props (validated server-side). */
  props: object;
  idleLabel?: string;
}) {
  const [job, setJob] = useState<RenderJob | null>(null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = () => {
    if (timer.current) clearInterval(timer.current);
    timer.current = null;
  };

  useEffect(() => stopPolling, []);

  const poll = (id: string) => {
    stopPolling();
    timer.current = setInterval(async () => {
      try {
        const res = await fetch(`/api/renders/${id}`);
        if (!res.ok) return;
        const data = (await res.json()) as { job: RenderJob };
        setJob(data.job);
        if (data.job.status === "ready" || data.job.status === "failed") stopPolling();
      } catch {
        /* keep polling — transient network blip */
      }
    }, 2500);
  };

  const start = async () => {
    setStarting(true);
    setError(null);
    try {
      const res = await fetch("/api/renders", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ kind, label, props }),
      });
      const data = (await res.json()) as { job?: RenderJob; error?: string };
      if (!res.ok || !data.job) throw new Error(data.error ?? "Could not start the render");
      setJob(data.job);
      poll(data.job.id);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setStarting(false);
    }
  };

  const reset = () => {
    stopPolling();
    setJob(null);
    setError(null);
  };

  if (job && (job.status === "queued" || job.status === "rendering")) {
    return (
      <span
        className="inline-flex items-center gap-1.5 rounded-full border border-border bg-bg-secondary px-2.5 py-1 text-[11px] font-semibold text-text-secondary"
        role="status"
        aria-live="polite"
      >
        <Loader2 size={12} className="animate-spin text-accent-primary" aria-hidden />
        {job.status === "queued" ? "Render queued — starts when the current one finishes" : "Rendering video…"}
      </span>
    );
  }

  if (job?.status === "ready") {
    return (
      <span className="inline-flex flex-wrap items-center gap-2">
        <span className="inline-flex items-center gap-1 rounded-full border border-status-success/40 bg-status-success/10 px-2.5 py-1 text-[11px] font-semibold text-status-success">
          <CheckCircle2 size={12} aria-hidden /> Video ready
        </span>
        <a
          href={`/api/renders/${job.id}/download`}
          className="inline-flex items-center gap-1.5 rounded-lg border border-accent-primary/50 bg-accent-primary/10 px-2.5 py-1 text-[11px] font-semibold text-accent-secondary hover:bg-accent-primary/20"
        >
          <Download size={12} aria-hidden /> Download MP4
        </a>
        <button
          onClick={reset}
          className="inline-flex items-center gap-1 px-1.5 py-1 text-[11px] font-medium text-text-muted hover:text-text-secondary"
          title="Render again"
        >
          <RotateCcw size={11} aria-hidden /> Again
        </button>
      </span>
    );
  }

  return (
    <span className="inline-flex flex-wrap items-center gap-2">
      <Button size="sm" variant="outline" icon={<Clapperboard size={13} />} loading={starting} onClick={start}>
        {idleLabel}
      </Button>
      {(error || job?.status === "failed") && (
        <span className="inline-flex max-w-xs items-center gap-1.5 text-[11px] text-status-danger" role="alert">
          <XCircle size={12} className="shrink-0" aria-hidden />
          <span className="truncate" title={error ?? job?.error}>
            {error ?? job?.error ?? "Render failed"}
          </span>
          <button onClick={reset} className="shrink-0 underline underline-offset-2 hover:text-text-secondary">
            Retry
          </button>
        </span>
      )}
    </span>
  );
}
