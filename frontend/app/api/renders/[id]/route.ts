import { NextResponse } from "next/server";
import { getJob } from "../../../../lib/renders/queue";

/** GET /api/renders/[id] — render job status. */
export async function GET(_req: Request, { params }: { params: { id: string } }) {
  const job = getJob(params.id);
  if (!job) return NextResponse.json({ error: "Render job not found" }, { status: 404 });
  return NextResponse.json({ job });
}
