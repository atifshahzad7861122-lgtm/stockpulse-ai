"use client";
/**
 * Inline composition previews via @remotion/player.
 * The Player plays the composition live in the browser — no render needed,
 * no queue, no Chrome. Rendering to MP4 is a separate explicit action
 * (see RenderControls).
 */
import dynamic from "next/dynamic";
import type { CSSProperties } from "react";
import {
  ConceptPreview,
  getConceptPreviewFrames,
  type ConceptPreviewProps,
} from "../../remotion/compositions/ConceptPreview";
import {
  DailyBriefing,
  getDailyBriefingFrames,
  type DailyBriefingProps,
} from "../../remotion/compositions/DailyBriefing";

const Player = dynamic(() => import("@remotion/player").then((m) => m.Player), {
  ssr: false,
  loading: () => (
    <div className="skeleton flex h-48 items-center justify-center rounded-xl text-xs text-text-muted">
      Loading preview…
    </div>
  ),
});

type AnyPropsComponent = (props: Record<string, unknown>) => JSX.Element;
const ConceptPreviewAny = ConceptPreview as unknown as AnyPropsComponent;
const DailyBriefingAny = DailyBriefing as unknown as AnyPropsComponent;

const frameStyle: CSSProperties = {
  width: "100%",
  aspectRatio: "16 / 9",
  borderRadius: 12,
  overflow: "hidden",
  border: "1px solid #242428",
  backgroundColor: "#0A0A0C",
};

export function ConceptPlayer({ input }: { input: ConceptPreviewProps }) {
  return (
    <Player
      component={ConceptPreviewAny}
      inputProps={input}
      durationInFrames={getConceptPreviewFrames(input)}
      compositionWidth={1920}
      compositionHeight={1080}
      fps={30}
      controls
      clickToPlay
      acknowledgeRemotionLicense
      style={frameStyle}
    />
  );
}

export function BriefingPlayer({ input }: { input: DailyBriefingProps }) {
  return (
    <Player
      component={DailyBriefingAny}
      inputProps={input}
      durationInFrames={getDailyBriefingFrames(input)}
      compositionWidth={1920}
      compositionHeight={1080}
      fps={30}
      controls
      clickToPlay
      acknowledgeRemotionLicense
      style={frameStyle}
    />
  );
}
