"use client";
/**
 * Command bar (⌘K / Ctrl+K) — docs/05 §6.1, docs/06 §3.3, docs/11 §7.5.
 * One search across navigation destinations, categories, trends, opportunities,
 * ideas, and prompts. Searches the workspace + trend data, never the web.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { overlayTransition } from "./motion/easing";
import {
  BarChart3,
  Bot,
  CalendarDays,
  ShieldCheck,
  Compass,
  FileImage,
  FileVideo,
  HelpCircle,
  Home,
  Image,
  Layers,
  Library,
  Lightbulb,
  Play,
  Search,
  Settings,
  Sparkles,
  Sun,
  Tags,
  Wand2,
  X,
  type LucideIcon,
} from "lucide-react";
import { useCommandBarState } from "./providers";
import { useCategories, useIdeas, useOpportunities, usePrompts, useRefreshTrends } from "../hooks/useApi";
import { Input } from "./ui";
import { enumLabel } from "../lib/format";

interface Action {
  id: string;
  group: string;
  label: string;
  sub?: string;
  icon: LucideIcon;
  run: () => void;
}

const DESTINATIONS: { href: string; label: string; icon: LucideIcon }[] = [
  { href: "/", label: "Dashboard", icon: Home },
  { href: "/daily", label: "Daily Intelligence", icon: Sun },
  { href: "/trends", label: "Trend Explorer", icon: Compass },
  { href: "/opportunities", label: "Opportunity Explorer", icon: Lightbulb },
  { href: "/image-ideas", label: "Image Ideas", icon: FileImage },
  { href: "/video-ideas", label: "Video Ideas", icon: FileVideo },
  { href: "/prompt-studio", label: "Prompt Studio", icon: Wand2 },
  { href: "/compliance", label: "Compliance Center", icon: ShieldCheck },
  { href: "/similarity", label: "Similarity Center", icon: Layers },
  { href: "/queue", label: "Production Queue", icon: CalendarDays },
  { href: "/planner", label: "Submission Planner", icon: CalendarDays },
  { href: "/metadata", label: "Metadata Studio", icon: Tags },
  { href: "/library", label: "Content Library", icon: Library },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/agents", label: "AI Agent Center", icon: Bot },
  { href: "/settings", label: "Settings", icon: Settings },
  { href: "/help", label: "Help", icon: HelpCircle },
];

export function useCommandBarShortcut() {
  const { setOpen } = useCommandBarState();
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen(true);
      } else if (e.key === "/" && !(e.target instanceof HTMLInputElement) && !(e.target instanceof HTMLTextAreaElement)) {
        e.preventDefault();
        setOpen(true);
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [setOpen]);
}

export function CommandBar() {
  const { open, setOpen } = useCommandBarState();
  const router = useRouter();
  const [q, setQ] = useState("");
  const [cursor, setCursor] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const refreshTrends = useRefreshTrends();

  const opps = useOpportunities({ page_size: 50 }, { enabled: open });
  const ideas = useIdeas({ page_size: 50 }, { enabled: open });
  const prompts = usePrompts({ page_size: 50 }, { enabled: open });
  const cats = useCategories({ enabled: open });

  useEffect(() => {
    if (open) {
      setQ("");
      setCursor(0);
      setTimeout(() => inputRef.current?.focus(), 40);
    }
  }, [open ]);

  const results: Action[] = useMemo(() => {
    const needle = q.trim().toLowerCase();
    const match = (s: string | null | undefined) => !needle || (s ?? "").toLowerCase().includes(needle);
    const out: Action[] = [];

    // Actions
    const runAnalysis = () => {
      setOpen(false);
      refreshTrends.mutate();
    };
    if (!needle || "run daily analysis".includes(needle) || "refresh".includes(needle) || "briefing".includes(needle)) {
      out.push({ id: "act-run", group: "Actions", label: "Run daily analysis", sub: "Trigger trend aggregation", icon: Play, run: runAnalysis });
    }
    if (!needle || "new idea".includes(needle) || "create idea".includes(needle)) {
      out.push({ id: "act-idea", group: "Actions", label: "New idea", sub: "Open opportunities to create from", icon: Sparkles, run: () => { setOpen(false); router.push("/opportunities"); } });
    }

    // Destinations
    for (const d of DESTINATIONS) {
      if (match(d.label)) out.push({ id: `nav-${d.href}`, group: "Go to", label: d.label, icon: d.icon, run: () => { setOpen(false); router.push(d.href); } });
    }
    // Records
    for (const o of opps.data?.data ?? []) {
      if (!match(o.title)) continue;
      out.push({ id: `opp-${o.id}`, group: "Opportunities", label: o.title, sub: `Score ${Math.round(o.opportunity_score)}`, icon: Lightbulb, run: () => { setOpen(false); router.push(`/opportunities/${o.id}`); } });
    }
    for (const i of ideas.data?.data ?? []) {
      if (!match(i.title)) continue;
      out.push({ id: `idea-${i.id}`, group: "Ideas", label: i.title, sub: i.kind === "image" ? "Image idea" : "Video idea", icon: i.kind === "image" ? FileImage : FileVideo, run: () => { setOpen(false); router.push(i.kind === "image" ? `/image-ideas?idea=${i.id}` : `/video-ideas?idea=${i.id}`); } });
    }
    for (const p of prompts.data?.data ?? []) {
      if (!match(p.name)) continue;
      out.push({ id: `prompt-${p.id}`, group: "Prompts", label: p.name, sub: p.status, icon: Wand2, run: () => { setOpen(false); router.push(`/prompt-studio/${p.id}`); } });
    }
    for (const c of cats.data ?? []) {
      if (!match(c.name)) continue;
      out.push({ id: `cat-${c.id}`, group: "Categories", label: c.name, sub: "Category", icon: Tags, run: () => { setOpen(false); router.push(`/trends?category=${c.slug}`); } });
    }
    return out.slice(0, 40);
  }, [q, opps.data, ideas.data, prompts.data, cats.data, router, setOpen, refreshTrends]);

  useEffect(() => setCursor(0), [q]);

  const groups = useMemo(() => {
    const g: { name: string; items: Action[] }[] = [];
    for (const r of results) {
      const last = g[g.length - 1];
      if (last && last.name === r.group) last.items.push(r);
      else g.push({ name: r.group, items: [r] });
    }
    return g;
  }, [results]);

  const flat = results;
  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setCursor((c) => Math.min(flat.length - 1, c + 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setCursor((c) => Math.max(0, c - 1)); }
    else if (e.key === "Enter" && flat[cursor]) { e.preventDefault(); flat[cursor].run(); }
  };

  let idx = -1;
  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.12 }}
          className="fixed inset-0 z-[95] bg-black/60 p-4 pt-[12vh]"
          onMouseDown={(e) => e.target === e.currentTarget && setOpen(false)}
        >
          <motion.div
            initial={{ y: -8, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: -8, opacity: 0 }}
            transition={overlayTransition}
            role="dialog"
            aria-modal="true"
            aria-label="Command bar"
            className="mx-auto max-w-xl overflow-hidden rounded-xl border border-border bg-surface-base shadow-2xl"
            onKeyDown={onKeyDown}
          >
            <div className="flex items-center gap-2 border-b border-border px-4">
              <Search size={15} className="shrink-0 text-text-muted" aria-hidden />
              <input
                ref={inputRef}
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="Search records, screens, actions…"
                aria-label="Search"
                className="w-full bg-transparent py-3 text-sm text-text-primary placeholder:text-text-muted focus:outline-none"
              />
              <button onClick={() => setOpen(false)} aria-label="Close" className="rounded p-1 text-text-muted hover:text-text-primary">
                <X size={15} />
              </button>
            </div>
            <div className="max-h-[50vh] overflow-y-auto p-2" role="listbox" aria-label="Results">
              {groups.map((g) => (
                <div key={g.name}>
                  <p className="px-2.5 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-[0.08em] text-text-muted">{g.name}</p>
                  {g.items.map((r) => {
                    idx += 1;
                    const active = idx === cursor;
                    const Icon = r.icon;
                    return (
                      <button
                        key={r.id}
                        role="option"
                        aria-selected={active}
                        onMouseEnter={() => setCursor(idx)}
                        onClick={() => r.run()}
                        className={`flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-left ${active ? "bg-surface-elevated" : ""}`}
                      >
                        <Icon size={14} className="shrink-0 text-text-muted" aria-hidden />
                        <span className="min-w-0 flex-1 truncate text-[13px] text-text-primary">{r.label}</span>
                        {r.sub && <span className="shrink-0 text-[11px] text-text-muted">{r.sub}</span>}
                      </button>
                    );
                  })}
                </div>
              ))}
              {!results.length && (
                <div className="px-4 py-8 text-center">
                  <p className="text-sm text-text-primary">No results for &ldquo;{q}&rdquo;</p>
                  <p className="mt-1 text-xs text-text-muted">Check spelling, broaden the scope — or create an idea from this query.</p>
                </div>
              )}
            </div>
            <div className="flex items-center gap-3 border-t border-border px-4 py-2 text-[11px] text-text-muted">
              <span><kbd className="rounded border border-border px-1">↑↓</kbd> navigate</span>
              <span><kbd className="rounded border border-border px-1">↵</kbd> select</span>
              <span><kbd className="rounded border border-border px-1">esc</kbd> close</span>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
