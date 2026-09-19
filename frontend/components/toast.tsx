"use client";
/**
 * Toast system — docs/06 §3.29: confirm completions, auto-dismiss 4s,
 * errors persist until dismissed, stacked max 3.
 */
import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { overlayTransition } from "./motion/easing";
import { AlertCircle, CheckCircle2, Info, X } from "lucide-react";

export type ToastTone = "success" | "warning" | "danger" | "info";

export interface ToastInput {
  title: string;
  description?: string;
  tone?: ToastTone;
  durationMs?: number;
}

interface ToastItem extends ToastInput {
  id: number;
  tone: ToastTone;
}

const ToastCtx = createContext<{ toast: (t: ToastInput) => void }>({ toast: () => {} });

export function useToast() {
  return useContext(ToastCtx);
}

const ICONS: Record<ToastTone, typeof Info> = {
  success: CheckCircle2,
  warning: AlertCircle,
  danger: AlertCircle,
  info: Info,
};

const TONE_CLASSES: Record<ToastTone, string> = {
  success: "text-status-success",
  warning: "text-status-warning",
  danger: "text-status-danger",
  info: "text-status-info",
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const idRef = useRef(1);

  const dismiss = useCallback((id: number) => {
    setItems((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const toast = useCallback(
    (t: ToastInput) => {
      const id = idRef.current++;
      const tone = t.tone ?? "info";
      setItems((prev) => [...prev.slice(-2), { ...t, id, tone }]);
      // Errors persist; everything else auto-dismisses after 4s.
      if (tone !== "danger") {
        setTimeout(() => dismiss(id), t.durationMs ?? 4000);
      }
    },
    [dismiss],
  );

  return (
    <ToastCtx.Provider value={{ toast }}>
      {children}
      <div
        aria-live="polite"
        className="pointer-events-none fixed bottom-4 right-4 z-[100] flex w-[360px] max-w-[calc(100vw-2rem)] flex-col gap-2"
      >
        <AnimatePresence>
          {items.map((t) => {
            const Icon = ICONS[t.tone];
            return (
              <motion.div
                key={t.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 8 }}
                transition={overlayTransition}
                className="pointer-events-auto flex items-start gap-3 rounded-lg border border-border bg-surface-elevated px-3.5 py-3 shadow-lg"
              >
                <Icon size={16} className={`mt-0.5 shrink-0 ${TONE_CLASSES[t.tone]}`} aria-hidden />
                <div className="min-w-0 flex-1">
                  <p className="text-[13px] font-semibold text-text-primary">{t.title}</p>
                  {t.description && (
                    <p className="mt-0.5 text-[12px] leading-snug text-text-secondary">{t.description}</p>
                  )}
                </div>
                <button
                  onClick={() => dismiss(t.id)}
                  aria-label="Dismiss notification"
                  className="shrink-0 rounded p-0.5 text-text-muted hover:text-text-primary"
                >
                  <X size={14} />
                </button>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    </ToastCtx.Provider>
  );
}
