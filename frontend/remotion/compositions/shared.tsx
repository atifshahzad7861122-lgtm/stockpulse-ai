/**
 * Shared design language for Remotion compositions.
 * Same system as the app: deep-black stage, champagne-gold accents,
 * telemetry typography (uppercase micro-labels, tabular numerals),
 * Didone serif reserved for hero moments. Inline styles only — the
 * Remotion bundle does not process Tailwind.
 */
import { AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import type { CSSProperties, ReactNode } from "react";

export const FPS = 30;
export const W = 1920;
export const H = 1080;

export const C = {
  bg: "#0A0A0C",
  panel: "#141417",
  panel2: "#1B1B20",
  hairline: "#242428",
  gold: "#D6B25E",
  goldBright: "#E9CE8F",
  text: "#F5F3EE",
  secondary: "#A9A49A",
  muted: "#6F6A60",
  red: "#E10600",
  success: "#34D399",
} as const;

export const SERIF = `"Bodoni Moda", Georgia, "Times New Roman", serif`;
export const SANS = `Inter, system-ui, -apple-system, "Segoe UI", sans-serif`;

export function Stage({ children }: { children: ReactNode }) {
  return (
    <AbsoluteFill style={{ backgroundColor: C.bg, color: C.text, fontFamily: SANS, overflow: "hidden" }}>
      {children}
    </AbsoluteFill>
  );
}

export function MicroLabel({ children, color = C.muted }: { children: ReactNode; color?: string }) {
  return (
    <div
      style={{
        fontSize: 26,
        letterSpacing: "0.32em",
        fontWeight: 600,
        color,
        textTransform: "uppercase",
      }}
    >
      {children}
    </div>
  );
}

export function GoldRule({ width = 220 }: { width?: number }) {
  const frame = useCurrentFrame();
  const w = interpolate(frame, [0, 18], [0, width], {
    easing: Easing.out(Easing.cubic),
    extrapolateRight: "clamp",
  });
  return (
    <div style={{ height: 3, width: w, backgroundColor: C.gold }} />
  );
}

/** Fade-and-rise entrance used across scenes. */
export function Rise({
  children,
  delay = 0,
  distance = 36,
  style,
}: {
  children: ReactNode;
  delay?: number;
  distance?: number;
  style?: CSSProperties;
}) {
  const frame = useCurrentFrame();
  const t = interpolate(frame, [delay, delay + 22], [0, 1], {
    easing: Easing.out(Easing.cubic),
    extrapolateRight: "clamp",
  });
  return (
    <div
      style={{
        opacity: t,
        transform: `translateY(${(1 - t) * distance}px)`,
        ...style,
      }}
    >
      {children}
    </div>
  );
}

/** Kinetic typography — words stagger upward inside a clipped line box. */
export function KineticWords({
  text,
  delay = 0,
  fontSize = 54,
  color = C.text,
  maxWidth = 1500,
  serif = false,
}: {
  text: string;
  delay?: number;
  fontSize?: number;
  color?: string;
  maxWidth?: number;
  serif?: boolean;
}) {
  const words = text.split(/\s+/).filter(Boolean);
  return (
    <div style={{ maxWidth, overflow: "hidden" }}>
      {words.map((w, i) => (
        <Word key={i} word={w} index={i} delay={delay} fontSize={fontSize} color={color} serif={serif} />
      ))}
    </div>
  );
}

function Word({
  word,
  index,
  delay,
  fontSize,
  color,
  serif,
}: {
  word: string;
  index: number;
  delay: number;
  fontSize: number;
  color: string;
  serif: boolean;
}) {
  const frame = useCurrentFrame();
  const t = interpolate(frame, [delay + index * 2.2, delay + index * 2.2 + 16], [0, 1], {
    easing: Easing.out(Easing.cubic),
    extrapolateRight: "clamp",
  });
  return (
    <span
      style={{
        display: "inline-block",
        overflow: "hidden",
        verticalAlign: "bottom",
        paddingBottom: "0.12em",
        marginBottom: "-0.12em",
      }}
    >
      <span
        style={{
          display: "inline-block",
          fontSize,
          lineHeight: 1.25,
          color,
          fontFamily: serif ? SERIF : SANS,
          fontWeight: serif ? 500 : 600,
          letterSpacing: serif ? "0.01em" : "-0.01em",
          opacity: t,
          transform: `translateY(${(1 - t) * 110}%)`,
          marginRight: "0.28em",
          fontVariantNumeric: "tabular-nums",
        }}
      >
        {word}
      </span>
    </span>
  );
}

/**
 * Simulated camera move on a backdrop panel — a previz suggestion of the
 * shot's camera_move, not real footage. progress is 0..1 across the beat.
 */
export function cameraStyle(move: string | null | undefined, progress: number): CSSProperties {
  const m = (move ?? "").toLowerCase();
  const p = Math.max(0, Math.min(1, progress));
  const ease = Easing.out(Easing.cubic);
  // normalize eased progress manually via interpolate below per-axis
  if (/pull|zoom out|dolly out|reveal/.test(m)) {
    return { transform: `scale(${1.18 - 0.18 * ease(p)})` };
  }
  if (/pan left/.test(m)) {
    return { transform: `translateX(${-70 + 140 * ease(p)}px) scale(1.12)` };
  }
  if (/pan right/.test(m)) {
    return { transform: `translateX(${70 - 140 * ease(p)}px) scale(1.12)` };
  }
  if (/pan/.test(m)) {
    return { transform: `translateX(${-70 + 140 * ease(p)}px) scale(1.12)` };
  }
  if (/tilt up/.test(m)) {
    return { transform: `translateY(${-50 + 100 * ease(p)}px) scale(1.12)` };
  }
  if (/tilt down/.test(m)) {
    return { transform: `translateY(${50 - 100 * ease(p)}px) scale(1.12)` };
  }
  if (/tilt/.test(m)) {
    return { transform: `translateY(${-50 + 100 * ease(p)}px) scale(1.12)` };
  }
  if (/orbit|arc|crane|gimbal/.test(m)) {
    return {
      transform: `translateX(${-60 + 120 * ease(p)}px) scale(${1.06 + 0.1 * ease(p)})`,
    };
  }
  if (/static|locked|tripod/.test(m)) {
    return { transform: `scale(${1 + 0.03 * ease(p)})` };
  }
  // default: gentle push-in
  return { transform: `scale(${1 + 0.1 * ease(p)})` };
}

export function cameraLabel(move: string | null | undefined): string {
  const m = (move ?? "").trim();
  return m ? m.toUpperCase() : "CAMERA —";
}

/** Telemetry strip: label/value pairs along the bottom. */
export function TelemetryStrip({ items }: { items: { label: string; value: string }[] }) {
  const frame = useCurrentFrame();
  const t = interpolate(frame, [0, 16], [0, 1], {
    easing: Easing.out(Easing.cubic),
    extrapolateRight: "clamp",
  });
  return (
    <div
      style={{
        display: "flex",
        gap: 64,
        opacity: t,
        transform: `translateY(${(1 - t) * 16}px)`,
      }}
    >
      {items.map((it) => (
        <div key={it.label}>
          <div style={{ fontSize: 22, letterSpacing: "0.22em", color: C.muted, fontWeight: 600 }}>{it.label}</div>
          <div
            style={{
              fontSize: 40,
              fontWeight: 700,
              color: C.text,
              marginTop: 6,
              fontVariantNumeric: "tabular-nums",
              letterSpacing: "-0.01em",
            }}
          >
            {it.value}
          </div>
        </div>
      ))}
    </div>
  );
}

/** Hairline frame inset — the "precision instrument" border. */
export function Frame() {
  const frame = useCurrentFrame();
  const t = interpolate(frame, [0, 20], [0, 1], {
    easing: Easing.out(Easing.cubic),
    extrapolateRight: "clamp",
  });
  return (
    <div
      style={{
        position: "absolute",
        inset: 36,
        border: `1px solid ${C.hairline}`,
        opacity: 0.35 + 0.65 * t,
        pointerEvents: "none",
      }}
    />
  );
}

/** Corner telemetry marks. */
export function CornerMarks({ left, right }: { left: string; right: string }) {
  return (
    <>
      <div style={{ position: "absolute", top: 58, left: 72 }}>
        <MicroLabel>{left}</MicroLabel>
      </div>
      <div style={{ position: "absolute", top: 58, right: 72 }}>
        <MicroLabel>{right}</MicroLabel>
      </div>
    </>
  );
}

export function useBeatProgress(startFrame: number, durationInFrames: number): number {
  const frame = useCurrentFrame();
  return Math.max(0, Math.min(1, (frame - startFrame) / Math.max(1, durationInFrames)));
}

export function Disclaimer({ children }: { children: ReactNode }) {
  return (
    <div
      style={{
        fontSize: 24,
        letterSpacing: "0.28em",
        color: C.muted,
        fontWeight: 600,
        textTransform: "uppercase",
      }}
    >
      {children}
    </div>
  );
}
