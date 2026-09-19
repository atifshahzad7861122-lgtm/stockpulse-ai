/**
 * Remotion entry point — registers the two production compositions.
 * Used by `remotion render` / `remotion studio`. NOT imported by the Next.js
 * app (the app imports the composition components directly for @remotion/player).
 */
import { Composition, registerRoot } from "remotion";
import type { FC } from "react";
import {
  ConceptPreview,
  getConceptPreviewFrames,
  type ConceptPreviewProps,
} from "./compositions/ConceptPreview";
import {
  DailyBriefing,
  getDailyBriefingFrames,
  type DailyBriefingProps,
} from "./compositions/DailyBriefing";
import { FPS, H, W } from "./compositions/shared";

/** Untyped compositions: Remotion's loose component type without a zod schema. */
type AnyPropsComponent = FC<Record<string, unknown>>;
const ConceptPreviewAny = ConceptPreview as unknown as AnyPropsComponent;
const DailyBriefingAny = DailyBriefing as unknown as AnyPropsComponent;

const defaultConceptProps: ConceptPreviewProps = {
  title: "Sample video concept",
  concept: "A sample storyboard previz — replace with a real concept.",
  category: null,
  microNiche: null,
  durationTargetSeconds: 15,
  shots: [
    { shot: "Opening frame: subject enters from the left.", cameraMove: "push in", durationS: 3, notes: null },
    { shot: "Detail pass across the workspace.", cameraMove: "pan right", durationS: 4, notes: null },
  ],
};

const defaultBriefingProps: DailyBriefingProps = {
  date: "Today",
  targetImages: 4,
  targetVideos: 1,
  items: [
    {
      rank: 1,
      assetType: "VIDEO",
      label: "Sample item",
      reason: "Sample briefing item — replace with today's production plan.",
      score: 82,
      confidence: 0.7,
      personalFit: null,
      quantity: 2,
    },
  ],
};

export function RemotionRoot() {
  return (
    <>
      <Composition
        id="ConceptPreview"
        component={ConceptPreviewAny}
        durationInFrames={getConceptPreviewFrames(defaultConceptProps)}
        fps={FPS}
        width={W}
        height={H}
        defaultProps={defaultConceptProps}
        calculateMetadata={({ props }) => ({
          durationInFrames: getConceptPreviewFrames(props as unknown as ConceptPreviewProps),
        })}
      />
      <Composition
        id="DailyBriefing"
        component={DailyBriefingAny}
        durationInFrames={getDailyBriefingFrames(defaultBriefingProps)}
        fps={FPS}
        width={W}
        height={H}
        defaultProps={defaultBriefingProps}
        calculateMetadata={({ props }) => ({
          durationInFrames: getDailyBriefingFrames(props as unknown as DailyBriefingProps),
        })}
      />
    </>
  );
}

registerRoot(RemotionRoot);
