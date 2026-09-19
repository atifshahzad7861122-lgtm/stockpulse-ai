"use client";
/**
 * Hand-rolled UI primitives — precision-instrument design system (2026-09-19).
 * Champagne gold is the single accent; racing red is alerts only.
 * Physical depth via layered soft shadows; Bodoni Moda reserved for hero
 * headlines; Inter tabular numerals for all telemetry.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useId,
  useRef,
  useState,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from "react";
import { AnimatePresence, motion } from "framer-motion";
import { overlayTransition } from "./motion/easing";
import { CountUp } from "./motion/motion";
import { AlertTriangle, ChevronDown, Inbox, Loader2, RefreshCw, X } from "lucide-react";
import { errorMessage, errorTraceId } from "../services/api";

export function cx(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}

// ---------------------------------------------------------------------------
// Button
// ---------------------------------------------------------------------------

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger" | "outline";
type ButtonSize = "sm" | "md" | "lg";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  icon?: ReactNode;
}

const BTN_BASE =
  "inline-flex items-center justify-center gap-1.5 rounded-lg font-semibold tracking-[-0.01em] transition-all duration-150 " +
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-primary " +
  "disabled:cursor-not-allowed disabled:bg-surface-elevated disabled:text-text-muted disabled:border-transparent disabled:shadow-none " +
  "active:translate-y-px";

const BTN_VARIANTS: Record<ButtonVariant, string> = {
  // Champagne gold, near-black text — the one primary action color.
  primary:
    "bg-accent-primary text-[#171307] shadow-[inset_0_1px_0_rgba(255,255,255,0.35),0_8px_20px_-8px_rgba(214,178,94,0.45)] hover:bg-accent-secondary",
  secondary:
    "bg-surface-elevated text-text-primary border border-border shadow-depth1 hover:border-border-strong hover:bg-[#202027]",
  ghost: "text-text-secondary hover:text-text-primary hover:bg-white/[0.04]",
  // Racing red — alerts / destructive only.
  danger:
    "bg-status-danger text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.2),0_8px_20px_-8px_rgba(225,6,0,0.5)] hover:brightness-110",
  outline:
    "border border-border-strong text-text-secondary hover:text-text-primary hover:border-text-muted hover:bg-white/[0.03]",
};

const BTN_SIZES: Record<ButtonSize, string> = {
  sm: "px-3 py-1.5 text-xs",
  md: "px-4 py-2 text-[13px]",
  lg: "px-5 py-2.5 text-sm",
};

export function Button({
  variant = "secondary",
  size = "md",
  loading,
  icon,
  children,
  disabled,
  className,
  ...rest
}: ButtonProps) {
  return (
    <button
      className={cx(BTN_BASE, BTN_VARIANTS[variant], BTN_SIZES[size], className)}
      disabled={disabled || loading}
      {...rest}
    >
      {loading ? <Loader2 size={14} className="animate-spin" aria-hidden /> : icon}
      {children}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Card / Panel — physical depth, hairline borders
// ---------------------------------------------------------------------------

export function Card({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cx("depth-1 rounded-xl border border-border bg-surface-base", className)}>
      {children}
    </div>
  );
}

/** A dashboard/section panel: title row + body. */
export function Panel({
  title,
  subtitle,
  action,
  children,
  className,
  bodyClassName,
  pad = true,
}: {
  title?: ReactNode;
  subtitle?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
  pad?: boolean;
}) {
  return (
    <section className={cx("depth-1 rounded-xl border border-border bg-surface-base", className)}>
      {title && (
        <header className="flex items-center justify-between gap-3 border-b border-border/70 px-5 py-3">
          <div>
            <h2 className="text-[13px] font-semibold tracking-[-0.01em] text-text-primary">{title}</h2>
            {subtitle && <p className="mt-0.5 text-[11px] text-text-muted">{subtitle}</p>}
          </div>
          {action}
        </header>
      )}
      <div className={cx(pad && "p-5", bodyClassName)}>{children}</div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Badge
// ---------------------------------------------------------------------------

type BadgeTone = "success" | "warning" | "danger" | "info" | "muted" | "accent" | "neutral";

const BADGE_CLASSES: Record<BadgeTone, string> = {
  success: "chip-success",
  warning: "chip-warning",
  danger: "chip-danger",
  info: "chip-info",
  muted: "bg-white/[0.05] text-text-muted",
  accent: "chip-accent",
  neutral: "bg-white/[0.05] text-text-secondary",
};

export function Badge({
  tone = "neutral",
  children,
  className,
  title,
}: {
  tone?: BadgeTone;
  children: ReactNode;
  className?: string;
  title?: string;
}) {
  return (
    <span
      title={title}
      className={cx(
        "inline-flex items-center gap-1 whitespace-nowrap rounded-md px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-[0.07em] leading-4",
        BADGE_CLASSES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Inputs
// ---------------------------------------------------------------------------

const INPUT_BASE =
  "w-full rounded-lg border border-border bg-bg-secondary px-3 py-2 text-[13px] text-text-primary " +
  "placeholder:text-text-muted focus:border-accent-primary focus:outline-none disabled:opacity-50 " +
  "shadow-[inset_0_1px_2px_rgba(0,0,0,0.4)] transition-colors";

export function Field({
  label,
  hint,
  error,
  required,
  children,
  htmlFor,
}: {
  label: string;
  hint?: string;
  error?: string;
  required?: boolean;
  children: ReactNode;
  htmlFor?: string;
}) {
  const id = useId();
  return (
    <div className="space-y-1.5">
      <label htmlFor={htmlFor ?? id} className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-text-muted">
        {label} {required && <span className="text-status-danger">*</span>}
      </label>
      {children}
      {hint && !error && <p className="text-xs text-text-muted">{hint}</p>}
      {error && (
        <p className="text-xs text-status-danger" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={cx(INPUT_BASE, props.className)} />;
}

export function Textarea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...props} className={cx(INPUT_BASE, "min-h-[88px] resize-y leading-relaxed", props.className)} />;
}

export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <div className="relative">
      <select
        {...props}
        className={cx(INPUT_BASE, "appearance-none pr-8", props.className)}
      />
      <ChevronDown
        size={14}
        className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-text-muted"
        aria-hidden
      />
    </div>
  );
}

export function Checkbox({
  label,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { label?: ReactNode }) {
  return (
    <label className="inline-flex cursor-pointer items-center gap-2 text-[13px] text-text-secondary">
      <input
        type="checkbox"
        {...props}
        className="h-4 w-4 rounded border-border bg-surface-base accent-[#D6B25E]"
      />
      {label}
    </label>
  );
}

// ---------------------------------------------------------------------------
// Tabs
// ---------------------------------------------------------------------------

export function Tabs({
  tabs,
  value,
  onChange,
  className,
}: {
  tabs: { value: string; label: ReactNode; count?: number }[];
  value: string;
  onChange: (v: string) => void;
  className?: string;
}) {
  return (
    <div className={cx("flex gap-1 border-b border-border", className)} role="tablist">
      {tabs.map((t) => {
        const active = t.value === value;
        return (
          <button
            key={t.value}
            role="tab"
            aria-selected={active}
            onClick={() => onChange(t.value)}
            className={cx(
              "-mb-px border-b-2 px-3 py-2 text-[13px] font-semibold transition-colors",
              active
                ? "border-accent-primary text-text-primary"
                : "border-transparent text-text-muted hover:text-text-secondary",
            )}
          >
            {t.label}
            {t.count !== undefined && (
              <span className="ml-1.5 rounded bg-white/[0.06] px-1.5 py-0.5 text-[10px] text-text-secondary tnum">
                {t.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Modal + Drawer (focus-trapped, Esc closes)
// ---------------------------------------------------------------------------

function useOverlayBehavior(open: boolean, onClose: () => void) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "Tab" && ref.current) {
        const els = ref.current.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
        );
        const list = Array.from(els).filter((el) => !el.hasAttribute("disabled"));
        if (!list.length) return;
        const first = list[0];
        const last = list[list.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    const t = setTimeout(() => {
      const h = ref.current?.querySelector<HTMLElement>("[data-autofocus]");
      (h ?? ref.current?.querySelector<HTMLElement>("button, input, select, textarea"))?.focus();
    }, 30);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
      clearTimeout(t);
    };
  }, [open, onClose]);
  return ref;
}

function OverlayShell({
  open,
  onClose,
  children,
  labelledBy,
  wide,
}: {
  open: boolean;
  onClose: () => void;
  children: ReactNode;
  labelledBy: string;
  wide?: boolean;
}) {
  const ref = useOverlayBehavior(open, onClose);
  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
          className="fixed inset-0 z-[80] bg-black/70 backdrop-blur-[2px]"
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) onClose();
          }}
        >
          <div className="flex h-full items-center justify-center p-4">
            <motion.div
              ref={ref}
              role="dialog"
              aria-modal="true"
              aria-labelledby={labelledBy}
              initial={{ opacity: 0, y: 12, scale: 0.99 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 12, scale: 0.99 }}
              transition={overlayTransition}
              className={cx(
                "depth-3 max-h-[90vh] w-full overflow-y-auto rounded-2xl border border-border bg-surface-elevated",
                wide ? "max-w-3xl" : "max-w-lg",
              )}
            >
              {children}
            </motion.div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export function Modal({
  open,
  onClose,
  title,
  children,
  footer,
  wide,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  footer?: ReactNode;
  wide?: boolean;
}) {
  const titleId = useId();
  return (
    <OverlayShell open={open} onClose={onClose} labelledBy={titleId} wide={wide}>
      <div className="flex items-center justify-between border-b border-border/70 px-5 py-4">
        <h2 id={titleId} className="font-display text-lg text-text-primary" data-autofocus tabIndex={-1}>
          {title}
        </h2>
        <button
          onClick={onClose}
          aria-label="Close dialog"
          className="rounded-lg p-1.5 text-text-muted hover:bg-white/[0.05] hover:text-text-primary"
        >
          <X size={16} />
        </button>
      </div>
      <div className="px-5 py-4">{children}</div>
      {footer && (
        <div className="flex justify-end gap-2 border-t border-border/70 px-5 py-4">{footer}</div>
      )}
    </OverlayShell>
  );
}

/** Confirmation dialog — required for destructive actions. */
export function ConfirmModal({
  open,
  onClose,
  title,
  description,
  confirmLabel = "Confirm",
  danger,
  requireReason,
  reasonLabel = "Reason",
  onConfirm,
  loading,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description: ReactNode;
  confirmLabel?: string;
  danger?: boolean;
  requireReason?: boolean;
  reasonLabel?: string;
  onConfirm: (reason?: string) => void;
  loading?: boolean;
}) {
  const [reason, setReason] = useState("");
  useEffect(() => {
    if (open) setReason("");
  }, [open ]);
  const canConfirm = !requireReason || reason.trim().length > 0;
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={title}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant={danger ? "danger" : "primary"}
            loading={loading}
            disabled={!canConfirm}
            onClick={() => onConfirm(reason || undefined)}
          >
            {confirmLabel}
          </Button>
        </>
      }
    >
      <div className="text-[13px] leading-relaxed text-text-secondary">{description}</div>
      {requireReason && (
        <div className="mt-4">
          <Field label={reasonLabel} required>
            <Textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="A reason is required — it is written to the audit log."
            />
          </Field>
        </div>
      )}
    </Modal>
  );
}

export function Drawer({
  open,
  onClose,
  title,
  children,
  footer,
  wide,
}: {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  wide?: boolean;
}) {
  const ref = useOverlayBehavior(open, onClose);
  const titleId = useId();
  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
          className="fixed inset-0 z-[80] bg-black/70 backdrop-blur-[2px]"
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) onClose();
          }}
        >
          <motion.aside
            ref={ref}
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
            initial={{ x: 48, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: 48, opacity: 0 }}
            transition={overlayTransition}
            className={cx(
              "depth-3 absolute right-0 top-0 flex h-full w-full flex-col border-l border-border bg-surface-elevated",
              wide ? "max-w-2xl" : "max-w-lg",
            )}
          >
            <div className="flex items-center justify-between border-b border-border/70 px-5 py-4">
              <h2 id={titleId} className="font-display text-lg text-text-primary" data-autofocus tabIndex={-1}>
                {title}
              </h2>
              <button
                onClick={onClose}
                aria-label="Close drawer"
                className="rounded-lg p-1.5 text-text-muted hover:bg-white/[0.05] hover:text-text-primary"
              >
                <X size={16} />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto px-5 py-4">{children}</div>
            {footer && <div className="border-t border-border/70 px-5 py-4">{footer}</div>}
          </motion.aside>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

// ---------------------------------------------------------------------------
// Tooltip (hover/focus, CSS-positioned)
// ---------------------------------------------------------------------------

export function Tooltip({ label, children }: { label: string; children: ReactNode }) {
  return (
    <span className="group relative inline-flex">
      {children}
      <span
        role="tooltip"
        className="depth-2 pointer-events-none absolute bottom-full left-1/2 z-[90] mb-1.5 hidden w-max max-w-[260px] -translate-x-1/2 rounded-lg border border-border bg-surface-elevated px-2.5 py-1.5 text-xs leading-snug text-text-primary shadow-lg group-hover:block group-focus-within:block"
      >
        {label}
      </span>
    </span>
  );
}

// ---------------------------------------------------------------------------
// Skeleton
// ---------------------------------------------------------------------------

export function Skeleton({ className, lines }: { className?: string; lines?: number }) {
  if (lines) {
    return (
      <div className="space-y-2" aria-hidden>
        {Array.from({ length: lines }).map((_, i) => (
          <div key={i} className={cx("skeleton h-3.5 rounded", i === lines - 1 && "w-2/3", className)} />
        ))}
      </div>
    );
  }
  return <div aria-hidden className={cx("skeleton rounded", className)} />;
}

export function TableSkeleton({ rows = 6, cols = 5 }: { rows?: number; cols?: number }) {
  return (
    <div aria-hidden className="divide-y divide-border">
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} className="flex gap-4 px-4 py-3">
          {Array.from({ length: cols }).map((_, c) => (
            <div key={c} className="skeleton h-4 flex-1 rounded" />
          ))}
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Empty / Error states
// ---------------------------------------------------------------------------

export function EmptyState({
  icon,
  title,
  description,
  action,
  compact: compactMode,
}: {
  icon?: ReactNode;
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  compact?: boolean;
}) {
  return (
    <div className={cx("flex flex-col items-center justify-center text-center", compactMode ? "py-8" : "py-14")}>
      <div className="depth-1 mb-3 flex h-11 w-11 items-center justify-center rounded-xl border border-border bg-surface-elevated text-text-muted">
        {icon ?? <Inbox size={18} aria-hidden />}
      </div>
      <p className="font-display text-[17px] text-text-primary">{title}</p>
      {description && <div className="mt-1.5 max-w-md text-[13px] leading-relaxed text-text-muted">{description}</div>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorState({
  title = "Something failed to load",
  message,
  onRetry,
  traceId,
  compact: compactMode,
}: {
  title?: string;
  message?: string;
  onRetry?: () => void;
  traceId?: string;
  compact?: boolean;
}) {
  return (
    <div
      role="alert"
      className={cx(
        "flex flex-col items-center justify-center rounded-xl border border-status-danger/40 bg-status-danger/[0.07] text-center",
        compactMode ? "px-4 py-6" : "px-6 py-10",
      )}
    >
      <AlertTriangle size={18} className="mb-2 text-status-danger" aria-hidden />
      <p className="text-sm font-semibold text-text-primary">{title}</p>
      {message && <p className="mt-1 max-w-md text-[13px] text-text-secondary">{message}</p>}
      {traceId && <p className="mt-1 font-mono text-[11px] text-text-muted">trace {traceId}</p>}
      {onRetry && (
        <Button variant="outline" size="sm" className="mt-3" icon={<RefreshCw size={13} />} onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page header — kicker + serif headline (hero moment), telemetry description
// ---------------------------------------------------------------------------

export function PageHeader({
  title,
  description,
  actions,
  badge,
  kicker,
}: {
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
  badge?: ReactNode;
  kicker?: string;
}) {
  return (
    <header className="mb-6 flex flex-wrap items-start justify-between gap-3">
      <div>
        {kicker && <p className="kicker mb-1.5">{kicker}</p>}
        <div className="flex items-center gap-3">
          <h1 className="font-display text-[30px] font-medium leading-tight tracking-[-0.01em] text-text-primary">
            {title}
          </h1>
          {badge}
        </div>
        {description && <p className="mt-1.5 max-w-3xl text-[13px] leading-relaxed text-text-muted">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2 pt-1">{actions}</div>}
    </header>
  );
}

// ---------------------------------------------------------------------------
// "Why this" expander — every recommendation explains itself
// ---------------------------------------------------------------------------

export function WhyThis({ children, label = "Why this" }: { children: ReactNode; label?: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mt-2">
      <button
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="inline-flex items-center gap-1 text-xs font-medium text-text-muted hover:text-text-secondary"
      >
        <ChevronDown size={13} className={cx("transition-transform", open && "rotate-180")} aria-hidden />
        {label}
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={overlayTransition}
            className="overflow-hidden"
          >
            <div className="mt-1.5 rounded-lg border border-border bg-bg-secondary p-3 text-[12.5px] leading-relaxed text-text-secondary">
              {children}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ---------------------------------------------------------------------------
// KPI card — F1 telemetry readout: micro label, bold tabular numeral
// ---------------------------------------------------------------------------

export function KpiCard({
  label,
  value,
  delta,
  provenance,
  loading,
  hint,
  countTo,
  countFormat,
}: {
  label: string;
  value: ReactNode;
  delta?: ReactNode;
  provenance?: ReactNode;
  loading?: boolean;
  hint?: string;
  /** When set, the value animates as a telemetry count-up instead of rendering `value`. */
  countTo?: number | null;
  countFormat?: (n: number) => string;
}) {
  return (
    <div className="depth-1 rounded-xl border border-border bg-surface-base p-4">
      <p className="text-[10px] font-semibold uppercase tracking-[0.1em] text-text-muted">{label}</p>
      {loading ? (
        <div className="skeleton mt-2.5 h-8 w-24 rounded" aria-hidden />
      ) : countTo !== undefined && countTo !== null ? (
        <p className="tnum mt-1.5 text-[30px] font-bold leading-none tracking-[-0.02em] text-text-primary">
          <CountUp value={countTo} format={countFormat} />
        </p>
      ) : (
        <p className="tnum mt-1.5 text-[30px] font-bold leading-none tracking-[-0.02em] text-text-primary">{value}</p>
      )}
      {(delta || provenance || hint) && (
        <div className="mt-2 flex items-center gap-2 text-xs text-text-muted">
          {delta}
          {provenance}
          {hint && !provenance && <span>{hint}</span>}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Pagination
// ---------------------------------------------------------------------------

export function Pagination({
  page,
  totalPages,
  onChange,
}: {
  page: number;
  totalPages: number;
  onChange: (p: number) => void;
}) {
  if (totalPages <= 1) return null;
  return (
    <nav aria-label="Pagination" className="flex items-center justify-center gap-1 py-3">
      <Button size="sm" variant="ghost" disabled={page <= 1} onClick={() => onChange(page - 1)}>
        Prev
      </Button>
      <span className="tnum px-2 text-xs text-text-muted" aria-live="polite">
        Page {page} of {totalPages}
      </span>
      <Button size="sm" variant="ghost" disabled={page >= totalPages} onClick={() => onChange(page + 1)}>
        Next
      </Button>
    </nav>
  );
}

// ---------------------------------------------------------------------------
// Data table — precision timing-sheet styling
// ---------------------------------------------------------------------------

export interface Column<T> {
  key: string;
  header: ReactNode;
  render: (row: T) => ReactNode;
  className?: string;
  sortKey?: string;
}

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  onRowClick,
  loading,
  empty,
  sort,
  onSort,
  testId,
}: {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  onRowClick?: (row: T) => void;
  loading?: boolean;
  empty?: ReactNode;
  sort?: string;
  onSort?: (sort: string) => void;
  testId?: string;
}) {
  if (loading) return <TableSkeleton rows={6} cols={columns.length} />;
  if (!rows.length)
    return (
      <div className="border-t border-border">
        {empty ?? <EmptyState compact title="No rows" description="Nothing matches the current filters." />}
      </div>
    );
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-left text-[13px]" data-testid={testId}>
        <thead>
          <tr className="border-b border-border">
            {columns.map((c) => (
              <th
                key={c.key}
                scope="col"
                className={cx(
                  "px-3 py-2.5 text-[10px] font-semibold uppercase tracking-[0.1em] text-text-muted",
                  c.className,
                )}
              >
                {c.sortKey && onSort ? (
                  <button
                    onClick={() => onSort(sort === `-${c.sortKey}` ? c.sortKey! : `-${c.sortKey}`)}
                    className="inline-flex items-center gap-1 hover:text-text-secondary"
                    aria-label={`Sort by ${c.key}`}
                  >
                    {c.header}
                    <span aria-hidden className="text-[10px] text-accent-primary">
                      {sort === `-${c.sortKey}` ? "▼" : sort === c.sortKey ? "▲" : ""}
                    </span>
                  </button>
                ) : (
                  c.header
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-border/60">
          {rows.map((row) => (
            <tr
              key={rowKey(row)}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
              className={cx(
                "transition-colors hover:bg-white/[0.025]",
                onRowClick && "cursor-pointer",
              )}
            >
              {columns.map((c) => (
                <td key={c.key} className={cx("px-3 py-2.5 align-top text-text-secondary tnum", c.className)}>
                  {c.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Query-state wrapper: loading / error / empty / data — no blank screens.
// ---------------------------------------------------------------------------

export function QueryView<T>({
  query: { data, isLoading, isError, error, refetch, isFetching },
  loading,
  empty,
  errorTitle,
  children,
  minHeight,
}: {
  query: {
    data: T | undefined;
    isLoading: boolean;
    isError: boolean;
    // unknown on purpose: React Query surfaces whatever the queryFn threw —
    // contract ApiClientErrors AND plain network TypeErrors (no .envelope).
    error: unknown;
    refetch: () => void;
    isFetching?: boolean;
  };
  loading?: ReactNode;
  empty?: ReactNode;
  errorTitle?: string;
  children: (data: T) => ReactNode;
  minHeight?: string;
}) {
  if (isLoading) {
    return (
      <div style={minHeight ? { minHeight } : undefined} aria-busy="true" aria-label="Loading">
        {loading ?? <Skeleton lines={5} />}
      </div>
    );
  }
  if (isError) {
    return (
      <ErrorState
        title={errorTitle ?? "Could not load this data"}
        message={errorMessage(error)}
        traceId={errorTraceId(error)}
        onRetry={() => refetch()}
      />
    );
  }
  if (data === undefined || data === null) {
    return <>{empty ?? <EmptyState title="No data" />}</>;
  }
  return (
    <>
      {isFetching && (
        <span className="sr-only" aria-live="polite">
          Updating…
        </span>
      )}
      {children(data)}
    </>
  );
}

// ---------------------------------------------------------------------------
// Dismissible banner
// ---------------------------------------------------------------------------

const BannerCtx = createContext<{ dismiss: (id: string) => void }>({ dismiss: () => {} });

export function BannerStack({ children }: { children: ReactNode }) {
  const [dismissed, setDismissed] = useState<string[]>([]);
  const dismiss = useCallback((id: string) => setDismissed((d) => [...d, id]), []);
  void dismissed;
  return <BannerCtx.Provider value={{ dismiss }}>{children}</BannerCtx.Provider>;
}

export function Banner({
  id,
  tone,
  children,
  className,
}: {
  id: string;
  tone: "info" | "warning" | "danger" | "success";
  children: ReactNode;
  className?: string;
}) {
  const { dismiss } = useContext(BannerCtx);
  const [gone, setGone] = useState(false);
  if (gone) return null;
  const tones: Record<string, string> = {
    info: "border-border bg-surface-base text-text-secondary",
    warning: "border-status-warning/30 bg-status-warning/[0.06] text-text-secondary",
    danger: "border-status-danger/40 bg-status-danger/[0.08] text-text-secondary",
    success: "border-status-success/30 bg-status-success/[0.06] text-text-secondary",
  };
  return (
    <div className={cx("depth-1 flex items-start gap-2.5 rounded-xl border px-4 py-3 text-[13px]", tones[tone], className)}>
      <div className="flex-1 leading-relaxed">{children}</div>
      <button
        aria-label="Dismiss"
        onClick={() => {
          setGone(true);
          dismiss(id);
        }}
        className="rounded p-0.5 text-text-muted hover:text-text-primary"
      >
        <X size={14} />
      </button>
    </div>
  );
}
