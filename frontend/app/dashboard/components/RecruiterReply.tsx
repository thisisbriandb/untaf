"use client";

/**
 * La dernière réponse du recruteur pour cette offre, là où on la cherche :
 * sur la fiche de l'offre. Le détail complet est dans Messages.
 */

import { useEffect, useState } from "react";
import { MessageCircleReply, Reply as ReplyIcon } from "lucide-react";
import { fetchInbox, KIND_LABEL, onInboxChanged, replyMailto, type Reply } from "@/lib/inbox-client";

export function RecruiterReply({ candidateId, jobId }: { candidateId: string; jobId: string }) {
  const [reply, setReply] = useState<Reply | null>(null);

  useEffect(() => {
    let alive = true;
    const load = () => void fetchInbox(candidateId, jobId).then((b) => alive && setReply(b?.replies[0] ?? null));
    load();
    const off = onInboxChanged(load);
    return () => { alive = false; off(); };
  }, [candidateId, jobId]);

  if (!reply) return null;
  const positive = reply.kind === "interview" || reply.kind === "offer";
  return (
    <div className={`px-5 py-3 border-b border-[#1A1918]/6 ${positive ? "bg-[#006045]/[0.06]" : ""}`}>
      <div className="flex items-center gap-1.5">
        <MessageCircleReply className="w-3 h-3 stroke-[1.6] text-[#006045] shrink-0" />
        <span className="text-[11px] uppercase tracking-wider text-[#1A1918]/55">
          Réponse reçue · {KIND_LABEL[reply.kind]}
        </span>
      </div>
      <p className="mt-1 text-[13px] text-[#161615] tracking-tight">{reply.summary}</p>
      {reply.next_step && <p className="text-[12px] text-[#006045] tracking-tight">À faire : {reply.next_step}</p>}
      {reply.kind !== "acknowledgement" && reply.kind !== "rejection" && (
        <a
          href={replyMailto(reply)}
          className="mt-2 inline-flex items-center gap-1.5 rounded-full bg-[#006045] px-3 py-1.5 text-[11px] text-white hover:bg-[#004d37]"
        >
          <ReplyIcon className="h-3 w-3" /> Répondre au recruteur
        </a>
      )}
    </div>
  );
}
