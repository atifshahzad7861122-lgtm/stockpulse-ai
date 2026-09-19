"use client";

import { Suspense } from "react";
import { IdeasHub } from "../../features/ideas/IdeasHub";
import { Skeleton } from "../../components/ui";

export default function VideoIdeasPage() {
  return (
    <Suspense fallback={<Skeleton className="h-64" />}>
      <IdeasHub kind="video" />
    </Suspense>
  );
}
