/**
 * On-demand Remotion render queue (server-only — imported from API routes).
 *
 * - Renders happen ONLY on explicit user action ("Render preview" /
 *   "Render briefing"). Nothing auto-renders in the background.
 * - One render at a time (single-user local app); extra jobs wait as "queued".
 * - State is a JSON file under remotion/.queue so statuses survive reloads;
 *   MP4s land in remotion/.queue/renders and are served via the download route.
 * - The actual render shells out to the Remotion CLI:
 *     node node_modules/.bin/remotion render remotion/index.tsx <comp> <out> --props '{...}'
 *   which bundles the composition and drives headless Chrome.
 *   Chrome binary: `npm run remotion:browser` (see remotion/REMOTION.md).
 */
import { spawn, type ChildProcess } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";

export type RenderKind = "concept" | "briefing";
export type RenderStatus = "queued" | "rendering" | "ready" | "failed";

export interface RenderJob {
  id: string;
  kind: RenderKind;
  label: string;
  status: RenderStatus;
  createdAt: string;
  updatedAt: string;
  startedAt?: string;
  finishedAt?: string;
  /** File name under remotion/.queue/renders (present when ready). */
  outputFile?: string;
  error?: string;
}

const COMP_ID: Record<RenderKind, string> = {
  concept: "ConceptPreview",
  briefing: "DailyBriefing",
};

const ROOT = resolve(process.cwd(), "remotion");
const QUEUE_DIR = join(ROOT, ".queue");
const JOBS_FILE = join(QUEUE_DIR, "jobs.json");
const RENDER_DIR = join(QUEUE_DIR, "renders");
const MAX_PROPS_BYTES = 512 * 1024;

function readJobs(): RenderJob[] {
  try {
    const raw = readFileSync(JOBS_FILE, "utf8");
    const arr = JSON.parse(raw);
    return Array.isArray(arr) ? (arr as RenderJob[]) : [];
  } catch {
    return [];
  }
}

function writeJobs(jobs: RenderJob[]) {
  mkdirSync(QUEUE_DIR, { recursive: true });
  writeFileSync(JOBS_FILE, JSON.stringify(jobs, null, 2));
}

function persist(job: RenderJob) {
  const jobs = readJobs().map((j) => (j.id === job.id ? job : j));
  writeJobs(jobs);
}

let active: { id: string; child: ChildProcess } | null = null;

function now() {
  return new Date().toISOString();
}

export function listJobs(): RenderJob[] {
  return readJobs().sort((a, b) => (a.createdAt < b.createdAt ? 1 : -1));
}

export function getJob(id: string): RenderJob | null {
  const job = readJobs().find((j) => j.id === id) ?? null;
  if (job && job.status === "rendering" && (!active || active.id !== job.id)) {
    // Server restarted mid-render — say so honestly instead of hanging forever.
    job.status = "failed";
    job.error = "Render did not complete — the server restarted while it was running. Re-queue it to try again.";
    job.finishedAt = now();
    job.updatedAt = now();
    persist(job);
  }
  return job;
}

export function renderFilePath(job: RenderJob): string | null {
  if (job.status !== "ready" || !job.outputFile) return null;
  const p = join(RENDER_DIR, job.outputFile);
  return existsSync(p) ? p : null;
}

function validateProps(props: unknown): Record<string, unknown> {
  if (!props || typeof props !== "object" || Array.isArray(props)) {
    throw new Error("props must be a JSON object");
  }
  const json = JSON.stringify(props);
  if (json.length > MAX_PROPS_BYTES) {
    throw new Error("props too large (max 512KB)");
  }
  return props as Record<string, unknown>;
}

export function enqueueJob(kind: RenderKind, label: string, props: unknown): RenderJob {
  if (kind !== "concept" && kind !== "briefing") throw new Error("unknown render kind");
  const cleanLabel = String(label ?? "").slice(0, 120) || kind;
  const cleanProps = validateProps(props);
  const job: RenderJob = {
    id: `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`,
    kind,
    label: cleanLabel,
    status: "queued",
    createdAt: now(),
    updatedAt: now(),
  };
  const jobs = readJobs();
  jobs.push(job);
  writeJobs(jobs);
  // Stash props next to the job record (not in jobs.json — keeps it small).
  mkdirSync(QUEUE_DIR, { recursive: true });
  writeFileSync(join(QUEUE_DIR, `${job.id}.props.json`), JSON.stringify(cleanProps));
  pump();
  return job;
}

function readProps(id: string): Record<string, unknown> {
  return JSON.parse(readFileSync(join(QUEUE_DIR, `${id}.props.json`), "utf8"));
}

function pump() {
  if (active) return;
  const next = readJobs().find((j) => j.status === "queued");
  if (!next) return;

  next.status = "rendering";
  next.startedAt = now();
  next.updatedAt = now();
  persist(next);

  mkdirSync(RENDER_DIR, { recursive: true });
  const outFile = join(RENDER_DIR, `${next.id}.mp4`);
  const cliBin = resolve(process.cwd(), "node_modules", ".bin", "remotion");
  const entry = join(ROOT, "index.tsx");

  let propsJson: string;
  try {
    propsJson = JSON.stringify(readProps(next.id));
  } catch (e) {
    fail(next, `Could not read render props: ${(e as Error).message}`);
    return;
  }

  const child = spawn(
    process.execPath,
    [
      cliBin,
      "render",
      entry,
      COMP_ID[next.kind],
      outFile,
      "--props",
      propsJson,
      "--overwrite",
      "--concurrency",
      "2",
    ],
    { cwd: process.cwd(), env: process.env },
  );
  active = { id: next.id, child };

  let stderr = "";
  child.stderr?.on("data", (d: Buffer) => {
    stderr = `${stderr}${d.toString()}`.slice(-6000);
  });
  child.on("error", (err) => {
    fail(next, `Could not start the Remotion renderer: ${err.message}. Is a browser installed? Run \`npm run remotion:browser\`.`);
  });
  child.on("exit", (code) => {
    active = null;
    const job = readJobs().find((j) => j.id === next.id);
    if (!job) {
      pump();
      return;
    }
    if (code === 0 && existsSync(outFile)) {
      job.status = "ready";
      job.outputFile = `${next.id}.mp4`;
      job.finishedAt = now();
      job.updatedAt = now();
      persist(job);
    } else {
      fail(job, `Render exited with code ${code ?? "unknown"}.${stderr ? ` ${tail(stderr)}` : ""}`);
    }
    pump();
  });
}

function tail(s: string): string {
  const lines = s.trim().split("\n").filter(Boolean);
  return lines.slice(-6).join(" ").slice(0, 800);
}

function fail(job: RenderJob, error: string) {
  active = null;
  job.status = "failed";
  job.error = error;
  job.finishedAt = now();
  job.updatedAt = now();
  persist(job);
  pump();
}
