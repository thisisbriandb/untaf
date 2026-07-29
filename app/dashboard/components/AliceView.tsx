"use client";

import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ArrowUp, ArrowUpRight, Plus, Mic } from "lucide-react";
import { AlicePresence, AliceEmotion } from "../../onboarding/components/AlicePresence";

interface AliceViewProps {
  userName: string;
}

interface ChatMessage {
  id: string;
  sender: "alice" | "user";
  text: string;
  timestamp?: string;
}

const METRICS = [
  { label: "49 nouvelles offres", query: "Montre-moi les 49 nouvelles offres" },
  { label: "8 candidatures", query: "Où en sont mes 8 candidatures ?" },
  { label: "2 CV consultés", query: "Quelles entreprises ont consulté mon CV ?" },
  { label: "1 entretien", query: "Dis-moi en plus sur mon entretien" },
];

const INITIAL_MESSAGES: ChatMessage[] = [
  {
    id: "seed-1",
    sender: "alice",
    timestamp: "09:41",
    text: "Doctolib a consulté ton CV et a demandé un premier échange.",
  },
  {
    id: "seed-2",
    sender: "alice",
    timestamp: "09:27",
    text: "Capgemini demande 5 ans d'expérience. Je n'ai pas postulé.",
  },
  {
    id: "seed-3",
    sender: "alice",
    timestamp: "09:19",
    text: "J'ai adapté ton CV pour 8 nouvelles opportunités.",
  },
];

/**
 * Placeholder reply generator. Swap this for a real API call
 * (e.g. `await fetchAliceReply(userText)`) once the backend is wired up —
 * the call site in submitQuery won't need to change shape.
 */
function getMockReply(userText: string): string {
  const lower = userText.toLowerCase();
  if (lower.includes("offre")) {
    return "J'ai sélectionné 49 offres compatibles avec ton profil sur Rennes et Paris (dont Doctolib, Miro et Qonto).";
  }
  if (lower.includes("candidature")) {
    return "Tes 8 candidatures sont envoyées. 2 entreprises ont déjà ouvert ton profil.";
  }
  if (lower.includes("cv") || lower.includes("consulté")) {
    return "Doctolib et Lucca ont consulté ton CV ce matin entre 09:15 et 09:41.";
  }
  if (lower.includes("entretien")) {
    return "Doctolib souhaite programmer un premier entretien vidéo pour le poste de Développeur.";
  }
  return "Je m'en occupe. J'ai mis à jour tes préférences d'analyse.";
}

function formatTime(date: Date): string {
  return `${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
}

function ChatBubble({ msg }: { msg: ChatMessage }) {
  if (msg.sender === "alice") {
    return (
      <div className="space-y-1 text-left w-full opacity-80">
        {msg.timestamp && (
          <span className="font-mono text-[11px] text-[#006045]/75 font-medium tracking-tight">
            {msg.timestamp}
          </span>
        )}
        <p className="text-sm md:text-base font-light text-[#1A1918]/60 leading-relaxed tracking-tight">
          {msg.text}
        </p>
      </div>
    );
  }
  return (
    <div className="max-w-[85%] px-4 py-2.5 rounded-2xl bg-[#1A1918]/75 text-white/90 text-sm font-light leading-relaxed rounded-br-none tracking-tight">
      {msg.text}
    </div>
  );
}

export function AliceView({ userName }: AliceViewProps) {
  const firstName = userName.split(" ")[0] || "Briand";
  const [prompt, setPrompt] = useState("");
  const [emotion, setEmotion] = useState<AliceEmotion>("idle");
  const [isThinking, setIsThinking] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>(INITIAL_MESSAGES);

  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Prevent state updates firing after unmount (e.g. route change mid-"thinking")
  useEffect(() => {
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, []);

  const submitQuery = (userText: string) => {
    const trimmed = userText.trim();
    if (!trimmed || isThinking) return;

    setEmotion("thinking");
    setIsThinking(true);
    setPrompt("");

    setMessages((prev) => [
      { id: crypto.randomUUID(), sender: "user", text: trimmed },
      ...prev,
    ]);

    timeoutRef.current = setTimeout(() => {
      const reply = getMockReply(trimmed);
      setMessages((prev) => [
        {
          id: crypto.randomUUID(),
          sender: "alice",
          timestamp: formatTime(new Date()),
          text: reply,
        },
        ...prev,
      ]);
      setEmotion("idle");
      setIsThinking(false);
    }, 1000);
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -6 }}
      transition={{ duration: 0.35 }}
      className="w-full max-w-xl mx-auto py-8 flex flex-col items-center select-none space-y-7 font-light tracking-tight"
    >
      {/* ═══ 1. Alice Eyes (○  ○) & Greeting ═══ */}
      <div className="flex flex-col items-center text-center gap-3">
        <AlicePresence emotion={emotion} size="lg" />
        <h1 className="text-2xl md:text-3xl font-light text-[#1A1918]/90 tracking-tight pt-1">
          Bonjour {firstName}. On commence ?
        </h1>
      </div>

      {/* ═══ 2. Input Capsule ═══ */}
      <div className="w-full pt-1">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            submitQuery(prompt);
          }}
          className="relative flex items-center bg-white border border-[#EDECEA] hover:border-[#1A1918]/25 focus-within:border-[#006045] rounded-full px-4.5 py-3 shadow-sm transition-all"
        >
          <button
            type="button"
            aria-label="Ajouter une pièce jointe"
            className="text-[#1A1918]/35 hover:text-[#1A1918] p-1 rounded-full transition-colors cursor-pointer shrink-0 mr-2"
          >
            <Plus className="w-4 h-4 stroke-[1.4]" />
          </button>

          <input
            type="text"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="Demande quelque chose à Alice..."
            maxLength={500}
            aria-label="Message à Alice"
            className="flex-1 bg-transparent text-sm font-light placeholder:text-[#1A1918]/35 text-[#1A1918] focus:outline-none tracking-tight"
          />

          <div className="flex items-center gap-2 shrink-0 ml-2">
            <button
              type="button"
              aria-label="Message vocal"
              className="text-[#1A1918]/35 hover:text-[#1A1918] p-1 rounded-full transition-colors cursor-pointer hidden sm:block"
            >
              <Mic className="w-4 h-4 stroke-[1.4]" />
            </button>
            <button
              type="submit"
              disabled={!prompt.trim() || isThinking}
              aria-label="Envoyer"
              className="p-2 rounded-full bg-[#006045] text-white hover:bg-[#004d37] disabled:opacity-30 transition-all cursor-pointer"
            >
              <ArrowUp className="w-3.5 h-3.5 stroke-[2.2]" />
            </button>
          </div>
        </form>
      </div>

      {/* ═══ 3. Quick metrics ═══ */}
      <div className="w-full flex flex-wrap items-center justify-center gap-x-5 gap-y-2 pt-1">
        {METRICS.map((m) => (
          <button
            key={m.label}
            type="button"
            onClick={() => submitQuery(m.query)}
            disabled={isThinking}
            className="flex items-center gap-1.5 text-xs md:text-sm font-light text-[#1A1918]/70 hover:text-[#006045] transition-colors cursor-pointer group py-1 tracking-tight disabled:opacity-40"
          >
            <ArrowUpRight className="w-3.5 h-3.5 text-[#006045] stroke-[2] shrink-0 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform" />
            <span className="font-light">{m.label}</span>
          </button>
        ))}
      </div>

      {/* ═══ 4. Message stream ═══ */}
      <div
        className="w-full pt-6 space-y-3.5 border-t border-[#1A1918]/8"
        role="log"
        aria-live="polite"
        aria-label="Historique des échanges avec Alice"
      >
        {isThinking && (
          <div className="flex items-center gap-1 text-[#1A1918]/40 text-sm font-light">
            <span className="animate-pulse">Alice réfléchit…</span>
          </div>
        )}
        <AnimatePresence initial={false}>
          {messages.map((msg) => (
            <motion.div
              key={msg.id}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.25 }}
              className={`flex flex-col ${msg.sender === "user" ? "items-end" : "items-start"}`}
            >
              <ChatBubble msg={msg} />
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}