"use client";

/**
 * En tête du fil : de quoi parle la conversation affichée, et repartir d'une
 * page blanche. L'historique complet est dans la barre latérale.
 */

import { Building2, Plus } from "lucide-react";
import { useAlice } from "../alice-context";

export function ConversationMenu() {
  const { newConversation, hasConversation, activeJob } = useAlice();
  if (!hasConversation && !activeJob) return null;

  return (
    <div className="flex items-center justify-between gap-2">
      {activeJob ? (
        <span className="flex min-w-0 items-center gap-1.5 text-[11px] font-light text-[#1A1918]/50">
          <Building2 className="h-3 w-3 shrink-0 text-[#006045]" />
          <span className="truncate">
            À propos de {activeJob.company} — {activeJob.title}
          </span>
        </span>
      ) : (
        <span />
      )}
      {hasConversation && (
        <button
          type="button"
          onClick={newConversation}
          className="flex shrink-0 items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-light text-[#1A1918]/50 hover:text-[#006045] hover:bg-[#006045]/5 transition-colors cursor-pointer"
        >
          <Plus className="h-3 w-3" /> Nouvelle conversation
        </button>
      )}
    </div>
  );
}
