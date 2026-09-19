/**
 * Queue state machine — CONTRACT §4.2–4.3 (binding).
 * 13 states; only transitions T01–T29 are legal. Any other pair → 400 INVALID_TRANSITION.
 * `legalTargets` powers the Move dialog so the UI can only offer legal moves.
 */
import type { QueueStatus } from "../types";

export type QueueState = QueueStatus;

export const ALL_STATES: QueueState[] = [
  "DISCOVERED",
  "ANALYZING",
  "IDEA_READY",
  "PROMPT_READY",
  "APPROVED",
  "IN_PRODUCTION",
  "QUALITY_CHECK",
  "COMPLIANCE_REVIEW",
  "READY_TO_UPLOAD",
  "SUBMITTED",
  "ACCEPTED",
  "REJECTED",
  "ARCHIVED",
];

/** T01–T29. Self-transitions (T06, T09) are regeneration/edit loops, not state changes. */
const EDGES: [QueueState, QueueState][] = [
  ["DISCOVERED", "ANALYZING"], // T01
  ["DISCOVERED", "ARCHIVED"], // T02
  ["ANALYZING", "IDEA_READY"], // T03
  ["ANALYZING", "ARCHIVED"], // T04
  ["IDEA_READY", "PROMPT_READY"], // T05
  ["IDEA_READY", "ARCHIVED"], // T07
  ["PROMPT_READY", "APPROVED"], // T08
  ["PROMPT_READY", "IDEA_READY"], // T10
  ["PROMPT_READY", "ARCHIVED"], // T11
  ["APPROVED", "IN_PRODUCTION"], // T12
  ["APPROVED", "PROMPT_READY"], // T13
  ["APPROVED", "ARCHIVED"], // T14
  ["IN_PRODUCTION", "QUALITY_CHECK"], // T15
  ["QUALITY_CHECK", "COMPLIANCE_REVIEW"], // T16
  ["QUALITY_CHECK", "IN_PRODUCTION"], // T17
  ["COMPLIANCE_REVIEW", "READY_TO_UPLOAD"], // T18 — compliance PASS
  ["COMPLIANCE_REVIEW", "IN_PRODUCTION"], // T19 — REVIEW, remediable
  ["COMPLIANCE_REVIEW", "ARCHIVED"], // T20 — HIGH_RISK, abandoned
  ["READY_TO_UPLOAD", "SUBMITTED"], // T21
  ["READY_TO_UPLOAD", "IN_PRODUCTION"], // T22
  ["READY_TO_UPLOAD", "ARCHIVED"], // T23
  ["SUBMITTED", "ACCEPTED"], // T24
  ["SUBMITTED", "REJECTED"], // T25
  ["REJECTED", "IN_PRODUCTION"], // T26
  ["REJECTED", "ARCHIVED"], // T27
  ["ACCEPTED", "ARCHIVED"], // T28
  ["ARCHIVED", "DISCOVERED"], // T29
];

/** T01–T29 labels for the transition that produces each edge (index aligned with EDGES). */
const EDGE_IDS = [
  "T01", "T02", "T03", "T04", "T05", "T07", "T08", "T10", "T11",
  "T12", "T13", "T14", "T15", "T16", "T17", "T18", "T19", "T20",
  "T21", "T22", "T23", "T24", "T25", "T26", "T27", "T28", "T29",
];

export function legalTargets(from: QueueState): QueueState[] {
  return EDGES.filter(([f]) => f === from).map(([, t]) => t);
}

/** Transition id (T01–T29) for a from→to pair, or null if illegal. */
export function transitionId(from: QueueState, to: QueueState): string | null {
  const i = EDGES.findIndex(([f, t]) => f === from && t === to);
  return i >= 0 ? EDGE_IDS[i] : null;
}

export function isLegalTransition(from: QueueState, to: QueueState): boolean {
  return transitionId(from, to) !== null;
}

const LABELS: Record<QueueState, string> = {
  DISCOVERED: "Discovered",
  ANALYZING: "Analyzing",
  IDEA_READY: "Idea ready",
  PROMPT_READY: "Prompt ready",
  APPROVED: "Approved",
  IN_PRODUCTION: "In production",
  QUALITY_CHECK: "Quality check",
  COMPLIANCE_REVIEW: "Compliance review",
  READY_TO_UPLOAD: "Ready to upload",
  SUBMITTED: "Submitted",
  ACCEPTED: "Accepted",
  REJECTED: "Rejected",
  ARCHIVED: "Archived",
};

export function stateLabel(s: QueueState): string {
  return LABELS[s] ?? s;
}

/** Board grouping for the queue kanban. */
export const STATE_GROUPS: { label: string; states: QueueState[] }[] = [
  { label: "Intake", states: ["DISCOVERED", "ANALYZING"] },
  { label: "Concepts", states: ["IDEA_READY", "PROMPT_READY"] },
  { label: "Approved", states: ["APPROVED"] },
  { label: "Production", states: ["IN_PRODUCTION", "QUALITY_CHECK", "COMPLIANCE_REVIEW"] },
  { label: "Ready", states: ["READY_TO_UPLOAD"] },
  { label: "Submitted", states: ["SUBMITTED"] },
  { label: "Outcomes", states: ["ACCEPTED", "REJECTED"] },
  { label: "Archived", states: ["ARCHIVED"] },
];

/** States with no active work expected (stale alerts skip these). */
export const QUIESCENT_STATES: QueueState[] = ["SUBMITTED", "ACCEPTED", "REJECTED", "ARCHIVED"];
