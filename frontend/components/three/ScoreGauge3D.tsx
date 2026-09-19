"use client";
/**
 * ScoreGauge3D — a precision-instrument dial for a single score.
 * 270° champagne-gold arc, tick ring, needle. The numeral itself is HTML
 * (Didone serif for hero moments). Static geometry — no animation loop cost.
 */
import { useMemo } from "react";
import { Canvas } from "@react-three/fiber";
import * as THREE from "three";
import { GOLD, GOLD_BRIGHT } from "../palette";

const START = Math.PI * 0.75; // 135° — gauge zero at lower-left
const SWEEP = Math.PI * 1.5; // 270°

function Ticks() {
  const ticks = useMemo(() => {
    const arr: { pos: [number, number, number]; rot: number }[] = [];
    for (let i = 0; i <= 20; i++) {
      const a = (i / 20) * SWEEP; // relative — parent group applies START
      const major = i % 5 === 0;
      const r1 = major ? 1.18 : 1.28;
      const r2 = 1.46;
      arr.push({
        pos: [Math.cos(a) * ((r1 + r2) / 2), Math.sin(a) * ((r1 + r2) / 2), 0],
        rot: a,
      });
    }
    return arr;
  }, []);
  return (
    <group>
      {ticks.map((t, i) => (
        <mesh key={i} position={t.pos} rotation={[0, 0, t.rot - Math.PI / 2]}>
          <boxGeometry args={[0.035, i % 5 === 0 ? 0.28 : 0.18, 0.02]} />
          <meshBasicMaterial color={i % 5 === 0 ? "#5A5A62" : "#333338"} />
        </mesh>
      ))}
    </group>
  );
}

function Gauge({ value }: { value: number }) {
  const v = Math.max(0, Math.min(100, value));
  const arc = (v / 100) * SWEEP;
  const trackGeo = useMemo(
    () => new THREE.TorusGeometry(1.32, 0.075, 16, 96, SWEEP),
    [],
  );
  const valueGeo = useMemo(
    () => new THREE.TorusGeometry(1.32, 0.075, 16, Math.max(8, Math.round(96 * (v / 100))), Math.max(0.02, arc)),
    [arc, v],
  );
  // One rotation: torus arcs start at +X, so rotate the whole dial by START.
  return (
    <group rotation={[0, 0, START]}>
      <mesh geometry={trackGeo}>
        <meshStandardMaterial color="#232328" roughness={0.6} metalness={0.4} />
      </mesh>
      <mesh geometry={valueGeo}>
        <meshStandardMaterial color={GOLD} emissive={GOLD_BRIGHT} emissiveIntensity={0.55} roughness={0.3} metalness={0.6} />
      </mesh>
      {/* needle */}
      <group rotation={[0, 0, arc]}>
        <mesh position={[0.62, 0, 0.02]}>
          <boxGeometry args={[1.05, 0.045, 0.03]} />
          <meshBasicMaterial color="#F5F3EE" />
        </mesh>
        <mesh position={[0, 0, 0.03]} rotation={[Math.PI / 2, 0, 0]}>
          <cylinderGeometry args={[0.09, 0.09, 0.06, 24]} />
          <meshStandardMaterial color={GOLD} roughness={0.3} metalness={0.7} />
        </mesh>
      </group>
      <Ticks />
      {/* end caps at 0 and SWEEP (relative) */}
      {[0, SWEEP].map((a, i) => (
        <mesh key={i} position={[Math.cos(a) * 1.32, Math.sin(a) * 1.32, 0]}>
          <sphereGeometry args={[0.075, 16, 12]} />
          <meshBasicMaterial color={i === 0 ? "#3A3A40" : GOLD} />
        </mesh>
      ))}
    </group>
  );
}

export function ScoreGauge3D({
  value,
  height = 190,
}: {
  value: number;
  height?: number;
}) {
  return (
    <div className="relative mx-auto w-full max-w-[280px]" style={{ height }}>
      <Canvas
        dpr={[1, 1.5]}
        camera={{ position: [0, 0, 4.6], fov: 42 }}
        gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
        onCreated={({ gl }) => gl.setClearColor("#000000", 0)}
      >
        <ambientLight intensity={0.7} />
        <directionalLight position={[3, 4, 5]} intensity={1.2} />
        <Gauge value={value} />
      </Canvas>
      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
        <span className="tnum font-display text-[44px] font-medium leading-none text-text-primary">
          {Math.round(value)}
        </span>
        <span className="mt-1 text-[10px] font-semibold uppercase tracking-[0.2em] text-text-muted">/ 100</span>
      </div>
    </div>
  );
}
