"use client";

/**
 * « Finir sur le site », en un geste.
 *
 * Quand l'envoi ne peut pas être automatique, Alice fait tout ce qui peut
 * l'être : elle ouvre l'offre, copie la lettre (prête à coller), télécharge
 * le dossier (CV adapté + lettre). Il ne reste qu'à coller, joindre, envoyer.
 * Au retour, une seule question : « Tu as postulé ? » — et la candidature
 * entre dans le suivi, relance comprise.
 */

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowUpRight, Check, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { downloadFile } from "@/lib/api";
import { markApplied } from "@/lib/apply-client";
import { fetchApplicationState, invalidateApplication } from "@/lib/application-state";
import { packUrl } from "@/lib/tailor-client";
import { useToast } from "./Toaster";

type Phase = "idle" | "working" | "confirm";

export function FinishOnSite({
  candidateId,
  jobId,
  companyName,
  url,
  variant = "pill",
  onDone,
}: {
  candidateId: string;
  jobId: string;
  companyName: string;
  url: string;
  variant?: "pill" | "block";
  onDone?: () => void;
}) {
  const toast = useToast();
  const [phase, setPhase] = useState<Phase>("idle");
  const [confirming, setConfirming] = useState(false);

  const start = async () => {
    // L'onglet d'abord, dans le geste même : sinon le navigateur le bloque.
    window.open(url, "_blank", "noopener,noreferrer");
    setPhase("working");

    const state = await fetchApplicationState(candidateId, jobId);
    let copied = false;
    if (state?.letter?.body) {
      try {
        await navigator.clipboard.writeText(
          [state.letter.subject, state.letter.body].filter(Boolean).join("\n\n"),
        );
        copied = true;
      } catch {
        /* presse-papiers refusé : le dossier contient la lettre */
      }
    }
    const downloaded = await downloadFile(packUrl(candidateId, jobId), `Candidature_${companyName}.zip`);

    toast(
      [
        "Offre ouverte",
        copied && "lettre copiée",
        downloaded ? "dossier téléchargé" : "dossier indisponible pour l'instant",
      ].filter(Boolean).join(" · ") + (copied ? " — colle la lettre, joins le CV." : "."),
      downloaded ? "success" : "warning",
    );
    setPhase("confirm");
  };

  const confirm = async () => {
    setConfirming(true);
    const ok = await markApplied(candidateId, jobId);
    setConfirming(false);
    if (!ok) return toast("Je n'ai pas pu l'enregistrer. Réessaie.", "warning");
    toast(`Noté : candidature envoyée chez ${companyName}. Je te rappelle de relancer.`);
    invalidateApplication(jobId);
    setPhase("idle");
    onDone?.();
  };

  return (
    <AnimatePresence mode="wait" initial={false}>
      {phase === "confirm" ? (
        <motion.div
          key="confirm"
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0 }}
          className={cn(
            "flex items-center gap-2 flex-wrap",
            variant === "block" && "w-full justify-center rounded-2xl bg-[#161615]/[0.04] px-3 py-2.5",
          )}
        >
          <span className="text-[12px] text-[#161615]">Tu as postulé chez {companyName} ?</span>
          <button
            type="button"
            onClick={confirm}
            disabled={confirming}
            className="inline-flex items-center gap-1.5 rounded-full bg-[#006045] px-3 py-1.5 text-[11px] text-white hover:bg-[#004d37] cursor-pointer disabled:opacity-50"
          >
            {confirming ? <Loader2 className="h-3 w-3 animate-spin" /> : <Check className="h-3 w-3" />}
            Oui, c&apos;est envoyé
          </button>
          <button
            type="button"
            onClick={() => setPhase("idle")}
            className="rounded-full px-2.5 py-1.5 text-[11px] text-[#1A1918]/60 hover:text-[#161615] cursor-pointer"
          >
            Pas encore
          </button>
        </motion.div>
      ) : (
        <motion.button
          key="go"
          type="button"
          whileTap={{ scale: 0.97 }}
          onClick={start}
          disabled={phase === "working"}
          className={cn(
            "inline-flex items-center justify-center gap-1.5 bg-[#006045] text-white hover:bg-[#004d37] transition-colors cursor-pointer disabled:opacity-60",
            variant === "pill" ? "rounded-full px-3 py-1.5 text-[11px]" : "w-full rounded-full px-4 py-2.5 text-xs",
          )}
        >
          {phase === "working" ? (
            <Loader2 className="h-3 w-3 animate-spin" />
          ) : (
            <ArrowUpRight className="h-3.5 w-3.5" />
          )}
          Finir sur le site
        </motion.button>
      )}
    </AnimatePresence>
  );
}
