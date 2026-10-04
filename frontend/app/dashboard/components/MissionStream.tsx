"use client";

/**
 * Une mission, racontée en direct dans la conversation.
 *
 * Pas de carte, pas de compte à rebours : Alice dit ce qu'elle fait au moment
 * où elle le fait — « dossier prêt pour X », « candidature envoyée chez Y ».
 * Chaque ligne est une action réelle tirée du journal. L'utilisateur peut
 * fermer l'onglet : un e-mail lui rend compte à la fin.
 */

import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, Check, Loader2, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { fetchCurrentRun, stopRun, STEP_LABELS, type MissionRun } from "@/lib/mission-run-client";

/** Assez vif pour paraître diffusé en direct. */
const POLL_MS = 2500;

const DOT: Record<string, string> = {
  applied: "bg-[#006045]",
  letter_written: "bg-[#006045]/70",
  awaiting_approval: "bg-amber-500",
  error: "bg-red-500",
};

export function MissionStream({
  candidateId,
  run,
  onChange,
  onOpenCandidatures,
  onDismiss,
}: {
  candidateId: string;
  run: MissionRun;
  onChange: (run: MissionRun | null) => void;
  onOpenCandidatures?: () => void;
  onDismiss?: () => void;
}) {
  const [stopping, setStopping] = useState(false);
  const live = run.status === "running" || run.status === "preparing";

  useEffect(() => {
    if (!live) return;
    const id = setInterval(async () => {
      const fresh = await fetchCurrentRun(candidateId);
      if (fresh) onChange(fresh);
    }, POLL_MS);
    return () => clearInterval(id);
  }, [candidateId, live, onChange]);

  // Le journal arrive du plus récent au plus ancien ; on le raconte dans
  // l'ordre. Le compte rendu final est posté à part, comme un message.
  const lines = useMemo(
    () => [...run.events].reverse().filter((e) => e.kind !== "status_changed" && e.kind !== "mission_created"),
    [run.events],
  );
  const stats = run.stats ?? {};
  const waiting = stats.awaiting_approval ?? 0;

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex flex-col items-start gap-2 w-full"
    >
      <div className="flex items-center gap-2 text-[11px] font-light text-[#1A1918]/45 tracking-tight">
        {live ? (
          <span className="relative flex h-1.5 w-1.5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#006045]/60" />
            <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-[#006045]" />
          </span>
        ) : (
          <Check className="h-3 w-3 text-[#006045]" />
        )}
        <span>
          {run.title}
          {live && " — tu peux fermer l'onglet, je t'écris quand c'est fini."}
        </span>
        {live && (
          <button
            type="button"
            disabled={stopping}
            onClick={async () => {
              setStopping(true);
              const stopped = await stopRun(candidateId, run.id);
              setStopping(false);
              if (stopped) onChange(stopped);
            }}
            className="text-[#1A1918]/35 hover:text-red-600 underline-offset-2 hover:underline cursor-pointer disabled:opacity-40"
          >
            arrêter
          </button>
        )}
      </div>

      <div className="space-y-1.5 w-full">
        <AnimatePresence initial={false}>
          {lines.map((e) => (
            <motion.p
              key={e.id}
              layout
              initial={{ opacity: 0, y: 6, filter: "blur(2px)" }}
              animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
              transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
              className="flex items-start gap-2.5 text-[15px] font-light text-[#1A1918]/80 leading-relaxed tracking-tight"
            >
              <span className={cn("mt-2.5 h-1.5 w-1.5 shrink-0 rounded-full", DOT[e.kind] ?? "bg-[#1A1918]/25")} />
              <span>{e.summary}</span>
            </motion.p>
          ))}
        </AnimatePresence>

        {live && (
          <motion.p
            key={run.current_step ?? "start"}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex items-center gap-2.5 text-[15px] font-light text-[#1A1918]/45 tracking-tight"
          >
            <Loader2 className="h-3.5 w-3.5 animate-spin text-[#006045]" />
            {run.current_step ? `${STEP_LABELS[run.current_step]}…` : "Je m'y mets…"}
          </motion.p>
        )}
      </div>

      {!live && (onOpenCandidatures || onDismiss) && (
        <div className="flex items-center gap-2 pt-1">
          {onOpenCandidatures && (stats.packs || waiting) ? (
            <button
              type="button"
              onClick={onOpenCandidatures}
              className="inline-flex items-center gap-1 rounded-full bg-[#006045] px-3 py-1.5 text-[11px] text-white hover:bg-[#004d38] cursor-pointer"
            >
              {waiting ? `Valider ${waiting} candidature${waiting > 1 ? "s" : ""}` : "Voir les dossiers"}
              <ArrowRight className="h-3 w-3" />
            </button>
          ) : null}
          {onDismiss && (
            <button
              type="button"
              onClick={onDismiss}
              aria-label="Masquer"
              className="p-1.5 rounded-full text-[#1A1918]/30 hover:text-[#1A1918] cursor-pointer"
            >
              <X className="h-3 w-3" />
            </button>
          )}
        </div>
      )}
    </motion.div>
  );
}
