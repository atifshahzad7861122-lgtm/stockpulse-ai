"use client";
/**
 * OpportunitySpace — opportunities as points in 3D space.
 *   X = market opportunity (opportunity score)
 *   Y = personal fit (null → rests on the N/A shelf: private data not connected)
 *   Z = commercial potential (null → N/A shelf)
 *   Size = confidence · Color = saturation risk (semantic: gold open →
 *   steel moderate → amber crowded → racing-red saturated).
 * Drag to orbit. Click a point to open the opportunity. Dark stage,
 * champagne-gold + telemetry palette only — no rainbow point clouds.
 */
import { useMemo, useRef, useState } from "react";
import { Canvas, type ThreeEvent } from "@react-three/fiber";
import * as THREE from "three";
import { DragRig } from "./DragRig";
import {
  GOLD,
  GOLD_BRIGHT,
  STEEL,
  TEXT_MUTED,
  saturationColor,
} from "../palette";
import { saturationBand } from "../../lib/scores";

export interface SpacePoint {
  id: string;
  title: string;
  x: number;
  y: number | null;
  z: number | null;
  size: number; // confidence 0..1
  saturation: number | null;
}

const NA = -14; // N/A shelf position (below the 0..100 stage)

function Stage() {
  const edges = useMemo(() => {
    const g = new THREE.BoxGeometry(100, 100, 100);
    return new THREE.EdgesGeometry(g);
  }, []);
  const ticks = useMemo(() => {
    // tick marks every 25 along X and Z at floor level
    const pts: number[] = [];
    for (let i = 0; i <= 100; i += 25) {
      pts.push(i, 0, -2, i, 0, 2); // X axis ticks (at z=0 plane edge)
      pts.push(-2, 0, i, 2, 0, i); // Z axis ticks
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(pts, 3));
    return g;
  }, []);
  const axes = useMemo(() => {
    const g = new THREE.BufferGeometry();
    g.setAttribute(
      "position",
      new THREE.Float32BufferAttribute(
        [
          0, 0, 0, 104, 0, 0, // X — market opportunity (gold)
          0, 0, 0, 0, 104, 0, // Y — personal fit (steel)
          0, 0, 0, 0, 0, 104, // Z — commercial (muted)
        ],
        3,
      ),
    );
    g.setAttribute(
      "color",
      new THREE.Float32BufferAttribute(
        [0.84, 0.7, 0.37, 0.84, 0.7, 0.37, 0.6, 0.58, 0.54, 0.6, 0.58, 0.54, 0.44, 0.42, 0.38, 0.44, 0.42, 0.38],
        3,
      ),
    );
    return g;
  }, []);
  const shelf = useMemo(() => {
    const g = new THREE.PlaneGeometry(100, 100, 12, 12);
    return g;
  }, []);
  return (
    <group position={[50, 0, 50]}>
      {/* stage wireframe */}
      <lineSegments geometry={edges} position={[0, 50, 0]}>
        <lineBasicMaterial color="#2E2E33" transparent opacity={0.9} />
      </lineSegments>
      {/* floor grid */}
      <gridHelper args={[100, 10, "#3A3A40", "#232328"]} position={[0, 0.1, 0]} />
      <lineSegments geometry={ticks} position={[0, 0.1, 0]}>
        <lineBasicMaterial color="#4A4A52" />
      </lineSegments>
      {/* axes */}
      <lineSegments geometry={axes}>
        <lineBasicMaterial vertexColors />
      </lineSegments>
      {/* N/A shelf — personal fit / commercial unknown rest here */}
      <mesh geometry={shelf} rotation={[-Math.PI / 2, 0, 0]} position={[0, NA, 0]}>
        <meshBasicMaterial color="#1A1A1E" wireframe transparent opacity={0.55} />
      </mesh>
      <mesh geometry={shelf} rotation={[-Math.PI / 2, 0, Math.PI / 2]} position={[0, 0, NA]}>
        <meshBasicMaterial color="#1A1A1E" wireframe transparent opacity={0.35} />
      </mesh>
    </group>
  );
}

function Points({
  points,
  onHover,
  onSelect,
}: {
  points: SpacePoint[];
  onHover: (p: SpacePoint | null, e?: { x: number; y: number }) => void;
  onSelect: (id: string) => void;
}) {
  const geo = useMemo(() => new THREE.SphereGeometry(1, 20, 16), []);
  const [active, setActive] = useState<string | null>(null);
  return (
    <group position={[50, 0, 50]}>
      {points.map((p) => {
        const y = p.y === null ? NA : p.y;
        const z = p.z === null ? NA : p.z;
        const r = 1.6 + Math.max(0, Math.min(1, p.size)) * 2.6;
        const color = saturationColor(p.saturation);
        const hollow = p.y === null || p.z === null;
        const isActive = active === p.id;
        return (
          <mesh
            key={p.id}
            geometry={geo}
            position={[p.x, y, z]}
            scale={isActive ? r * 1.35 : r}
            onPointerOver={(e: ThreeEvent<PointerEvent>) => {
              e.stopPropagation();
              setActive(p.id);
              onHover(p, { x: e.nativeEvent.clientX, y: e.nativeEvent.clientY });
              document.body.style.cursor = "pointer";
            }}
            onPointerMove={(e: ThreeEvent<PointerEvent>) => {
              onHover(p, { x: e.nativeEvent.clientX, y: e.nativeEvent.clientY });
            }}
            onPointerOut={() => {
              setActive(null);
              onHover(null);
              document.body.style.cursor = "";
            }}
            onClick={(e: ThreeEvent<MouseEvent>) => {
              e.stopPropagation();
              onSelect(p.id);
            }}
          >
            {hollow ? (
              <meshBasicMaterial color={STEEL} wireframe transparent opacity={0.8} />
            ) : (
              <meshStandardMaterial
                color={color}
                emissive={color === GOLD ? GOLD_BRIGHT : color}
                emissiveIntensity={color === GOLD ? 0.35 : 0.12}
                roughness={0.35}
                metalness={0.55}
              />
            )}
          </mesh>
        );
      })}
    </group>
  );
}

export function OpportunitySpace({
  points,
  onSelect,
  height = 420,
}: {
  points: SpacePoint[];
  onSelect: (id: string) => void;
  height?: number;
}) {
  const wrap = useRef<HTMLDivElement>(null);
  const [hover, setHover] = useState<{ p: SpacePoint; x: number; y: number } | null>(null);

  const onHover = (p: SpacePoint | null, e?: { x: number; y: number }) => {
    if (!p || !e || !wrap.current) {
      setHover(null);
      return;
    }
    const r = wrap.current.getBoundingClientRect();
    setHover({ p, x: e.x - r.left, y: e.y - r.top });
  };

  return (
    <div ref={wrap} className="relative" style={{ height }}>
      <Canvas
        dpr={[1, 1.5]}
        camera={{ position: [150, 105, 185], fov: 38, near: 1, far: 1200 }}
        gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
        onCreated={({ gl }) => gl.setClearColor("#000000", 0)}
      >
        <ambientLight intensity={0.55} />
        <directionalLight position={[80, 140, 60]} intensity={1.4} />
        <pointLight position={[-40, 60, -40]} intensity={0.4} color={GOLD} />
        <DragRig initial={[-0.42, -0.5, 0]}>
          <Stage />
          <Points points={points} onHover={onHover} onSelect={onSelect} />
        </DragRig>
      </Canvas>

      {/* hover readout */}
      {hover && (
        <div
          className="depth-2 pointer-events-none absolute z-10 w-56 rounded-lg border border-border bg-surface-elevated p-2.5"
          style={{ left: Math.min(hover.x + 14, (wrap.current?.clientWidth ?? 300) - 232), top: Math.max(hover.y - 10, 8) }}
        >
          <p className="truncate text-[12px] font-bold text-text-primary">{hover.p.title}</p>
          <dl className="tnum mt-1.5 space-y-0.5 text-[11px]">
            <div className="flex justify-between"><dt className="text-text-muted">Market opportunity</dt><dd className="font-bold text-text-primary">{Math.round(hover.p.x)}</dd></div>
            <div className="flex justify-between"><dt className="text-text-muted">Personal fit</dt><dd className="font-bold text-text-primary">{hover.p.y === null ? "N/A" : Math.round(hover.p.y)}</dd></div>
            <div className="flex justify-between"><dt className="text-text-muted">Commercial</dt><dd className="font-bold text-text-primary">{hover.p.z === null ? "N/A" : Math.round(hover.p.z)}</dd></div>
            <div className="flex justify-between"><dt className="text-text-muted">Confidence</dt><dd className="font-bold text-text-primary">{Math.round(hover.p.size * 100)}%</dd></div>
            <div className="flex justify-between"><dt className="text-text-muted">Saturation</dt><dd className="font-bold" style={{ color: saturationColor(hover.p.saturation) }}>{hover.p.saturation === null ? "—" : `${saturationBand(hover.p.saturation)} · ${Math.round(hover.p.saturation)}`}</dd></div>
          </dl>
          {hover.p.y === null && <p className="mt-1.5 text-[10px] text-text-muted">On the N/A shelf — private data not connected.</p>}
        </div>
      )}

      {/* axis legend */}
      <div className="pointer-events-none absolute bottom-2 left-3 flex flex-wrap gap-x-4 gap-y-1 text-[10px] font-semibold uppercase tracking-[0.08em]">
        <span style={{ color: GOLD }}>X · Market opportunity</span>
        <span style={{ color: STEEL }}>Y · Personal fit</span>
        <span style={{ color: TEXT_MUTED }}>Z · Commercial</span>
        <span className="text-text-muted normal-case tracking-normal">drag to orbit · click a point to open</span>
      </div>
    </div>
  );
}
