"use client";
/**
 * Metadata page (docs/05 screen 15) — submission-ready titles, descriptions,
 * keywords, categories. Bound to an asset (?asset=); CONTRACT exposes
 * MetadataBundle per asset (current + version history), async generation
 * (POST /metadata), and sync validation (POST /metadata/{id}/validate).
 * The technical checklist is tracked in this browser only — the contract
 * stores no checklist state.
 */
import {useEffect, useState, Suspense} from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { CheckCircle2, Copy, ListChecks, Save, Sparkles, XCircle } from "lucide-react";
import {
  Badge,
  Button,
  EmptyState,
  Field,
  Input,
  PageHeader,
  Panel,
  QueryView,
  Select,
  Skeleton,
  Textarea,
  WhyThis,
  cx,
} from "../../components/ui";
import { useToast } from "../../components/toast";
import {
  useAssets,
  useCategories,
  useMetadataBundles,
  useMetadataMutations,
} from "../../hooks/useApi";
import { useJobPoll } from "../../hooks/useJobPoll";
import { enumLabel, timeAgo } from "../../lib/format";
import type { MetadataBundle, MetadataValidation } from "../../types";

const LOCAL_CHECKS = [
  "Meets minimum resolution (image ≥ 4MP / video ≥ HD)",
  "No watermarks or borders",
  "No excessive noise, artifacts, or banding",
  "Model release on file (recognizable people)",
  "Property release on file (private property / brands)",
];

function MetadataPage() {
  const params = useSearchParams();
  const assetId = params.get("asset");
  return (
    <div className="space-y-4">
      <PageHeader
        title="Metadata"
        description="Submission-ready titles, descriptions, and keywords — per asset, versioned, validated."
      />
      {!assetId ? <AssetPicker /> : <MetadataEditor assetId={assetId} />}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Asset picker
// ---------------------------------------------------------------------------

function AssetPicker() {
  const assets = useAssets({ page_size: 50 });
  return (
    <Panel title="Choose an asset">
      <QueryView query={assets} loading={<Skeleton lines={4} />}
        empty={<EmptyState title="No assets yet" description="Metadata is prepared per asset. Generate ideas and produce assets first." action={<Link href="/image-ideas"><Button size="sm">Browse ideas</Button></Link>} />}
        errorTitle="Assets unavailable">
        {(page) => (
          <ul className="divide-y divide-border">
            {page.data.map((a) => (
              <li key={a.id} className="flex items-center gap-3 py-2.5">
                <div className="min-w-0 flex-1">
                  <Link href={`/metadata?asset=${a.id}`} className="block truncate text-[13px] font-semibold text-text-primary hover:text-accent-secondary">
                    {a.title || `Asset · ${a.id.slice(0, 8)}`}
                  </Link>
                  <p className="text-[11px] text-text-muted">{enumLabel(a.asset_type)} · {enumLabel(a.status)} · created {timeAgo(a.created_at)}</p>
                </div>
                <Link href={`/metadata?asset=${a.id}`}><Button size="sm" variant="outline">Edit metadata</Button></Link>
              </li>
            ))}
          </ul>
        )}
      </QueryView>
    </Panel>
  );
}

// ---------------------------------------------------------------------------
// Editor
// ---------------------------------------------------------------------------

function MetadataEditor({ assetId }: { assetId: string }) {
  const { toast } = useToast();
  const bundles = useMetadataBundles({ asset_id: assetId, is_current: true });
  const allBundles = useMetadataBundles({ asset_id: assetId, page_size: 20, sort: "-version_number" });
  const muts = useMetadataMutations();
  const categories = useCategories();

  const current = bundles.data?.data[0];
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [keywords, setKeywords] = useState("");
  const [category, setCategory] = useState("");
  const [initializedFor, setInitializedFor] = useState<string | null>(null);
  const [validation, setValidation] = useState<MetadataValidation | null>(null);

  useEffect(() => {
    if (current && initializedFor !== current.id) {
      setTitle(current.title ?? "");
      setDescription(current.description ?? "");
      setKeywords((current.keywords ?? []).join(", "));
      setCategory(current.adobe_category ?? "");
      setValidation(null);
      setInitializedFor(current.id);
    }
  }, [current, initializedFor]);

  const keywordList = keywords.split(",").map((k) => k.trim()).filter(Boolean);
  const dirty =
    current &&
    (title.trim() !== (current.title ?? "") ||
      description.trim() !== (current.description ?? "") ||
      keywords !== (current.keywords ?? []).join(", ") ||
      category !== (current.adobe_category ?? ""));

  const save = () => {
    if (!current) return;
    muts.update.mutate(
      { id: current.id, body: { title: title.trim(), description: description.trim(), keywords: keywordList, adobe_category: category || undefined } },
    );
  };

  const validate = () => {
    if (!current) return;
    muts.validate.mutate(current.id, { onSuccess: (v) => setValidation(v) });
  };

  const copyAll = async () => {
    const text = `Title: ${title}\n\nDescription: ${description}\n\nKeywords: ${keywordList.join(", ")}\n\nCategory: ${category || "—"}`;
    try {
      await navigator.clipboard.writeText(text);
      toast({ title: "Copied", description: "Paste into the Adobe Stock contributor portal.", tone: "success" });
    } catch {
      toast({ title: "Copy failed", description: "Select the fields manually.", tone: "warning" });
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <Link href="/metadata" className="text-xs text-accent-secondary hover:underline">← Choose a different asset</Link>
        <div className="flex gap-2">
          <Button size="sm" variant="outline" icon={<Copy size={13} />} onClick={copyAll}>Copy all</Button>
          {current && (
            <>
              <Button size="sm" variant="outline" icon={<CheckCircle2 size={13} />} loading={muts.validate.isPending} onClick={validate}>
                Validate
              </Button>
              <Button size="sm" variant="primary" icon={<Save size={13} />} loading={muts.update.isPending} disabled={!dirty} onClick={save} data-testid="metadata-save">
                Save new version
              </Button>
            </>
          )}
        </div>
      </div>

      <QueryView query={bundles} loading={<Skeleton className="h-72" />}
        empty={<GenerateCTA assetId={assetId} />}
        errorTitle="Metadata unavailable">
        {(page) => !page.data.length ? <GenerateCTA assetId={assetId} /> : (
          <div className="grid gap-4 lg:grid-cols-2">
            <Panel title="Submission copy">
              <div className="space-y-3">
                <Field label="Title" hint="Descriptive, ≤ 200 characters. What is literally in the frame.">
                  <Input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} data-testid="metadata-title" />
                  <p className="mt-1 text-right text-[11px] text-text-muted">{title.length}/200</p>
                </Field>
                <Field label="Description" hint="One or two sentences. Adobe uses this for search relevance.">
                  <Textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={4} data-testid="metadata-description" />
                </Field>
                <Field label={`Keywords (${keywordList.length})`} hint="Comma-separated. 25–49 is the healthy range for Adobe Stock.">
                  <Textarea value={keywords} onChange={(e) => setKeywords(e.target.value)} rows={3} placeholder="wellness, lifestyle, morning light, …" data-testid="metadata-keywords" />
                </Field>
                <Field label="Adobe category">
                  <Select value={category} onChange={(e) => setCategory(e.target.value)} data-testid="metadata-category">
                    <option value="">Select a category…</option>
                    {(categories.data ?? []).map((c) => <option key={c.id} value={c.slug}>{c.name}</option>)}
                  </Select>
                </Field>
                <p className="text-[11px] text-text-muted">
                  Editing creates a new version (v{(current?.version_number ?? 0) + 1}) — versions are never overwritten. Current bundle: v{current?.version_number} · {current?.created_by === "agent" ? "agent-drafted" : "you"}
                </p>
              </div>
            </Panel>

            <div className="space-y-4">
              {validation && <ValidationCard validation={validation} />}
              <Panel title="Version history">
                <QueryView query={allBundles} loading={<Skeleton lines={3} />} empty={<EmptyState compact title="No versions" />} errorTitle="Versions unavailable">
                  {(bp) => (
                    <ul className="space-y-1.5">
                      {bp.data.map((b: MetadataBundle) => (
                        <li key={b.id} className="flex items-center gap-2 rounded-md border border-border bg-bg-secondary px-3 py-2 text-xs">
                          <span className="font-display font-semibold text-text-primary">v{b.version_number}</span>
                          {b.is_current && <Badge tone="success">current</Badge>}
                          <span className="min-w-0 flex-1 truncate text-text-secondary">{b.title}</span>
                          <span className="shrink-0 text-text-muted">{b.created_by === "agent" ? "agent" : "you"} · {timeAgo(b.created_at)}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </QueryView>
              </Panel>
              <LocalChecklist assetId={assetId} />
            </div>
          </div>
        )}
      </QueryView>
    </div>
  );
}

function ValidationCard({ validation }: { validation: MetadataValidation }) {
  return (
    <Panel title={validation.valid ? "Validation passed" : "Validation issues"}>
      <ul className="space-y-2">
        {validation.issues.map((i, idx) => (
          <li key={idx} className="flex items-start gap-2 text-[13px]">
            {i.severity === "error" ? <XCircle size={14} className="mt-0.5 shrink-0 text-status-danger" /> :
              i.severity === "warning" ? <XCircle size={14} className="mt-0.5 shrink-0 text-status-warning" /> :
              <CheckCircle2 size={14} className="mt-0.5 shrink-0 text-status-info" />}
            <div>
              <p className="text-text-primary">{i.message}</p>
              <p className="font-mono text-[11px] text-text-muted">{i.code}</p>
            </div>
          </li>
        ))}
        {validation.issues.length === 0 && <li className="text-[13px] text-status-success">No issues found.</li>}
      </ul>
    </Panel>
  );
}

function GenerateCTA({ assetId }: { assetId: string }) {
  const muts = useMetadataMutations();
  const [jobId, setJobId] = useState<string | null>(null);
  const poll = useJobPoll(jobId, { onDone: () => setJobId(null) });
  return (
    <EmptyState
      title="No metadata draft yet"
      description="Generate an agent-drafted bundle for this asset — you edit the result before anything is saved."
      action={
        <Button size="sm" variant="primary" icon={<Sparkles size={13} />}
          loading={muts.generate.isPending || poll.isPolling}
          onClick={() => muts.generate.mutate(assetId, { onSuccess: (r) => setJobId(r.job_id) })}>
          {poll.isPolling ? `Drafting… ${Math.round((poll.job?.progress ?? 0) * 100)}%` : "Generate draft"}
        </Button>
      }
    />
  );
}

/** Local-only checklist — contract stores no checklist state; kept in this browser. */
function LocalChecklist({ assetId }: { assetId: string }) {
  const key = `stockpulse.metadata.checklist.${assetId}`;
  const [checks, setChecks] = useState<Record<string, boolean>>(() => {
    if (typeof window === "undefined") return {};
    try { return JSON.parse(localStorage.getItem(key) ?? "{}"); } catch { return {}; }
  });
  const toggle = (k: string) => setChecks((c) => {
    const next = { ...c, [k]: !c[k] };
    try { localStorage.setItem(key, JSON.stringify(next)); } catch { /* storage unavailable */ }
    return next;
  });
  const done = LOCAL_CHECKS.filter((c) => checks[c]).length;
  return (
    <Panel title={`Technical checklist · ${done}/${LOCAL_CHECKS.length}`}
      action={<span className="flex items-center gap-1 text-[11px] text-text-muted"><ListChecks size={12} /> browser-only</span>}>
      <ul className="space-y-1.5">
        {LOCAL_CHECKS.map((c) => (
          <li key={c}>
            <label className="flex cursor-pointer items-start gap-2.5 rounded-md border border-border bg-bg-secondary px-3 py-2 text-[13px] hover:border-text-muted">
              <input type="checkbox" className="mt-0.5 accent-[#FF5C35]" checked={!!checks[c]} onChange={() => toggle(c)} aria-label={c} />
              <span className={cx(checks[c] ? "text-text-primary" : "text-text-secondary")}>{c}</span>
            </label>
          </li>
        ))}
      </ul>
      <WhyThis label="Why releases matter" >
        <p>Adobe rejects on sight for missing releases on recognizable people or private property. When in doubt, attach the release or choose a different frame.</p>
      </WhyThis>
    </Panel>
  );
}

// ---------------------------------------------------------------------------
// Suspense wrapper — useSearchParams() requires a Suspense boundary during
// prerender (Next.js missing-suspense-with-csr-bailout).
// ---------------------------------------------------------------------------

export default function PageWrapper() {
  return (
    <Suspense fallback={<div className="skeleton h-64 rounded" />}>
      <MetadataPage />
    </Suspense>
  );
}
