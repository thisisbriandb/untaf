"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ArrowRight, Loader2, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { AlicePresence } from "@/app/onboarding/components/AlicePresence";
import {
  DURATIONS,
  OBJECTIVES,
  startRun,
  type MissionRun,
  type RunObjective,
} from "@/lib/mission-run-client";

/**
 * Confier une mission.
 *
 * Alice pose ses questions une par une plutôt que d'afficher un formulaire :
 * la délégation doit se vivre comme une conversation, pas comme un paramétrage.
 */
export function MissionLauncher({
  candidateId,
  onLaunched,
  onClose,
}: {
  candidateId: string;
  onLaunched: (run: MissionRun) => void;
  onClose: () => void;
}) {
  const [step, setStep] = useState(0);
  const [objective, setObjective] = useState<RunObjective>("search");
  const [duration, setDuration] = useState(30);
  const [allowSend, setAllowSend] = useState(false);
  const [isLaunching, setIsLaunching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const objectiveLabel = OBJECTIVES.find((o) => o.id === objective)!;
  const durationLabel = DURATIONS.find((d) => d.minutes === duration)?.label ?? `${duration} min`;

  // La question de l'envoi n'a de sens que si la mission va jusque-là.
  const steps = objective === "apply" ? 4 : 3;

  const launch = async () => {
    setIsLaunching(true);
    setError(null);
    const run = await startRun(candidateId, {
      title: objectiveLabel.label,
      objective,
      duration_minutes: duration,
      allowed_actions: { send: allowSend },
    });
    setIsLaunching(false);

    if (!run) {
      setError("Je n'ai pas pu démarrer. Une mission est peut-être déjà en cours.");
      return;
    }
    onLaunched(run);
  };

  const questions = [
    {
      prompt: "Quelle mission tu me confies ?",
      content: (
        <div className="space-y-0 border-t border-b border-[#1A1918]/10 divide-y divide-[#1A1918]/8">
          {OBJECTIVES.map((o) => (
            <button
              key={o.id}
              type="button"
              onClick={() => {
                setObjective(o.id);
                setStep(1);
              }}
              className="w-full py-3.5 flex items-start gap-3 text-left cursor-pointer group"
            >
              <span
                className={cn(
                  "mt-0.5 w-3.5 shrink-0 text-center text-sm",
                  objective === o.id ? "text-[#006045]" : "text-[#1A1918]/20",
                )}
              >
                {objective === o.id ? "✓" : "—"}
              </span>
              <span className="min-w-0">
                <span className="block text-sm text-[#1A1918] group-hover:text-[#006045] transition-colors">
                  {o.label}
                </span>
                <span className="block text-xs font-light text-[#1A1918]/40 mt-0.5">
                  {o.detail}
                </span>
              </span>
            </button>
          ))}
        </div>
      ),
    },
    {
      prompt: "Pendant combien de temps ?",
      content: (
        <div className="flex flex-wrap gap-2">
          {DURATIONS.map((d) => (
            <button
              key={d.minutes}
              type="button"
              onClick={() => {
                setDuration(d.minutes);
                setStep(2);
              }}
              className={cn(
                "px-4 py-2 rounded-full border text-sm transition-colors cursor-pointer",
                duration === d.minutes
                  ? "border-[#006045] bg-[#006045]/8 text-[#006045]"
                  : "border-[#1A1918]/12 text-[#1A1918]/60 hover:border-[#1A1918]/30 hover:text-[#1A1918]",
              )}
            >
              {d.label}
            </button>
          ))}
        </div>
      ),
    },
    ...(objective === "apply"
      ? [{
          prompt: "Je peux envoyer moi-même, ou te les présenter d'abord ?",
          content: (
            <div className="space-y-0 border-t border-b border-[#1A1918]/10 divide-y divide-[#1A1918]/8">
              {[
                { send: false, label: "Présente-les-moi d'abord", detail: "Je prépare tout, tu valides chaque envoi." },
                { send: true, label: "Envoie toi-même", detail: "Dans les limites de ton mandat et de ton quota." },
              ].map((opt) => (
                <button
                  key={String(opt.send)}
                  type="button"
                  onClick={() => {
                    setAllowSend(opt.send);
                    setStep(3);
                  }}
                  className="w-full py-3.5 flex items-start gap-3 text-left cursor-pointer group"
                >
                  <span
                    className={cn(
                      "mt-0.5 w-3.5 shrink-0 text-center text-sm",
                      allowSend === opt.send ? "text-[#006045]" : "text-[#1A1918]/20",
                    )}
                  >
                    {allowSend === opt.send ? "✓" : "—"}
                  </span>
                  <span className="min-w-0">
                    <span className="block text-sm text-[#1A1918] group-hover:text-[#006045] transition-colors">
                      {opt.label}
                    </span>
                    <span className="block text-xs font-light text-[#1A1918]/40 mt-0.5">
                      {opt.detail}
                    </span>
                  </span>
                </button>
              ))}
            </div>
          ),
        }]
      : []),
    {
      prompt: "C'est noté. Je récapitule :",
      content: (
        <div className="space-y-4">
          <div className="border-t border-b border-[#1A1918]/10 divide-y divide-[#1A1918]/8 text-sm">
            {[
              ["Mission", objectiveLabel.label],
              ["Durée", durationLabel],
              ...(objective === "apply"
                ? [["Envoi", allowSend ? "J'envoie moi-même" : "Tu valides chaque envoi"]]
                : []),
            ].map(([label, value]) => (
              <div key={label} className="py-3 flex justify-between gap-4">
                <span className="text-xs text-[#1A1918]/40 uppercase tracking-wider font-medium">
                  {label}
                </span>
                <span className="text-[#1A1918] text-right">{value}</span>
              </div>
            ))}
          </div>

          {/* Le contrat de délégation, dit en clair avant de partir */}
          <p className="text-xs font-light text-[#1A1918]/50 text-center leading-relaxed tracking-tight">
            Tu peux fermer l&apos;application : je continue sans toi.
            {objective === "search"
              ? " Je te présente les offres retenues à la fin."
              : " Chaque offre retenue reçoit un CV adapté et sa lettre."}
            {objective === "apply" && !allowSend && " Rien ne part sans ton feu vert."}
            {" "}Je t&apos;écris quand c&apos;est fini.
          </p>

          {error && <p className="text-xs text-red-600/80 text-center">{error}</p>}

          <div className="flex justify-center">
            <button
              type="button"
              onClick={launch}
              disabled={isLaunching}
              className="group inline-flex items-center gap-2.5 py-3.5 px-7 text-[#006045] hover:text-[#004d37] font-medium text-base transition-all cursor-pointer disabled:opacity-40"
            >
              <span>Vas-y, je te laisse faire</span>
              {isLaunching ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
              )}
            </button>
          </div>
        </div>
      ),
    },
  ];

  const current = questions[Math.min(step, questions.length - 1)];

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-[60] flex items-center justify-center bg-[#FAFAF8]/92 backdrop-blur-sm px-6"
    >
      <button
        type="button"
        onClick={onClose}
        aria-label="Fermer"
        className="absolute top-5 right-6 p-2 rounded-full text-[#1A1918]/40 hover:text-[#1A1918] hover:bg-[#1A1918]/5 transition-colors cursor-pointer"
      >
        <X className="w-4 h-4 stroke-[1.4]" />
      </button>

      <motion.div
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
        className="w-full max-w-[440px] flex flex-col items-center gap-6"
      >
        <AlicePresence emotion={isLaunching ? "working" : "listening"} />

        <AnimatePresence mode="wait">
          <motion.p
            key={current.prompt}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.3 }}
            className="text-center text-lg md:text-xl font-normal text-[#1A1918]/85 tracking-tight"
          >
            {current.prompt}
          </motion.p>
        </AnimatePresence>

        <AnimatePresence mode="wait">
          <motion.div
            key={step}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.3 }}
            className="w-full"
          >
            {current.content}
          </motion.div>
        </AnimatePresence>

        {step > 0 && step < steps && (
          <button
            type="button"
            onClick={() => setStep((s) => Math.max(0, s - 1))}
            className="text-xs font-light text-[#1A1918]/35 hover:text-[#1A1918] transition-colors cursor-pointer"
          >
            revenir en arrière
          </button>
        )}
      </motion.div>
    </motion.div>
  );
}
