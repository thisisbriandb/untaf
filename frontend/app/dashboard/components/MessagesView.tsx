"use client";

/**
 * Messages — les réponses des recruteurs et ce qu'Alice t'a écrit.
 *
 * Les réponses arrivent sur ton adresse de candidature : Alice les lit
 * (entretien, refus, demande…), met ton suivi à jour et te les transfère.
 * Celles que tu as notées toi-même depuis Candidatures restent listées à part.
 */

import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Check, Copy, Inbox as InboxIcon, Loader2, Mail, MessageCircleReply, Reply as ReplyIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { fetchJournal, type MissionEvent } from "@/lib/mission-client";
import { fetchNotificationHistory, type NotificationRecord } from "@/lib/pipeline-client";
import {
  fetchInbox, fetchReply, KIND_LABEL, replyMailto,
  type Inbox, type Reply, type ReplyDetail, type ReplyKind,
} from "@/lib/inbox-client";

const KIND_TONE: Record<ReplyKind, string> = {
  interview: "bg-[#006045] text-white",
  offer: "bg-[#006045] text-white",
  request: "bg-[#1A1918] text-white",
  rejection: "bg-[#1A1918]/[0.07] text-[#1A1918]/70",
  acknowledgement: "ring-1 ring-[#1A1918]/12 text-[#1A1918]/60",
  other: "ring-1 ring-[#1A1918]/12 text-[#1A1918]/60",
};

function ReplyRow({ reply, candidateId, index, onRead }: { reply: Reply; candidateId: string; index: number; onRead: () => void }) {
  const [open, setOpen] = useState(false);
  const [detail, setDetail] = useState<ReplyDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [read, setRead] = useState(reply.read);

  const toggle = async () => {
    const next = !open;
    setOpen(next);
    if (next && !detail) {
      setLoading(true);
      setDetail(await fetchReply(candidateId, reply.id));
      setLoading(false);
      if (!read) onRead();
      setRead(true);
    }
  };

  const who = reply.company_name || reply.from_name || reply.from_email;
  return (
    <motion.li
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.03 }}
      className="py-3"
    >
      <button type="button" onClick={toggle} className="w-full text-left cursor-pointer group">
        <div className="flex items-center gap-2 flex-wrap">
          {!read && <span className="h-1.5 w-1.5 rounded-full bg-[#006045]" aria-label="non lu" />}
          <span className={cn("rounded-full px-2 py-0.5 text-[10.5px] tracking-tight", KIND_TONE[reply.kind])}>
            {KIND_LABEL[reply.kind]}
          </span>
          <span className={cn("text-[13px] tracking-tight", read ? "text-[#1A1918]/75" : "text-[#161615]")}>{who}</span>
          {reply.job_title && <span className="text-[12px] text-[#1A1918]/50 truncate">· {reply.job_title}</span>}
          <span className="ml-auto text-[11px] text-[#1A1918]/50 shrink-0">{date(reply.received_at)}</span>
        </div>
        <p className="mt-1 text-sm font-light text-[#1A1918]/80 tracking-tight group-hover:text-[#161615]">
          {reply.summary}
        </p>
        {reply.next_step && (
          <p className="mt-0.5 text-[12px] text-[#006045] tracking-tight">À faire : {reply.next_step}</p>
        )}
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden"
          >
            <div className="mt-3 rounded-2xl bg-white ring-1 ring-[#1A1918]/8 p-4 space-y-3">
              <div className="text-[11px] text-[#1A1918]/55 space-y-0.5">
                <p>De : {reply.from_name ? `${reply.from_name} <${reply.from_email}>` : reply.from_email}</p>
                <p>Objet : {reply.subject}</p>
              </div>
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin text-[#006045]" />
              ) : (
                <p className="text-[13px] leading-relaxed text-[#161615] whitespace-pre-line">
                  {detail?.text || "Message vide."}
                </p>
              )}
              <a
                href={replyMailto(reply)}
                className="inline-flex items-center gap-1.5 rounded-full bg-[#006045] px-3 py-1.5 text-[11px] text-white hover:bg-[#004d37]"
              >
                <ReplyIcon className="h-3 w-3" /> Répondre
              </a>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.li>
  );
}

function AddressCard({ inbox }: { inbox: Inbox }) {
  const [copied, setCopied] = useState(false);
  if (!inbox.configured || !inbox.address) {
    return (
      <p className="text-xs text-[#1A1918]/55 tracking-tight">
        La réception automatique des réponses n&apos;est pas encore active : les recruteurs te
        répondent directement. Note leurs réponses depuis Candidatures.
      </p>
    );
  }
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(inbox.address!);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* presse-papiers refusé */
    }
  };
  return (
    <div className="rounded-2xl bg-[#006045]/[0.05] px-4 py-3 space-y-1">
      <div className="flex items-center gap-2">
        <span className="text-[13px] text-[#161615] tracking-tight truncate">{inbox.address}</span>
        <button
          type="button"
          onClick={copy}
          className="ml-auto inline-flex items-center gap-1 text-[11px] text-[#006045] hover:underline cursor-pointer shrink-0"
        >
          {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
          {copied ? "Copiée" : "Copier"}
        </button>
      </div>
      <p className="text-[11.5px] text-[#1A1918]/60 tracking-tight">
        Ton adresse de candidature. Je la donne aux recruteurs : leurs réponses m&apos;arrivent,
        je mets ton suivi à jour et je te les transfère. Tu réponds de ta messagerie habituelle.
      </p>
    </div>
  );
}

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
  const [inbox, setInbox] = useState<Inbox | null>(null);
  const [emails, setEmails] = useState<NotificationRecord[]>([]);

  useEffect(() => {
    if (!candidateId) return;
    Promise.all([
      fetchJournal(candidateId, 100),
      fetchNotificationHistory(candidateId),
      fetchInbox(candidateId),
    ]).then(([journal, history, box]) => {
      // Celles notées à la main ; les e-mails reçus ont leur propre liste.
      setReplies(journal.filter((e) => e.kind === "reply" && !e.payload?.inbound_id));
      setEmails(history ?? []);
      setInbox(box ?? { address: null, configured: false, unread: 0, replies: [] });
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
            <InboxIcon className="w-3 h-3 stroke-[1.6] text-[#006045]" />
            <p className="text-xs text-[#1A1918]/55 uppercase tracking-wider font-medium">Réponses des recruteurs</p>
            {inbox && inbox.unread > 0 && (
              <span className="rounded-full bg-[#006045] px-1.5 py-px text-[10px] tabular-nums text-white">{inbox.unread}</span>
            )}
          </div>
          {inbox === null ? (
            <div className="h-10 rounded-xl bg-[#1A1918]/5 animate-pulse" />
          ) : (
            <>
              <AddressCard inbox={inbox} />
              {inbox.replies.length > 0 ? (
                <ul className="border-t border-[#1A1918]/10 divide-y divide-[#1A1918]/8">
                  {inbox.replies.map((r, i) => (
                    <ReplyRow
                      key={r.id} reply={r} candidateId={candidateId!} index={i}
                      onRead={() => setInbox((b) => (b ? { ...b, unread: Math.max(0, b.unread - 1) } : b))}
                    />
                  ))}
                </ul>
              ) : inbox.configured ? (
                <p className="text-sm font-light text-[#1A1918]/55 tracking-tight py-1">
                  Pas encore de réponse. Je te préviens dès qu&apos;un recruteur écrit.
                </p>
              ) : null}
            </>
          )}
        </section>

        {replies && (replies.length > 0 || !inbox?.configured) && (
        <section className="space-y-3">
          <div className="flex items-center gap-1.5">
            <MessageCircleReply className="w-3 h-3 stroke-[1.6] text-[#006045]" />
            <p className="text-xs text-[#1A1918]/55 uppercase tracking-wider font-medium">Notées par toi</p>
          </div>
          {replies.length === 0 ? (
            <div className="space-y-1.5 py-1">
              <p className="text-xs font-normal text-[#1A1918]/55 tracking-tight">
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
                  <span className="text-[11px] font-normal text-[#1A1918]/50 shrink-0">{date(e.created_at)}</span>
                </motion.li>
              ))}
            </ul>
          )}
        </section>
        )}

        <section className="space-y-3">
          <div className="flex items-center gap-1.5">
            <Mail className="w-3 h-3 stroke-[1.6] text-[#006045]" />
            <p className="text-xs text-[#1A1918]/55 uppercase tracking-wider font-medium">
              Ce que je t&apos;ai écrit
            </p>
          </div>
          {emails.length === 0 ? (
            <p className="text-sm font-light text-[#1A1918]/60 tracking-tight py-1">
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
                        "text-[11px] font-normal tracking-tight",
                        n.status === "sent" ? "text-[#006045]" : n.status === "failed" ? "text-red-600" : "text-[#1A1918]/55",
                      )}
                    >
                      {STATUS_LABEL[n.status]}
                    </p>
                  </div>
                  <span className="text-[11px] font-normal text-[#1A1918]/50 shrink-0">{date(n.created_at)}</span>
                </motion.li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </motion.div>
  );
}
