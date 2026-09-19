/**
 * DailyBriefing — a short MP4 summarizing "WHAT TO CREATE TODAY":
 * the top production recommendations with their scores, confidence,
 * personal fit, and quantities, plus the day's targets. Same design
 * system as the app. Estimates stay labeled as estimates.
 */
import { AbsoluteFill, Easing, Sequence, interpolate, useCurrentFrame } from "remotion";
import {
  C,
  CornerMarks,
  Disclaimer,
  Frame,
  GoldRule,
  KineticWords,
  MicroLabel,
  Rise,
  SERIF,
  Stage,
  TelemetryStrip,
  cameraStyle,
} from "./shared";

export interface BriefingItemInput {
  rank: number;
  assetType: string;
  label: string;
  reason: string;
  score: number;
  confidence: number; // 0..1 or 0..100
  personalFit: number | null;
  quantity: number;
}

export interface DailyBriefingProps {
  date: string;
  targetImages: number;
  targetVideos: number;
  items: BriefingItemInput[];
}

export const BRIEF_INTRO = 90; // 3s
export const BRIEF_ITEM = 105; // 3.5s
export const BRIEF_OUTRO = 105; // 3.5s
const MAX_ITEMS = 6;

function effectiveItems(props: DailyBriefingProps): BriefingItemInput[] {
  return props.items.slice(0, MAX_ITEMS);
}

export function getDailyBriefingFrames(props: DailyBriefingProps): number {
  return BRIEF_INTRO + effectiveItems(props).length * BRIEF_ITEM + BRIEF_OUTRO;
}

function truncate(s: string, n: number): string {
  return s.length > n ? `${s.slice(0, n - 1).trimEnd()}…` : s;
}

function confidencePct(c: number): number {
  const v = c <= 1 ? c * 100 : c;
  return Math.max(0, Math.min(100, v));
}

// ---------------------------------------------------------------------------

function BriefIntro({ props }: { props: DailyBriefingProps }) {
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <Frame />
      <CornerMarks left="Daily briefing" right={props.date} />
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", padding: "0 200px" }}>
        <Rise>
          <MicroLabel color={C.gold}>What to create today</MicroLabel>
        </Rise>
        <div style={{ height: 36 }} />
        <KineticWords text="Daily Briefing" delay={8} fontSize={150} serif />
        <div style={{ height: 44 }} />
        <GoldRule width={260} />
        <div style={{ height: 56 }} />
        <Rise delay={30}>
          <TelemetryStrip
            items={[
              { label: "Date", value: props.date },
              { label: "Plan items", value: String(effectiveItems(props).length).padStart(2, "0") },
              { label: "Targets", value: `${props.targetImages} IMG + ${props.targetVideos} VID` },
            ]}
          />
        </Rise>
      </div>
    </AbsoluteFill>
  );
}

function BriefItem({ item, total }: { item: BriefingItemInput; total: number }) {
  const frame = useCurrentFrame();
  const score = Math.round(
    interpolate(frame, [6, 40], [0, Math.max(0, Math.min(100, item.score))], {
      easing: Easing.out(Easing.cubic),
      extrapolateRight: "clamp",
    }),
  );
  const conf = confidencePct(item.confidence);
  const barW = interpolate(frame, [14, 48], [0, conf], {
    easing: Easing.out(Easing.cubic),
    extrapolateRight: "clamp",
  });
  const progress = Math.max(0, Math.min(1, frame / BRIEF_ITEM));

  return (
    <AbsoluteFill>
      {/* subtle drift backdrop */}
      <AbsoluteFill>
        <div
          style={{
            position: "absolute",
            inset: -120,
            background:
              "radial-gradient(800px 520px at 78% 30%, #16161B 0%, #0D0D10 60%, #0A0A0C 100%)",
            ...cameraStyle("push in", progress),
          }}
        />
      </AbsoluteFill>
      <Frame />
      <CornerMarks
        left={`Item ${String(item.rank).padStart(2, "0")} / ${String(total).padStart(2, "0")}`}
        right={item.assetType.toUpperCase()}
      />

      <div style={{ position: "absolute", left: 130, top: 190, display: "flex", gap: 90, right: 130 }}>
        {/* rank */}
        <div>
          <Rise>
            <MicroLabel color={C.gold}>Rank</MicroLabel>
          </Rise>
          <div
            style={{
              fontFamily: SERIF,
              fontSize: 300,
              lineHeight: 1,
              color: C.gold,
              fontVariantNumeric: "tabular-nums",
              marginTop: 8,
            }}
          >
            {String(item.rank).padStart(2, "0")}
          </div>
        </div>

        {/* what + why */}
        <div style={{ flex: 1, paddingTop: 44, minWidth: 0 }}>
          <Rise delay={6}>
            <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
              <div
                style={{
                  border: `1px solid ${C.gold}`,
                  color: C.goldBright,
                  borderRadius: 999,
                  padding: "8px 20px",
                  fontSize: 24,
                  letterSpacing: "0.2em",
                  fontWeight: 700,
                }}
              >
                {item.assetType.toUpperCase()}
              </div>
              <MicroLabel>{truncate(item.label, 42)}</MicroLabel>
            </div>
          </Rise>
          <div style={{ height: 30 }} />
          <KineticWords text={truncate(item.reason, 170)} delay={14} fontSize={52} />
          <Rise delay={40}>
            <div style={{ marginTop: 34, display: "flex", gap: 56, fontSize: 28 }}>
              <span style={{ color: C.muted }}>
                Personal fit{" "}
                <strong style={{ color: C.text, fontVariantNumeric: "tabular-nums" }}>
                  {item.personalFit === null || item.personalFit === undefined ? "N/A" : Math.round(item.personalFit)}
                </strong>
              </span>
              <span style={{ color: C.muted }}>
                Make{" "}
                <strong style={{ color: C.text, fontVariantNumeric: "tabular-nums" }}>
                  ×{item.quantity}
                </strong>
              </span>
            </div>
          </Rise>
        </div>

        {/* score telemetry */}
        <div style={{ paddingTop: 44, width: 320 }}>
          <Rise delay={10}>
            <MicroLabel>Score</MicroLabel>
          </Rise>
          <div
            style={{
              fontSize: 150,
              fontWeight: 700,
              color: C.text,
              fontVariantNumeric: "tabular-nums",
              letterSpacing: "-0.03em",
              lineHeight: 1.1,
            }}
          >
            {score}
          </div>
          <Rise delay={18}>
            <MicroLabel>Confidence</MicroLabel>
          </Rise>
          <div style={{ marginTop: 14, height: 10, borderRadius: 999, backgroundColor: C.hairline, width: 280 }}>
            <div style={{ height: "100%", borderRadius: 999, backgroundColor: C.gold, width: `${barW}%` }} />
          </div>
          <div style={{ marginTop: 10, fontSize: 30, color: C.secondary, fontVariantNumeric: "tabular-nums" }}>
            {Math.round(conf)}%
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
}

function BriefOutro({ props }: { props: DailyBriefingProps }) {
  const n = effectiveItems(props).length;
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <Frame />
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", padding: "0 200px" }}>
        <Rise>
          <MicroLabel color={C.gold}>Today&rsquo;s plan</MicroLabel>
        </Rise>
        <div style={{ height: 36 }} />
        <KineticWords
          text={`${props.targetImages} images · ${props.targetVideos} videos`}
          delay={8}
          fontSize={104}
          serif
        />
        <div style={{ height: 44 }} />
        <GoldRule width={220} />
        <div style={{ height: 52 }} />
        <Rise delay={28}>
          <TelemetryStrip
            items={[
              { label: "Approved items", value: String(n).padStart(2, "0") },
              { label: "Images", value: String(props.targetImages) },
              { label: "Videos", value: String(props.targetVideos) },
            ]}
          />
        </Rise>
        <div style={{ height: 48 }} />
        <Rise delay={40}>
          <Disclaimer>Scores are estimates — probabilistic, never a guarantee</Disclaimer>
        </Rise>
      </div>
    </AbsoluteFill>
  );
}

// ---------------------------------------------------------------------------

export function DailyBriefing(props: DailyBriefingProps) {
  const items = effectiveItems(props);
  const itemStarts = items.map((_, i) => BRIEF_INTRO + i * BRIEF_ITEM);
  const outroStart = BRIEF_INTRO + items.length * BRIEF_ITEM;

  return (
    <Stage>
      <Sequence from={0} durationInFrames={BRIEF_INTRO} name="Intro">
        <BriefIntro props={props} />
      </Sequence>
      {items.map((item, i) => (
        <Sequence key={item.rank} from={itemStarts[i]} durationInFrames={BRIEF_ITEM} name={`Item ${item.rank}`}>
          <BriefItem item={item} total={items.length} />
        </Sequence>
      ))}
      <Sequence from={outroStart} durationInFrames={BRIEF_OUTRO} name="Outro">
        <BriefOutro props={props} />
      </Sequence>
    </Stage>
  );
}
