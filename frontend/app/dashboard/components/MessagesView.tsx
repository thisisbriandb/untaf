"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { API_BASE_URL } from "@/lib/config";

interface RecruiterMessage {
  id: string;
  sender_name: string | null;
  company_name: string | null;
  subject: string | null;
  body: string;
  is_read: boolean;
  received_at: string;
}

interface MessagesViewProps {
  candidateId: string | null;
}

export function MessagesView({ candidateId }: MessagesViewProps) {
  const [messages, setMessages] = useState<RecruiterMessage[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!candidateId) {
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);

    fetch(`${API_BASE_URL}/api/candidates/${candidateId}/messages`)
      .then((res) => (res.ok ? res.json() : []))
      .then((data: RecruiterMessage[]) => {
        if (!cancelled) setMessages(data);
      })
      .catch(() => {
        if (!cancelled) setMessages([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [candidateId]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.35 }}
      className="w-full max-w-2xl text-left space-y-6 py-4"
    >
      <div>
        <h2 className="text-xl font-normal text-[#1A1918]">Messages &amp; Réponses</h2>
        <p className="text-xs text-[#1A1918]/50 mt-0.5">
          Les recruteurs qui ont répondu à Alice pour tes candidatures.
        </p>
      </div>

      {loading ? (
        <p className="text-xs text-[#1A1918]/40">Chargement…</p>
      ) : messages.length === 0 ? (
        <div className="text-left py-10 space-y-2">
          <p className="text-sm text-[#1A1918]/60">Aucun message pour le moment.</p>
          <p className="text-xs text-[#1A1918]/40">
            Les réponses des recruteurs à tes candidatures apparaîtront ici.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className="p-5 rounded-2xl bg-white border border-[#EDECEA] space-y-2 text-left shadow-sm"
            >
              <div className="flex justify-between items-center">
                <span className="text-xs font-semibold text-[#006045]">
                  {msg.company_name || msg.sender_name || "Recruteur"}
                  {msg.company_name && msg.sender_name ? ` • ${msg.sender_name}` : ""}
                </span>
                <span className="text-[11px] text-[#1A1918]/40">
                  {new Date(msg.received_at).toLocaleString("fr-FR", {
                    day: "2-digit",
                    month: "2-digit",
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </span>
              </div>
              {msg.subject && (
                <p className="text-xs font-medium text-[#1A1918]/70">{msg.subject}</p>
              )}
              <p className="text-xs md:text-sm font-medium text-[#1A1918] leading-relaxed">
                {msg.body}
              </p>
            </div>
          ))}
        </div>
      )}
    </motion.div>
  );
}
