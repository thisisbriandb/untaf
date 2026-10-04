"use client";

/**
 * Historique des conversations — sauvegardées côté serveur, donc retrouvées
 * sur n'importe quel appareil.
 */

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { History, Plus, Trash2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { deleteConversation } from "@/lib/alice-client";
import { useAlice } from "../alice-context";

function when(iso: string): string {
  const d = new Date(iso);
  const days = Math.floor((Date.now() - d.getTime()) / 86_400_000);
  if (days === 0) return d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
  if (days === 1) return "hier";
  return d.toLocaleDateString("fr-FR", { day: "numeric", month: "short" });
}

export function ConversationMenu() {
  const {
    candidateId, conversations, conversationId, newConversation, openConversation,
    refreshConversations, hasConversation,
  } = useAlice();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  if (!conversations.length && !hasConversation) return null;

  return (
    <div ref={ref} className="relative flex items-center justify-end gap-1">
      {hasConversation && (
        <button
          type="button"
          onClick={newConversation}
          className="flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-light text-[#1A1918]/50 hover:text-[#006045] hover:bg-[#006045]/5 transition-colors cursor-pointer"
        >
          <Plus className="h-3 w-3" /> Nouvelle conversation
        </button>
      )}
      {conversations.length > 0 && (
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-label="Conversations précédentes"
          className="flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-light text-[#1A1918]/50 hover:text-[#1A1918] hover:bg-[#1A1918]/5 transition-colors cursor-pointer"
        >
          <History className="h-3 w-3" /> Historique
        </button>
      )}

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: 4, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 4, scale: 0.97 }}
            transition={{ type: "spring", stiffness: 420, damping: 32 }}
            style={{ transformOrigin: "top right" }}
            className="absolute right-0 top-8 z-40 w-80 max-w-[calc(100vw-2rem)] max-h-80 overflow-y-auto scroll-discreet bg-white border border-[#EDECEA] rounded-2xl shadow-lg p-1.5"
          >
            {conversations.map((c) => (
              <div
                key={c.id}
                className={cn(
                  "group flex items-center gap-2 rounded-xl px-2.5 py-2 hover:bg-[#FAFAF8]",
                  c.id === conversationId && "bg-[#006045]/5",
                )}
              >
                <button
                  type="button"
                  onClick={() => {
                    setOpen(false);
                    void openConversation(c.id);
                  }}
                  className="min-w-0 flex-1 text-left cursor-pointer"
                >
                  <span className="block truncate text-xs text-[#1A1918]/80 tracking-tight">{c.title}</span>
                  <span className="block text-[10px] font-light text-[#1A1918]/35">{when(c.updated_at)}</span>
                </button>
                <button
                  type="button"
                  aria-label="Supprimer la conversation"
                  onClick={async () => {
                    if (!candidateId) return;
                    await deleteConversation(candidateId, c.id);
                    if (c.id === conversationId) newConversation();
                    void refreshConversations();
                  }}
                  className="p-1 rounded-full text-[#1A1918]/25 opacity-0 group-hover:opacity-100 hover:text-red-600 cursor-pointer"
                >
                  <Trash2 className="h-3 w-3" />
                </button>
              </div>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
