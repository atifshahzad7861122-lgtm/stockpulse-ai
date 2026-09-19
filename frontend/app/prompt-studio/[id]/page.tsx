"use client";

import { use } from "react";
import { useRouter } from "next/navigation";
import { PageHeader } from "../../../components/ui";
import { StudioEditor } from "../../../features/prompts/StudioEditor";

export default function PromptDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  return (
    <div className="space-y-4">
      <PageHeader title="Prompt" description="Edit, refine, and screen this prompt." />
      <StudioEditor id={id} onBack={() => router.push("/prompt-studio")} />
    </div>
  );
}
