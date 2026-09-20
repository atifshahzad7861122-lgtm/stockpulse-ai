"use client";
/**
 * Opportunity Detail (docs/05 §5.1): header, scores, prediction, demand
 * evidence, formats, image/video concepts, compliance guidance, related
 * opportunities, activity timeline, action buttons.
 */
import { useEffect, useState, Suspense } from "react";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { ArrowLeft, Bookmark, Check, CheckCircle2, Wand2, XCircle, Archive, Lightbulb, Download, FileText } from "lucide-react";
import {
  Badge,
  Button,
  ConfirmModal,
  EmptyState,
  Field,
  Input,
  Modal,
  PageHeader,
  Panel,
  QueryView,
  Select,
  Skeleton,
  Tabs,
  Textarea,
  WhyThis,
} from "../../../components/ui";
import {
  ConfidenceMeter,
  FormatBadge,
  ProvenanceBadge,
  RiskChip,
  ScoreBar,
  ScoreInline,
  SaturationBadge,
  isMock,
} from "../../../components/scores";
import { useToast } from "../../../components/toast";
import {
  EvidenceList,
  FusionBreakdown,
  FusionLabelBadge,
  PersonalFitChip,
} from "../../../components/fusion";
import {
  useAgentJobs,
  useAssetAnalysis,
  useAssetAnalysisGenerate,
  useFusionMutations,
  useFusionScore,
  useIdeas,
  useLibraryMutations,
  useOpportunities,
  useOpportunity,
  useOpportunityMutations,
  useIdeaMutations,
  useProductionRecommendationMutations,
  useProductionRecommendations,
  usePromptPackExport,
  usePromptPacks,
} from "../../../hooks/useApi";
import { useJobPoll } from "../../../hooks/useJobPoll";
import { enumLabel, fmtPct01, timeAgo } from "../../../lib/format";
import { isActionable } from "../../../features/opportunities/OpportunityCard";
import type { AssetAnalysis, FusionEvidence, Idea, MarketMomentum, MarketSignalLevel, Opportunity, ProductionRecommendation } from "../../../types";

function OpportunityDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const router = useRouter();
  const search = useSearchParams();
  const opp = useOpportunity(id);
  const [createOpen, setCreateOpen] = useState(false);

  // Deep link from dashboard hero (?create=idea) opens the create-idea modal.
  useEffect(() => {
    if (search.get("create") === "idea" && opp.data) {
      setCreateOpen(true);
      router.replace(`/opportunities/${id}`);
    }
  }, [search, opp.data, id, router]);

  return (
    <div className="space-y-4">
      <Button size="sm" variant="ghost" icon={<ArrowLeft size={13} />} onClick={() => router.back()}>Back to opportunities</Button>

      <QueryView
        query={opp}
        loading={<Skeleton className="h-64" />}
        empty={<EmptyState title="Opportunity not found" description="It may have been deleted or the link is wrong." action={<Button size="sm" onClick={() => router.push("/opportunities")}>All opportunities</Button>} />}
        errorTitle="Opportunity unavailable"
      >
        {(o) => <DetailBody opp={o} onCreateIdea={() => setCreateOpen(true)} />}
      </QueryView>

      {opp.data && <CreateIdeaModal open={createOpen} onClose={() => setCreateOpen(false)} opportunity={opp.data} />}
    </div>
  );
}

function DetailBody({ opp, onCreateIdea }: { opp: Opportunity; onCreateIdea: () => void }) {
  const { toast } = useToast();
  const router = useRouter();
  const muts = useOpportunityMutations();
  const lib = useLibraryMutations();
  const [confirm, setConfirm] = useState<null | "reject" | "archive">(null);
  const [rejectReason, setRejectReason] = useState("");
  const [assetModalOpen, setAssetModalOpen] = useState(false);
  const [assetDefault, setAssetDefault] = useState<"image" | "video">("image");
  const openAssetAnalyzer = (def: "image" | "video" = "image") => {
    setAssetDefault(def);
    setAssetModalOpen(true);
  };

  const actionable = isActionable(opp);
  const demo = isMock(opp) || isMock({ provenance: opp.data_provenance });

  const approve = () => {
    if (!actionable) {
      toast({ title: "Not approvable yet", description: `Needs score ≥ 55 and confidence ≥ 50% — this item has score ${Math.round(opp.opportunity_score)} and confidence ${fmtPct01(opp.confidence)}.`, tone: "warning" });
      return;
    }
    muts.approve.mutate({ id: opp.id }, {
      onSuccess: () => toast({ title: "Approved", description: "This opportunity is now eligible for idea generation and queueing.", tone: "success" }),
    });
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <PageHeader
        title={opp.title}
        description={
          <span className="flex flex-wrap items-center gap-1.5">
            {opp.category && <Badge tone="neutral">{opp.category}</Badge>}
            {opp.micro_niche && <Badge tone="info">{opp.micro_niche}</Badge>}
            {(opp.formats ?? []).map((f) => <FormatBadge key={f} format={f} />)}
            <Badge tone={opp.status === "approved" ? "success" : opp.status === "new" ? "info" : "muted"}>{enumLabel(opp.status)}</Badge>
            {demo ? <ProvenanceBadge mock /> : <ProvenanceBadge provenance={opp.data_provenance} />}
            <span className="text-text-muted">· updated {timeAgo(opp.updated_at)}</span>
          </span>
        }
        actions={
          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant="primary" icon={<Wand2 size={13} />} onClick={() => setAssetModalOpen(true)} data-testid="opp-generate-original-prompt">
              Generate original prompt
            </Button>
            <Button size="sm" variant="ghost" icon={<Bookmark size={13} />} loading={lib.save.isPending}
              onClick={() => lib.save.mutate({ item_kind: "OPPORTUNITY", item_id: opp.id })}>
              Save
            </Button>
            <Button size="sm" variant="ghost" icon={<Archive size={13} />} onClick={() => setConfirm("archive")}>Archive</Button>
            {opp.status !== "approved" ? (
              <>
                <Button size="sm" variant="outline" icon={<XCircle size={13} />} onClick={() => { setRejectReason(""); setConfirm("reject"); }}>Reject</Button>
                <Button size="sm" variant="primary" icon={<CheckCircle2 size={13} />} onClick={approve} loading={muts.approve.isPending} data-testid="opp-approve">
                  Approve
                </Button>
              </>
            ) : (
              <Button size="sm" variant="primary" icon={<Lightbulb size={13} />} onClick={onCreateIdea} data-testid="opp-save-idea">
                Save idea
              </Button>
            )}
          </div>
        }
      />

      {!actionable && opp.status !== "approved" && (
        <div className="rounded-lg border border-status-warning/30 bg-status-warning/[0.06] px-4 py-3 text-[13px] text-text-secondary">
          <strong className="text-text-primary">Insufficient evidence — do not act yet.</strong>{" "}
          {`Score ${Math.round(opp.opportunity_score)} / confidence ${fmtPct01(opp.confidence)} is below the action bar (≥ 55 / ≥ 50%).`}
          Approval is disabled until the evidence clears it.
        </div>
      )}

      {/* Scores */}
      <Panel title="Scores">
        <div className="grid gap-4 md:grid-cols-2">
          <ScoreRow label="Opportunity score" value={opp.opportunity_score}
            explainer="OS = 0.35·trend + 0.25·commercial relevance + 0.20·content demand + 0.20·(100 − saturation) (CONTRACT §8.2). The score is an estimate — it never guarantees sales." />
          <ScoreRow label="Confidence" value={opp.confidence * 100} pct
            explainer="PC = 0.30·coverage + 0.25·freshness + 0.20·sources + 0.15·stability + 0.10·your agreement (CONTRACT §8.5)." />
        </div>
        {opp.scores?.saturation_score !== undefined && opp.scores?.saturation_score !== null && (
          <div className="mt-4">
            <p className="micro-label mb-2">Saturation</p>
            <SaturationBadge value={opp.scores.saturation_score} />
          </div>
        )}
        {opp.summary && (
          <div className="mt-4 rounded-md border border-border bg-bg-secondary p-3 text-[13px] text-text-secondary">{opp.summary}</div>
        )}
      </Panel>

      {/* Fusion — market × personal, honestly labeled */}
      <FusionIntelligencePanel opp={opp} />

      {/* Prediction */}
      {opp.scores?.predicted_direction && (
        <Panel title="Prediction">
          <div className="flex flex-wrap items-center gap-3">
            <Badge tone={opp.scores.predicted_direction === "up" ? "success" : opp.scores.predicted_direction === "down" ? "danger" : "muted"}>
              Predicted: {enumLabel(opp.scores.predicted_direction)}
            </Badge>
            {opp.scores.prediction_confidence !== undefined && opp.scores.prediction_confidence !== null && (
              <ConfidenceMeter value={opp.scores.prediction_confidence} />
            )}
          </div>
          <p className="mt-2 text-xs text-text-muted">An estimate, not a guarantee — predictions are directional hints only, never promises of Adobe acceptance or sales.</p>
        </Panel>
      )}

      {/* Demand evidence */}
      <Panel title="Demand evidence">
        {opp.demand_evidence.length ? (
          <ul className="space-y-2">
            {opp.demand_evidence.map((e, i) => (
              <li key={i} className="flex items-start gap-2.5 rounded-md border border-border bg-bg-secondary px-3 py-2 text-[13px]">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-accent-primary" aria-hidden />
                <p className="text-text-secondary">{e.note}</p>
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState compact title="No structured evidence rows" description="This record has no demand-evidence rows — the score breakdown above is the evidence you have." />
        )}
        {opp.risk_notes && (
          <div className="mt-3 rounded-md border border-status-warning/30 bg-status-warning/[0.06] p-3 text-[13px] text-text-secondary">
            <strong className="text-text-primary">Risk notes.</strong> {opp.risk_notes}
          </div>
        )}
      </Panel>

      {/* Recommended formats */}
      <Panel title="Recommended formats">
        <div className="flex flex-wrap gap-2">
          {(opp.formats ?? []).length ? opp.formats!.map((f) => <FormatBadge key={f} format={f} />) : <p className="text-xs text-text-muted">No format recommendation recorded — both image and video ideas can be explored.</p>}
        </div>
      </Panel>

      {/* Commercial use cases */}
      <CommercialUseCasesPanel opp={opp} />

      {/* Concepts (ideas linked to this opportunity) */}
      <ConceptsPanel opportunityId={opp.id} onCreateIdea={onCreateIdea} onPromptIdea={(i) => openAssetAnalyzer(i.kind === "video" ? "video" : "image")} />

      {/* Similarity screening (per concept) */}
      <SimilarityPanel opportunityId={opp.id} />

      {/* Production recommendations tied to this opportunity */}
      <OpportunityRecommendationsPanel opportunityId={opp.id} />

      {/* Prompt packs with export */}
      <PromptPacksPanel opportunityId={opp.id} />

      {/* Compliance guidance */}
      <Panel title="Compliance">
        <p className="text-xs text-text-muted">
          Compliance screening runs on <strong className="text-text-primary">ideas, prompts, assets, and metadata</strong> — a PASS is required before
          queue items leave compliance review (T18). Screening is available from the Ideas pages and the Compliance Center.
        </p>
        <Link href="/compliance" className="mt-2 inline-block text-xs text-accent-secondary hover:underline">Open Compliance Center</Link>
      </Panel>

      {/* Related */}
      <RelatedPanel opp={opp} />
      {/* Activity */}
      <ActivityPanel opportunityId={opp.id} />

      {/* Footer actions */}
      <Panel title="Actions">
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="primary" icon={<Wand2 size={13} />} onClick={() => setAssetModalOpen(true)}>
            Generate original prompt
          </Button>
          <Button size="sm" variant="outline" icon={<Lightbulb size={13} />} onClick={onCreateIdea}>Save idea</Button>
        </div>
        <p className="mt-2 text-xs text-text-muted">Idea generation is human-initiated — the system never creates ideas on its own.</p>
      </Panel>

      <AssetAnalysisModal open={assetModalOpen} onClose={() => setAssetModalOpen(false)} opportunity={opp} defaultAssetType={assetDefault} />

      <ConfirmModal
        open={confirm === "archive"}
        onClose={() => setConfirm(null)}
        title="Archive opportunity"
        description="Archived opportunities stay visible in filters but leave active lists."
        confirmLabel="Archive"
        onConfirm={() => { muts.archive.mutate(opp.id); setConfirm(null); }}
      />
      {confirm === "reject" && (
        <Modal open onClose={() => setConfirm(null)} title="Reject opportunity"
          footer={
            <>
              <Button variant="ghost" onClick={() => setConfirm(null)}>Cancel</Button>              <Button variant="danger" disabled={!rejectReason.trim()} loading={muts.reject.isPending}
                onClick={() => { muts.reject.mutate({ id: opp.id, reason: rejectReason.trim() }); setConfirm(null); }}>
                Reject
              </Button>
            </>
          }>
          <Field label="Reason" required hint="Recorded for your review — required by the API.">
            <Textarea value={rejectReason} onChange={(e) => setRejectReason(e.target.value)} rows={3} placeholder="Why is this opportunity being rejected?" />
          </Field>
        </Modal>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Phase 3 — fusion intelligence: market evidence, personal evidence,
// full scoring breakdown (saturation subtracted visibly), confidence.
// ---------------------------------------------------------------------------

function FusionIntelligencePanel({ opp }: { opp: Opportunity }) {
  const fusion = useFusionScore(opp.id);
  const muts = useFusionMutations();

  return (
    <Panel
      title="Fusion intelligence"
      action={
        <Button size="sm" variant="outline" loading={muts.compute.isPending} onClick={() => muts.compute.mutate(opp.id)}>
          {fusion.data ? "Recompute" : "Compute fusion score"}
        </Button>
      }
    >
      <QueryView
        query={fusion}
        loading={<Skeleton lines={6} />}
        empty={
          <EmptyState
            compact
            title="No fusion score computed yet"
            description="Fuse this opportunity: market signals blended with your personal performance history — or an honest MARKET-ONLY score when private data is not connected. Personal fit is never invented."
            action={<Button size="sm" variant="primary" loading={muts.compute.isPending} onClick={() => muts.compute.mutate(opp.id)}>Compute fusion score</Button>}
          />
        }
        errorTitle="Fusion score unavailable"
      >
        {(f) => {
          const market: FusionEvidence[] = (f.evidence ?? []).filter((e) => !e.private);
          const personal: FusionEvidence[] = (f.evidence ?? []).filter((e) => e.private);
          return (
            <div className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <FusionBreakdown fusion={f} />
                </div>
                <div className="space-y-3">
                  <div>
                    <p className="micro-label mb-1.5">Personal fit</p>
                    <PersonalFitChip value={f.components.personal_fit} />
                    {f.label === "MARKET-ONLY" && (
                      <p className="mt-1.5 text-[11px] text-text-muted">
                        MARKET-ONLY — your private data is not connected, so this score uses market signals alone.
                        Nothing personal was invented to fill the gap.
                      </p>
                    )}
                  </div>
                  <div>
                    <p className="micro-label mb-1.5">Confidence</p>
                    <ConfidenceMeter value={f.confidence_score} />
                    <WhyThis label="What confidence means">
                      <p>A probabilistic estimate of how much the available evidence supports this score — it is not a promise of Adobe acceptance or sales.</p>
                    </WhyThis>
                  </div>
                </div>
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <p className="micro-label mb-2">Market evidence</p>
                  {market.length ? (
                    <EvidenceList evidence={market} />
                  ) : (
                    <p className="text-xs text-text-muted">No market evidence rows on this score.</p>
                  )}
                  <WhyThis label="Why these">
                    <p>Public signals the trend engine observed for this opportunity — source, observation time, and signal are shown per row.</p>
                  </WhyThis>
                </div>
                <div>
                  <p className="micro-label mb-2">Personal evidence</p>
                  {personal.length ? (
                    <EvidenceList evidence={personal} />
                  ) : (
                    <p className="text-xs text-text-muted">
                      No personal evidence — your private performance is not connected, so there is nothing personal to fuse. Connect it on the{" "}
                      <Link href="/private" className="text-accent-secondary hover:underline">Private page</Link>.
                    </p>
                  )}
                  <WhyThis label="Why these">
                    <p>Your own acceptance, downloads, and earnings history matched to this opportunity&rsquo;s category, micro-niche, and themes. Private rows are tagged so you always know what the score is built on.</p>
                  </WhyThis>
                </div>
              </div>
            </div>
          );
        }}
      </QueryView>
    </Panel>
  );
}

// ---------------------------------------------------------------------------
// Commercial use cases — buyer-side angles implied by the formats/scores.
// Honest: framed as "plausible uses to explore", never promises.
// ---------------------------------------------------------------------------

function CommercialUseCasesPanel({ opp }: { opp: Opportunity }) {
  const formats = opp.formats ?? [];
  const image = formats.length === 0 || formats.includes("image");
  const video = formats.length === 0 || formats.includes("video");
  const sat = opp.scores?.saturation_score;
  return (
    <Panel title="Commercial use cases">
      <ul className="space-y-2 text-[13px] text-text-secondary">
        {image && (
          <li className="rounded-md border border-border bg-bg-secondary px-3 py-2.5">
            <strong className="text-text-primary">Image:</strong> editorial and web licensing, presentations,
            marketing layouts, book covers — anywhere a still holds the story.
          </li>
        )}
        {video && (
          <li className="rounded-md border border-border bg-bg-secondary px-3 py-2.5">
            <strong className="text-text-primary">Video:</strong> b-roll and loops for backgrounds, social cuts,
            title sequences — anywhere motion adds buyer value.
          </li>
        )}
        {sat !== undefined && sat !== null && sat > 70 && (
          <li className="rounded-md border border-status-warning/30 bg-status-warning/[0.06] px-3 py-2.5">
            <strong className="text-text-primary">Saturation note:</strong> this niche scores saturated ({Math.round(sat)}/100) —
            favor angles your portfolio already wins at rather than generic coverage.
          </li>
        )}
      </ul>
      <p className="mt-2 text-[11px] text-text-muted">Use cases are angles to explore, not guarantees of demand.</p>
    </Panel>
  );
}

// ---------------------------------------------------------------------------
// Similarity screening per concept — the checks run on ideas, not on the
// opportunity itself; surface each concept's latest verdict here.
// ---------------------------------------------------------------------------

function SimilarityPanel({ opportunityId }: { opportunityId: string }) {
  const ideas = useIdeas({ opportunity_id: opportunityId, page_size: 20 });
  return (
    <Panel title="Similarity screening">
      <QueryView query={ideas} loading={<Skeleton lines={3} />} empty={<EmptyState compact title="No concepts to screen" description="Similarity checks run on concepts — save an idea first." />} errorTitle="Concepts unavailable">
        {(page) => {
          const screened = page.data.filter((i) => i.similarity);
          return (
            <div className="space-y-2">
              <p className="text-xs text-text-muted">
                Similarity verdicts are recorded per concept. Screen from the Ideas pages before producing — the pipeline never clears similarity on its own.
              </p>
              {screened.length ? (
                <ul className="space-y-1.5">
                  {screened.map((i) => (
                    <li key={i.id} className="flex items-center gap-2.5 rounded-md border border-border bg-bg-secondary px-3 py-2 text-[13px]">
                      <Link href={`/${i.kind}-ideas?idea=${i.id}`} className="min-w-0 flex-1 truncate text-text-secondary hover:text-text-primary">{i.title}</Link>
                      <RiskChip risk={i.similarity!.risk_level} />
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-xs text-text-muted">No similarity verdicts yet on this opportunity&rsquo;s concepts.</p>
              )}
              <Link href="/similarity" className="inline-block text-xs text-accent-secondary hover:underline">Open the similarity checker</Link>
            </div>
          );
        }}
      </QueryView>
    </Panel>
  );
}

// ---------------------------------------------------------------------------
// Production recommendations tied to this opportunity — each with evidence
// provenance (source, timestamp, signal, private/public, prediction version)
// and approve / reject / archive actions.
// ---------------------------------------------------------------------------

function OpportunityRecommendationsPanel({ opportunityId }: { opportunityId: string }) {
  const recs = useProductionRecommendations({ retry: false });
  const muts = useProductionRecommendationMutations();
  const busy = muts.approve.isPending || muts.reject.isPending || muts.archive.isPending;

  return (
    <Panel title="Production recommendations">
      <QueryView
        query={recs}
        loading={<Skeleton lines={3} />}
        empty={<EmptyState compact title="No recommendations yet" description="The daily planner has not recommended this opportunity. Build today's plan from the Daily page." />}
        errorTitle="Recommendations unavailable"
      >
        {(rows) => {
          const mine = rows.filter((r) => r.opportunity_id === opportunityId);
          if (!mine.length)
            return <EmptyState compact title="No recommendations for this opportunity" description="It has not been picked up by the daily planner yet." />;
          return (            <ul className="space-y-2.5">
              {mine.map((p) => (
                <li key={p.id} className="flex flex-wrap items-center gap-2.5 rounded-lg border border-border bg-bg-secondary px-3.5 py-3">
                  <FileText size={15} className="shrink-0 text-text-muted" aria-hidden />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[13px] font-semibold text-text-primary">{p.name}</p>
                    <p className="text-[11px] text-text-muted">
                      {p.prompt_count} prompts{p.asset_type ? ` · ${p.asset_type.toLowerCase()}` : ""}{p.status ? ` · ${enumLabel(p.status)}` : ""}
                    </p>
                  </div>
                  <Button
                    size="sm"
                    variant="outline"
                    icon={<Download size={13} />}
                    loading={exporter.isPending}
                    onClick={() => exporter.mutate(p.id)}
                    title="Download the pack as a file"
                  >
                    Export
                  </Button>
                </li>
              ))}
            </ul>
          );
        }}
      </QueryView>
      <p className="mt-2 text-[11px] text-text-muted">Export downloads the pack as a file — nothing is pasted into a chat.</p>
    </Panel>
  );
}

function ScoreRow({ label, value, pct, explainer }: { label: string; value: number; pct?: boolean; explainer: string }) {
  return (
    <div>
      <div className="flex items-baseline justify-between">
        <p className="micro-label">{label}</p>
        <p className="font-display text-lg font-semibold text-text-primary">{pct ? fmtPct01(value / 100) : Math.round(value)}</p>
      </div>
      <ScoreBar value={value} />
      <WhyThis label="How this is computed"><p>{explainer}</p></WhyThis>
    </div>
  );
}

function ConceptsPanel({ opportunityId, onCreateIdea, onPromptIdea }: { opportunityId: string; onCreateIdea: () => void; onPromptIdea: (i: Idea) => void }) {
  const ideas = useIdeas({ opportunity_id: opportunityId, page_size: 8 });
  return (
    <Panel title="Image / video concepts" action={<Button size="sm" variant="outline" icon={<Lightbulb size={13} />} onClick={onCreateIdea}>Save idea</Button>}>
      <QueryView
        query={ideas}
        loading={<Skeleton lines={3} />}
        empty={<EmptyState compact title="No concepts yet" description="Save the first idea for this opportunity — you write the concept, the pipeline refines it." action={<Button size="sm" variant="primary" onClick={onCreateIdea}>Save idea</Button>} />}
        errorTitle="Concepts unavailable"
      >
        {(page) => (
          <div className="grid gap-3 md:grid-cols-2">
            {page.data.map((i) => (
              <div key={i.id} className="rounded-lg border border-border bg-bg-secondary p-3">
                <div className="flex items-center gap-1.5">
                  <FormatBadge format={i.kind} />
                  <Link href={`/${i.kind}-ideas?idea=${i.id}`} className="min-w-0 flex-1 truncate text-[13px] font-semibold text-text-primary hover:text-accent-secondary">
                    {i.title}
                  </Link>
                </div>
                <p className="mt-1 line-clamp-2 text-xs text-text-muted">{i.concept}</p>
                <div className="mt-2 flex gap-2">
                  <Button size="sm" variant="outline" icon={<Wand2 size={13} />} onClick={() => onPromptIdea(i)}>Generate prompt</Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </QueryView>
    </Panel>
  );
}

function RelatedPanel({ opp }: { opp: Opportunity }) {
  const others = useOpportunities({ category: opp.category ?? undefined, page_size: 4 });
  return (
    <Panel title="Related opportunities">
      <QueryView query={others} loading={<Skeleton lines={2} />} empty={<EmptyState compact title="No related opportunities" />} errorTitle="Unavailable">
        {(page) => (
          <ul className="space-y-1.5">
            {page.data.filter((o) => o.id !== opp.id).slice(0, 3).map((o) => (
              <li key={o.id} className="flex items-center gap-2 text-[13px]">
                <Link href={`/opportunities/${o.id}`} className="min-w-0 flex-1 truncate text-text-secondary hover:text-text-primary">{o.title}</Link>
                <ScoreInline value={o.opportunity_score} />
              </li>
            ))}
          </ul>
        )}
      </QueryView>
    </Panel>
  );
}

function ActivityPanel({ opportunityId }: { opportunityId: string }) {
  const jobs = useAgentJobs({ page_size: 5, sort: "-created_at" });
  return (
    <Panel title="Activity timeline">
      <QueryView query={jobs} loading={<Skeleton lines={3} />} empty={<EmptyState compact title="No activity recorded" />} errorTitle="Activity unavailable">
        {(page) => (
          <ul className="space-y-2 text-[13px]">
            {page.data.map((j) => (
              <li key={j.job_id} className="flex items-center gap-2.5">
                <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-text-muted" aria-hidden />
                <span className="text-text-secondary">{j.agent.replace(/_/g, " ")} — {j.run_kind.replace(/_/g, " ").toLowerCase()}</span>
                <Badge tone={j.status === "succeeded" ? "success" : j.status === "failed" ? "danger" : "muted"}>{j.status}</Badge>
                <span className="ml-auto shrink-0 text-[11px] text-text-muted">{timeAgo(j.created_at)}</span>
              </li>
            ))}
          </ul>
        )}
      </QueryView>
    </Panel>
  );
}

// ---------------------------------------------------------------------------
// Create idea (GATE-02) — form for writing your own idea
// ---------------------------------------------------------------------------

function CreateIdeaModal({ open, onClose, opportunity }: { open: boolean; onClose: () => void; opportunity: Opportunity }) {
  const ideas = useIdeaMutations();
  const [kind, setKind] = useState<"image" | "video">("image");
  const [title, setTitle] = useState("");
  const [concept, setConcept] = useState("");
  const [notes, setNotes] = useState("");

  const save = () => {
    if (!title.trim() || !concept.trim() || !notes.trim()) return;
    ideas.create.mutate(
      {
        opportunity_id: opportunity.id,
        kind,
        title: title.trim(),
        concept: concept.trim(),
        originality_notes: notes.trim(),
      },
      { onSuccess: () => { setTitle(""); setConcept(""); setNotes(""); onClose(); } },
    );
  };

  return (
    <Modal open={open} onClose={onClose} title="Save idea" wide
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button variant="primary" loading={ideas.create.isPending} disabled={!title.trim() || !concept.trim() || !notes.trim()} onClick={save} data-testid="idea-save">
            Save idea
          </Button>
        </>
      }>
      <div className="space-y-3">
        <p className="text-xs text-text-muted">For <strong className="text-text-primary">{opportunity.title}</strong>. Ideas are created by you — the pipeline only refines and screens them.</p>
        <Field label="Format">
          <Select value={kind} onChange={(e) => setKind(e.target.value as "image" | "video")}>
            <option value="image">Image</option>
            <option value="video">Video</option>
          </Select>
        </Field>
        <Field label="Title" required><Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="A working title" /></Field>
        <Field label="Concept" required><Textarea value={concept} onChange={(e) => setConcept(e.target.value)} rows={5} placeholder="Describe the concept: subject, mood, composition, details…" /></Field>
        <Field label="Originality notes" required hint="What makes this angle different — required by the API."><Textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} /></Field>
      </div>
    </Modal>
  );
}

// ---------------------------------------------------------------------------
// Asset analyzer: original prompt generation per opportunity.
// POST /api/asset-analysis/generate → poll the job (same useJobPoll pattern
// as PromptLinkModal) → render the completed analysis verbatim.
// Prompt caching: an existing completed analysis is shown (prefilled) instead
// of regenerating. Never invents content client-side.
// ---------------------------------------------------------------------------

async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    // Fallback for contexts where the async clipboard API is unavailable.
    try {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.setAttribute("readonly", "");
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      ta.setSelectionRange(0, text.length);
      const ok = document.execCommand("copy");
      document.body.removeChild(ta);
      return ok;
    } catch {
      return false;
    }
  }
}

const AA_SIGNAL_TONE: Record<MarketSignalLevel, "success" | "warning" | "muted"> = {
  HIGH: "success",
  MEDIUM: "warning",
  LOW: "muted",
};

const AA_MOMENTUM_TONE: Record<MarketMomentum, "success" | "muted" | "warning" | "danger"> = {
  STRONGLY_RISING: "success",
  RISING: "success",
  STABLE: "muted",
  DECLINING: "warning",
  STRONGLY_DECLINING: "danger",
};

function AaInfoRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-3 py-1 text-[13px]">
      <dt className="w-36 shrink-0 text-text-muted">{label}</dt>
      <dd className="min-w-0 flex-1 text-text-primary">{children}</dd>
    </div>
  );
}

function AaSectionLabel({ children }: { children: React.ReactNode }) {
  return <p className="micro-label mb-2">{children}</p>;
}

function PromptBlock({
  label,
  sub,
  text,
  copyKey,
  copiedKey,
  onCopy,
}: {
  label: string;
  sub: string;
  text: string;
  copyKey: string;
  copiedKey: string | null;
  onCopy: (key: string, text: string, what: string) => void;
}) {
  const copied = copiedKey === copyKey;
  return (
    <div className="rounded-lg border border-border bg-bg-secondary p-3.5">
      <div className="flex items-center justify-between gap-2">
        <p className="micro-label">
          {label} <span className="ml-1 font-normal normal-case tracking-normal text-text-muted">{sub}</span>
        </p>
        <Button
          size="sm"
          variant="outline"
          icon={copied ? <Check size={13} /> : undefined}
          onClick={() => onCopy(copyKey, text, `${label} copied.`)}
        >
          {copied ? "Copied" : "Copy prompt"}
        </Button>
      </div>
      <p className="mt-2 whitespace-pre-wrap text-[13px] leading-relaxed text-text-primary">{text}</p>
    </div>
  );
}

function AssetAnalysisResult({
  analysis,
  copiedKey,
  onCopy,
  onRegenerate,
  regenerating,
}: {
  analysis: AssetAnalysis;
  copiedKey: string | null;
  onCopy: (key: string, text: string, what: string) => void;
  onRegenerate: () => void;
  regenerating: boolean;
}) {
  const mc = analysis.market_context;
  const ca = analysis.commercial_analysis;

  const copyAll = () => {
    const all = [
      "ORIGINAL CONCEPT",
      analysis.original_concept,
      "",
      "PROMPT A — PRIMARY",
      analysis.prompt_a,
      "",
      "PROMPT B — ALTERNATIVE",
      analysis.prompt_b,
      "",
      "PROMPT C — DIFFERENT USE CASE",
      analysis.prompt_c,
      "",
      "NEGATIVE PROMPT",
      analysis.negative_prompt,    ].join("\n");
    onCopy("all", all, "Concept and all prompts copied.");
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-text-muted">
          Viewing existing analysis — generated {timeAgo(analysis.created_at)}. Switch asset type or
          regenerate for a fresh run.
        </p>
        <Button size="sm" variant="outline" loading={regenerating} onClick={onRegenerate}>
          Regenerate
        </Button>
      </div>

      {/* Selected asset */}
      <div>
        <AaSectionLabel>Selected asset</AaSectionLabel>
        <dl className="rounded-lg border border-border bg-bg-secondary px-3.5 py-2">
          <AaInfoRow label="Title">{mc.title}</AaInfoRow>
          <AaInfoRow label="Asset type">
            <Badge tone="accent">{enumLabel(analysis.asset_type)}</Badge>
          </AaInfoRow>
          <AaInfoRow label="Model">{analysis.model}</AaInfoRow>
        </dl>
      </div>

      {/* Market information */}
      <div>
        <AaSectionLabel>Market information</AaSectionLabel>
        <dl className="rounded-lg border border-border bg-bg-secondary px-3.5 py-2">
          <AaInfoRow label="Category">{mc.category}</AaInfoRow>
          <AaInfoRow label="Topic">{mc.topic}</AaInfoRow>
          <AaInfoRow label="7D / 30D signal">
            <span className="flex items-center gap-1">
              <Badge tone={AA_SIGNAL_TONE[mc.signal_7d]}>7D {mc.signal_7d}</Badge>
              <Badge tone={AA_SIGNAL_TONE[mc.signal_30d]}>30D {mc.signal_30d}</Badge>
            </span>
          </AaInfoRow>
          <AaInfoRow label="Momentum">
            <Badge tone={AA_MOMENTUM_TONE[mc.momentum]}>{enumLabel(mc.momentum)}</Badge>
          </AaInfoRow>
          <AaInfoRow label="Source">{mc.source ?? "—"}{mc.source_type ? ` · ${mc.source_type}` : ""}</AaInfoRow>
          <AaInfoRow label="Collected">{mc.collected_at ? timeAgo(mc.collected_at) : "—"}</AaInfoRow>
          <AaInfoRow label="Provenance">
            <ProvenanceBadge provenance={mc.provenance} />
          </AaInfoRow>
        </dl>
      </div>

      {/* Keywords */}
      {(mc.keywords?.length ?? 0) > 0 && (
        <div>
          <AaSectionLabel>Keywords</AaSectionLabel>
          <div className="flex flex-wrap gap-1.5">
            {mc.keywords.map((k) => (
              <span key={k} className="rounded-full bg-text-primary/[0.06] px-2.5 py-1 text-[12px] text-text-secondary">
                {k}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Commercial analysis */}
      <div>
        <AaSectionLabel>Commercial analysis</AaSectionLabel>
        <dl className="rounded-lg border border-border bg-bg-secondary px-3.5 py-2">
          <AaInfoRow label="Topic">{ca.topic}</AaInfoRow>
          <AaInfoRow label="Category">{ca.category}</AaInfoRow>
          <AaInfoRow label="Micro-niche">{ca.micro_niche}</AaInfoRow>
          <AaInfoRow label="Primary keywords">{ca.primary_keywords.join(", ")}</AaInfoRow>
          <AaInfoRow label="Secondary keywords">{ca.secondary_keywords.join(", ")}</AaInfoRow>
          <AaInfoRow label="Commercial use case">{ca.commercial_use_case}</AaInfoRow>
          <AaInfoRow label="Subject">{ca.subject}</AaInfoRow>
          <AaInfoRow label="Environment">{ca.environment}</AaInfoRow>
          <AaInfoRow label="Composition">{ca.composition}</AaInfoRow>
          <AaInfoRow label="Visual characteristics">{ca.visual_characteristics}</AaInfoRow>
          <AaInfoRow label="Content type">{ca.content_type}</AaInfoRow>
        </dl>
      </div>

      {/* Original concept */}
      <div>
        <AaSectionLabel>Original concept</AaSectionLabel>
        <p className="whitespace-pre-wrap rounded-lg border border-border bg-bg-secondary px-3.5 py-3 text-[13px] leading-relaxed text-text-primary">
          {analysis.original_concept}
        </p>
      </div>

      {/* Prompts */}
      <div className="space-y-2.5">
        <div className="flex items-center justify-between">
          <AaSectionLabel>Prompts</AaSectionLabel>
          <Button size="sm" variant="primary" onClick={copyAll}>
            {copiedKey === "all" ? "Copied" : "Copy all"}
          </Button>
        </div>
        <PromptBlock label="Prompt A" sub="primary" text={analysis.prompt_a} copyKey="a" copiedKey={copiedKey} onCopy={onCopy} />
        <PromptBlock label="Prompt B" sub="alternative" text={analysis.prompt_b} copyKey="b" copiedKey={copiedKey} onCopy={onCopy} />
        <PromptBlock label="Prompt C" sub="different use case" text={analysis.prompt_c} copyKey="c" copiedKey={copiedKey} onCopy={onCopy} />
        <PromptBlock label="Negative prompt" sub="" text={analysis.negative_prompt} copyKey="neg" copiedKey={copiedKey} onCopy={onCopy} />
      </div>
    </div>
  );
}

function AssetAnalysisModal({
  open,
  onClose,
  opportunity,
  defaultAssetType = "image",
}: {
  open: boolean;
  onClose: () => void;
  opportunity: Opportunity;
  defaultAssetType?: "image" | "video";
}) {
  const { toast } = useToast();
  const [assetType, setAssetType] = useState<"image" | "video">("image");
  const [jobId, setJobId] = useState<string | null>(null);
  const [failMsg, setFailMsg] = useState<string | null>(null);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const existing = useAssetAnalysis(open ? opportunity.id : null, assetType);
  const gen = useAssetAnalysisGenerate();

  // When opened with a preselected asset type (e.g. from a concept's
  // "Generate prompt" action), apply it and reset transient job state.
  useEffect(() => {
    if (open) {
      setAssetType(defaultAssetType);
      setJobId(null);
      setFailMsg(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, defaultAssetType]);

  const switchAssetType = (v: string) => {
    setAssetType(v as "image" | "video");
    setJobId(null);
    setFailMsg(null);
  };

  // Poll the job the same way other long-running jobs are polled:
  // GET /agents/jobs/{job_id} until terminal. On success the completed analysis is re-read from the
  // by-opportunity cache endpoint (prompt caching); on failure the backend's
  // own error message is shown — never invented here.
  const poll = useJobPoll(jobId, {
    onDone: (job) => {
      setJobId(null);
      if (job.status === "succeeded") {
        toast({ title: "Analysis ready", description: "Original prompts are generated.", tone: "success" });
        void existing.refetch();
      } else {
        setFailMsg(job.error?.message ?? "The backend did not return an error message.");
      }
    },
  });

  const generate = () => {
    if (!open || gen.generate.isPending || poll.isPolling) return;
    setFailMsg(null);
    gen.generate.mutate(
      { opportunity_id: opportunity.id, asset_type: assetType },
      { onSuccess: (r) => setJobId(r.job_id) },
    );
  };

  const copy = async (key: string, text: string, what: string) => {
    const ok = await copyToClipboard(text);
    if (ok) {
      setCopiedKey(key);
      setTimeout(() => setCopiedKey((k) => (k === key ? null : k)), 2000);
      toast({ title: "Copied", description: what, tone: "success", durationMs: 1500 });
    } else {
      toast({ title: "Copy failed", description: "Select and copy the text manually.", tone: "warning" });
    }
  };

  // Prompt caching: a completed analysis is shown (prefilled) instead of
  // regenerating — a fresh run only happens when none exists.
  const completed =
    existing.data && existing.data.status === "completed" && existing.data.prompt_a
      ? existing.data
      : null;
  const running = poll.isPolling || !!jobId;
  const showResult = !running && !failMsg && !!completed;
  const showGenerate = !running && !failMsg && !completed;

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Asset analyzer — original prompts"
      wide
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Close</Button>
          {showGenerate && (
            <Button variant="primary" loading={gen.generate.isPending} onClick={generate} data-testid="asset-analysis-generate">
              Generate original prompt
            </Button>
          )}
        </>
      }
    >
      <div className="space-y-4">
        <Tabs
          tabs={[
            { value: "image", label: "Image" },
            { value: "video", label: "Video" },
          ]}
          value={assetType}
          onChange={switchAssetType}
        />

        {running && (
          <div className="space-y-2.5">
            <p className="text-[13px] text-text-secondary">
              Analyzing market data and generating original prompts…{" "}
              <strong className="tnum text-text-primary">{Math.round((poll.job?.progress ?? 0) * 100)}%</strong>
            </p>
            <Skeleton lines={6} />
          </div>
        )}

        {!running && failMsg && (
          <EmptyState
            title="Generation failed"
            description={failMsg}
            action={
              <Button size="sm" variant="primary" onClick={generate}>
                Try again
              </Button>
            }
          />
        )}

        {!running && !failMsg && existing.isError && (
          <EmptyState
            title="Could not check for an existing analysis"
            description={existing.error?.envelope?.message ?? "Try again."}
            action={
              <Button size="sm" variant="outline" onClick={() => existing.refetch()}>
                Retry
              </Button>
            }
          />
        )}

        {showGenerate && !existing.isError && (
          <div className="space-y-3">
            {existing.isLoading ? (
              <Skeleton lines={3} />
            ) : (
              <p className="text-[13px] leading-relaxed text-text-secondary">
                Generate market-grounded original prompts for{" "}
                <strong className="text-text-primary">{opportunity.title}</strong> ({assetType}). The analyzer
                reads live market signals for this opportunity&rsquo;s category, scores commercial angles, then
                writes an original concept plus three production prompts — concept, Prompt A (primary),
                Prompt B (alternative), Prompt C (different use case), and a negative prompt. Everything
                shown is generated by the backend; nothing is invented in this screen.
              </p>
            )}
          </div>
        )}

        {showResult && completed && (
          <AssetAnalysisResult
            analysis={completed}
            copiedKey={copiedKey}
            onCopy={copy}
            onRegenerate={generate}
            regenerating={gen.generate.isPending}
          />
        )}
      </div>
    </Modal>
  );
}

// ---------------------------------------------------------------------------
// Suspense wrapper — useSearchParams() requires a Suspense boundary during
// prerender (Next.js missing-suspense-with-csr-bailout).
// ---------------------------------------------------------------------------

export default function PageWrapper() {
  return (
    <Suspense fallback={<div className="skeleton h-64 rounded" />}>
      <OpportunityDetailPage />
    </Suspense>
  );
}
