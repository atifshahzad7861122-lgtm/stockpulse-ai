import { createReadStream, statSync } from "node:fs";
import { Readable } from "node:stream";
import { NextResponse } from "next/server";
import { getJob, renderFilePath } from "../../../../../lib/renders/queue";

/** GET /api/renders/[id]/download — stream the finished MP4. */
export async function GET(_req: Request, { params }: { params: { id: string } }) {
  const job = getJob(params.id);
  const path = job ? renderFilePath(job) : null;
  if (!path || !job) {
    return NextResponse.json({ error: "Render is not ready for download" }, { status: 404 });
  }
  const stat = statSync(path);
  const webStream = Readable.toWeb(createReadStream(path));
  return new NextResponse(webStream as unknown as ReadableStream, {
    headers: {
      "Content-Type": "video/mp4",
      "Content-Length": String(stat.size),
      "Content-Disposition": `attachment; filename="stockpulse-${job.kind}-${job.id}.mp4"`,
      "Cache-Control": "private, max-age=3600",
    },
  });
}
