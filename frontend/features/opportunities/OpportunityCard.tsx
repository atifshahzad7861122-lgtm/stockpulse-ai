"use client";
/**
 * Opportunity card — docs/06 §3.7. Used on Dashboard, Daily, Opportunities.
 * Click → opportunity detail; action buttons stop propagation.
 */
import Link from "next/link";
import { Bookmark, Check } from "lucide-react";
import { Badge, Button, Card, WhyThis, cx } from "../../components/ui";
import { ConfidenceMeter, FormatBadge, ProvenanceBadge, ScoreInline, isMock } from "../../components/scores";
import { useLibraryMutations, useOpportunityMutations } from "../../hooks/useApi";
import type { Opportunity } from "../../types";
import { enumLabel } from "../../lib/format";

/** Actionable per CONTRACT §8.2: OS ≥ 55 AND confidence ≥ 0.5 (PC ≥ 35 implied). */
export function isActionable(o: Opportunity): boolean {
  return o.opportunity_score >= 55 && o.confidence >= 0.5;
}

export function OpportunityCard({ opp, rank }: { opp: Opportunity; rank?: number }) {
  const muts = useOpportunityMutations();
  const lib = useLibraryMutations();
  const actionable = isActionable(opp);
  const demo = isMock(opp) || isMock({ provenance: opp.data_provenance });

  return (
    <Card
      className={cx(
        "p-3.5 transition-colors hover:border-text-muted",
        actionable && "border-l-2 border-l-accent-primary",
      )}
    >
      <div className="flex items-start gap-3">
        {rank !== undefined && (
          <span className="font-display text-xl font-semibold text-text-muted" aria-hidden>
            {rank}
          </span>
        )}
        <ScoreInline value={opp.opportunity_score} />
        <div className="min-w-0 flex-1">
          <Link href={`/opportunities/${opp.id}`} className="block truncate text-[13.5px] font-semibold text-text-primary hover:text-accent-secondary">
            {opp.title}
          </Link>
          <p className="mt-0.5 line-clamp-2 text-xs leading-relaxed text-text-muted">{opp.summary}</p>
          <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
            {opp.category && <Badge tone="neutral">{opp.category}</Badge>}
            {opp.micro_niche && <Badge tone="neutral">{opp.micro_niche}</Badge>}
            {(opp.formats ?? []).map((f) => (
              <FormatBadge key={f} format={f} />
            ))}
            <ConfidenceMeter value={opp.confidence} compact />
            <Badge tone={opp.status === "approved" ? "success" : opp.status === "new" ? "info" : "muted"}>
              {enumLabel(opp.status)}
            </Badge>
            <ProvenanceBadge provenance={opp.data_provenance} />
            {demo && <ProvenanceBadge mock />}
            {!actionable && (
              <Badge tone="muted" title="Opportunity score < 55 or confidence < 0.5 — insufficient evidence, do not act (CONTRACT §8.2).">
                Below action bar
              </Badge>
            )}
          </div>
          <WhyThis>
            <p>
              Opportunity score <strong className="text-text-primary">{Math.round(opp.opportunity_score)}</strong> —
              trend × commercial relevance × demand, discounted by saturation (CONTRACT §8.2).
            </p>
            {opp.risk_notes && <p className="mt-1.5">Risk notes: {opp.risk_notes}</p>}
            {opp.demand_evidence.length > 0 && (
              <ul className="mt-1.5 list-disc space-y-0.5 pl-4">
                {opp.demand_evidence.slice(0, 4).map((e, i) => (
                  <li key={i}>{e.note}</li>
                ))}
              </ul>
            )}
            {opp.demand_evidence.length === 0 && (
              <p className="mt-1.5 text-text-muted">No structured evidence rows on this record — open the detail page for the full picture.</p>
            )}
          </WhyThis>
        </div>
        <div className="flex shrink-0 flex-col gap-1" onClick={(e) => e.stopPropagation()}>
          <Button
            size="sm"
            variant="primary"
            icon={<Check size={13} />}
            title="Approve — the human gate to ideation (GATE-02)"
            loading={muts.approve.isPending}
            disabled={opp.status !== "new"}
            onClick={() => muts.approve.mutate({ id: opp.id })}
            data-testid="opportunities-card-approve"
          >
            Approve
          </Button>
          <Button
            size="sm"
            variant="ghost"
            icon={<Bookmark size={13} />}
            title="Save to library"
            loading={lib.save.isPending}
            onClick={() => lib.save.mutate({ item_kind: "OPPORTUNITY", item_id: opp.id })}
          >
            Save
          </Button>
        </div>
      </div>
    </Card>
  );
}
