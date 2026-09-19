import { NextRequest, NextResponse } from "next/server";
import { enqueueJob, listJobs } from "../../../lib/renders/queue";

/** GET /api/renders — list render jobs (newest first). */
export async function GET() {
  return NextResponse.json({ jobs: listJobs() });
}

/**
 * POST /api/renders — enqueue an on-demand render.
 * Body: { kind: "concept" | "briefing", label: string, props: object }
 * Renders only start from this explicit call — never automatically.
 */
export async function POST(req: NextRequest) {
  try {
    const body = (await req.json()) as { kind?: unknown; label?: unknown; props?: unknown };
    const job = enqueueJob(
      body.kind as "concept" | "briefing",
      typeof body.label === "string" ? body.label : "render",
      body.props,
    );
    return NextResponse.json({ job }, { status: 201 });
  } catch (e) {
    return NextResponse.json({ error: (e as Error).message ?? "Invalid request" }, { status: 400 });
  }
}
