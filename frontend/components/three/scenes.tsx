"use client";
/**
 * 3D scene entry points. Every scene is:
 *  - lazy-loaded via next/dynamic with ssr:false (code-split, no SSR cost),
 *  - gated on useRender3D() — WebGL + no prefers-reduced-motion,
 *  - given an explicit 2D fallback rendered otherwise.
 * Pages use these, never the raw R3F components.
 */
import dynamic from "next/dynamic";
import type { ReactNode } from "react";
import { useRender3D } from "./webgl";
import type { SpacePoint } from "./OpportunitySpace";
import type { TerrainRidge } from "./TrendTerrain";

const LazyOpportunitySpace = dynamic(
  () => import("./OpportunitySpace").then((m) => ({ default: m.OpportunitySpace })),
  { ssr: false },
);
const LazyTrendTerrain = dynamic(
  () => import("./TrendTerrain").then((m) => ({ default: m.TrendTerrain })),
  { ssr: false },
);
const LazyScoreGauge = dynamic(
  () => import("./ScoreGauge3D").then((m) => ({ default: m.ScoreGauge3D })),
  { ssr: false },
);

function SceneShell({
  fallback,
  children,
  label,
}: {
  fallback: ReactNode;
  children: ReactNode;
  label: string;
}) {
  const ok = useRender3D();
  if (!ok) return <>{fallback}</>;
  return (
    <div role="img" aria-label={label}>
      {children}
    </div>
  );
}

export function OpportunitySpaceScene({
  points,
  onSelect,
  height,
  fallback,
  label,
}: {
  points: SpacePoint[];
  onSelect: (id: string) => void;
  height?: number;
  fallback: ReactNode;
  label: string;
}) {
  return (
    <SceneShell fallback={fallback} label={label}>
      <LazyOpportunitySpace points={points} onSelect={onSelect} height={height} />
    </SceneShell>
  );
}

export function TrendTerrainScene({
  ridges,
  height,
  fallback,
  label,
}: {
  ridges: TerrainRidge[];
  height?: number;
  fallback: ReactNode;
  label: string;
}) {
  return (
    <SceneShell fallback={fallback} label={label}>
      <LazyTrendTerrain ridges={ridges} height={height} />
    </SceneShell>
  );
}

export function ScoreGaugeScene({
  value,
  height,
  fallback,
  label,
}: {
  value: number;
  height?: number;
  fallback: ReactNode;
  label: string;
}) {
  return (
    <SceneShell fallback={fallback} label={label}>
      <LazyScoreGauge value={value} height={height} />
    </SceneShell>
  );
}

export type { SpacePoint, TerrainRidge };
