"use client";

/**
 * Les conversations, rangées : le fil général avec Alice, puis une
 * conversation par offre, sous le nom de l'entreprise.
 *
 * Chaque conversation d'offre garde son propre contexte (l'annonce, le
 * dossier, ce qui s'est dit) : parler de Doctolib ne pollue pas ce qui se dit
 * sur Alan. Les chiffres, eux, restent communs — ils viennent de la base à
 * chaque tour, pas de la conversation.
 */

import { AnimatePresence, motion } from "framer-motion";
import { Building2, MessageCircle, Plus, Trash2, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { deleteConversation, type ConversationSummary } from "@/lib/alice-client";
import { useAlice } from "../alice-context";

function when(iso: string): string {
  const d = new Date(iso);
  const days = Math.floor((Date.now() - d.getTime()) / 86_400_000);
  if (days === 0) return d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
  if (days === 1) return "hier";
  return d.toLocaleDateString("fr-FR", { day: "numeric", month: "short" });
}

export function ConversationSidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  const {
    candidateId, conversations, conversationId, openConversation, newConversation,
    refreshConversations, goToConversation,
  } = useAlice();

  const general = conversations.filter((c) => !c.job_id);
  const byJob = conversations.filter((c) => c.job_id);

  const select = (c: ConversationSummary) => {
    void openConversation(c.id);
    goToConversation();
    if (window.innerWidth < 1024) onClose();
  };

  const remove = async (c: ConversationSummary) => {
    if (!candidateId) return;
    await deleteConversation(candidateId, c.id);
    if (c.id === conversationId) newConversation();
    void refreshConversations();
  };

  const Item = ({ c, label, sub }: { c: ConversationSummary; label: string; sub?: string }) => (
    <div
      className={cn(
        "group flex items-center gap-2 rounded-xl px-2.5 py-2 transition-colors",
        c.id === conversationId ? "bg-[#006045]/8" : "hover:bg-[#1A1918]/[0.04]",
      )}
    >
      <button type="button" onClick={() => select(c)} className="min-w-0 flex-1 text-left cursor-pointer">
        <span className="block truncate text-[13px] text-[#1A1918]/85 tracking-tight">{label}</span>
        <span className="block truncate text-[10px] font-light text-[#1A1918]/40">
          {sub ? `${sub} · ` : ""}
          {when(c.updated_at)}
        </span>
      </button>
      <button
        type="button"
        aria-label="Supprimer la conversation"
        onClick={() => void remove(c)}
        className="p-1 rounded-full text-[#1A1918]/25 opacity-0 group-hover:opacity-100 hover:text-red-600 cursor-pointer"
      >
        <Trash2 className="h-3 w-3" />
      </button>
    </div>
  );

  return (
    <AnimatePresence>
      {open && (
        <motion.aside
          initial={{ x: -24, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          exit={{ x: -24, opacity: 0 }}
          transition={{ type: "spring", stiffness: 420, damping: 36 }}
          className="fixed lg:static left-0 top-[64px] bottom-0 z-40 w-[260px] shrink-0 bg-[#FAFAF8] lg:bg-transparent border-r border-[#1A1918]/6 flex flex-col"
        >
          <div className="flex items-center justify-between px-4 pt-2 pb-3">
            <button
              type="button"
              onClick={() => {
                newConversation();
                goToConversation();
              }}
              className="flex items-center gap-1.5 rounded-full border border-[#1A1918]/10 bg-white px-3 py-1.5 text-[11px] text-[#1A1918]/70 hover:border-[#006045]/40 hover:text-[#006045] transition-colors cursor-pointer"
            >
              <Plus className="h-3 w-3" /> Nouvelle conversation
            </button>
            <button
              type="button"
              onClick={onClose}
              aria-label="Fermer"
              className="p-1.5 rounded-full text-[#1A1918]/35 hover:text-[#1A1918] cursor-pointer lg:hidden"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>

          <div className="scroll-discreet flex-1 overflow-y-auto px-2 pb-6 space-y-5">
            <section className="space-y-0.5">
              <p className="flex items-center gap-1.5 px-2.5 pb-1 text-[10px] uppercase tracking-wider text-[#1A1918]/35">
                <MessageCircle className="h-3 w-3" /> Avec Alice
              </p>
              {general.length === 0 ? (
                <p className="px-2.5 text-[11px] font-light text-[#1A1918]/35">Pas encore de conversation.</p>
              ) : (
                general.map((c) => <Item key={c.id} c={c} label={c.title} />)
              )}
            </section>

            <section className="space-y-0.5">
              <p className="flex items-center gap-1.5 px-2.5 pb-1 text-[10px] uppercase tracking-wider text-[#1A1918]/35">
                <Building2 className="h-3 w-3" /> Par offre
              </p>
              {byJob.length === 0 ? (
                <p className="px-2.5 text-[11px] font-light text-[#1A1918]/35 leading-relaxed">
                  Pose une question depuis une offre : la conversation se range ici, sous le nom de
                  l&apos;entreprise.
                </p>
              ) : (
                byJob.map((c) => (
                  <Item key={c.id} c={c} label={c.company_name || c.title} sub={c.job_title ?? undefined} />
                ))
              )}
            </section>
          </div>
        </motion.aside>
      )}
    </AnimatePresence>
  );
}
