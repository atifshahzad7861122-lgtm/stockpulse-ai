"use client";
/**
 * Prompt Studio (docs/05 screen 10) — generate & optimize prompts.
 */
import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Wand2 } from "lucide-react";
import {
  Button,
  EmptyState,
  PageHeader,
  Panel,
  QueryView,
  Select,
  Skeleton,
  cx,
} from "../../components/ui";
import { FormatBadge, PromptStatusChip, ProvenanceBadge, isMock } from "../../components/scores";
import { GeneratePromptForm, StudioEditor } from "../../features/prompts/StudioEditor";
import { usePrompts } from "../../hooks/useApi";
import type { AssetType } from "../../types";

function PromptStudioPage() {
  const search = useSearchParams();
  const ideaId = search.get("idea");
  const [assetType, setAssetType] = useState<"" | AssetType>("");
  const [selected, setSelected] = useState<string | null>(ideaId ? "__new__" : null);

  const prompts = usePrompts({ idea_id: ideaId ?? undefined, asset_type: assetType || undefined, page_size: 20, sort: "-updated_at" });

  return (
    <div className="space-y-4">
      <PageHeader
        title="Prompt Studio"
        description="Generate, refine, and screen prompts. Prompts never upload to Adobe — copying text into Firefly is your own manual step."
      />

      <div className="grid gap-4 xl:grid-cols-[1fr_1.4fr]">
        <Panel title="Prompts" action={
          <div className="flex gap-2">
            <div className="w-32">
              <Select value={assetType} onChange={(e) => setAssetType(e.target.value as "" | AssetType)} aria-label="Filter prompts by asset type">
                <option value="">All</option>
                <option value="IMAGE">Image</option>
                <option value="VIDEO">Video</option>
              </Select>
            </div>
            <Button size="sm" variant="primary" onClick={() => setSelected("__new__")}>New</Button>
          </div>
        }>
          <QueryView query={prompts} loading={<Skeleton lines={5} />}
            empty={<EmptyState compact title="No prompts yet" description="Generate a prompt from an idea, or pick an idea first." action={<Button size="sm" variant="primary" onClick={() => setSelected("__new__")}>New prompt</Button>} />}
            errorTitle="Prompts unavailable">
            {(page) => (
              <ul className="space-y-2">
                {page.data.map((p) => (
                  <li key={p.id}>
                    <button onClick={() => setSelected(p.id)}
                      className={cx("w-full rounded-md border px-3 py-2.5 text-left transition-colors",
                        selected === p.id ? "border-accent-primary bg-bg-secondary" : "border-border hover:border-text-muted")}>
                      <div className="flex items-center gap-2">
                        <FormatBadge format={p.asset_type} />
                        <span className="min-w-0 flex-1 truncate text-[13px] font-semibold text-text-primary">{p.name}</span>
                        {isMock(p) && <ProvenanceBadge mock />}
                      </div>
                      <p className="mt-1 line-clamp-1 text-xs text-text-muted">{p.current_version.prompt_text}</p>
                      <div className="mt-1.5 flex items-center gap-2 text-[11px] text-text-muted">
                        <PromptStatusChip status={p.status} />
                        <span>v{p.current_version.version_number} of {p.versions_count}</span>
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </QueryView>
        </Panel>

        <div>
          {selected === "__new__" ? (
            <GeneratePromptForm ideaId={ideaId} onGenerated={() => setSelected(null)} />
          ) : selected ? (
            <StudioEditor id={selected} onBack={() => setSelected(null)} embedded />
          ) : (
            <Panel title="Editor">
              <EmptyState icon={<Wand2 size={18} />} title="Select a prompt" description="Choose a prompt from the list, or generate one from an idea." />
            </Panel>
          )}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Suspense wrapper — useSearchParams() requires a Suspense boundary during
// prerender (Next.js missing-suspense-with-csr-bailout).
// ---------------------------------------------------------------------------

export default function PageWrapper() {
  return (
    <Suspense fallback={<div className="skeleton h-64 rounded" />}>
      <PromptStudioPage />
    </Suspense>
  );
}
