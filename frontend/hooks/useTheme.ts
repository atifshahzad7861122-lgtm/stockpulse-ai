"use client";
/**
 * Theme state (2026-09-20) — dark / light toggle for StockPulse.
 *
 * The visual switch is driven by `data-theme` on <html> (see the bootstrap
 * script in app/layout.tsx, which sets it before first paint to avoid any
 * flash). This hook only mirrors that attribute into React state for the
 * toggle icon and persists the choice to localStorage.
 */
import { useCallback, useEffect, useState } from "react";

export type ThemeName = "dark" | "light";

const STORAGE_KEY = "stockpulse-theme";

function readTheme(): ThemeName {
  if (typeof document === "undefined") return "dark";
  const t = document.documentElement.dataset.theme;
  return t === "light" ? "light" : "dark";
}

export function useTheme() {
  const [theme, setThemeState] = useState<ThemeName>("dark");

  useEffect(() => {
    setThemeState(readTheme());
  }, []);

  const setTheme = useCallback((t: ThemeName) => {
    document.documentElement.dataset.theme = t;
    try {
      localStorage.setItem(STORAGE_KEY, t);
    } catch {
      /* storage unavailable — theme still applies for this session */
    }
    setThemeState(t);
  }, []);

  const toggle = useCallback(() => {
    setTheme(readTheme() === "dark" ? "light" : "dark");
  }, [setTheme]);

  return { theme, setTheme, toggle };
}
