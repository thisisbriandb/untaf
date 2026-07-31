"use client";

import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ArrowRight, ArrowUp, ArrowUpRight, Mic, PanelRight, Plus, Radar } from "lucide-react";
import { AlicePresence } from "../../onboarding/components/AlicePresence";
import type {
  UiBlock, JobCardData, CvAuditData, ApplicationData, MissionReportData,
} from "@/lib/alice-client";
import { JobCardList } from "./JobCard";
import { Markdown } from "./Markdown";
import { ActiveMissionCard } from "./ActiveMissionCard";
import { MissionLauncher } from "./MissionLauncher";
import { fetchCurrentRun, type MissionRun } from "@/lib/mission-run-client";
import { canvasLabel, useAlice, type CanvasPayload, type ChatMessage } from "../alice-context";

// ── Constants ──────────────────────────────────────────────────────────────

/**
 * Formulées comme des ordres, pas comme des rubriques.
 *
 * « Nouvelles offres » est un sujet de consultation ; « Trouve-moi des offres »
 * est une mission confiée. La nuance porte tout le positionnement du produit.
 */
const METRICS = [
  { label: "Trouve-moi des offres", query: "Montre-moi les nouvelles offres" },
  { label: "Occupe-toi de mon CV", query: "Audite mon CV et dis-moi ce que tu corriges" },
  { label: "Écris ma lettre", query: "Rédige-moi une lettre de motivation" },
  { label: "Fais le point", query: "Où en est ma recherche ? Fais-moi le bilan." },
];

// ── Inline UI Blocks ───────────────────────────────────────────────────────

function AuditBlock({ data }: { data: CvAuditData }) {
  return (
    <div className="w-full p-4 rounded-xl border border-[#1A1918]/8 bg-white space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-normal text-[#1A1918] tracking-tight">
          Audit ATS
        </span>
        <span className="text-sm font-medium text-[#006045] tabular-nums">
          {data.ats_score}/100
        </span>
      </div>
      {data.strengths.length > 0 && (
        <div className="space-y-1">
          {data.strengths.map((s, i) => (
            <p key={i} className="text-xs font-light text-[#006045]/80 tracking-tight">
              ✓ {s}
            </p>
          ))}
        </div>
      )}
      {data.improvements.length > 0 && (
        <div className="space-y-1">
          {data.improvements.map((s, i) => (
            <p key={i} className="text-xs font-light text-[#1A1918]/55 tracking-tight">
              → {s}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}

function ApplicationsBlock({ data }: { data: { applications: ApplicationData[]; counts: Record<string, number> } }) {
  const STATUS_LABELS: Record<string, string> = {
    matched: "Matchée",
    pending: "En attente",
    applied: "Postulée",
    interview: "Entretien",
    offer: "Offre",
    rejected: "Refusée",
    closed: "Fermée",
  };

  return (
    <div className="w-full space-y-2 py-1">
      {data.applications.map((app) => (
        <div
          key={app.id}
          className="p-3 rounded-xl border border-[#1A1918]/8 bg-white flex items-center justify-between"
        >
          <div className="space-y-0.5 min-w-0">
            <p className="text-sm font-normal text-[#1A1918] tracking-tight truncate">
              {app.job_title}
            </p>
            <p className="text-xs font-light text-[#1A1918]/55 tracking-tight">
              {app.company_name}
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <span className="text-[11px] font-light text-[#1A1918]/50 tracking-tight">
              {STATUS_LABELS[app.status] || app.status}
            </span>
            <span className="text-xs font-medium text-[#006045] tabular-nums">
              {app.match_score}%
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}

/** Bilan de mission — les chiffres, et surtout ce qui a été écarté et pourquoi. */
function MissionBlock({ data }: { data: MissionReportData }) {
  const scan = data.derniere_veille ?? {};
  const reasons = Object.entries(scan.top_reasons ?? {})
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3);

  return (
    <div className="w-full p-4 rounded-xl border border-[#1A1918]/8 bg-white space-y-3">
      <div className="flex items-center justify-between gap-3">
        <span className="text-sm font-normal text-[#1A1918] tracking-tight">
          {data.mission.titre}
        </span>
        <span className="text-[11px] font-light text-[#1A1918]/45 tracking-tight">
          {data.mission.statut === "paused" ? "en pause" : data.mission.autonomie}
        </span>
      </div>

      <div className="grid grid-cols-4 gap-2">
        {[
          [scan.scanned ?? 0, "vues"],
          [data.compteurs.retenues, "retenues"],
          [data.compteurs.envoyees, "envoyées"],
          [data.compteurs.entretiens, "entretiens"],
        ].map(([value, label]) => (
          <div key={label as string}>
            <p className="text-lg font-light text-[#1A1918] tabular-nums leading-none">
              {value}
            </p>
            <p className="text-[10px] font-light text-[#1A1918]/45 tracking-tight pt-0.5">
              {label}
            </p>
          </div>
        ))}
      </div>

      {reasons.length > 0 && (
        <div className="space-y-1 pt-1 border-t border-[#1A1918]/6">
          {reasons.map(([motif, n]) => (
            <p key={motif} className="text-xs font-light text-[#1A1918]/55 tracking-tight">
              <span className="tabular-nums text-[#1A1918]/70">{n}</span> écartées — {motif}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}

function UiBlockRenderer({ block }: { block: UiBlock }) {
  switch (block.type) {
    case "jobs":
      return <JobCardList jobs={block.data as JobCardData[]} />;
    case "cv_audit":
      return <AuditBlock data={block.data as CvAuditData} />;
    case "mission":
      return <MissionBlock data={block.data as MissionReportData} />;
    case "applications":
      return <ApplicationsBlock data={block.data as { applications: ApplicationData[]; counts: Record<string, number> }} />;
    default:
      return null;
  }
}

/** Persistent handle on a Canvas artifact, left inline in the thread. */
function CanvasRefChip({ canvasRef }: { canvasRef: CanvasPayload }) {
  const { openCanvas, canvas } = useAlice();
  const isActive = canvas?.mode === canvasRef.mode;

  return (
    <button
      type="button"
      onClick={() => openCanvas(canvasRef)}
      className="group flex items-center gap-2.5 w-full max-w-xs px-3.5 py-2.5 rounded-xl border border-[#1A1918]/10 bg-white hover:border-[#006045]/45 transition-colors cursor-pointer text-left"
    >
      <PanelRight className="w-3.5 h-3.5 stroke-[1.5] text-[#006045] shrink-0" />
      <span className="flex-1 min-w-0 text-xs font-normal text-[#1A1918] tracking-tight truncate">
        {canvasLabel(canvasRef)}
      </span>
      <span className="text-[10px] font-light text-[#1A1918]/40 group-hover:text-[#006045] tracking-tight shrink-0">
        {isActive ? "ouvert" : "rouvrir"}
      </span>
    </button>
  );
}

// ── Chat Bubble ────────────────────────────────────────────────────────────

function ChatBubble({ msg }: { msg: ChatMessage }) {
  if (msg.sender === "alice") {
    return (
      <div className="space-y-2 text-left w-full opacity-80">
        {msg.timestamp && (
          <span className="font-mono text-[11px] text-[#006045]/75 font-medium tracking-tight">
            {msg.timestamp}
          </span>
        )}
        <Markdown
          source={msg.text}
          className="text-sm md:text-base text-[#1A1918]/60"
        />
        {msg.uiBlocks?.map((block, idx) => (
          <UiBlockRenderer key={idx} block={block} />
        ))}
        {msg.canvasRef && <CanvasRefChip canvasRef={msg.canvasRef} />}
      </div>
    );
  }
  return (
    <div className="max-w-[85%] px-4 py-2.5 rounded-2xl bg-[#1A1918]/75 text-white/90 text-sm font-light leading-relaxed rounded-br-none tracking-tight">
      {msg.text}
    </div>
  );
}

// ── Main Component ─────────────────────────────────────────────────────────

/**
 * Ce qu'Alice affiche pendant qu'elle travaille.
 *
 * « Alice réfléchit… » décrit une machine qui calcule. On annonce plutôt une
 * action en cours, choisie d'après la demande — l'attente devient une mission
 * en train de s'exécuter.
 */
function workingLabelFor(query: string): string {
  const q = query.toLowerCase();
  if (/offre|poste|opportunit|cherch|trouve/.test(q)) return "Je passe les offres en revue…";
  if (/lettre|motivation/.test(q)) return "Je rédige ta lettre…";
  if (/cv|audit|ats/.test(q)) return "Je reprends ton CV…";
  if (/candidatur|postul/.test(q)) return "Je fais le tour de tes candidatures…";
  if (/bilan|point|où en/.test(q)) return "Je rassemble mon compte rendu…";
  return "Je m'en occupe…";
}

export function AliceView({ userName }: { userName: string }) {
  const firstName = userName.split(" ")[0] || "Briand";
  const [prompt, setPrompt] = useState("");
  const [workingLabel, setWorkingLabel] = useState("Je m'en occupe…");
  const { messages, isThinking, emotion, hasConversation, submitQuery, candidateId } =
    useAlice();

  // Mission bornée en cours, s'il y en a une.
  const [run, setRun] = useState<MissionRun | null>(null);
  const [showLauncher, setShowLauncher] = useState(false);

  useEffect(() => {
    if (!candidateId) return;
    fetchCurrentRun(candidateId).then(setRun);
  }, [candidateId]);

  const scrollContainerRef = useRef<HTMLDivElement | null>(null);
  const didMountRef = useRef(false);

  // The thread grows downward and is anchored to the composer, so the newest
  // message always sits just above the input — jump on mount, glide after.
  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) return;
    container.scrollTo({
      top: container.scrollHeight,
      behavior: didMountRef.current ? "smooth" : "auto",
    });
    didMountRef.current = true;
  }, [messages, isThinking]);

  const send = (text: string) => {
    setPrompt("");
    setWorkingLabel(workingLabelFor(text));
    void submitQuery(text);
  };

  // La largeur de lecture est portée par la colonne (page.tsx) : ici on la remplit.
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -6 }}
      transition={{ duration: 0.35 }}
      className="w-full h-full flex flex-col select-none font-light tracking-tight overflow-hidden"
    >
      {/* ═══ Zone scrollable : contenu ancré en bas, comme une messagerie ═══ */}
      <div
        ref={scrollContainerRef}
        className="scroll-discreet w-full flex-1 min-h-0 overflow-y-auto pr-1"
        role="log"
        aria-live="polite"
        aria-label="Historique des échanges avec Alice"
      >
        <div
          className={`min-h-full flex flex-col gap-7 py-6 ${
            hasConversation ? "justify-end" : "justify-center"
          }`}
        >
          {/* Hero — remonte et sort du champ au fil de la conversation */}
          <div className="flex flex-col items-center text-center gap-3 shrink-0">
            <AlicePresence emotion={emotion} size="lg" />
            <h1 className="text-2xl md:text-3xl font-light text-[#1A1918]/90 tracking-tight pt-1">
              Bonjour {firstName}.
            </h1>
          </div>

          {/* Action principale : confier une mission. Le produit tient sur ce
              geste — il ne peut pas être caché derrière une icône. */}
          {!run || run.status === "completed" || run.status === "interrupted" ? (
            <div className="w-full flex justify-center shrink-0">
              <button
                type="button"
                onClick={() => setShowLauncher(true)}
                className="group inline-flex items-center gap-2.5 px-6 py-3 rounded-full border border-[#006045]/30 bg-[#006045]/5 text-[#006045] text-sm tracking-tight hover:bg-[#006045]/10 hover:border-[#006045]/50 transition-all cursor-pointer"
              >
                <Radar className="w-4 h-4 stroke-[1.6]" />
                <span>Confier une mission à Alice</span>
                <ArrowRight className="w-3.5 h-3.5 stroke-[1.8] transition-transform group-hover:translate-x-0.5" />
              </button>
            </div>
          ) : null}

          <div className="w-full flex flex-wrap items-center justify-center gap-x-5 gap-y-2 shrink-0">
            {METRICS.map((m) => (
              <button
                key={m.label}
                type="button"
                onClick={() => send(m.query)}
                disabled={isThinking}
                className="flex items-center gap-1.5 text-xs md:text-sm font-light text-[#1A1918]/70 hover:text-[#006045] transition-colors cursor-pointer group py-1 tracking-tight disabled:opacity-40"
              >
                <ArrowUpRight className="w-3.5 h-3.5 text-[#006045] stroke-[2] shrink-0 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform" />
                <span className="font-light">{m.label}</span>
              </button>
            ))}
          </div>

          {/* Mission en cours — visible en permanence pendant qu'elle tourne */}
          {run && (run.status === "running" || run.status === "preparing" || !hasConversation) && candidateId && (
            <div className="w-full shrink-0">
              <ActiveMissionCard candidateId={candidateId} run={run} onChange={setRun} />
            </div>
          )}

          <div className="w-full space-y-3.5 border-t border-[#1A1918]/8 pt-6 shrink-0">
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
            {isThinking && (
              <div className="flex items-center gap-1 text-[#1A1918]/40 text-sm font-light py-2">
                <span className="animate-pulse">{workingLabel}</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ═══ Bloc fixe en bas : input ═══ */}
      <div className="w-full shrink-0 pt-3 pb-2 bg-[#FAFAF8]/90 backdrop-blur-sm">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            send(prompt);
          }}
          className="relative flex items-center bg-white border border-[#EDECEA] hover:border-[#1A1918]/25 focus-within:border-[#006045] rounded-full px-4.5 py-3 shadow-sm transition-all"
        >
          <button
            type="button"
            onClick={() => setShowLauncher(true)}
            aria-label="Confier une mission à Alice"
            title="Confier une mission"
            className="text-[#1A1918]/35 hover:text-[#006045] p-1 rounded-full transition-colors cursor-pointer shrink-0 mr-2"
          >
            <Plus className="w-4 h-4 stroke-[1.4]" />
          </button>

          <input
            type="text"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="Confie une mission à Alice..."
            maxLength={500}
            aria-label="Confier une mission à Alice"
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

      {/* Confier une mission — Alice pose ses questions une par une */}
      <AnimatePresence>
        {showLauncher && candidateId && (
          <MissionLauncher
            candidateId={candidateId}
            onClose={() => setShowLauncher(false)}
            onLaunched={(r) => {
              setRun(r);
              setShowLauncher(false);
            }}
          />
        )}
      </AnimatePresence>
    </motion.div>
  );
}
