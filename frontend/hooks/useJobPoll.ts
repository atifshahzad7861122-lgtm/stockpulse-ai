"use client";
/**
 * Polling hook for CONTRACT §2.7 async jobs: polls GET /agents/jobs/{job_id}
 * until the job reaches a terminal status.
 */
import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, ApiClientError } from "../services/api";
import { qk } from "../services/queryKeys";
import type { AgentJob, JobStatus } from "../types";

const TERMINAL: JobStatus[] = ["succeeded", "failed", "cancelled", "dead_letter"];

export interface JobPollState {
  job: AgentJob | null;
  status: JobStatus | "idle";
  error: ApiClientError | null;
  isPolling: boolean;
}

export function useJobPoll(jobId: string | null, opts?: { intervalMs?: number; onDone?: (job: AgentJob) => void }) {
  const [state, setState] = useState<JobPollState>({ job: null, status: "idle", error: null, isPolling: false });
  const qc = useQueryClient();
  const cbRef = useRef(opts?.onDone);
  cbRef.current = opts?.onDone;
  const intervalMs = opts?.intervalMs ?? 3000;

  useEffect(() => {
    if (!jobId) {
      setState({ job: null, status: "idle", error: null, isPolling: false });
      return;
    }
    let cancelled = false;
    let timer: ReturnType<typeof setInterval> | null = null;
    setState((s) => ({ ...s, status: "queued", isPolling: true, error: null }));

    const poll = async () => {
      try {
        const job = await api.agents.job(jobId);
        if (cancelled) return;
        setState({ job, status: job.status, error: null, isPolling: !TERMINAL.includes(job.status) });
        qc.setQueryData(qk.agents.job(jobId), job);
        if (TERMINAL.includes(job.status)) {
          if (timer) clearInterval(timer);
          cbRef.current?.(job);
        }
      } catch (e) {
        if (cancelled) return;
        const err = e instanceof ApiClientError ? e : new ApiClientError(0, {
          code: "INTERNAL_ERROR", message: "Job poll failed", severity: "error", retryable: true, details: {},
        });
        setState((s) => ({ ...s, error: err, isPolling: false }));
        if (timer) clearInterval(timer);
      }
    };

    poll();
    timer = setInterval(poll, intervalMs);
    return () => {
      cancelled = true;
      if (timer) clearInterval(timer);
    };
  }, [jobId, intervalMs, qc]);

  return state;
}
