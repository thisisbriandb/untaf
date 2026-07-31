"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown, Square } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  fetchCurrentRun,
  formatRemaining,
  stopRun,
  STEP_LABELS,
  type MissionRun,
} from "@/lib/mission-run-client";

/** Cadence de rafraîchissement : assez vive pour paraître vivante, assez
 *  lente pour ne pas marteler l'API. Le compte à rebours, lui, tourne en local. */
const POLL_MS = 8000;

export function ActiveMissionCard({
  candidateId,
  run,
  onChange,
}: {
  candidateId: string;
  run: MissionRun;
  onChange: (run: MissionRun | null) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [remaining, setRemaining] = useState(run.seconds_remaining);
  const [isStopping, setIsStopping] = useState(false);

  const isLive = run.status === "running" || run.status === "preparing";

  // Le décompte s'écoule en local, sinon il avancerait par à-coups de 8 s.
  useEffect(() => {
    setRemaining(run.seconds_remaining);
    if (!isLive) return;
    const id = setInterval(() => setRemaining((r) => Math.max(0, r - 1)), 1000);
    return () => clearInterval(id);
  }, [run.seconds_remaining, isLive]);

  useEffect(() => {
    if (!isLive) return;
    const id = setInterval(async () => {
      const fresh = await fetchCurrentRun(candidateId);
      if (fresh) onChange(fresh);
    }, POLL_MS);
    return () => clearInterval(id);
  }, [candidateId, isLive, onChange]);

  const handleStop = async () => {
    setIsStopping(true);
    const stopped = await stopRun(candidateId, run.id);
    setIsStopping(false);
    if (stopped) onChange(stopped);
  };

  const stats = run.stats ?? {};
  const elapsed = isLive
    ? Math.max(0, Math.min(1, 1 - remaining / (run.duration_minutes * 60)))
    : 1;

  return (
    <motion.div
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      className="w-full rounded-2xl border border-[#1A1918]/10 bg-white overflow-hidden"
    >
      {/* Barre de progression — le travail rendu visible */}
      <div className="h-0.5 bg-[#1A1918]/6">
        <motion.div
          className="h-full bg-[#006045]"
          animate={{ width: `${elapsed * 100}%` }}
          transition={{ duration: 0.6, ease: "linear" }}
        />
      </div>

      <div className="px-4 py-3 space-y-2.5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex items-center gap-2.5">
            {isLive && (
              <span className="relative flex h-2 w-2 shrink-0">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#006045]/60" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-[#006045]" />
              </span>
            )}
            <div className="min-w-0">
              <p className="text-sm font-normal text-[#1A1918] tracking-tight truncate">
                {run.title}
              </p>
              <p className="text-[11px] font-light text-[#1A1918]/50 tracking-tight truncate">
                {run.status === "running" && run.current_step
                  ? STEP_LABELS[run.current_step]
                  : run.status === "preparing"
                    ? "Je m'organise…"
                    : run.status === "completed"
                      ? "Mission terminée"
                      : "Mission interrompue"}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            {isLive && (
              <span className="text-xs text-[#006045] tabular-nums">
                {formatRemaining(remaining)}
              </span>
            )}
            {isLive && (
              <button
                type="button"
                onClick={handleStop}
                disabled={isStopping}
                aria-label="Arrêter la mission"
                title="Arrêter la mission"
                className="p-1.5 rounded-full text-[#1A1918]/40 hover:text-red-600 hover:bg-red-50 transition-colors cursor-pointer disabled:opacity-40"
              >
                <Square className="w-3 h-3 fill-current" />
              </button>
            )}
            <button
              type="button"
              onClick={() => setExpanded((v) => !v)}
              aria-label={expanded ? "Replier" : "Voir le détail"}
              className="p-1 rounded-full text-[#1A1918]/40 hover:text-[#1A1918] transition-colors cursor-pointer"
            >
              <ChevronDown
                className={cn("w-4 h-4 stroke-[1.5] transition-transform", expanded && "rotate-180")}
              />
            </button>
          </div>
        </div>

        {/* Compteurs — ce qu'elle a réellement fait */}
        <div className="flex items-center gap-4">
          {[
            [stats.scanned ?? 0, "vues"],
            [stats.shortlisted ?? 0, "retenues"],
            [stats.letters ?? 0, "lettres"],
            ...(stats.awaiting_approval ? [[stats.awaiting_approval, "à valider"]] : []),
          ].map(([value, label]) => (
            <div key={label as string} className="flex items-baseline gap-1">
              <span className="text-sm text-[#1A1918] tabular-nums">{value}</span>
              <span className="text-[11px] font-light text-[#1A1918]/45">{label}</span>
            </div>
          ))}
        </div>

        <AnimatePresence>
          {expanded && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.25 }}
              className="overflow-hidden"
            >
              <div className="pt-2 border-t border-[#1A1918]/8 space-y-2">
                {run.report && (
                  <p className="text-xs font-light text-[#1A1918]/70 leading-relaxed tracking-tight">
                    {run.report}
                  </p>
                )}
                {run.events.slice(0, 8).map((e) => (
                  <p
                    key={e.id}
                    className="text-[11px] font-light text-[#1A1918]/50 tracking-tight leading-relaxed"
                  >
                    — {e.summary}
                  </p>
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}
