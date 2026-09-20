"use client";
/**
 * Theme-aware chart colors (2026-09-20).
 *
 * recharts/SVG need real color strings (not var() references), so this hook
 * resolves the current theme's CSS variables via getComputedStyle and
 * re-renders when `data-theme` changes (MutationObserver). Brand/semantic
 * data colors (gold, red, green) stay constant — only neutrals adapt.
 */
import { useEffect, useState } from "react";
import type { ThemeName } from "./useTheme";

export interface ChartPalette {
  grid: string;
  tick: string;
  muted: string;
  track: string;
  surface: string;
}

function readVar(name: string): string {
  if (typeof window === "undefined") return "";
  return window.getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function readPalette(): ChartPalette {
  return {
    grid: readVar("--chart-grid"),
    tick: readVar("--text-muted"),
    muted: readVar("--text-secondary"),
    track: readVar("--border-default"),
    surface: readVar("--surface-elevated"),
  };
}

export function useChartPalette(): ChartPalette {
  const [theme, setTheme] = useState<ThemeName>(() =>
    typeof document === "undefined"
      ? "dark"
      : ((document.documentElement.dataset.theme as ThemeName) || "dark"),
  );
  const [palette, setPalette] = useState<ChartPalette>(() => readPalette());

  useEffect(() => {
    const el = document.documentElement;
    const update = () => {
      setTheme((el.dataset.theme as ThemeName) || "dark");
      setPalette(readPalette());
    };
    update();
    const obs = new MutationObserver(update);
    obs.observe(el, { attributes: true, attributeFilter: ["data-theme"] });
    return () => obs.disconnect();
  }, []);

  void theme; // re-render trigger; values come from readPalette()
  return palette;
}
