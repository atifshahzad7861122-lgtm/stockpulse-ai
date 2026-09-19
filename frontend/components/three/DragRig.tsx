"use client";
/**
 * DragRig — hand-rolled bounded rotation for 3D scenes (no drei).
 * Drag horizontally to orbit, vertically to tilt within limits.
 * Pointer events only; no auto-rotation (calm, battery-friendly).
 */
import { useEffect, useRef, type ReactNode } from "react";
import { useThree } from "@react-three/fiber";
import * as THREE from "three";

export function DragRig({
  children,
  initial = [-0.42, -0.55, 0],
  minX = -1.15,
  maxX = 0.15,
}: {
  children: ReactNode;
  initial?: [number, number, number];
  minX?: number;
  maxX?: number;
}) {
  const group = useRef<THREE.Group>(null);
  const { gl } = useThree();
  const drag = useRef<{ sx: number; sy: number; rx: number; ry: number } | null>(null);

  useEffect(() => {
    const el = gl.domElement;
    const down = (e: PointerEvent) => {
      drag.current = {
        sx: e.clientX,
        sy: e.clientY,
        rx: group.current?.rotation.x ?? initial[0],
        ry: group.current?.rotation.y ?? initial[1],
      };
      el.setPointerCapture(e.pointerId);
    };
    const move = (e: PointerEvent) => {
      const d = drag.current;
      if (!d || !group.current) return;
      const dx = e.clientX - d.sx;
      const dy = e.clientY - d.sy;
      group.current.rotation.y = d.ry + dx * 0.006;
      group.current.rotation.x = Math.min(maxX, Math.max(minX, d.rx + dy * 0.006));
    };
    const up = () => {
      drag.current = null;
    };
    el.addEventListener("pointerdown", down);
    el.addEventListener("pointermove", move);
    el.addEventListener("pointerup", up);
    el.addEventListener("pointercancel", up);
    return () => {
      el.removeEventListener("pointerdown", down);
      el.removeEventListener("pointermove", move);
      el.removeEventListener("pointerup", up);
      el.removeEventListener("pointercancel", up);
    };
  }, [gl, initial, minX, maxX]);

  return (
    <group ref={group} rotation={initial}>
      {children}
    </group>
  );
}
