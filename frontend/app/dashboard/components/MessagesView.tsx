"use client";

/**
 * Messages — les réponses des recruteurs et ce qu'Alice t'a écrit.
 *
 * Aucune boîte de réception n'est encore raccordée : les réponses affichées
 * sont celles que tu as consignées (entretien, offre, refus) depuis
 * Candidatures. La vue le dit plutôt que d'inventer des messages.
 */

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Mail, MessageCircleReply } from "lucide-react";
import { cn } from "@/lib/utils";
import { fetchJournal, type MissionEvent } from "@/lib/mission-client";
import { fetchNotificationHistory, type NotificationRecord } from "@/lib/pipeline-client";

const STATUS_LABEL: Record<NotificationRecord["status"], string> = {
  sent: "envoyé",
  simulated: "non envoyé — aucun service d'e-mail",
  failed: "échec d'envoi",
};

function date(iso: string) {
  return new Date(iso).toLocaleDateString("fr-FR", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

export function MessagesView({
  candidateId,
  onSelectTab,
}: {
  candidateId: string | null;
  onSelectTab: (tab: "candidatures") => void;
}) {
  const [replies, setReplies] = useState<MissionEvent[] | null>(null);
  const [emails, setEmails] = useState<NotificationRecord[]>([]);

  useEffect(() => {
    if (!candidateId) return;
    Promise.all([
      fetchJournal(candidateId, 100),
      fetchNotificationHistory(candidateId),
    ]).then(([journal, history]) => {
      setReplies(journal.filter((e) => e.kind === "reply"));
      setEmails(history ?? []);
    });
  }, [candidateId]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.35 }}
      className="scroll-discreet w-full h-full overflow-y-auto"
    >
      <div className="w-full max-w-[640px] mx-auto text-left space-y-8 py-2 pb-10">
        <div>
          <h2 className="text-xl font-normal text-[#1A1918] tracking-tight">Messages</h2>
          <p className="text-xs text-[#1A1918]/50 mt-0.5 tracking-tight">
            Les réponses des recruteurs, et ce que je t&apos;ai écrit.
          </p>
        </div>

        <section className="space-y-3">
          <div className="flex items-center gap-1.5">
            <MessageCircleReply className="w-3 h-3 stroke-[1.6] text-[#006045]" />
            <p className="text-xs text-[#1A1918]/40 uppercase tracking-wider font-medium">Réponses</p>
          </div>
          {replies === null ? (
            <div className="h-10 rounded-xl bg-[#1A1918]/5 animate-pulse" />
          ) : replies.length === 0 ? (
            <div className="space-y-1.5 py-1">
              <p className="text-sm font-light text-[#1A1918]/55 tracking-tight">Pas encore de réponse consignée.</p>
              <p className="text-xs font-light text-[#1A1918]/40 tracking-tight">
                Un recruteur t&apos;a répondu ? Note-le depuis{" "}
                <button
                  type="button"
                  onClick={() => onSelectTab("candidatures")}
                  className="text-[#006045] hover:underline cursor-pointer"
                >
                  Candidatures
                </button>{" "}
                (Entretien, Offre, Refus) : je m&apos;en sers pour les relances et les bilans.
              </p>
            </div>
          ) : (
            <ul className="border-t border-[#1A1918]/10 divide-y divide-[#1A1918]/8">
              {replies.map((e, i) => (
                <motion.li
                  key={e.id}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.03 }}
                  className="py-3 flex items-start justify-between gap-3"
                >
                  <p className="text-sm font-light text-[#1A1918]/80 tracking-tight">{e.summary}</p>
                  <span className="text-[11px] font-light text-[#1A1918]/35 shrink-0">{date(e.created_at)}</span>
                </motion.li>
              ))}
            </ul>
          )}
        </section>

        <section className="space-y-3">
          <div className="flex items-center gap-1.5">
            <Mail className="w-3 h-3 stroke-[1.6] text-[#006045]" />
            <p className="text-xs text-[#1A1918]/40 uppercase tracking-wider font-medium">
              Ce que je t&apos;ai écrit
            </p>
          </div>
          {emails.length === 0 ? (
            <p className="text-sm font-light text-[#1A1918]/45 tracking-tight py-1">
              Aucun e-mail pour l&apos;instant. Je t&apos;écris à la fin de chaque mission et quand une
              candidature attend ton accord.
            </p>
          ) : (
            <ul className="border-t border-[#1A1918]/10 divide-y divide-[#1A1918]/8">
              {emails.map((n, i) => (
                <motion.li
                  key={n.id}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.03 }}
                  className="py-3 flex items-start justify-between gap-3"
                >
                  <div className="min-w-0">
                    <p className="text-sm font-light text-[#1A1918]/80 tracking-tight truncate">{n.subject}</p>
                    <p
                      className={cn(
                        "text-[11px] font-light tracking-tight",
                        n.status === "sent" ? "text-[#006045]" : n.status === "failed" ? "text-red-600" : "text-[#1A1918]/40",
                      )}
                    >
                      {STATUS_LABEL[n.status]}
                    </p>
                  </div>
                  <span className="text-[11px] font-light text-[#1A1918]/35 shrink-0">{date(n.created_at)}</span>
                </motion.li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </motion.div>
  );
}
