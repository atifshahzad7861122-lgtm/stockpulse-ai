"use client";
/**
 * Prompt Studio editor — shared by /prompt-studio and /prompt-studio/[id].
 * Builder tabs (templates, keywords), SEO drafts, version history,
 * compliance checklist (GATE-06), copy-to-Firefly.
 *
 * Contract notes: prompt text lives in current_version; editing text creates a
 * new version (saveVersion). Name/status are edited via PATCH (update).
 * Generation is an async PROMPT_GENERATION job — never synchronous.
 */
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, CheckCircle2, Copy, ExternalLink, History, Save, ShieldCheck, Sparkles, Wand2, XCircle } from "lucide-react";
import {
  Badge,
  Button,
  EmptyState,
  Field,
  Input,
  Panel,
  QueryView,
  Select,
  Skeleton,
  Tabs,
  Textarea,
  WhyThis,
} from "../../components/ui";
import { ComplianceChip, FormatBadge, PromptStatusChip, ProvenanceBadge, RiskChip } from "../../components/scores";
import { useToast } from "../../components/toast";
import {
  useComplianceCheck,
  useComplianceMutations,
  usePrompt,
  usePromptMutations,
  usePromptVersions,
} from "../../hooks/useApi";
import { useJobPoll } from "../../hooks/useJobPoll";
import { timeAgo } from "../../lib/format";
import type { AssetType, ComplianceCheck, Prompt, PromptStatus } from "../../types";

export const MODELS = [
  { value: "adobe_firefly", label: "Adobe Firefly" },
  { value: "custom", label: "Custom / other" },
] as const;

// ---------------------------------------------------------------------------
// Generate prompt (async PROMPT_GENERATION job) — replaces direct "create"
// ---------------------------------------------------------------------------

export function GeneratePromptForm({ ideaId, onGenerated }: { ideaId: string | null; onGenerated: () => void }) {
  const { toast } = useToast();
  const qc = useQueryClient();
  const muts = usePromptMutations();
  const [assetType, setAssetType] = useState<AssetType>("IMAGE");
  const [tool, setTool] = useState("adobe_firefly");
  const [jobId, setJobId] = useState<string | null>(null);

  const poll = useJobPoll(jobId, {
    onDone: (job) => {
      setJobId(null);
      if (job.status === "succeeded") {
        qc.invalidateQueries({ queryKey: ["prompts"] });
        toast({ title: "Prompt generated", description: "It appears in the list — review and edit before producing.", tone: "success" });
        onGenerated();
      } else {
        toast({ title: "Prompt generation failed", description: job.error?.message ?? "Try again later.", tone: "warning" });
      }
    },
  });

  if (!ideaId) {
    return (
      <Panel title="Generate prompt">
        <EmptyState compact title="Pick an idea first" description="Prompts are generated from ideas — open an idea and send it to Prompt Studio, or pick one from the Ideas pages." />
      </Panel>
    );
  }

  return (
    <Panel title="Generate prompt">
      <div className="space-y-3">
        <p className="text-xs text-text-muted">
          Linked to idea <strong className="text-text-primary">{ideaId.slice(0, 8)}…</strong>. Generation runs on the backend as an async job —
          the prompt text is generated, so review and edit it before producing.
        </p>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Asset type">
            <Select value={assetType} onChange={(e) => setAssetType(e.target.value as AssetType)}>
              <option value="IMAGE">Image</option>
              <option value="VIDEO">Video</option>
            </Select>
          </Field>
          <Field label="Target tool">
            <Select value={tool} onChange={(e) => setTool(e.target.value)}>
              {MODELS.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
            </Select>
          </Field>
        </div>
        <Button variant="primary" icon={<Wand2 size={13} />} loading={muts.generate.isPending || poll.isPolling}
          onClick={() => muts.generate.mutate({ idea_id: ideaId, asset_type: assetType, tool }, { onSuccess: (r) => setJobId(r.job_id) })}
          data-testid="prompt-generate">
          {poll.isPolling ? `Generating… ${Math.round((poll.job?.progress ?? 0) * 100)}%` : "Generate prompt"}
        </Button>
        <WhyThis label="Why async">
          <p>Prompt generation runs through the PROMPT_GENERATION job channel; this screen polls the job. Nothing is auto-approved.</p>
        </WhyThis>
      </div>
    </Panel>
  );
}

// ---------------------------------------------------------------------------
// Studio editor
// ---------------------------------------------------------------------------

export function StudioEditor({ id, onBack, embedded }: { id: string; onBack: () => void; embedded?: boolean }) {
  const { toast } = useToast();
  const prompt = usePrompt(id);
  const muts = usePromptMutations();
  const comp = useComplianceMutations();

  const [tab, setTab] = useState<"build" | "seo" | "versions" | "screen">("build");
  const [text, setText] = useState<string | null>(null);
  const [changeSummary, setChangeSummary] = useState("");
  const [negative, setNegative] = useState("");
  const [alternative, setAlternative] = useState("");
  const [technicalNotes, setTechnicalNotes] = useState("");
  const [name, setName] = useState<string | null>(null);
  const [status, setStatus] = useState<PromptStatus | null>(null);
  const [textDirty, setTextDirty] = useState(false);
  const [metaDirty, setMetaDirty] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [regenJob, setRegenJob] = useState<string | null>(null);
  const [screenJob, setScreenJob] = useState<string | null>(null);
  const [screenCheckId, setScreenCheckId] = useState<string | null>(null);

  const pollRegen = useJobPoll(regenJob, {
    onDone: (job) => {
      setRegenJob(null);
      if (job.status === "succeeded") {
        toast({ title: "Regeneration complete", description: "A new version was saved — review it below.", tone: "success" });
        setText(null); setTextDirty(false); setMetaDirty(false); setFeedback("");
      } else toast({ title: "Regeneration failed", description: job.error?.message ?? "Try again.", tone: "warning" });
    },
  });
  const pollScreen = useJobPoll(screenJob, {
    onDone: (job) => {
      setScreenJob(null);
      const checkId = (job.output_summary as { check_id?: string } | null)?.check_id;
      if (job.status === "succeeded" && checkId) {
        setScreenCheckId(checkId);
        toast({ title: "Screening complete", description: "Review the findings below.", tone: "success" });
      } else if (job.status === "succeeded") {
        toast({ title: "Screening finished", description: "The check record was not returned inline — see the Compliance Center.", tone: "warning" });
      } else toast({ title: "Screening failed", description: job.error?.message ?? "Try again.", tone: "warning" });
    },
  });

  const p = prompt.data;
  const current = text ?? p?.current_version.prompt_text ?? "";

  const saveVersion = () => {
    if (!p || !changeSummary.trim()) return;
    muts.saveVersion.mutate(
      {
        id,
        body: {
          prompt_text: current,
          change_summary: changeSummary.trim(),
          negative_prompt_text: negative.trim() || undefined,
          alternative_prompt_text: alternative.trim() || undefined,
          technical_notes: technicalNotes.trim() || undefined,
        },
      },
      { onSuccess: () => { setText(null); setTextDirty(false); setChangeSummary(""); } },
    );
  };

  const saveMeta = () => {
    if (!p) return;
    muts.update.mutate(
      { id, body: { name: name ?? p.name, status: status ?? p.status } },
      { onSuccess: () => setMetaDirty(false) },
    );
  };

  const runScreening = () => {
    comp.runCheck.mutate(
      { check_type: "PROMPT_SCREEN", subject_kind: "prompt", subject_id: id },
      {
        onSuccess: (r) => {
          if ("job_id" in r) setScreenJob(r.job_id);
          else {
            setScreenCheckId(r.id);
            toast({ title: "Screening complete", description: `Result: ${r.result}`, tone: r.result === "PASS" ? "success" : "warning" });
          }
        },
      },
    );
  };

  const copyFirefly = async () => {
    try {
      await navigator.clipboard.writeText(current);
      toast({ title: "Copied", description: "Paste it into Adobe Firefly yourself — StockPulse never uploads anything.", tone: "success" });
    } catch {
      toast({ title: "Copy failed", description: "Select the text manually and copy it.", tone: "warning" });
    }
  };

  return (
    <Panel
      title={
        <div className="flex items-center gap-2">
          {!embedded && <Button size="sm" variant="ghost" icon={<ArrowLeft size={13} />} onClick={onBack}>All</Button>}
          <span className="truncate">{p?.name ?? "Prompt"}</span>
          {p && <FormatBadge format={p.asset_type} />}
          {p && <PromptStatusChip status={p.status} />}
          {(textDirty || metaDirty) && <Badge tone="warning">Unsaved</Badge>}
        </div>
      }
      action={p ? (
        <div className="flex gap-2">
          <Button size="sm" variant="outline" icon={<Copy size={13} />} onClick={copyFirefly}>Copy to Firefly</Button>
          <Button size="sm" variant="primary" icon={<Save size={13} />} loading={muts.saveVersion.isPending || muts.update.isPending}
            disabled={!(textDirty || metaDirty) || (textDirty && !changeSummary.trim())}
            title={textDirty && !changeSummary.trim() ? "A change summary is required for a new version" : undefined}
            onClick={() => { if (textDirty) saveVersion(); if (metaDirty) saveMeta(); }}>
            {textDirty ? "Save as new version" : "Save"}
          </Button>
        </div>
      ) : undefined}
    >
      <QueryView query={prompt} loading={<Skeleton className="h-64" />} empty={<EmptyState title="Prompt not found" action={<Button size="sm" onClick={onBack}>Back</Button>} />} errorTitle="Prompt unavailable">
        {(pp) => (
          <div className="space-y-4">
            <Tabs
              tabs={[
                { value: "build", label: "Build" },
                { value: "seo", label: "SEO & metadata" },
                { value: "versions", label: `Versions (${pp.versions_count})` },
                { value: "screen", label: "Screening" },
              ]}
              value={tab}
              onChange={(v) => setTab(v as typeof tab)}
            />

            {tab === "build" && (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-3">
                  <Field label="Name">
                    <Input value={name ?? pp.name} onChange={(e) => { setName(e.target.value); setMetaDirty(true); }} />
                  </Field>
                  <Field label="Status">
                    <Select value={status ?? pp.status} onChange={(e) => { setStatus(e.target.value as PromptStatus); setMetaDirty(true); }}>
                      {(["DRAFT", "READY", "APPROVED", "ARCHIVED"] as PromptStatus[]).map((s) => (
                        <option key={s} value={s}>{s}</option>
                      ))}
                    </Select>
                  </Field>
                </div>
                <Field label="Prompt text" hint="Editing the text saves a NEW version — the current version is never overwritten.">
                  <Textarea value={text ?? pp.current_version.prompt_text} onChange={(e) => { setText(e.target.value); setTextDirty(true); }} rows={8} data-testid="prompt-editor" />
                </Field>
                <div className="grid gap-3 md:grid-cols-2">
                  <Field label="Negative prompt (optional)"><Textarea value={negative} onChange={(e) => { setNegative(e.target.value); setTextDirty(true); }} rows={2} /></Field>
                  <Field label="Alternative prompt (optional)"><Textarea value={alternative} onChange={(e) => { setAlternative(e.target.value); setTextDirty(true); }} rows={2} /></Field>
                </div>
                <Field label="Technical notes (optional)"><Textarea value={technicalNotes} onChange={(e) => { setTechnicalNotes(e.target.value); setTextDirty(true); }} rows={2} /></Field>
                <Field label="Change summary" required hint="Required — every new version records what changed.">
                  <Input value={changeSummary} onChange={(e) => { setChangeSummary(e.target.value); }} placeholder="e.g. Tightened lighting description, added negative prompt" />
                </Field>
                <TemplatePicker kind={pp.asset_type === "VIDEO" ? "video" : "image"} onInsert={(tpl) => { setText((t) => `${t ?? pp.current_version.prompt_text}\n${tpl}`); setTextDirty(true); }} />
                <KeywordExplorer />
                <div className="flex flex-wrap gap-2">
                <div className="min-w-64 flex-1">
                  <Field label="Regeneration feedback">
                    <Input value={feedback} onChange={(e) => setFeedback(e.target.value)} placeholder="What should the regeneration change?" />
                  </Field>
                </div>
                  <Button size="sm" variant="outline" icon={<Sparkles size={13} />} loading={pollRegen.isPolling || muts.regenerate.isPending}
                    disabled={!feedback.trim()}
                    onClick={() => muts.regenerate.mutate({ id, feedback: feedback.trim() }, { onSuccess: (r) => setRegenJob(r.job_id) })}>
                    {pollRegen.isPolling ? `Regenerating… ${Math.round((pollRegen.job?.progress ?? 0) * 100)}%` : "Regenerate with AI"}
                  </Button>
                  <Button size="sm" variant="ghost" icon={<ExternalLink size={13} />} onClick={copyFirefly}>
                    Copy & open Firefly manually
                  </Button>
                </div>
              </div>
            )}

            {tab === "seo" && <SeoPanel promptText={current} />}

            {tab === "versions" && <VersionsPanel prompt={pp} onLoad={(v) => { setText(v.prompt_text); setTextDirty(true); setTab("build"); }} />}

            {tab === "screen" && (
              <ScreeningPanel
                promptId={id}
                checkId={screenCheckId}
                jobRunning={pollScreen.isPolling}
                onRun={runScreening}
                runPending={comp.runCheck.isPending}
              />
            )}
          </div>
        )}
      </QueryView>
    </Panel>
  );
}

function Checklist({ items }: { items: { label: string; pass: boolean }[] }) {
  return (
    <ul className="space-y-1.5">
      {items.map((i) => (
        <li key={i.label} className="flex items-center gap-2 text-[13px] text-text-secondary">
          {i.pass ? <CheckCircle2 size={14} className="text-status-success" aria-hidden /> : <XCircle size={14} className="text-status-danger" aria-hidden />}
          {i.label}
        </li>
      ))}
    </ul>
  );
}

// ---------------------------------------------------------------------------
// Versions
// ---------------------------------------------------------------------------

function VersionsPanel({ prompt, onLoad }: { prompt: Prompt; onLoad: (v: { prompt_text: string }) => void }) {
  const q = usePromptVersions(prompt.id);
  const versions = { data: q.data, isLoading: q.isLoading, isError: q.isError, error: null as never, refetch: () => { void q.refetch(); } };
  return (
    <QueryView query={versions} loading={<Skeleton lines={4} />} empty={<EmptyState compact title="No versions" />} errorTitle="Versions unavailable">
      {(list) => (
        <ul className="space-y-2">
          {list.map((v) => (
            <li key={v.version_number} className="rounded-md border border-border bg-bg-secondary p-3">
              <div className="flex items-center gap-2">
                <span className="font-display text-sm font-semibold text-text-primary">v{v.version_number}</span>
                <Badge tone="muted">{v.created_by === "agent" ? "agent" : "you"}</Badge>
                <span className="text-[11px] text-text-muted">{timeAgo(v.created_at)}</span>
                {v.version_number === prompt.current_version.version_number ? (
                  <Badge tone="success">current</Badge>
                ) : (
                  <Button size="sm" variant="ghost" icon={<History size={12} />} className="ml-auto"
                    onClick={() => onLoad(v)} title="Load this version's text into the editor (saves as a new version)">
                    Load into editor
                  </Button>
                )}
              </div>
              {v.change_summary && <p className="mt-1 text-xs text-text-secondary">{v.change_summary}</p>}
              <p className="mt-1.5 line-clamp-2 text-xs text-text-muted">{v.prompt_text}</p>
            </li>
          ))}
        </ul>
      )}
    </QueryView>
  );
}

// ---------------------------------------------------------------------------
// Screening (GATE-06)
// ---------------------------------------------------------------------------

function ScreeningPanel({ promptId, checkId, jobRunning, onRun, runPending }: {
  promptId: string;
  checkId: string | null;
  jobRunning: boolean;
  onRun: () => void;
  runPending: boolean;
}) {
  const check = useComplianceCheck(checkId);
  return (
    <div className="space-y-4">
      <div>
        <p className="micro-label mb-2">Compliance checklist (GATE-06)</p>
        {!checkId && !jobRunning ? (
          <div>
            <p className="text-xs text-text-muted">
              Screening checks trademark, release, and disallowed-content rules (PROMPT_SCREEN). A PASS is required before the prompt
              can move through the queue gates.
            </p>
            <Button size="sm" variant="outline" icon={<ShieldCheck size={13} />} className="mt-2" loading={runPending} onClick={onRun} data-testid="prompt-screen">
              Run screening
            </Button>
          </div>
        ) : jobRunning ? (
          <p className="text-xs text-text-muted">Screening running — results appear here when the job finishes…</p>
        ) : (
          <QueryView query={check} loading={<Skeleton lines={4} />} empty={<EmptyState compact title="Check not found" />} errorTitle="Check unavailable">
            {(c: ComplianceCheck) => <ScreeningResult check={c} promptId={promptId} />}
          </QueryView>
        )}
      </div>
    </div>
  );
}

function ScreeningResult({ check, promptId }: { check: ComplianceCheck; promptId: string }) {
  const { toast } = useToast();
  const comp = useComplianceMutations();
  const triggered = check.findings.filter((f) => f.triggered);
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <ComplianceChip result={check.result} />
        <RiskChip risk={check.risk_level} />
        <span className="text-[11px] text-text-muted">checked {timeAgo(check.created_at)} · rules {check.rules_version}</span>
      </div>
      {check.explanation && <p className="text-[13px] text-text-secondary">{check.explanation}</p>}
      {triggered.length ? (
        <ul className="space-y-2">
          {triggered.map((f) => (
            <li key={f.rule_key} className="rounded-md border border-border bg-bg-secondary p-3">
              <div className="flex items-center gap-2">
                <Badge tone={f.severity === "BLOCK" ? "danger" : f.severity === "WARN" ? "warning" : "muted"}>{f.severity}</Badge>
                <span className="font-mono text-xs text-text-primary">{f.rule_key}</span>
              </div>
              <p className="mt-1.5 text-[13px] text-text-secondary">{f.explanation}</p>
              {f.remediation && <p className="mt-1 text-xs text-text-muted"><strong className="text-text-primary">Fix:</strong> {f.remediation}</p>}
            </li>
          ))}
        </ul>
      ) : (
        <Checklist items={[
          { label: "No trademarked terms triggered", pass: true },
          { label: "No people/release flags triggered", pass: true },
          { label: "No disallowed content triggered", pass: true },
        ]} />
      )}
      <p className="text-[11px] text-text-muted">Screening is advisory — human review is still required before queueing.</p>
      {check.result === "REVIEW" && !check.review_decision && (
        <div className="flex flex-wrap gap-2 border-t border-border pt-3">
          <Button size="sm" variant="primary" loading={comp.review.isPending}
            onClick={() => comp.review.mutate({ id: check.id, decision: "accepted" }, { onSuccess: () => toast({ title: "Review recorded: accepted", tone: "success" }) })}>
            Accept
          </Button>
          <Button size="sm" variant="outline" loading={comp.review.isPending}
            onClick={() => comp.review.mutate({ id: check.id, decision: "accepted_with_changes" }, { onSuccess: () => toast({ title: "Review recorded: accepted with changes", tone: "success" }) })}>
            Accept with changes
          </Button>
          <Button size="sm" variant="danger" loading={comp.review.isPending}
            onClick={() => comp.review.mutate({ id: check.id, decision: "rejected" }, { onSuccess: () => toast({ title: "Review recorded: rejected", tone: "info" }) })}>
            Reject
          </Button>
        </div>
      )}
      {check.review_decision && (
        <p className="text-xs text-text-muted">Reviewed: <strong className="text-text-primary">{check.review_decision}</strong>{check.reviewed_at ? ` · ${timeAgo(check.reviewed_at)}` : ""}</p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Templates / keywords / SEO (client-side helpers, demo-labeled)
// ---------------------------------------------------------------------------

const TEMPLATES: Record<string, { name: string; text: string }[]> = {
  image: [
    { name: "Product flat lay", text: "Top-down flat lay on a warm beige background, soft diffused studio light, gentle long shadows, photorealistic, high detail, e-commerce ready." },
    { name: "Lifestyle portrait", text: "Candid lifestyle photo, golden hour light, shallow depth of field, natural skin tones, editorial style, photorealistic." },
    { name: "Abstract background", text: "Abstract flowing gradient background, soft organic shapes, subtle grain, minimal, copy space in the center, high resolution." },
  ],
  video: [
    { name: "Slow push-in", text: "Cinematic slow push-in shot, shallow depth of field, golden hour, photorealistic, 8 seconds, smooth motion, no camera shake." },
    { name: "Seamless loop", text: "Seamless looping background, gentle continuous motion, minimal, negative space for text overlay, 10 seconds, smooth and calming." },
  ],
};

function TemplatePicker({ kind, onInsert }: { kind: "image" | "video"; onInsert: (text: string) => void }) {
  return (
    <div className="rounded-lg border border-border bg-bg-secondary p-3">
      <p className="micro-label mb-2">Firefly templates</p>
      <div className="flex flex-wrap gap-2">
        {(TEMPLATES[kind] ?? []).map((t) => (
          <Button key={t.name} size="sm" variant="outline" onClick={() => onInsert(t.text)} title={t.text}>
            + {t.name}
          </Button>
        ))}
      </div>
    </div>
  );
}

const TRENDING_KEYWORDS = [
  { keyword: "wellness lifestyle", volume: "high", trend: "up" },
  { keyword: "remote work team", volume: "high", trend: "flat" },
  { keyword: "sustainable packaging", volume: "medium", trend: "up" },
  { keyword: "ai generated abstract", volume: "medium", trend: "up" },
  { keyword: "senior fitness", volume: "low", trend: "up" },
] as const;

function KeywordExplorer() {
  const [q, setQ] = useState("");
  const results = TRENDING_KEYWORDS.filter((k) => !q.trim() || k.keyword.includes(q.trim().toLowerCase()));
  return (
    <div className="rounded-lg border border-border bg-bg-secondary p-3">
      <p className="micro-label mb-2">Keyword explorer</p>
      <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search trending keywords…" aria-label="Search trending keywords" />
      <ul className="mt-2 space-y-1.5">
        {results.map((k) => (
          <li key={k.keyword} className="flex items-center gap-2 text-[13px]">
            <span className="min-w-0 flex-1 text-text-secondary">{k.keyword}</span>
            <Badge tone={k.volume === "high" ? "success" : k.volume === "medium" ? "warning" : "muted"}>{k.volume} volume</Badge>
            <Badge tone={k.trend === "up" ? "info" : "muted"}>{k.trend === "up" ? "↗ rising" : "→ steady"}</Badge>
          </li>
        ))}
        {!results.length && <li className="text-xs text-text-muted">No keywords match.</li>}
      </ul>
      <p className="mt-2 text-[11px] text-text-muted">
        <ProvenanceBadge mock /> Illustrative keyword data — not live Adobe search volume. Connect a keyword provider for real numbers.
      </p>
    </div>
  );
}

function SeoPanel({ promptText }: { promptText: string }) {
  const { toast } = useToast();
  const [title, setTitle] = useState<string | null>(null);
  const [caption, setCaption] = useState<string | null>(null);

  const generate = () => {
    const words = promptText.replace(/[^a-zA-Z0-9 ,.-]/g, "").split(/[\s,]+/).filter(Boolean).slice(0, 8);
    const core = words.join(" ") || "stock concept";
    setTitle(`${core[0]?.toUpperCase() ?? ""}${core.slice(1)} — stock photo concept`);
    setCaption(`A ${core} captured in high detail, perfect for commercial use. Model released where applicable. Keywords: ${words.slice(0, 5).join(", ")}.`);
    toast({ title: "Draft generated", description: "Edit before use — a starting draft, not final metadata.", tone: "info" });
  };

  return (
    <div className="space-y-3">
      <Button size="sm" variant="primary" icon={<Sparkles size={13} />} onClick={generate} disabled={!promptText.trim()}>
        Generate SEO draft
      </Button>
      {title ? (
        <>
          <Field label="Title draft"><Input value={title} onChange={(e) => setTitle(e.target.value)} /></Field>
          <Field label="Caption draft"><Textarea value={caption ?? ""} onChange={(e) => setCaption(e.target.value)} rows={4} /></Field>
          <Button size="sm" variant="outline" icon={<Copy size={13} />}
            onClick={async () => { await navigator.clipboard.writeText(`${title}\n\n${caption ?? ""}`); toast({ title: "Copied", description: "Title and caption copied.", tone: "success" }); }}>
            Copy both
          </Button>
        </>
      ) : (
        <p className="text-xs text-text-muted">Generates a title + caption draft from the current prompt text. Review and refine before submitting to Adobe.</p>
      )}
    </div>
  );
}
