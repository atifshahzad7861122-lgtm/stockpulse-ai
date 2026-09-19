"use client";
/**
 * App shell — precision-instrument restyle (2026-09-19).
 * Sidebar nav (grouped, icons, count badges) + top bar (command bar trigger,
 * briefing pill, alert bell) + mobile bottom tab bar. Champagne-gold active
 * states; racing red reserved for the notification alert dot.
 */
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  BarChart3,
  Bell,
  Bot,
  CalendarDays,
  ShieldCheck,
  Compass,
  Database,
  FileImage,
  FileVideo,
  Activity,
  HelpCircle,
  History,
  Home,
  Layers,
  Library,
  Lightbulb,
  Search,
  Settings,
  Sun,
  Tags,
  Wand2,
  Wallet,
  MoreHorizontal,
  type LucideIcon,
} from "lucide-react";
import { useCommandBarState } from "./providers";
import { useCommandBarShortcut } from "./CommandBar";
import { DevModeBanner } from "./DevModeBanner";
import { PageTransition } from "./motion/motion";
import { useAgentJobs, useComplianceChecks, useNotifications, useQueue } from "../hooks/useApi";
import { useToast } from "./toast";
import { cx } from "./ui";

interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  badgeKey?: "queue" | "compliance";
}

const NAV: { group: string; items: NavItem[] }[] = [
  {
    group: "Intelligence",
    items: [
      { href: "/", label: "Dashboard", icon: Home },
      { href: "/daily", label: "Daily Intelligence", icon: Sun },
      { href: "/trends", label: "Trends", icon: Compass },
      { href: "/opportunities", label: "Opportunities", icon: Lightbulb },
    ],
  },
  {
    group: "Ideation",
    items: [
      { href: "/image-ideas", label: "Image Ideas", icon: FileImage },
      { href: "/video-ideas", label: "Video Ideas", icon: FileVideo },
      { href: "/prompt-studio", label: "Prompt Studio", icon: Wand2 },
    ],
  },
  {
    group: "Quality",
    items: [
      { href: "/compliance", label: "Compliance", icon: ShieldCheck, badgeKey: "compliance" },
      { href: "/similarity", label: "Similarity", icon: Layers },
    ],
  },
  {
    group: "Production",
    items: [
      { href: "/queue", label: "Queue", icon: CalendarDays, badgeKey: "queue" },
      { href: "/planner", label: "Planner", icon: CalendarDays },
      { href: "/metadata", label: "Metadata", icon: Tags },
      { href: "/library", label: "Library", icon: Library },
    ],
  },
  {
    group: "Data layer",
    items: [
      { href: "/sources", label: "Data Sources", icon: Database },
      { href: "/sources/health", label: "Source Health", icon: Activity },
      { href: "/runs", label: "Collection Runs", icon: History },
      { href: "/private", label: "Private Performance", icon: Wallet },
    ],
  },
  {
    group: "Insights",
    items: [
      { href: "/analytics", label: "Analytics", icon: BarChart3 },
      { href: "/agents", label: "Agents", icon: Bot },
    ],
  },
  {
    group: "System",
    items: [
      { href: "/settings", label: "Settings", icon: Settings },
      { href: "/help", label: "Help", icon: HelpCircle },
    ],
  },
];

const MOBILE_TABS: { href: string; label: string; icon: LucideIcon }[] = [
  { href: "/", label: "Dashboard", icon: Home },
  { href: "/daily", label: "Briefing", icon: Sun },
  { href: "/opportunities", label: "Ideas", icon: Lightbulb },
  { href: "/queue", label: "Queue", icon: CalendarDays },
  { href: "/settings", label: "More", icon: MoreHorizontal },
];

function Wordmark({ compact }: { compact?: boolean }) {
  return (
    <span className="flex items-center gap-2.5">
      <span
        className={cx(
          "flex items-center justify-center rounded-lg bg-accent-primary font-display text-[#171307] shadow-[inset_0_1px_0_rgba(255,255,255,0.4),0_4px_12px_-4px_rgba(214,178,94,0.5)]",
          compact ? "h-6 w-6 text-xs" : "h-8 w-8 text-base",
        )}
        aria-hidden
      >
        S
      </span>
      <span className={cx("font-display text-text-primary", compact ? "text-sm" : "text-[19px]")}>
        StockPulse
      </span>
    </span>
  );
}

function BriefingPill() {
  const router = useRouter();
  const { toast } = useToast();
  const jobs = useAgentJobs({ run_kind: "BRIEFING_BUILD", page_size: 1 }, { retry: false });
  const job = jobs.data?.data?.[0];
  void toast;
  if (jobs.isError || !job) return null;
  const tone =
    job.status === "succeeded"
      ? "chip-success"
      : job.status === "running" || job.status === "queued"
        ? "chip-warning"
        : "chip-danger";
  const label =
    job.status === "succeeded"
      ? "Briefing ready"
      : job.status === "running" || job.status === "queued"
        ? `Briefing ${Math.round(job.progress * 100)}%`
        : "Briefing failed";
  return (
    <button
      onClick={() => router.push("/daily")}
      title="Open Daily Intelligence"
      className={cx("hidden items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold sm:inline-flex", tone)}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden />
      {label}
    </button>
  );
}

function BellButton() {
  const router = useRouter();
  const { toast } = useToast();
  const { data } = useNotifications({ unread: true, page_size: 1 }, { retry: false });
  const unread = data?.unread_count ?? 0;
  return (
    <button
      onClick={() => {
        toast({ title: `${unread} unread notifications`, description: "Opening the notification inbox.", tone: "info", durationMs: 2000 });
        router.push("/agents");
      }}
      aria-label={`Notifications${unread ? `, ${unread} unread` : ""}`}
      className="relative rounded-lg p-2 text-text-secondary transition-colors hover:bg-white/[0.05] hover:text-text-primary"
    >
      <Bell size={16} aria-hidden />
      {unread > 0 && (
        <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-status-danger px-1 text-[9px] font-bold text-white tnum">
          {unread > 99 ? "99+" : unread}
        </span>
      )}
    </button>
  );
}

export default function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { setOpen } = useCommandBarState();
  useCommandBarShortcut();

  const queue = useQueue({ page_size: 1 }, { retry: false });
  const compliance = useComplianceChecks({ pending_review: true, page_size: 1 }, { retry: false });
  const queueDepth = queue.data?.pagination.total ?? 0;
  const compliancePending = compliance.data?.pagination.total ?? 0;

  const badgeFor = (key?: "queue" | "compliance") => {
    if (key === "queue" && queueDepth > 0) return queueDepth;
    if (key === "compliance" && compliancePending > 0) return compliancePending;
    return 0;
  };

  // Longest-prefix match so nested routes (e.g. /sources/health) highlight
  // only their own nav item, not the parent (e.g. /sources).
  const matches = (href: string) =>
    href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(href + "/");
  const activeHref = NAV.flatMap((g) => g.items)
    .map((it) => it.href)
    .filter(matches)
    .sort((a, b) => b.length - a.length)[0];

  return (
    <div className="flex min-h-screen">
      {/* Sidebar — desktop */}
      <aside className="hidden w-60 shrink-0 border-r border-border bg-bg-secondary lg:block">
        <Link href="/" className="flex items-center px-5 pb-5 pt-5">
          <Wordmark />
        </Link>
        <nav className="px-3 pb-6" aria-label="Primary">
          {NAV.map((g) => (
            <div key={g.group} className="mb-5">
              <div className="px-2.5 pb-1.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-text-muted">
                {g.group}
              </div>
              {g.items.map((it) => {
                const active = it.href === activeHref;
                const Icon = it.icon;
                const badge = badgeFor(it.badgeKey);
                return (
                  <Link
                    key={it.href}
                    href={it.href}
                    aria-current={active ? "page" : undefined}
                    className={cx(
                      "relative mb-0.5 flex items-center gap-2.5 rounded-lg px-2.5 py-[7px] text-[13px] font-medium transition-colors",
                      active
                        ? "bg-white/[0.05] text-text-primary shadow-[inset_0_1px_0_rgba(255,255,255,0.06)]"
                        : "text-text-secondary hover:bg-white/[0.03] hover:text-text-primary",
                    )}
                  >
                    <span
                      aria-hidden
                      className={cx(
                        "absolute left-0 top-1/2 h-5 w-[2px] -translate-y-1/2 rounded-full bg-accent-primary transition-opacity",
                        active ? "opacity-100" : "opacity-0",
                      )}
                    />
                    <Icon size={15} aria-hidden className={active ? "text-accent-primary" : ""} />
                    <span className="flex-1">{it.label}</span>
                    {badge > 0 && (
                      <span
                        className={cx(
                          "tnum rounded-full px-1.5 py-0.5 text-[10px] font-bold",
                          it.badgeKey === "compliance" ? "chip-warning" : "bg-white/[0.07] text-text-secondary",
                        )}
                      >
                        {badge > 99 ? "99+" : badge}
                      </span>
                    )}
                  </Link>
                );
              })}
            </div>
          ))}
        </nav>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Top bar */}
        <header className="sticky top-0 z-[60] flex items-center gap-2 border-b border-border bg-bg-secondary/90 px-4 py-2 backdrop-blur">
          <Link href="/" className="lg:hidden" aria-label="StockPulse home">
            <Wordmark compact />
          </Link>
          <button
            onClick={() => setOpen(true)}
            aria-label="Open command bar (Ctrl+K)"
            className="ml-auto hidden w-64 items-center gap-2 rounded-lg border border-border bg-surface-base px-3 py-1.5 text-[13px] text-text-muted shadow-[inset_0_1px_2px_rgba(0,0,0,0.4)] hover:border-border-strong sm:flex lg:w-72"
          >
            <Search size={13} aria-hidden />
            <span className="flex-1 text-left">Search or jump to…</span>
            <kbd className="rounded border border-border px-1 text-[10px] tnum">⌘K</kbd>
          </button>
          <button
            onClick={() => setOpen(true)}
            aria-label="Open search"
            className="ml-auto rounded-lg p-2 text-text-secondary hover:bg-white/[0.05] hover:text-text-primary sm:hidden"
          >
            <Search size={16} aria-hidden />
          </button>
          <BriefingPill />
          <BellButton />
        </header>

        {/* Main content */}
        <main id="main" className="min-w-0 flex-1 pb-20 lg:pb-6">
          <a href="#main" className="sr-only">
            Skip to content
          </a>
          <div className="mx-auto max-w-[1600px] px-4 py-6 lg:px-8">
            <DevModeBanner />
            <PageTransition>{children}</PageTransition>
          </div>
        </main>

        {/* Bottom tab bar — mobile */}
        <nav
          aria-label="Mobile"
          className="fixed bottom-0 left-0 right-0 z-[60] flex border-t border-border bg-bg-secondary/95 backdrop-blur lg:hidden"
        >
          {MOBILE_TABS.map((t) => {
            const active = pathname === t.href;
            const Icon = t.icon;
            return (
              <Link
                key={t.href}
                href={t.href}
                aria-current={active ? "page" : undefined}
                className={cx(
                  "flex min-h-[52px] flex-1 flex-col items-center justify-center gap-0.5 text-[10px] font-semibold",
                  active ? "text-accent-primary" : "text-text-muted",
                )}
              >
                <Icon size={17} aria-hidden />
                {t.label}
              </Link>
            );
          })}
        </nav>
      </div>
    </div>
  );
}
