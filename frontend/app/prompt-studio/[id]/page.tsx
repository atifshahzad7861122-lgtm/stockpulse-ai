"use client";

import { useParams, useRouter } from "next/navigation";
import { PageHeader } from "../../../components/ui";
import { StudioEditor } from "../../../features/prompts/StudioEditor";

export default function PromptDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const router = useRouter();
  return (
    <div className="space-y-4">
      <PageHeader title="Prompt" description="Edit, refine, and screen this prompt." />
      <StudioEditor id={id} onBack={() => router.push("/prompt-studio")} />
    </div>
  );
}
