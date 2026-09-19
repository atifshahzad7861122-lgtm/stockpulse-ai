/**
 * Score helpers — mirror CONTRACT.md §8 exactly so frontend and backend
 * interpret scores identically. Pure functions; derived at render time (docs/11 §5.3).
 */

export type ScoreBand = "high" | "medium" | "low";

export function scoreBand(score: number): ScoreBand {
  if (score >= 70) return "high";
  if (score >= 40) return "medium";
  return "low";
}

/** Score bands per docs/07: high → accent, medium → text.secondary, low → text.muted. */
export function scoreBandClass(band: ScoreBand): string {
  return band === "high" ? "text-accent-primary" : band === "medium" ? "text-text-secondary" : "text-text-muted";
}

export function formatScore(score: number, bandLabel: string): string {
  return `${Math.round(score)} · ${bandLabel}`;
}

export type SaturationBand = "Open" | "Moderate" | "Crowded" | "Saturated";

/** Saturation bands (docs/15 §4.4) — meaning-inverted colors (docs/07 §4). */
export function saturationBand(css: number): SaturationBand {
  if (css <= 30) return "Open";
  if (css <= 55) return "Moderate";
  if (css <= 75) return "Crowded";
  return "Saturated";
}

export function saturationChipClass(band: SaturationBand): string {
  return band === "Open" ? "chip-success" : band === "Saturated" ? "chip-danger" : "chip-warning";
}

export type ConfidenceBand = "High" | "Medium" | "Low";

/** Prediction confidence bands: High ≥ 70, Medium 40–69, Low < 40 (docs/07 §4). */
export function confidenceBand(pc: number): ConfidenceBand {
  if (pc >= 70) return "High";
  if (pc >= 40) return "Medium";
  return "Low";
}

export const PROVENANCE_LABELS: Record<string, string> = {
  VERIFIED: "Verified",
  USER_PROVIDED: "User-provided",
  THIRD_PARTY: "Third-party",
  ESTIMATED: "Estimated",
  PREDICTED: "Predicted",
  MOCK: "Demo data",
};

export function provenanceLabel(p: string): string {
  return PROVENANCE_LABELS[p] ?? p;
}
