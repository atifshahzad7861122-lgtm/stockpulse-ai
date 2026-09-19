/**
 * Shared color constants for canvas/SVG/JS-driven visuals (charts, scores,
 * 3D scenes). Single source of truth — keep in sync with tailwind.config.js
 * and styles/globals.css. Champagne gold is the one accent; racing red is
 * alerts/live/critical only; no blue anywhere in the system.
 */
export const GOLD = "#D6B25E";
export const GOLD_BRIGHT = "#E9CE8F";
export const GOLD_DEEP = "#A8842F";

export const RACING_RED = "#E10600";
export const RED_TEXT = "#FF5A4D"; // brightened red for text on dark
export const SUCCESS = "#34D399";
export const WARNING = "#F5A524";
export const STEEL = "#9A958A"; // warm gray — replaces the old info blue

export const TEXT_PRIMARY = "#F5F3EE";
export const TEXT_SECONDARY = "#A9A49A";
export const TEXT_MUTED = "#6F6A60";

export const GRID = "rgba(255,255,255,0.06)";
export const TICK = "#6F6A60";
export const MUTED_SERIES = "#A9A49A";
export const TRACK = "#242428"; // bar/ring track
export const SCORE_TRACK = TRACK;

export const SURFACE_BASE = "#141417";
export const SURFACE_ELEVATED = "#1B1B20";
export const BG_PRIMARY = "#0A0A0C";

/** Saturation → point/segment color (semantic risk encoding). */
export function saturationColor(saturation: number | null | undefined): string {
  if (saturation === null || saturation === undefined || Number.isNaN(saturation)) return STEEL;
  if (saturation > 75) return RACING_RED; // saturated — critical
  if (saturation > 55) return WARNING; // crowded
  if (saturation > 30) return STEEL; // moderate
  return GOLD; // open — the opportunity highlight
}

/** Score band → color: high = gold, medium = secondary, low = muted. */
export function scoreBandColor(band: "high" | "medium" | "low"): string {
  return band === "high" ? GOLD : band === "medium" ? TEXT_SECONDARY : TEXT_MUTED;
}
