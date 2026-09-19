"use client";
/**
 * TrendTerrain — momentum as terrain. X = time, each ridge = one series,
 * height = value. Ridges are each scaled to their own peak (shape, not
 * scale — the legend says so) so series in different units stay comparable.
 * Dark stage, champagne-gold wireframe, telemetry ridge colors. Drag to orbit.
 */
import { useMemo } from "react";
import { Canvas } from "@react-three/fiber";
import * as THREE from "three";
import { DragRig } from "./DragRig";
import { GOLD } from "../palette";

export interface TerrainRidge {
  name: string;
  values: number[];
  color: string;
}

const W = 46;
const D = 20;
const H = 13;

function buildTerrain(ridges: TerrainRidge[]): THREE.BufferGeometry | null {
  const n = ridges[0]?.values.length ?? 0;
  const m = ridges.length;
  if (n < 2 || m < 1) return null;
  const positions: number[] = [];
  const indices: number[] = [];
  const peaks = ridges.map((r) => Math.max(1e-6, ...r.values.map((v) => Math.abs(v))));
  for (let j = 0; j < m; j++) {
    for (let i = 0; i < n; i++) {
      const x = (i / (n - 1) - 0.5) * W;
      const z = m === 1 ? 0 : (j / (m - 1) - 0.5) * D;
      const y = (Math.abs(ridges[j].values[i]) / peaks[j]) * H;
      positions.push(x, y, z);
    }
  }
  for (let j = 0; j < m - 1; j++) {
    for (let i = 0; i < n - 1; i++) {
      const a = j * n + i;
      const b = a + 1;
      const c = a + n;
      const d = c + 1;
      indices.push(a, c, b, b, c, d);
    }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  g.setIndex(indices);
  g.computeVertexNormals();
  return g;
}

function ridgeLineObject(ridge: TerrainRidge, z: number, peak: number): THREE.Line {
  const n = ridge.values.length;
  const pts = ridge.values.map((v, i) => {
    const x = (i / (n - 1) - 0.5) * W;
    const y = (Math.abs(v) / peak) * H + 0.12;
    return new THREE.Vector3(x, y, z);
  });
  return new THREE.Line(
    new THREE.BufferGeometry().setFromPoints(pts),
    new THREE.LineBasicMaterial({ color: ridge.color }),
  );
}

function Terrain({ ridges }: { ridges: TerrainRidge[] }) {
  const geo = useMemo(() => buildTerrain(ridges), [ridges]);
  const lines = useMemo(() => {
    const m = ridges.length;
    const peaks = ridges.map((r) => Math.max(1e-6, ...r.values.map((v) => Math.abs(v))));
    return ridges.map((r, j) =>
      ridgeLineObject(r, m === 1 ? 0 : (j / (m - 1) - 0.5) * D, peaks[j]),
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ridges]);
  const floor = useMemo(() => {
    const g = new THREE.BufferGeometry();
    const pts: number[] = [];
    const n = ridges[0]?.values.length ?? 2;
    for (let i = 0; i < n; i++) {
      const x = (i / (n - 1) - 0.5) * W;
      pts.push(x, 0, -D / 2, x, 0, D / 2);
    }
    g.setAttribute("position", new THREE.Float32BufferAttribute(pts, 3));
    return g;
  }, [ridges]);

  if (!geo) return null;
  return (
    <group>
      <mesh geometry={geo}>
        <meshStandardMaterial color="#101013" roughness={0.9} metalness={0.15} />
      </mesh>
      <mesh geometry={geo}>
        <meshBasicMaterial color={GOLD} wireframe transparent opacity={0.14} />
      </mesh>
      <lineSegments geometry={floor}>
        <lineBasicMaterial color="#232328" transparent opacity={0.8} />
      </lineSegments>
      {lines.map((l, i) => (
        <primitive key={i} object={l} />
      ))}
    </group>
  );
}

export function TrendTerrain({
  ridges,
  height = 300,
}: {
  ridges: TerrainRidge[];
  height?: number;
}) {
  if (!ridges.length || ridges.some((r) => r.values.length < 2)) {
    return (
      <p className="py-8 text-center text-xs text-text-muted">
        Not enough dated points to build terrain — the line view needs at least two points per series.
      </p>
    );
  }
  return (
    <div className="relative" style={{ height }}>
      <Canvas
        dpr={[1, 1.5]}
        camera={{ position: [0, 30, 48], fov: 40, near: 1, far: 800 }}
        gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
        onCreated={({ gl }) => gl.setClearColor("#000000", 0)}
      >
        <ambientLight intensity={0.6} />
        <directionalLight position={[20, 40, 20]} intensity={1.3} />
        <pointLight position={[-20, 12, 10]} intensity={0.5} color={GOLD} />
        <DragRig initial={[-0.52, 0, 0]} minX={-1.2} maxX={-0.12}>
          <Terrain ridges={ridges} />
        </DragRig>
      </Canvas>
      <div className="pointer-events-none absolute bottom-2 left-3 flex flex-wrap gap-x-4 gap-y-1 text-[10px] font-semibold uppercase tracking-[0.08em]">
        {ridges.map((r) => (
          <span key={r.name} style={{ color: r.color }}>
            — {r.name}
          </span>
        ))}
        <span className="text-text-muted normal-case tracking-normal">each ridge scaled to its own peak · drag to orbit</span>
      </div>
    </div>
  );
}
