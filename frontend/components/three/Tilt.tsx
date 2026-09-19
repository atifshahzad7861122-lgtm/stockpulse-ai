"use client";
/**
 * Tilt — subtle physical tilt on hover (max ~3.5°), driven by Motion springs
 * for a buttery, Apple-grade feel, plus a specular sheen that follows the
 * pointer like light on brushed metal. Disabled under
 * prefers-reduced-motion, coarse pointers, and touch — the content is
 * identical without it. Tasteful depth, never gimmick.
 */
import { motion, useMotionTemplate, useMotionValue, useSpring, useTransform } from "framer-motion";
import { useEffect, type CSSProperties, type ReactNode } from "react";
import { cx } from "../ui";
import { usePrefersReducedMotion } from "./webgl";

export function Tilt({
  children,
  max = 3.5,
  className,
  style,
  sheen = true,
}: {
  children: ReactNode;
  max?: number;
  className?: string;
  style?: CSSProperties;
  sheen?: boolean;
}) {
  const reduced = usePrefersReducedMotion();
  const px = useMotionValue(0.5);
  const py = useMotionValue(0.5);

  const rotateX = useSpring(useTransform(py, [0, 1], [max, -max]), {
    stiffness: 320,
    damping: 30,
    mass: 0.6,
  });
  const rotateY = useSpring(useTransform(px, [0, 1], [-max, max]), {
    stiffness: 320,
    damping: 30,
    mass: 0.6,
  });

  const sheenX = useTransform(px, (v) => `${(v * 100).toFixed(1)}%`);
  const sheenY = useTransform(py, (v) => `${(v * 100).toFixed(1)}%`);
  const sheenBg = useMotionTemplate`radial-gradient(420px circle at ${sheenX} ${sheenY}, rgba(255,255,255,0.055), transparent 65%)`;

  useEffect(() => {
    // Springs park at center when disabled; values are inert anyway.
    px.set(0.5);
    py.set(0.5);
  }, [reduced, px, py]);

  const enabled = !reduced && typeof window !== "undefined" && window.matchMedia("(pointer: fine)").matches;

  const onMove = (e: React.PointerEvent) => {
    if (!enabled) return;
    const r = (e.currentTarget as HTMLDivElement).getBoundingClientRect();
    px.set((e.clientX - r.left) / r.width);
    py.set((e.clientY - r.top) / r.height);
  };
  const onLeave = () => {
    px.set(0.5);
    py.set(0.5);
  };

  return (
    <motion.div
      onPointerMove={onMove}
      onPointerLeave={onLeave}
      className={cx("group/tilt relative", className)}
      style={{ rotateX: enabled ? rotateX : 0, rotateY: enabled ? rotateY : 0, transformPerspective: 900, ...style }}
    >
      {children}
      {sheen && enabled && (
        <motion.div
          aria-hidden
          className="pointer-events-none absolute inset-0 rounded-[inherit] opacity-0 transition-opacity duration-200 group-hover/tilt:opacity-100"
          style={{ background: sheenBg }}
        />
      )}
    </motion.div>
  );
}
