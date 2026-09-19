"use client";
/**
 * Idea card + detail drawer — shared by Image Ideas and Video Ideas (docs/06 §3.7).
 */
import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Bookmark, Clock, Copy, Pencil, Play, RefreshCw, Send, Archive } from "lucide-react";
import { Badge, Button, Card, ConfirmModal, Drawer, EmptyState, Field, Input, Modal, Textarea, WhyThis } from "../../components/ui";
import { ComplianceChip, FormatBadge, IdeaStatusChip, ProvenanceBadge, RiskChip, isMock } from "../../components/scores";
import { useIdea, useIdeaMutations, useLibraryMutations, useQueueMutations } from "../../hooks/useApi";
import { useToast } from "../../components/toast";
import { ConceptPlayer } from "../../components/remotion/players";
import { RenderVideoButton } from "../../components/remotion/RenderControls";
import { conceptPropsFromIdea } from "../../components/remotion/props";
import type { Idea } from "../../types";
import { enumLabel, timeAgo } from "../../lib/format";

export function IdeaCard({ idea, onOpen }: { idea: Idea; onOpen: (id: string) => void }) {
  const muts = useIdeaMutations();
  const queue = useQueueMutations();
  const lib = useLibraryMutations();
  const demo = isMock(idea);
  const [previewOpen, setPreviewOpen] = useState(false);

  return (
    <Card className="flex flex-col p-3.5 transition-colors hover:border-text-muted">
      {/* Inline motion preview (video ideas) — the Player plays the composition
          live; no render needed. Asset thumbnail arrives when attached. */}
      {idea.kind === "video" && previewOpen ? (
        <div className="mb-3">
          <ConceptPlayer input={conceptPropsFromIdea(idea)} />
        </div>
      ) : (
        <button
          onClick={() => onOpen(idea.id)}
          aria-label={`Open idea: ${idea.title}`}
          className="mb-3 flex h-28 w-full items-center justify-center rounded-md border border-border bg-bg-secondary text-text-muted transition-colors hover:bg-surface-elevated"
        >
          <span className="text-[10px] font-semibold uppercase tracking-[0.08em]">
            {idea.kind === "image" ? "Image concept" : "Video concept"}
          </span>
        </button>
      )}
      <button onClick={() => onOpen(idea.id)} className="text-left">
        <span className="block truncate text-[13.5px] font-semibold text-text-primary hover:text-accent-secondary">
          {idea.title}
        </span>
      </button>
      <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-text-muted">{idea.concept}</p>
      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        <IdeaStatusChip status={idea.status} />
        <FormatBadge format={idea.kind} />
        {idea.duration_target_seconds ? (
          <Badge tone="neutral">{idea.duration_target_seconds}s</Badge>
        ) : null}
        {idea.compliance && <ComplianceChip result={idea.compliance.result} />}
        {idea.similarity && <RiskChip risk={idea.similarity.risk_level} />}
        {demo && <ProvenanceBadge mock />}
        {!demo && idea.provenance && <ProvenanceBadge provenance={idea.provenance} />}
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-1 border-t border-border pt-2.5">
        {idea.kind === "video" && (
          <Button size="sm" variant="ghost" icon={<Play size={12} />} onClick={() => setPreviewOpen((v) => !v)} aria-expanded={previewOpen} title="Play an animated storyboard preview of this concept">
            {previewOpen ? "Hide preview" : "Preview"}
          </Button>
        )}
        <Button size="sm" variant="ghost" icon={<Send size={12} />} title="Send to production queue"
          onClick={() => queue.enqueue.mutate({ title: idea.title, asset_type: idea.kind === "image" ? "IMAGE" : "VIDEO", image_idea_id: idea.kind === "image" ? idea.id : undefined, video_idea_id: idea.kind === "video" ? idea.id : undefined })}>
          Queue
        </Button>
        <Button size="sm" variant="ghost" icon={<Bookmark size={12} />} title="Save to library"
          onClick={() => lib.save.mutate({ item_kind: idea.kind === "image" ? "IMAGE_IDEA" : "VIDEO_IDEA", item_id: idea.id })}>
          Save
        </Button>
        {idea.kind === "video" && (
          <RenderVideoButton kind="concept" label={idea.title} props={conceptPropsFromIdea(idea)} idleLabel="Render" />
        )}
        <span className="ml-auto text-[11px] text-text-muted">{timeAgo(idea.updated_at)}</span>
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Detail drawer (URL-driven: ?idea=<id>) — quick view without leaving the grid.
// ---------------------------------------------------------------------------

export function IdeaDrawer({ kind, onClose }: { kind: "image" | "video"; onClose: () => void }) {
  const params = useSearchParams();
  const router = useRouter();
  const id = params.get("idea");
  const idea = useIdea(id);
  return (
    <Drawer
      open={!!id}
      onClose={onClose}
      title={idea.data ? idea.data.title : "Idea"}
      footer={idea.data ? <IdeaDrawerActions idea={idea.data} /> : undefined}
    >
      {!id ? null : idea.isLoading ? (
        <div className="space-y-3" aria-busy="true">
          <div className="skeleton h-32 rounded-md" />
          <div className="skeleton h-4 w-2/3 rounded" />
          <div className="skeleton h-20 rounded" />
        </div>
      ) : idea.isError || !idea.data ? (
        <EmptyState title="Idea not found" description="It may have been archived or deleted." action={<Button size="sm" onClick={onClose}>Close</Button>} />
      ) : (
        <IdeaDrawerBody idea={idea.data} kind={kind} />
      )}
    </Drawer>
  );
}

function IdeaDrawerActions({ idea }: { idea: Idea }) {
  const router = useRouter();
  const muts = useIdeaMutations();
  const queue = useQueueMutations();
  const [confirmArchive, setConfirmArchive] = useState(false);
  const assetType = idea.kind === "image" ? "IMAGE" : "VIDEO";
  return (
    <div className="flex flex-wrap gap-2">
      <Button size="sm" variant="primary" icon={<Play size={13} />}
        onClick={() => router.push(`/prompt-studio?idea=${idea.id}&asset_type=${assetType}`)}
        data-testid="idea-open-prompt-studio">
        Send to Prompt Studio
      </Button>
      <Button size="sm" icon={<Send size={13} />} loading={queue.enqueue.isPending}
        onClick={() => queue.enqueue.mutate({ title: idea.title, asset_type: assetType, image_idea_id: idea.kind === "image" ? idea.id : undefined, video_idea_id: idea.kind === "video" ? idea.id : undefined })}>
        Add to queue
      </Button>
      <Button size="sm" variant="ghost" icon={<Archive size={13} />} onClick={() => setConfirmArchive(true)}>
        Archive
      </Button>
      <ConfirmModal
        open={confirmArchive}
        onClose={() => setConfirmArchive(false)}
        title="Archive idea"
        description="This idea will be archived. It stays in your library and can be restored later."
        confirmLabel="Archive"
        onConfirm={() => { muts.archive.mutate(idea.id); setConfirmArchive(false); }}
        loading={muts.archive.isPending}
      />
    </div>
  );
}

function IdeaDrawerBody({ idea, kind }: { idea: Idea; kind: "image" | "video" }) {
  const router = useRouter();
  const { toast } = useToast();
  const muts = useIdeaMutations();
  const [editing, setEditing] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [title, setTitle] = useState(idea.title);
  const [concept, setConcept] = useState(idea.concept);
  const [regenerating, setRegenerating] = useState(false);

  const saveEdit = () => {
    muts.update.mutate({ id: idea.id, body: { title, concept } }, { onSuccess: () => setEditOpen(false) });
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-1.5">
        <IdeaStatusChip status={idea.status} />
        <FormatBadge format={kind} />
        {idea.duration_target_seconds && (
          <Badge tone="neutral"><Clock size={10} aria-hidden /> {idea.duration_target_seconds}s target</Badge>
        )}
        {idea.compliance && <ComplianceChip result={idea.compliance.result} />}
        {idea.similarity && <RiskChip risk={idea.similarity.risk_level} />}
        {isMock(idea) ? <ProvenanceBadge mock /> : idea.provenance ? <ProvenanceBadge provenance={idea.provenance} /> : null}
        <span className="ml-auto text-[11px] text-text-muted">Updated {timeAgo(idea.updated_at)}</span>
      </div>

      <section>
        <p className="micro-label mb-1.5">Concept</p>
        <p className="text-[13.5px] leading-relaxed text-text-primary">{idea.concept}</p>
      </section>

      <section>
        <p className="micro-label mb-1.5">Originality notes</p>
        <p className="text-[13px] leading-relaxed text-text-secondary">{idea.originality_notes}</p>
      </section>

      {idea.reference_mood && idea.reference_mood.length > 0 && (
        <section>
          <p className="micro-label mb-1.5">Reference mood</p>
          <div className="flex flex-wrap gap-1.5">
            {idea.reference_mood.map((m) => <Badge key={m} tone="neutral">{m}</Badge>)}
          </div>
        </section>
      )}

      {idea.shot_list && idea.shot_list.length > 0 && (
        <section>
          <p className="micro-label mb-1.5">Shot list</p>
          <ol className="space-y-2">
            {idea.shot_list.map((s, i) => (
              <li key={i} className="rounded-md border border-border bg-bg-secondary p-2.5 text-[12.5px]">
                <p className="font-semibold text-text-primary">Shot {i + 1} — {s.shot}</p>
                <p className="mt-0.5 text-text-secondary">
                  {s.camera_move && <span>Move: {s.camera_move}. </span>}
                  {s.duration_s !== undefined && <span>Duration: {s.duration_s}s. </span>}
                  {s.notes}
                </p>
              </li>
            ))}
          </ol>
        </section>
      )}

      {kind === "video" && (
        <section>
          <div className="mb-1.5 flex flex-wrap items-center justify-between gap-2">
            <p className="micro-label">Motion preview</p>
            <RenderVideoButton kind="concept" label={idea.title} props={conceptPropsFromIdea(idea)} idleLabel="Render MP4" />
          </div>
          <ConceptPlayer input={conceptPropsFromIdea(idea)} />
          <p className="mt-1.5 text-[11px] text-text-muted">
            Storyboard previz built from this concept&rsquo;s shot list — a planning aid, not final footage.
            MP4 rendering is on-demand only and runs one job at a time.
          </p>
        </section>
      )}

      <WhyThis label="Why this idea">
        <p>
          This idea was prepared from {idea.opportunity_id ? "an approved opportunity" : "a freeform brief"}.
          Originality is attested in the notes above; similarity screening happens before queue entry (GATE-06/07).
        </p>
        {idea.agent_run_id && <p className="mt-1">Prepared by agent run <span className="font-mono">{idea.agent_run_id.slice(0, 8)}</span> — you decide.</p>}
      </WhyThis>

      <div className="flex flex-wrap gap-2 border-t border-border pt-3">
        <Button size="sm" variant="outline" icon={<Pencil size={12} />} onClick={() => { setTitle(idea.title); setConcept(idea.concept); setEditOpen(true); }}>
          Edit
        </Button>
        <Button size="sm" variant="outline" icon={<RefreshCw size={12} />} loading={regenerating}
          onClick={() => {
            setRegenerating(true);
            muts.generateConcepts.mutate(idea.id, {
              onSettled: () => setRegenerating(false),
              onSuccess: () => toast({ title: "Regeneration queued", description: "New concept versions will appear here.", tone: "info" }),
            });
          }}>
          Regenerate
        </Button>
        <Button size="sm" variant="outline" icon={<Copy size={12} />}
          onClick={() => { navigator.clipboard.writeText(`${idea.title}\n\n${idea.concept}`).then(() => toast({ title: "Copied to clipboard", tone: "success", durationMs: 2000 })); }}>
          Copy
        </Button>
      </div>

      <Modal open={editOpen} onClose={() => setEditOpen(false)} title="Edit idea"
        footer={
          <>
            <Button variant="ghost" onClick={() => setEditOpen(false)}>Cancel</Button>
            <Button variant="primary" loading={muts.update.isPending} onClick={saveEdit}>Save changes</Button>
          </>
        }>
        <div className="space-y-3">
          <Field label="Title"><Input value={title} onChange={(e) => setTitle(e.target.value)} /></Field>
          <Field label="Concept"><Textarea value={concept} onChange={(e) => setConcept(e.target.value)} rows={6} /></Field>
        </div>
      </Modal>
    </div>
  );
}
