"use client";
/**
 * Client-side providers: TanStack Query + toasts.
 * Global UI store choice (docs/11 §12.1): React context (toast) + TanStack Query
 * cache as the server-state store. Command-bar open state lives here too.
 */
import { createContext, useContext, useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MotionConfig } from "framer-motion";
import { ToastProvider } from "./toast";

const CmdCtx = createContext<{ open: boolean; setOpen: (v: boolean) => void }>({
  open: false,
  setOpen: () => {},
});

export function useCommandBarState() {
  return useContext(CmdCtx);
}

let client: QueryClient | null = null;
function getClient() {
  if (!client) {
    client = new QueryClient({
      defaultOptions: {
        queries: {
          refetchOnWindowFocus: true,
          retry: (count, err: unknown) => {
            // Don't retry client errors (4xx) — they carry contract envelopes.
            const status = (err as { status?: number })?.status ?? 0;
            if (status >= 400 && status < 500) return false;
            return count < 2;
          },
        },
      },
    });
  }
  return client;
}

export function Providers({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <QueryClientProvider client={getClient()}>
      {/* reducedMotion="user" — all Motion animation honors prefers-reduced-motion */}
      <MotionConfig reducedMotion="user">
        <ToastProvider>
          <CmdCtx.Provider value={{ open, setOpen }}>{children}</CmdCtx.Provider>
        </ToastProvider>
      </MotionConfig>
    </QueryClientProvider>
  );
}
