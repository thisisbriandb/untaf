"use client";

/**
 * Retours d'action discrets — « Candidature envoyée », « Relance copiée ».
 *
 * Chaque geste qui a un effet hors de l'écran (un envoi, une validation) doit
 * être confirmé là où l'utilisateur regarde, sans le forcer à vérifier
 * ailleurs. Un toast suffit ; il s'efface seul.
 */

import { createContext, useCallback, useContext, useState, type ReactNode } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Check, Info, TriangleAlert } from "lucide-react";
import { cn } from "@/lib/utils";

type Tone = "success" | "info" | "warning";

interface Toast {
  id: string;
  tone: Tone;
  text: string;
}

const ToastContext = createContext<(text: string, tone?: Tone) => void>(() => {});

const ICONS = { success: Check, info: Info, warning: TriangleAlert };

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const push = useCallback((text: string, tone: Tone = "success") => {
    const id = crypto.randomUUID();
    setToasts((prev) => [...prev.slice(-2), { id, tone, text }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 4200);
  }, []);

  return (
    <ToastContext.Provider value={push}>
      {children}
      <div
        aria-live="polite"
        className="pointer-events-none fixed bottom-5 left-1/2 -translate-x-1/2 z-[100] flex flex-col items-center gap-2 w-[min(92vw,420px)]"
      >
        <AnimatePresence initial={false}>
          {toasts.map((t) => {
            const Icon = ICONS[t.tone];
            return (
              <motion.div
                key={t.id}
                layout
                initial={{ opacity: 0, y: 16, scale: 0.96 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 8, scale: 0.97 }}
                transition={{ type: "spring", stiffness: 420, damping: 32 }}
                className="pointer-events-auto flex items-center gap-2.5 rounded-full bg-[#1A1918] text-white pl-3 pr-4 py-2.5 shadow-lg shadow-black/10"
              >
                <span
                  className={cn(
                    "flex h-5 w-5 shrink-0 items-center justify-center rounded-full",
                    t.tone === "success" && "bg-[#006045]",
                    t.tone === "info" && "bg-white/15",
                    t.tone === "warning" && "bg-[#006045]",
                  )}
                >
                  <Icon className="h-3 w-3 stroke-[2.2]" />
                </span>
                <span className="text-xs font-normal tracking-tight">{t.text}</span>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  );
}

export const useToast = () => useContext(ToastContext);
