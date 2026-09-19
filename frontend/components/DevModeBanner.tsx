"use client";
/**
 * Dev-mode banner — PHASE2_DESIGN.md §2: when the `dev_mode` setting is on,
 * a visible "DEV MODE — demo data active" banner appears on every page.
 * Intelligence queries exclude MOCK rows in production; in dev mode demo
 * data is allowed but must be labeled.
 */
import { FlaskConical } from "lucide-react";
import { useSettings } from "../hooks/useApi";

export function useDevMode(): boolean {
  const settings = useSettings({ retry: false, staleTime: 60_000 });
  return settings.data?.["dev_mode"] === true;
}

export function DevModeBanner() {
  const dev = useDevMode();
  if (!dev) return null;
  return (
    <div
      role="status"
      className="mb-4 flex items-center gap-2.5 rounded-lg border border-status-warning/40 bg-status-warning/[0.10] px-3.5 py-2.5 text-[13px] text-text-secondary"
    >
      <FlaskConical size={15} className="shrink-0 text-status-warning" aria-hidden />
      <p>
        <strong className="font-semibold uppercase tracking-[0.06em] text-status-warning">Dev mode</strong>
        {" — "}demo data is active. Mock rows may appear and are always badged{" "}
        <span className="chip-warning rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase">Demo data</span>.
        Turn <code className="font-mono text-xs">dev_mode</code> off in Settings for production intelligence.
      </p>
    </div>
  );
}
