"use client";
/**
 * Shared Motion (framer-motion) primitives — the single animation language
 * for all UI/chrome animation. React Three Fiber stays reserved for 3D data
 * viz; everything here is DOM UI.
 *
 * Feel: Apple-grade — buttery, precise, fast (150–400ms), never bouncy or
 * gratuitous. Easing is one shared expo-out curve; durations are short.
 * Reduced motion is handled globally via MotionConfig reducedMotion="user"
 * in providers.tsx, plus useReducedMotion guards on imperative animation.
 */
import { AnimatePresence, animate, motion, useReducedMotion } from "framer-motion";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { cx } from "../ui";
import { DUR, EASE_APPLE } from "./easing";

export { DUR, EASE_APPLE };

// ---------------------------------------------------------------------------
// Page transition — keyed crossfade/slide on route change.
// ---------------------------------------------------------------------------

export function PageTransition({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  return (
    <AnimatePresence mode="wait" initial={false}>
      <motion.div
        key={pathname}
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -6 }}
        transition={{ duration: DUR.med, ease: EASE_APPLE }}
      >
        {children}
      </motion.div>
    </AnimatePresence>
  );
}

// ---------------------------------------------------------------------------
// Stagger — container + items for list entrances.
// ---------------------------------------------------------------------------

type AsTag = "div" | "ol" | "ul" | "li" | "span";

export function Stagger({
  children,
  className,
  as = "div",
  gap = 0.035,
  delay = 0.03,
}: {
  children: ReactNode;
  className?: string;
  as?: "div" | "ol" | "ul";
  gap?: number;
  delay?: number;
}) {
  const Tag = (motion as unknown as Record<AsTag, typeof motion.div>)[as];
  return (
    <Tag
      className={className}
      initial="hidden"
      animate="show"
      variants={{
        hidden: {},
        show: { transition: { staggerChildren: gap, delayChildren: delay } },
      }}
    >
      {children}
    </Tag>
  );
}

export function StaggerItem({
  children,
  className,
  as = "div",
  y = 10,
  layout = false,
}: {
  children: ReactNode;
  className?: string;
  as?: AsTag;
  y?: number;
  /** Enable for lists that re-rank/reorder — buttery FLIP moves. */
  layout?: boolean;
}) {
  const Tag = (motion as unknown as Record<AsTag, typeof motion.div>)[as];
  return (
    <Tag
      className={className}
      layout={layout || undefined}
      variants={{
        hidden: { opacity: 0, y },
        show: { opacity: 1, y: 0, transition: { duration: DUR.med, ease: EASE_APPLE } },
      }}
      {...(layout
        ? { transition: { layout: { duration: DUR.med, ease: EASE_APPLE } } }
        : {})}
    >
      {children}
    </Tag>
  );
}

// ---------------------------------------------------------------------------
// Reveal — fade-up when scrolled into view.
// ---------------------------------------------------------------------------

export function Reveal({
  children,
  className,
  delay = 0,
  y = 12,
}: {
  children: ReactNode;
  className?: string;
  delay?: number;
  y?: number;
}) {
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-32px" }}
      transition={{ duration: 0.32, ease: EASE_APPLE, delay }}
    >
      {children}
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
// CountUp — animated F1-style telemetry numeral. Tabular figures, expo-out,
// 600ms. Jumps straight to the value under prefers-reduced-motion.
// ---------------------------------------------------------------------------

export function CountUp({
  value,
  decimals = 0,
  duration = 0.6,
  className,
  format,
}: {
  value: number;
  decimals?: number;
  duration?: number;
  className?: string;
  /** Custom formatter, e.g. (n) => `$${Math.round(n)}`. */
  format?: (n: number) => string;
}) {
  const reduce = useReducedMotion();
  const [display, setDisplay] = useState(value);

  useEffect(() => {
    if (reduce || !Number.isFinite(value)) {
      setDisplay(value);
      return;
    }
    const controls = animate(0, value, {
      duration,
      ease: EASE_APPLE,
      onUpdate: (v) => setDisplay(v),
    });
    return () => controls.stop();
  }, [value, duration, reduce]);

  const text = format
    ? format(display)
    : decimals > 0
      ? display.toFixed(decimals)
      : String(Math.round(display));

  return (
    <span className={cx("tnum", className)} aria-label={format ? format(value) : String(Math.round(value * 10 ** decimals) / 10 ** decimals)}>
      {text}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Shared overlay transitions (modal / drawer / toast / command bar).
// ---------------------------------------------------------------------------

export { overlayTransition } from "./easing";
