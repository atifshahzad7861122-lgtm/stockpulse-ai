/**
 * Client-safe builders: domain objects → Remotion composition input props.
 * Props must stay JSON-serializable (they travel through the render queue).
 */
import type {
  ConceptPreviewProps,
  ConceptShotInput,
} from "../../remotion/compositions/ConceptPreview";
import type {
  BriefingItemInput,
  DailyBriefingProps,
} from "../../remotion/compositions/DailyBriefing";
import type { DailyProductionResponse, Idea, ProductionRecommendation } from "../../types";
import { fmtDate } from "../../lib/format";

export function conceptShotsFromIdea(idea: Idea): ConceptShotInput[] {
  return (idea.shot_list ?? []).map((s) => ({
    shot: s.shot,
    cameraMove: s.camera_move ?? null,
    durationS: s.duration_s ?? null,
    notes: s.notes ?? null,
  }));
}

export function conceptPropsFromIdea(idea: Idea): ConceptPreviewProps {
  return {
    title: idea.title,
    concept: idea.concept,
    category: idea.category ?? null,
    microNiche: idea.micro_niche ?? null,
    durationTargetSeconds: idea.duration_target_seconds ?? null,
    shots: conceptShotsFromIdea(idea),
  };
}

function briefingItemFromRec(rec: ProductionRecommendation): BriefingItemInput {
  const label = [rec.category, rec.micro_niche_name].filter(Boolean).join(" · ") || "Opportunity";
  return {
    rank: rec.rank,
    assetType: rec.asset_type,
    label,
    reason: rec.reason,
    score: rec.unified_score,
    confidence: rec.confidence,
    personalFit: rec.personal_fit,
    quantity: rec.recommended_quantity,
  };
}

export function briefingPropsFromPlan(dateISO: string, plan: DailyProductionResponse): DailyBriefingProps {
  const items = (plan.recommendations ?? [])
    .filter((r) => r.status !== "rejected" && r.status !== "archived")
    .sort((a, b) => a.rank - b.rank)
    .map(briefingItemFromRec);
  return {
    date: fmtDate(dateISO),
    targetImages: plan.plan?.target_images ?? 0,
    targetVideos: plan.plan?.target_videos ?? 0,
    items,
  };
}
