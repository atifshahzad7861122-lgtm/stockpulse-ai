"use client";
/**
 * Daily Intelligence (Phase 3) — the daily briefing in two moves:
 * MARKET (what's rising) → ACTION (what to create today, approve/reject/archive).
 *
 * Product simplification (2026-09-20): the PERSONAL and FUSION zones are hidden
 * from the rendered UI but their components/files are kept intact.
 *
 * Every backend contract endpoint is optional at render time: missing or
 * unconfigured modules degrade to honest empty/error states, never crashes.
 */
import Link from "next/link";
import { useState } from "react";
import {
  AlertTriangle,
  Archive,
  Check,
  Combine,
  FileDown,
  Flame,
  Lightbulb,
  PersonStanding,
  RefreshCw,
  Hammer,
  Sparkles,
  Target,
  TrendingUp,
  X,
} from "lucide-react";
import {
  Badge,
  Button,
  EmptyState,
  PageHeader,
  Panel,
  QueryView,
  Skeleton,
  Tabs,
  WhyThis,
  cx,
} from "../../components/ui";
import { ConfidenceMeter, FormatBadge, ProvenanceBadge, ScoreInline } from "../../components/scores";
import { MiniBars } from "../../components/charts";
import { motion } from "framer-motion";
import { DUR, EASE_APPLE } from "../../components/motion/easing";
import { RenderVideoButton } from "../../components/remotion/RenderControls";
import { briefingPropsFromPlan } from "../../components/remotion/props";
import {
  CapacitySettingsForm,
  EvidenceList,
  FusionBreakdown,
  FusionLabelBadge,
  PersonalFitChip,
} from "../../components/fusion";
import {
  useConceptMutations,
  useConcepts,
  useContentTypes,
  useDailyMutations,
  useDailyPlan,
  useFusionMutations,
  useFusionScore,
  useOpportunities,
  usePersonalCategories,
  usePersonalPerformance,
  usePersonalThemes,
  useProductionRecommendationMutations,
  useProductionRecommendations,
  usePromptPackCreate,
  useTrends,
} from "../../hooks/useApi";
import { enumLabel, fmtDate, fmtInt, fmtPct01, timeAgo, todayISO } from "../../lib/format";
import type { ConceptVariation, Opportunity, PersonalPeriod, ProductionRecommendation } from "../../types";

// ---------------------------------------------------------------------------
// Section wrapper — lettered, collapsible, self-explaining
// ---------------------------------------------------------------------------

function Zone({
  letter,
  title,
  icon,
  why,
  children,
  loading,
}: {
  letter: string;
  title: string;
  icon: React.ReactNode;
  why: React.ReactNode;
  children: React.ReactNode;
  loading?: boolean;
}) {
  const [open, setOpen] = useState(true);
  return (
    <Panel
      title={
        <button onClick={() => setOpen((o) => !o)} aria-expanded={open} className="flex items-center gap-2">
          <span className="flex h-5 w-5 items-center justify-center rounded bg-accent-primary font-display text-[11px] font-bold text-white">
            {letter}
          </span>
          <span className="flex items-center gap-1.5">{icon}{title}</span>
        </button>
      }
    >
      {open && (
        <div>
          <WhyThis label={`Why this section`}>{why}</WhyThis>
          <div className="mt-3">{loading ? <Skeleton lines={4} /> : children}</div>
        </div>
      )}
    </Panel>
  );
}

const PERIOD_TABS = [
  { value: "7d", label: "7D" },
  { value: "30d", label: "30D" },
  { value: "90d", label: "90D" },
] as const;

// ===========================================================================
// MARKET
// ===========================================================================

function MarketZone() {
  const trends = useTrends({ window: "7d", page_size: 8, sort: "-score" });
  const opps = useOpportunities({ sort: "-opportunity_score", page_size: 8 });

  return (
    <Zone
      letter="A"
      title="Market"
      icon={<Flame size={14} className="text-accent-primary" aria-hidden />}
      why={<p>What is rising out there, regardless of you. Top categories come from the 7-day trend window; top micro-niches from opportunity scores. This is the raw material fusion later blends with your own performance.</p>}
      loading={trends.isLoading || opps.isLoading}
    >
      <div className="grid gap-4 lg:grid-cols-2">
        <div>
          <p className="micro-label mb-2">Top rising categories</p>
          <QueryView query={trends} loading={<Skeleton lines={4} />} empty={<EmptyState compact title="No rising categories" />} errorTitle="Trends unavailable">
            {(page) => (
              <MiniBars rows={page.data.map((t) => ({ label: t.title, value: t.score, color: "#FF5C35" }))} />
            )}
          </QueryView>
        </div>
        <div>
          <p className="micro-label mb-2">Top rising micro-niches</p>
          <QueryView query={opps} loading={<Skeleton lines={4} />} empty={<EmptyState compact title="No opportunities" />} errorTitle="Opportunities unavailable">
            {(page) => (
              <ul className="space-y-2">
                {page.data.slice(0, 6).map((o, i) => (
                  <li key={o.id} className="flex items-center gap-2.5 rounded-md border border-border bg-bg-secondary px-3 py-2">
                    <span className="font-display text-sm font-semibold text-text-muted" aria-hidden>{i + 1}</span>
                    <div className="min-w-0 flex-1">
                      <Link href={`/opportunities/${o.id}`} className="block truncate text-[13px] font-medium text-text-primary hover:text-accent-secondary">
                        {o.title}
                      </Link>
                      <p className="text-[11px] text-text-muted">
                        {o.micro_niche ?? o.category ?? "—"} · <span className="italic">opportunity score, not a sales promise</span>
                      </p>
                    </div>
                    <ScoreInline value={o.opportunity_score} />
                  </li>
                ))}
              </ul>
            )}
          </QueryView>
        </div>
      </div>
    </Zone>
  );
}

// ===========================================================================
// PERSONAL
// ===========================================================================

function PersonalNotConfigured() {
  return (
    <EmptyState
      icon={<PersonStanding size={18} />}
      title="Private performance not connected"
      description={
        <span>
          This zone lights up once your own Adobe Stock performance data is connected — earnings, downloads,
          and acceptance by category. Until then, fusion runs <strong className="text-text-primary">MARKET-ONLY</strong>.
          {' '}<Link href="/private" className="text-accent-secondary hover:underline">Set it up on the Private page</Link>.
        </span>
      }
    />
  );
}

function PersonalZone() {
  const [period, setPeriod] = useState<PersonalPeriod>("30d");
  const perf = usePersonalPerformance(period);
  const cats = usePersonalCategories(period);
  const types = useContentTypes();

  return (
    <Zone
      letter="B"
      title="Personal"
      icon={<PersonStanding size={14} className="text-accent-primary" aria-hidden />}
      why={<p>What already works for <em>you</em>: your own earnings, downloads, acceptance, and momentum by category and format. These numbers come only from your connected Adobe Stock data — they are never invented, and never mixed with market estimates.</p>}
      loading={perf.isLoading || cats.isLoading || types.isLoading}
    >
      <Tabs tabs={PERIOD_TABS.map((t) => ({ value: t.value, label: t.label }))} value={period} onChange={(v) => setPeriod(v as PersonalPeriod)} className="mb-3" />

      <QueryView query={perf} loading={<Skeleton lines={3} />} errorTitle="Personal performance unavailable">
        {(p) => {
          if (p.status !== "available") return <PersonalNotConfigured />;
          const stats = [
            { label: "Earnings", value: p.earnings_total !== null ? `$${fmtInt(p.earnings_total)}` : "—", delta: p.earnings_momentum },
            { label: "Downloads", value: fmtInt(p.downloads_total), delta: p.downloads_momentum },
            { label: "Acceptance rate", value: fmtPct01(p.acceptance_rate), delta: null },
            { label: "Assets tracked", value: fmtInt(p.assets_tracked), delta: null },
          ];
          return (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                {stats.map((s) => (
                  <div key={s.label} className="rounded-lg border border-border bg-bg-secondary p-3">
                    <p className="font-display text-xl font-semibold text-text-primary" style={{ fontVariantNumeric: "tabular-nums" }}>{s.value}</p>
                    <p className="text-[11px] text-text-muted">{s.label}</p>
                    {s.delta !== null && s.delta !== undefined && (
                      <p className={cx("mt-0.5 text-[11px] font-medium", s.delta >= 0 ? "text-status-success" : "text-status-danger")}>
                        {s.delta >= 0 ? "▲" : "▼"} {Math.abs(Math.round(s.delta))}% momentum
                      </p>
                    )}
                    <ProvenanceBadge provenance={p.provenance} mock={p.mock} />
                  </div>
                ))}
              </div>
              {(p.top_categories?.length ?? 0) > 0 && (
                <div>
                  <p className="micro-label mb-2">Best categories for you</p>
                  <MiniBars rows={p.top_categories.slice(0, 6).map((c) => ({ label: c.category, value: c.earnings, color: "#22C55E", suffix: "$" }))} />
                </div>
              )}
              {p.updated_at && <p className="text-[11px] text-text-muted">Updated {timeAgo(p.updated_at)}</p>}
            </div>
          );
        }}
      </QueryView>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <QueryView query={types} loading={<Skeleton lines={3} />} errorTitle="Format comparison unavailable">
          {(t) => {
            if (t.status !== "available" || !t.types.length) return <PersonalNotConfigured />;
            return (
              <div>
                <p className="micro-label mb-2">Image vs video — your own results</p>
                <div className="grid grid-cols-2 gap-3">
                  {t.types.map((x) => (
                    <div key={x.content_type} className="rounded-lg border border-border bg-bg-secondary p-3">
                      <p className="text-xs font-semibold uppercase tracking-[0.06em] text-text-secondary">{x.content_type}</p>
                      <p className="mt-1 font-display text-lg font-semibold text-text-primary" style={{ fontVariantNumeric: "tabular-nums" }}>
                        ${fmtInt(x.earnings)} <span className="text-xs font-normal text-text-muted">· {fmtInt(x.downloads)} downloads</span>
                      </p>
                      <p className="mt-1 text-[11px] text-text-muted">
                        {fmtInt(x.assets_total)} assets · {fmtPct01(x.acceptance_rate)} accepted · {fmtInt(x.avg_earnings_per_asset ?? null)}$/asset avg
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            );
          }}
        </QueryView>
        <QueryView query={cats} loading={<Skeleton lines={3} />} errorTitle="Category detail unavailable">
          {(r) => {
            if (r.status !== "available" || !r.categories.length) return <PersonalNotConfigured />;
            const sorted = [...r.categories].sort((a, b) => b.earnings - a.earnings).slice(0, 5);
            return (
              <div>
                <p className="micro-label mb-2">Top categories by earnings ({period})</p>
                <MiniBars rows={sorted.map((c) => ({ label: c.category, value: c.earnings, color: "#38BDF8", suffix: "$" }))} />
              </div>
            );
          }}
        </QueryView>
      </div>
    </Zone>
  );
}

// ===========================================================================
// FUSION
// ===========================================================================

function FusionRow({ opp }: { opp: Opportunity }) {
  const [open, setOpen] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const fusion = useFusionScore(open ? opp.id : null);
  const muts = useFusionMutations();

  return (
    <div className="rounded-lg border border-border bg-bg-secondary">
      <button onClick={() => setOpen((o) => !o)} aria-expanded={open} className="flex w-full items-center gap-3 px-3 py-2.5 text-left">
        <ScoreInline value={opp.opportunity_score} />
        <div className="min-w-0 flex-1">
          <p className="truncate text-[13px] font-semibold text-text-primary">{opp.title}</p>
          <p className="text-[11px] text-text-muted">
            {opp.micro_niche ?? opp.category ?? "—"} · market score — fusion adds your personal fit
          </p>
        </div>
        {(opp.formats ?? []).map((f) => <FormatBadge key={f} format={f} />)}
        {fusion.data && <FusionLabelBadge label={fusion.data.label} />}
        <span className={cx("text-[11px] font-medium text-accent-secondary", !open && "whitespace-nowrap")}>
          {open ? "Hide fusion" : "Show fusion"}
        </span>
      </button>
      {open && (
        <div className="border-t border-border px-3 py-3">
          <QueryView
            query={fusion}
            loading={<Skeleton lines={5} />}
            empty={
              <EmptyState
                compact
                title="No fusion score computed yet"
                description="Compute one — it blends this market opportunity with your personal performance history (or runs market-only if that is not connected)."
                action={<Button size="sm" variant="primary" loading={muts.compute.isPending} onClick={() => muts.compute.mutate(opp.id)}>Compute fusion score</Button>}
              />
            }
            errorTitle="Fusion score unavailable"
          >
            {(f) => (
              <div className="grid gap-3 md:grid-cols-2">
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
                  </div>
                  {(f.evidence?.length ?? 0) > 0 && (
                    <div>
                      <p className="micro-label mb-1.5">Evidence</p>
                      <EvidenceList evidence={f.evidence} />
                    </div>
                  )}
                  <div className="flex gap-2">
                    <Button size="sm" variant="outline" loading={muts.compute.isPending} onClick={() => muts.compute.mutate(opp.id)}>
                      Recompute
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => setExpanded(true)}>Full detail</Button>
                  </div>
                </div>
              </div>
            )}
          </QueryView>
          {expanded && fusion.data && (
            <WhyThis label="Why this">
              <p>Full breakdown is shown above; open the <Link href={`/opportunities/${opp.id}`} className="text-accent-secondary hover:underline">opportunity detail page</Link> for evidence provenance, predictions, and production recommendations.</p>
            </WhyThis>
          )}
        </div>
      )}
    </div>
  );
}

function FusionZone() {
  const opps = useOpportunities({ sort: "-opportunity_score", page_size: 6 });
  return (
    <Zone
      letter="C"
      title="Fusion"
      icon={<Combine size={14} className="text-accent-primary" aria-hidden />}
      why={<p>Market opportunity × your personal fit. Each row computes a unified score from market signals and — when connected — your own performance history. Personal fit is never invented: without private data the score is honestly labeled MARKET-ONLY.</p>}
      loading={opps.isLoading}
    >
      <QueryView query={opps} loading={<div className="space-y-2">{[0, 1].map((i) => <Skeleton key={i} className="h-14" />)}</div>} empty={<EmptyState compact title="No opportunities to fuse" />} errorTitle="Opportunities unavailable">
        {(page) => (
          <div className="space-y-2">
            {page.data.map((o) => <FusionRow key={o.id} opp={o} />)}
          </div>
        )}
      </QueryView>
    </Zone>
  );
}

// ===========================================================================
// ACTION — WHAT TO CREATE TODAY
// ============================================================================

const REC_STATUS_TONE: Record<ProductionRecommendation["status"], "muted" | "info" | "success" | "warning" | "neutral"> = {
  recommended: "warning",
  approved: "success",
  rejected: "muted",
  archived: "neutral",
};

const COMPLIANCE_TONE: Record<string, "success" | "warning" | "danger" | "neutral"> = {
  PASS: "success",
  REVIEW: "warning",
  HIGH_RISK: "danger",
};

function ConceptCard({ recId, concept }: { recId: string; concept: ConceptVariation }) {
  const muts = useConceptMutations();
  const packCreate = usePromptPackCreate();
  const [showFindings, setShowFindings] = useState(false);
  const busy = muts.update.isPending || packCreate.isPending;
  const findings = (concept.compliance_result_json?.findings ?? []).filter((f) => f.triggered);
  const simFlags = concept.similarity_flags_json?.flags ?? [];
  const blocked = concept.compliance_result === "HIGH_RISK";

  return (
    <div className="rounded-lg border border-border bg-bg-tertiary p-3">
      <div className="flex flex-wrap items-start gap-2">
        <div className="min-w-0 flex-1">
          <p className="text-[13px] font-medium text-text-primary">{concept.title}</p>
          <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
            <Badge tone={COMPLIANCE_TONE[concept.compliance_result ?? ""] ?? "neutral"}>
              Compliance: {concept.compliance_result ?? "unscreened"}
            </Badge>
            <Badge tone="neutral">{enumLabel(concept.status)}</Badge>
            <Badge tone="neutral">Round {concept.variation_round}</Badge>
            {concept.ai_disclosure === null || concept.ai_disclosure === undefined ? (
              <Badge tone="warning" title="The AI-disclosure decision has not been recorded yet.">Disclosure: not recorded</Badge>
            ) : (
              <Badge tone={concept.ai_disclosure ? "success" : "neutral"}>
                Disclosure: {concept.ai_disclosure ? "will disclose as AI-generated" : "not AI-generated"}
              </Badge>
            )}
            {simFlags.map((f, i) => (
              <Badge key={i} tone={f.flag === "HIGH_SIMILARITY" || f.flag === "POSSIBLE_DUPLICATE" ? "danger" : "warning"}>
                {f.flag.replace(/_/g, " ")}
              </Badge>
            ))}
          </div>
        </div>
      </div>
      {concept.originality_notes && (
        <p className="mt-2 text-[12px] leading-relaxed text-text-muted">{concept.originality_notes}</p>
      )}
      {findings.length > 0 && (
        <button
          onClick={() => setShowFindings((s) => !s)}
          aria-expanded={showFindings}
          className="mt-2 text-[12px] text-text-muted underline-offset-2 hover:text-text-secondary hover:underline"
        >
          {showFindings ? "Hide findings" : `Compliance findings (${findings.length})`}
        </button>
      )}
      {showFindings && (
        <ul className="mt-2 space-y-1.5">
          {findings.map((f) => (
            <li key={f.rule_key} className="rounded-md bg-bg-secondary p-2 text-[12px]">
              <span className="font-semibold text-text-primary">{f.rule_key}</span>
              <span className="text-text-secondary"> — {f.explanation}</span>
              {f.remediation && <span className="block text-text-muted">Fix: {f.remediation}</span>}
            </li>
          ))}
        </ul>
      )}
      <div className="mt-2.5 flex flex-wrap gap-1.5">
        {(concept.ai_disclosure === null || concept.ai_disclosure === undefined) && (
          <Button
            size="sm"
            variant="outline"
            disabled={busy}
            loading={muts.update.isPending}
            onClick={() => muts.update.mutate({ recId, conceptId: concept.id, body: { status: concept.status, ai_disclosure: true } })}
            title="Record that the produced asset will be disclosed as AI-generated at submission, then re-screen."
          >
            Record AI disclosure
          </Button>
        )}
        {!blocked && concept.status !== "approved" && (
          <Button
            size="sm"
            variant="primary"
            icon={<Check size={13} />}
            disabled={busy}
            loading={muts.update.isPending}
            onClick={() => muts.update.mutate({ recId, conceptId: concept.id, body: { status: "approved" } })}
          >
            Approve concept
          </Button>
        )}
        {concept.status !== "archived" && (
          <Button
            size="sm"
            variant="ghost"
            icon={<Archive size={13} />}
            disabled={busy}
            onClick={() => muts.update.mutate({ recId, conceptId: concept.id, body: { status: "archived" } })}
          >
            Archive
          </Button>
        )}
        {(concept.status === "approved" || concept.compliance_result === "PASS") && (
          <Button
            size="sm"
            variant="outline"
            icon={<FileDown size={13} />}
            disabled={busy}
            loading={packCreate.isPending}
            onClick={() => packCreate.mutate({ conceptId: concept.id, target_tool: "muse" })}
            title="Build an export-only prompt pack from this concept. Nothing auto-generates."
          >
            Create prompt pack
          </Button>
        )}
      </div>
    </div>
  );
}

function ConceptsSection({ recId }: { recId: string }) {
  const [open, setOpen] = useState(false);
  const concepts = useConcepts(open ? recId : null);
  const muts = useConceptMutations();
  const rows = concepts.data ?? [];

  return (
    <div className="mt-3 border-t border-border pt-3">
      <button
        onClick={() => setOpen((s) => !s)}
        aria-expanded={open}
        className="flex items-center gap-2 text-[12px] font-medium text-text-secondary hover:text-text-primary"
      >
        <Lightbulb size={13} className="text-accent-primary" aria-hidden />
        {open ? "Hide concepts" : `Concepts${rows.length ? ` (${rows.length})` : ""}`}
      </button>
      {open && (
        <div className="mt-2.5 space-y-2.5">
          <QueryView
            query={concepts}
            loading={<Skeleton lines={2} />}
            empty={
              <EmptyState
                compact
                title="No concepts yet"
                description="Generate distinct, screened concept variations for this recommendation."
                action={
                  <Button size="sm" variant="primary" loading={muts.generate.isPending} onClick={() => muts.generate.mutate({ recId, count: 3 })}>
                    Generate concepts
                  </Button>
                }
              />
            }
            errorTitle="Concepts unavailable"
          >
            {(list) => (
              <>
                {list.map((c) => (
                  <ConceptCard key={c.id} recId={recId} concept={c} />
                ))}
                <div className="flex items-center justify-between gap-2">
                  <p className="text-[11px] text-text-muted">
                    Screening is advisory — it does not guarantee Adobe acceptance.
                  </p>
                  <Button size="sm" variant="ghost" loading={muts.generate.isPending} onClick={() => muts.generate.mutate({ recId, count: 3 })}>
                    Regenerate
                  </Button>
                </div>
              </>
            )}
          </QueryView>
        </div>
      )}
    </div>
  );
}

function RecommendationCard({ rec }: { rec: ProductionRecommendation }) {
  const [showEvidence, setShowEvidence] = useState(false);
  const muts = useProductionRecommendationMutations();
  const busy = muts.approve.isPending || muts.reject.isPending || muts.archive.isPending;

  return (
    <motion.li
      layout
      variants={{
        hidden: { opacity: 0, y: 10 },
        show: { opacity: 1, y: 0, transition: { duration: DUR.med, ease: EASE_APPLE } },
      }}
      transition={{ layout: { duration: DUR.med, ease: EASE_APPLE } }}
      className="rounded-lg border border-border bg-bg-secondary p-3.5"
    >
      <div className="flex flex-wrap items-start gap-3">
        <span className="font-display text-2xl font-semibold text-accent-primary" style={{ fontVariantNumeric: "tabular-nums" }} aria-hidden>
          {rec.rank}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <Badge tone="accent">{rec.asset_type.toUpperCase()}</Badge>
            {rec.category && <Badge tone="neutral">{rec.category}</Badge>}
            {rec.micro_niche_name && <Badge tone="info">{rec.micro_niche_name}</Badge>}
            <Badge tone={REC_STATUS_TONE[rec.status]}>{enumLabel(rec.status)}</Badge>
          </div>
          <p className="mt-1.5 text-[13px] leading-relaxed text-text-secondary">{rec.reason}</p>
          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[12px]">
            <span className="text-text-secondary">Score <strong className="text-text-primary" style={{ fontVariantNumeric: "tabular-nums" }}>{Math.round(rec.unified_score)}</strong></span>
            {rec.personal_fit === null || rec.personal_fit === undefined ? (
              <span className="text-text-muted">Personal fit: N/A — private data not connected</span>
            ) : (
              <span className="text-text-secondary">Personal fit <strong className="text-text-primary">{Math.round(rec.personal_fit)}</strong></span>
            )}
            <span className="flex items-center gap-1.5"><ConfidenceMeter value={rec.confidence} compact /></span>
            <span className="text-text-secondary">Make <strong className="text-text-primary" style={{ fontVariantNumeric: "tabular-nums" }}>{rec.recommended_quantity}</strong></span>
            {rec.opportunity_id && (
              <Link href={`/opportunities/${rec.opportunity_id}`} className="text-accent-secondary hover:underline">Open opportunity</Link>
            )}
            {(rec.evidence?.length ?? 0) > 0 && (
              <button onClick={() => setShowEvidence((s) => !s)} aria-expanded={showEvidence} className="text-text-muted underline-offset-2 hover:text-text-secondary hover:underline">
                {showEvidence ? "Hide evidence" : `Why? (${rec.evidence!.length} signals)`}
              </button>
            )}
          </div>
          {showEvidence && (
            <div className="mt-2.5">
              <EvidenceList evidence={rec.evidence} />
            </div>
          )}
        </div>
        <div className="flex shrink-0 gap-1.5">
          {rec.status === "recommended" && (
            <>
              <Button size="sm" variant="primary" icon={<Check size={13} />} loading={muts.approve.isPending} disabled={busy} onClick={() => muts.approve.mutate(rec.id)}>
                Approve
              </Button>
              <Button size="sm" variant="outline" icon={<X size={13} />} loading={muts.reject.isPending} disabled={busy} onClick={() => muts.reject.mutate({ id: rec.id })}>
                Reject
              </Button>
            </>
          )}
          {rec.status !== "archived" && (
            <Button size="sm" variant="ghost" icon={<Archive size={13} />} loading={muts.archive.isPending} disabled={busy} onClick={() => muts.archive.mutate(rec.id)}>
              Archive
            </Button>
          )}
        </div>
      </div>
      <ConceptsSection recId={rec.id} />
    </motion.li>
  );
}

function ActionZone() {
  const date = todayISO();
  const plan = useDailyPlan(date);
  const recs = useProductionRecommendations();
  const muts = useDailyMutations();
  const recMuts = useProductionRecommendationMutations();

  return (
    <Zone
      letter="D"
      title="Action — what to create today"
      icon={<Target size={14} className="text-accent-primary" aria-hidden />}
      why={<p>The plan, not the scoreboard. Ranked by unified fusion score against your capacity — every item shows its score, personal fit (or an honest N/A), confidence, the reason, and the evidence behind the reason. Nothing is auto-queued: you approve each item.</p>}
      loading={plan.isLoading}
    >
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <span className="text-[13px] text-text-secondary">
          Plan for <strong className="text-text-primary">{fmtDate(date)}</strong>
          {plan.data?.plan && (
            <> · target <strong className="text-text-primary" style={{ fontVariantNumeric: "tabular-nums" }}>{plan.data.plan.target_images} images + {plan.data.plan.target_videos} videos</strong> · {enumLabel(plan.data.plan.status)}</>
          )}
        </span>
        <span className="ml-auto flex flex-wrap items-center gap-2">
          <Button size="sm" variant="primary" icon={<Hammer size={13} />} loading={muts.build.isPending} onClick={() => muts.build.mutate(date)} data-testid="daily-build-plan">
            Build / refresh plan
          </Button>
          {plan.data && (plan.data.recommendations?.length ?? 0) > 0 && (
            <RenderVideoButton
              kind="briefing"
              label={`Daily briefing — ${date}`}
              props={briefingPropsFromPlan(date, plan.data)}
              idleLabel="Render briefing"
            />
          )}
        </span>
      </div>

      <QueryView query={plan} loading={<div className="space-y-2">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-20" />)}</div>} errorTitle="Today's plan unavailable">
        {(p) => {
          const items = p.recommendations ?? [];
          if (!items.length) {
            return (
              <EmptyState
                icon={<Target size={18} />}
                title="No production plan for today yet"
                description="Build one — the planner ranks fused opportunities against your capacity settings. If the backend module is not deployed yet, this is where it will appear."
                action={<Button variant="primary" size="sm" icon={<Hammer size={13} />} loading={muts.build.isPending} onClick={() => muts.build.mutate(date)}>Build today&rsquo;s plan</Button>}
              />
            );
          }
          return (
            <motion.ol
              className="space-y-2.5"
              initial="hidden"
              animate="show"
              variants={{
                hidden: {},
                show: { transition: { staggerChildren: 0.04, delayChildren: 0.03 } },
              }}
            >
              {items.map((r) => <RecommendationCard key={r.id} rec={r} />)}
            </motion.ol>
          );
        }}
      </QueryView>

      <div className="mt-4">
        <p className="micro-label mb-2">All recommendations</p>
        <QueryView query={recs} loading={<Skeleton lines={2} />} empty={<EmptyState compact title="No recommendations" />} errorTitle="Recommendations unavailable">
          {(rows) => {
            const pending = rows.filter((r) => r.status === "recommended").length;
            return (
              <p className="text-[13px] text-text-secondary">
                <strong className="text-text-primary" style={{ fontVariantNumeric: "tabular-nums" }}>{rows.length}</strong> total ·{" "}
                <strong className="text-text-primary" style={{ fontVariantNumeric: "tabular-nums" }}>{pending}</strong> pending decision ·{" "}
                <strong className="text-text-primary" style={{ fontVariantNumeric: "tabular-nums" }}>{rows.filter((r) => r.status === "approved").length}</strong> approved
              </p>
            );
          }}
        </QueryView>
      </div>
    </Zone>
  );
}

// ===========================================================================
// Page
// ===========================================================================

export default function DailyPage() {
  return (
    <div className="space-y-4">
      <PageHeader
        title="Daily Intelligence"
        description="Market → Action. Two zones, one flow: see what's rising, then approve today's production plan. (Personal performance and fusion scoring were part of the product before 2026-09-20; the underlying code is kept but the zones are hidden.)"
        badge={<Badge tone="accent">Phase 3</Badge>}
      />
      <MarketZone />
      {/*
        Product simplification (2026-09-20): the Personal performance, Personal
        fit, and Opportunity Fusion zones are hidden from the UI — the page is
        now Market → Action only. The underlying components (PersonalZone,
        FusionZone, and their supporting hooks/queries) are intentionally kept
        so the feature can be re-enabled without re-writing.
      */}
      {false && <PersonalZone />}
      {false && <FusionZone />}
      <ActionZone />
      <CapacitySettingsForm />
      <p className="flex items-start gap-2 text-xs text-text-muted">
        <AlertTriangle size={13} className="mt-0.5 shrink-0" aria-hidden />
        Every score on this page is an estimate from observed signals — an opportunity, never a guarantee.
        Fusion scores marked MARKET-ONLY do not use your private data because it is not connected.
      </p>
    </div>
  );
}
