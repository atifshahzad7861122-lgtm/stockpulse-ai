"use client";
/**
 * 3D capability guards. Every 3D scene renders only when:
 *  - code is running on the client (post-mount),
 *  - WebGL is actually available,
 *  - the user has NOT requested reduced motion.
 * Otherwise the caller renders the 2D fallback — never a blank stage.
 */
import { useEffect, useState } from "react";

export function supportsWebGL(): boolean {
  if (typeof document === "undefined") return false;
  try {
    const c = document.createElement("canvas");
    return !!(
      c.getContext("webgl2") ??
      c.getContext("webgl") ??
      (c as HTMLCanvasElement & { getContext(s: string): unknown }).getContext("experimental-webgl")
    );
  } catch {
    return false;
  }
}

export function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(mq.matches);
    const onChange = (e: MediaQueryListEvent) => setReduced(e.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);
  return reduced;
}

/** True only on the client when WebGL exists and motion is allowed. */
export function useRender3D(): boolean {
  const reduced = usePrefersReducedMotion();
  const [ok, setOk] = useState(false);
  useEffect(() => {
    setOk(supportsWebGL());
  }, []);
  return ok && !reduced;
}
