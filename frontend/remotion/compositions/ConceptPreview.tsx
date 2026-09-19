/**
 * ConceptPreview — storyboard-style motion preview for a video concept.
 * Built from the concept's own fields: title, concept, category, target
 * duration, and the shot list (shot / camera_move / duration_s / notes).
 * Each shot beat animates a previz suggestion of its camera move over a
 * dark stage panel — kinetic typography carries the shot description.
 * This is a planning previz, never presented as final footage.
 */
import { AbsoluteFill, Sequence, useCurrentFrame, useVideoConfig } from "remotion";
import {
  C,
  CornerMarks,
  Disclaimer,
  FPS,
  Frame,
  GoldRule,
  KineticWords,
  MicroLabel,
  Rise,
  SERIF,
  Stage,
  TelemetryStrip,
  cameraLabel,
  cameraStyle,
} from "./shared";

export interface ConceptShotInput {
  shot: string;
  cameraMove?: string | null;
  durationS?: number | null;
  notes?: string | null;
}

export interface ConceptPreviewProps {
  title: string;
  concept: string;
  category?: string | null;
  microNiche?: string | null;
  durationTargetSeconds?: number | null;
  shots: ConceptShotInput[];
}

export const INTRO_FRAMES = 75; // 2.5s
export const OUTRO_FRAMES = 75; // 2.5s

export function shotFrames(s: ConceptShotInput): number {
  const d = s.durationS ?? 3;
  return Math.max(60, Math.min(180, Math.round(d * FPS)));
}

function effectiveShots(props: ConceptPreviewProps): ConceptShotInput[] {
  return props.shots.length
    ? props.shots
    : [
        {
          shot: "No shot list yet — add shots to this concept to preview the full sequence.",
          cameraMove: null,
          durationS: 3,
          notes: null,
        },
      ];
}

export function getConceptPreviewFrames(props: ConceptPreviewProps): number {
  const shots = effectiveShots(props);
  return INTRO_FRAMES + shots.reduce((a, s) => a + shotFrames(s), 0) + OUTRO_FRAMES;
}

function truncate(s: string, n: number): string {
  return s.length > n ? `${s.slice(0, n - 1).trimEnd()}…` : s;
}

// ---------------------------------------------------------------------------

function IntroScene({ props, shotCount }: { props: ConceptPreviewProps; shotCount: number }) {
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <Frame />
      <CornerMarks left="Concept preview" right="Storyboard" />
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", padding: "0 200px" }}>
        <Rise>
          <MicroLabel color={C.gold}>Video concept</MicroLabel>
        </Rise>
        <div style={{ height: 36 }} />
        <KineticWords text={truncate(props.title, 72)} delay={8} fontSize={118} serif />
        <div style={{ height: 44 }} />
        <GoldRule width={260} />
        <div style={{ height: 56 }} />
        <Rise delay={26}>
          <TelemetryStrip
            items={[
              { label: "Shots", value: String(shotCount).padStart(2, "0") },
              { label: "Target", value: props.durationTargetSeconds ? `${props.durationTargetSeconds}s` : "—" },
              { label: "Category", value: (props.category ?? props.microNiche ?? "—").toUpperCase().slice(0, 18) },
            ]}
          />
        </Rise>
      </div>
    </AbsoluteFill>
  );
}

function ShotScene({
  shot,
  index,
  total,
  durationInFrames,
}: {
  shot: ConceptShotInput;
  index: number;
  total: number;
  durationInFrames: number;
}) {
  const frame = useCurrentFrame();
  const progress = Math.max(0, Math.min(1, frame / Math.max(1, durationInFrames)));
  const num = String(index + 1).padStart(2, "0");
  const totalStr = String(total).padStart(2, "0");

  return (
    <AbsoluteFill>
      {/* previz backdrop — camera-move suggestion, not footage */}
      <AbsoluteFill>
        <div
          style={{
            position: "absolute",
            inset: -160,
            background:
              "radial-gradient(900px 600px at 32% 24%, #1E1E24 0%, #101013 55%, #0A0A0C 100%)",
            ...cameraStyle(shot.cameraMove, progress),
          }}
        >
          <div
            style={{
              position: "absolute",
              right: 120,
              bottom: 40,
              fontFamily: SERIF,
              fontSize: 560,
              lineHeight: 1,
              color: "rgba(214,178,94,0.07)",
              userSelect: "none",
            }}
          >
            {num}
          </div>
          {/* faint telemetry grid */}
          <div
            style={{
              position: "absolute",
              inset: 0,
              backgroundImage:
                "linear-gradient(rgba(255,255,255,0.035) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.035) 1px, transparent 1px)",
              backgroundSize: "120px 120px",
            }}
          />
        </div>
      </AbsoluteFill>

      <Frame />
      <CornerMarks left={`Shot ${num} / ${totalStr}`} right={cameraLabel(shot.cameraMove)} />

      {/* duration chip */}
      <div style={{ position: "absolute", top: 110, right: 72 }}>
        <Rise delay={6}>
          <div
            style={{
              border: `1px solid ${C.hairline}`,
              backgroundColor: "rgba(20,20,23,0.85)",
              borderRadius: 999,
              padding: "10px 22px",
              fontSize: 24,
              letterSpacing: "0.18em",
              fontWeight: 600,
              color: C.goldBright,
              fontVariantNumeric: "tabular-nums",
            }}
          >
            {(shot.durationS ?? 3).toFixed(1)}S
          </div>
        </Rise>
      </div>

      {/* shot description — kinetic */}
      <div style={{ position: "absolute", left: 120, right: 120, bottom: 150 }}>
        <Rise delay={4}>
          <MicroLabel color={C.gold}>Action</MicroLabel>
        </Rise>
        <div style={{ height: 28 }} />
        <KineticWords text={truncate(shot.shot, 170)} delay={10} fontSize={60} />
        {shot.notes ? (
          <Rise delay={30}>
            <div style={{ marginTop: 30, fontSize: 30, color: C.secondary, maxWidth: 1400, lineHeight: 1.5 }}>
              {truncate(shot.notes, 180)}
            </div>
          </Rise>
        ) : null}
      </div>
    </AbsoluteFill>
  );
}

function OutroScene({ props }: { props: ConceptPreviewProps }) {
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <Frame />
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", padding: "0 200px" }}>
        <GoldRule width={200} />
        <div style={{ height: 40 }} />
        <Rise delay={8}>
          <Disclaimer>Previz — not final footage</Disclaimer>
        </Rise>
        <div style={{ height: 32 }} />
        <KineticWords text={truncate(props.title, 64)} delay={14} fontSize={64} serif color={C.secondary} />
        <div style={{ height: 40 }} />
        <Rise delay={34}>
          <div style={{ fontSize: 28, color: C.muted, maxWidth: 1200, textAlign: "center", lineHeight: 1.6 }}>
            {truncate(props.concept, 200)}
          </div>
        </Rise>
      </div>
    </AbsoluteFill>
  );
}

// ---------------------------------------------------------------------------

export function ConceptPreview(props: ConceptPreviewProps) {
  const { fps } = useVideoConfig();
  void fps;
  const shots = effectiveShots(props);
  let cursor = 0;
  const shotStarts = shots.map((s) => {
    const start = cursor + INTRO_FRAMES;
    cursor += shotFrames(s);
    return start;
  });
  const outroStart = INTRO_FRAMES + cursor;

  return (
    <Stage>
      <Sequence from={0} durationInFrames={INTRO_FRAMES} name="Intro">
        <IntroScene props={props} shotCount={shots.length} />
      </Sequence>
      {shots.map((s, i) => (
        <Sequence key={i} from={shotStarts[i]} durationInFrames={shotFrames(s)} name={`Shot ${i + 1}`}>
          <ShotScene shot={s} index={i} total={shots.length} durationInFrames={shotFrames(s)} />
        </Sequence>
      ))}
      <Sequence from={outroStart} durationInFrames={OUTRO_FRAMES} name="Outro">
        <OutroScene props={props} />
      </Sequence>
    </Stage>
  );
}
