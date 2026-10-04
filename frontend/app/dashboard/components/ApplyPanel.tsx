"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ArrowLeft, Check, Download, ExternalLink, FileText, FolderDown, Loader2, Mail, Send, X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { AlicePresence } from "@/app/onboarding/components/AlicePresence";
import {
  COMPLEXITY_LABEL,
  dispatchLetterUrl,
  dispatchResumeUrl,
  fetchApplyOutcome,
  fetchApplyPlan,
  markApplied,
  rememberSkipConfirm,
  shouldConfirmApply,
  streamApply,
  type ApplyEvent,
  type ApplyOutcome,
  type ApplyPlan,
  type Requirement,
} from "@/lib/apply-client";
import { useAlice } from "../alice-context";
import { DownloadLink } from "./ProtectedFile";
import { useToast } from "./Toaster";
import { packUrl, tailoredCvUrl } from "@/lib/tailor-client";
import { invalidateApplication } from "@/lib/application-state";

type Phase = "confirm" | "running" | "settled";

interface StepLine {
  key: string;
  label: string;
  status: "running" | "done";
  detail?: string;
}

const MARK: Record<Requirement["status"], { mark: string; className: string }> = {
  satisfied: { mark: "✓", className: "text-[#006045]" },
  generate: { mark: "→", className: "text-[#006045]/70" },
  missing: { mark: "!", className: "text-amber-600" },
};

/**
 * La candidature prend tout le Canvas.
 *
 * Elle remplace l'annonce plutôt que de s'entasser sous elle : postuler est
 * une action, pas une note de bas de page. On revient à l'offre quand c'est
 * fini.
 */
export function ApplyPanel({
  candidateId,
  jobId,
  companyName,
  jobTitle,
  onBack,
}: {
  candidateId: string;
  jobId: string;
  companyName: string;
  jobTitle: string;
  onBack: () => void;
}) {
  const { sayAsAlice, openCanvas } = useAlice();

  const [plan, setPlan] = useState<ApplyPlan | null>(null);
  const [phase, setPhase] = useState<Phase>("confirm");
  const [steps, setSteps] = useState<StepLine[]>([]);
  const [outcome, setOutcome] = useState<ApplyEvent | null>(null);
  const [result, setResult] = useState<ApplyOutcome | null>(null);
  const [dontAskAgain, setDontAskAgain] = useState(false);
  const [markedApplied, setMarkedApplied] = useState(false);
  const toast = useToast();

  useEffect(() => {
    fetchApplyPlan(candidateId, jobId).then((p) => {
      setPlan(p);
      // Sans confirmation à demander, on enchaîne directement.
      if (p && !shouldConfirmApply()) void launch();
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [candidateId, jobId]);

  const launch = async () => {
    if (dontAskAgain) rememberSkipConfirm();
    setPhase("running");
    setSteps([]);
    setOutcome(null);
    setResult(null);

    await streamApply(candidateId, jobId, (event) => {
      if (event.type === "step") {
        setSteps((prev) => [
          ...prev.filter((s) => s.key !== event.key),
          { key: event.key, label: event.label, status: event.status, detail: event.detail },
        ]);
        return;
      }
      setOutcome(event);
      setPhase("settled");
      // Dossier rédigé, envoi fait ou en attente : toute l'interface le sait.
      invalidateApplication(jobId);
      if (event.type === "done") sayAsAlice(event.message);

      // Dès qu'un envoi existe en base, on récupère ce qu'il en reste :
      // les pièces assemblées et les gestes qui restent. C'est vrai aussi
      // quand ça a échoué — surtout quand ça a échoué.
      const id =
        "dispatch_id" in event && event.dispatch_id ? event.dispatch_id : null;
      if (id) void fetchApplyOutcome(candidateId, id).then(setResult);
    });
  };

  const requirements =
    outcome && outcome.type === "unsupported" && "requirements" in outcome
      ? ((outcome as unknown as { requirements: Requirement[] }).requirements ?? [])
      : (plan?.requirements ?? []);

  const succeeded = outcome?.type === "done" && outcome.real;
  const resumeInPack =
    outcome && (outcome.type === "unsupported" || outcome.type === "blocked")
      ? outcome.has_resume !== false
      : true;

  return (
    <div className="h-full flex flex-col min-h-0">
      {/* En-tête du panneau */}
      <div className="shrink-0 flex items-center gap-3 px-5 py-3.5 border-b border-[#1A1918]/8">
        <button
          type="button"
          onClick={onBack}
          aria-label="Revenir à l'offre"
          className="p-1.5 rounded-full text-[#1A1918]/45 hover:text-[#1A1918] hover:bg-[#1A1918]/5 transition-colors cursor-pointer shrink-0"
        >
          <ArrowLeft className="w-4 h-4 stroke-[1.5]" />
        </button>
        <div className="min-w-0">
          <p className="text-sm font-normal text-[#1A1918] tracking-tight truncate">
            Candidature — {companyName}
          </p>
          <p className="text-xs font-light text-[#1A1918]/50 tracking-tight truncate">
            {jobTitle}
          </p>
        </div>
      </div>

      <div className="scroll-discreet flex-1 min-h-0 overflow-y-auto px-6 py-6">
        {!plan ? (
          <div className="h-full flex flex-col items-center justify-center gap-2.5">
            <Loader2 className="w-5 h-5 animate-spin text-[#006045]" />
            <p className="text-xs font-light text-[#1A1918]/50 tracking-tight">
              J&apos;examine l&apos;offre…
            </p>
          </div>
        ) : (
          <div className="max-w-md mx-auto space-y-6">
            {/* Alice, présente pendant toute l'opération */}
            <div className="flex flex-col items-center gap-3 text-center">
              <AlicePresence
                emotion={phase === "running" ? "working" : succeeded ? "happy" : "listening"}
                size="md"
              />
              <p className="text-base font-light text-[#1A1918]/85 tracking-tight leading-snug">
                {phase === "running"
                  ? "Je m'en occupe…"
                  : outcome && "message" in outcome
                    ? outcome.message
                    : plan.summary}
              </p>
            </div>

            {/* Ce que l'offre demande */}
            {requirements.length > 0 && (
              <div className="space-y-1.5 p-4 rounded-xl bg-[#FAFAF8] border border-[#1A1918]/6">
                <p className="text-[10px] font-mono uppercase tracking-wider text-[#1A1918]/40 pb-0.5">
                  Ce que l&apos;offre demande
                </p>
                {requirements.map((r) => (
                  <p
                    key={r.key}
                    className="text-xs font-light tracking-tight text-[#1A1918]/65"
                  >
                    <span className={cn("mr-1.5", MARK[r.status].className)}>
                      {MARK[r.status].mark}
                    </span>
                    {r.label}
                    {r.detail && <span className="text-[#1A1918]/35"> — {r.detail}</span>}
                  </p>
                ))}
              </div>
            )}

            {/* Étapes réelles — n'apparaissent que s'il y a du travail */}
            {steps.length > 0 && (
              <div className="space-y-2">
                <AnimatePresence initial={false}>
                  {steps.map((s) => (
                    <motion.p
                      key={s.key}
                      initial={{ opacity: 0, x: -6 }}
                      animate={{ opacity: 1, x: 0 }}
                      className="flex items-start gap-2.5 text-xs font-light tracking-tight text-[#1A1918]/70"
                    >
                      {s.status === "running" ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin text-[#006045] shrink-0 mt-0.5" />
                      ) : (
                        <Check className="w-3.5 h-3.5 text-[#006045] shrink-0 mt-0.5 stroke-[2.5]" />
                      )}
                      <span>
                        {s.label}
                        {s.detail && <span className="text-[#1A1918]/35"> — {s.detail}</span>}
                      </span>
                    </motion.p>
                  ))}
                </AnimatePresence>
              </div>
            )}

            {/* Pourquoi l'envoi automatique ne passe pas — dit en une ligne */}
            {outcome?.type === "unsupported" && (
              <div className="space-y-2">
                <span className="inline-block px-2 py-0.5 rounded-full text-[10px] tracking-tight bg-[#1A1918]/6 text-[#1A1918]/55">
                  {COMPLEXITY_LABEL[outcome.complexity]}
                </span>
                {outcome.reason && (
                  <p className="text-xs font-light text-[#1A1918]/60 tracking-tight leading-relaxed">
                    {outcome.reason}
                  </p>
                )}
              </div>
            )}

            {/* Le dossier — la promesse minimale de « Postuler », toujours tenue */}
            {phase === "settled" && !succeeded && outcome?.type !== "error" && (
              <motion.div
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                className="space-y-3 p-4 rounded-2xl border border-[#006045]/20 bg-[#006045]/[0.03]"
              >
                <div className="flex items-center gap-2">
                  <FolderDown className="w-4 h-4 text-[#006045] stroke-[1.6]" />
                  <p className="text-sm font-normal text-[#1A1918] tracking-tight">Ton dossier est prêt</p>
                </div>
                <p className="text-xs font-light text-[#1A1918]/55 tracking-tight leading-relaxed">
                  {resumeInPack
                    ? "CV adapté à l'offre, lettre de motivation et annonce, dans un seul fichier."
                    : "Lettre de motivation et annonce prêtes. Ton CV n'a pas pu être produit : complète-le ou dépose-le dans l'éditeur, puis télécharge à nouveau."}
                </p>
                <DownloadLink
                  url={packUrl(candidateId, jobId)}
                  filename={`Candidature_${companyName}.zip`}
                  className="flex items-center justify-center gap-2 w-full px-4 py-2.5 rounded-full bg-[#006045] text-white text-xs font-light tracking-tight hover:bg-[#004d37] transition-colors"
                >
                  <Download className="w-3.5 h-3.5 stroke-[1.6]" />
                  Télécharger le dossier
                </DownloadLink>
                <div className="grid grid-cols-2 gap-2">
                  {resumeInPack ? (
                  <DownloadLink
                    url={tailoredCvUrl(candidateId, jobId)}
                    filename="CV.pdf"
                    className="flex items-center justify-center gap-1.5 px-3 py-2 rounded-full border border-[#1A1918]/12 text-[11px] font-light text-[#1A1918]/70 tracking-tight hover:border-[#006045]/40 hover:text-[#006045] transition-colors"
                  >
                    <FileText className="w-3 h-3 stroke-[1.6]" />
                    CV seul (PDF)
                  </DownloadLink>
                  ) : (
                    <button
                      type="button"
                      onClick={() => openCanvas({ mode: "cv_editor", pane: "content" })}
                      className="flex items-center justify-center gap-1.5 px-3 py-2 rounded-full border border-amber-500/30 text-[11px] font-light text-amber-700 tracking-tight hover:bg-amber-50 transition-colors cursor-pointer"
                    >
                      <FileText className="w-3 h-3 stroke-[1.6]" />
                      Compléter mon CV
                    </button>
                  )}
                  {outcome?.type === "unsupported" && outcome.fallback_url ? (
                    <a
                      href={outcome.fallback_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center justify-center gap-1.5 px-3 py-2 rounded-full border border-[#1A1918]/12 text-[11px] font-light text-[#1A1918]/70 tracking-tight hover:border-[#006045]/40 hover:text-[#006045] transition-colors"
                    >
                      Ouvrir l&apos;offre
                      <ExternalLink className="w-3 h-3 stroke-[1.5]" />
                    </a>
                  ) : (
                    <span />
                  )}
                </div>
                {!markedApplied ? (
                  <button
                    type="button"
                    onClick={async () => {
                      if (await markApplied(candidateId, jobId)) {
                        setMarkedApplied(true);
                        invalidateApplication(jobId);
                        toast(`Candidature chez ${companyName} ajoutée à ton suivi.`);
                        sayAsAlice(
                          `C'est noté : tu as postulé chez ${companyName}. Je suis la réponse, ` +
                            "et je te proposerai une relance si rien ne bouge.",
                        );
                      } else {
                        toast("Je n'ai pas pu l'enregistrer. Réessaie.", "warning");
                      }
                    }}
                    className="flex items-center justify-center gap-1.5 w-full text-[11px] font-light text-[#006045] hover:underline tracking-tight cursor-pointer"
                  >
                    <Check className="w-3 h-3" />
                    J&apos;ai postulé avec ce dossier
                  </button>
                ) : (
                  <p className="flex items-center justify-center gap-1.5 text-[11px] font-light text-[#006045]">
                    <Check className="w-3 h-3" /> Ajoutée à ton suivi
                  </p>
                )}
              </motion.div>
            )}

            {outcome?.type === "blocked" && (
              <div className="space-y-1.5 p-3.5 rounded-xl bg-amber-500/8">
                {outcome.missing.map((m) => (
                  <p key={m.label} className="text-xs font-light text-amber-800 tracking-tight">
                    {m.label} — {m.detail}
                  </p>
                ))}
              </div>
            )}

            {outcome?.type === "awaiting" && (
              <p className="text-xs font-light text-amber-800 tracking-tight p-3.5 rounded-xl bg-amber-500/8">
                {outcome.message}
              </p>
            )}

            {/* Ce qu'il reste : les pièces, l'annonce, et la suite */}
            {result && (
              <div className="space-y-5 pt-1">
                {result.steps.length > 0 && (
                  <div className="space-y-2.5">
                    <p className="text-[10px] font-mono uppercase tracking-wider text-[#1A1918]/40">
                      Ce qu&apos;il reste à faire
                    </p>
                    <ol className="space-y-2">
                      {result.steps.map((step, i) => (
                        <li
                          key={step}
                          className="flex items-start gap-2.5 text-xs font-light text-[#1A1918]/70 tracking-tight leading-relaxed"
                        >
                          <span className="shrink-0 mt-px w-4 h-4 rounded-full bg-[#1A1918]/6 text-[10px] text-[#1A1918]/55 flex items-center justify-center tabular-nums">
                            {i + 1}
                          </span>
                          {step}
                        </li>
                      ))}
                    </ol>
                  </div>
                )}

                {(result.has_resume || result.has_letter) && (
                  <div className="space-y-2">
                    <p className="text-[10px] font-mono uppercase tracking-wider text-[#1A1918]/40">
                      {result.sent ? "Documents envoyés" : "Documents préparés"}
                    </p>
                    <div className="grid grid-cols-2 gap-2">
                      {result.has_resume && (
                        <DownloadLink
                          url={dispatchResumeUrl(candidateId, result.dispatch_id)}
                          filename="CV.pdf"
                          className="flex items-center justify-center gap-1.5 px-3 py-2 rounded-full border border-[#1A1918]/12 text-[11px] font-light text-[#1A1918]/70 tracking-tight hover:border-[#006045]/40 hover:text-[#006045] transition-colors"
                        >
                          <Download className="w-3 h-3 stroke-[1.6]" />
                          CV
                        </DownloadLink>
                      )}
                      {result.has_letter && (
                        <DownloadLink
                          url={dispatchLetterUrl(candidateId, result.dispatch_id)}
                          filename="Lettre.txt"
                          className="flex items-center justify-center gap-1.5 px-3 py-2 rounded-full border border-[#1A1918]/12 text-[11px] font-light text-[#1A1918]/70 tracking-tight hover:border-[#006045]/40 hover:text-[#006045] transition-colors"
                        >
                          <Download className="w-3 h-3 stroke-[1.6]" />
                          Lettre
                        </DownloadLink>
                      )}
                    </div>
                  </div>
                )}

                <div className="space-y-2">
                  {result.mailto && (
                    <a
                      href={result.mailto}
                      className="flex items-center justify-center gap-2 w-full px-4 py-2.5 rounded-full bg-[#006045] text-white text-xs font-light tracking-tight hover:bg-[#004d37] transition-colors"
                    >
                      <Mail className="w-3.5 h-3.5 stroke-[1.6]" />
                      Ouvrir l&apos;e-mail pré-rempli
                    </a>
                  )}
                  {result.job_url && (
                    <a
                      href={result.job_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center justify-center gap-1.5 w-full text-[11px] font-light text-[#1A1918]/45 hover:text-[#006045] tracking-tight transition-colors"
                    >
                      Voir l&apos;offre d&apos;origine
                      <ExternalLink className="w-3 h-3 stroke-[1.5]" />
                    </a>
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Pied : uniquement le retour. La confirmation est une modale. */}
      {phase === "settled" && (
        <div className="shrink-0 border-t border-[#1A1918]/8 bg-[#FAFAF8] px-5 py-3.5">
          <button
            type="button"
            onClick={onBack}
            className="w-full px-4 py-2.5 rounded-full border border-[#1A1918]/12 text-xs font-light text-[#1A1918]/65 tracking-tight hover:border-[#1A1918]/30 transition-colors cursor-pointer"
          >
            Revenir à l&apos;offre
          </button>
        </div>
      )}

      {/* Confirmation — pop-up, affichée une seule fois */}
      <AnimatePresence>
        {phase === "confirm" && plan && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onBack}
            className="fixed inset-0 z-[70] flex items-center justify-center bg-[#1A1918]/25 backdrop-blur-sm px-6"
          >
            <motion.div
              initial={{ opacity: 0, y: 12, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 8, scale: 0.98 }}
              transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
              onClick={(e) => e.stopPropagation()}
              className="w-full max-w-[400px] bg-white rounded-2xl border border-[#EDECEA] shadow-xl p-6 space-y-4"
            >
              <div className="flex items-start gap-3">
                <AlicePresence emotion="listening" size="sm" />
                <div className="min-w-0 space-y-1">
                  <p className="text-sm font-normal text-[#1A1918] tracking-tight">
                    Je postule chez {companyName} ?
                  </p>
                  <p className="text-xs font-light text-[#1A1918]/55 tracking-tight leading-relaxed">
                    {plan.complexity === "simple"
                      ? "J'envoie la candidature en ton nom. Tu ne pourras pas la rappeler."
                      : "Cette offre ne se postule pas automatiquement. Je prépare ton dossier complet — CV adapté et lettre — et tu l'envoies en deux clics sur le site de l'employeur."}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={onBack}
                  aria-label="Annuler"
                  className="p-1 rounded-full text-[#1A1918]/35 hover:text-[#1A1918] transition-colors cursor-pointer shrink-0"
                >
                  <X className="w-4 h-4 stroke-[1.4]" />
                </button>
              </div>

              {/* Ce qui part, nommément — pas seulement « CV » */}
              <div className="space-y-1 p-3 rounded-xl bg-[#FAFAF8]">
                {plan.requirements.map((r) => (
                  <p key={r.key} className="text-[11px] font-light text-[#1A1918]/60 tracking-tight">
                    <span className={cn("mr-1.5", MARK[r.status].className)}>
                      {MARK[r.status].mark}
                    </span>
                    {r.label}
                    {r.detail && <span className="text-[#1A1918]/35"> — {r.detail}</span>}
                  </p>
                ))}
              </div>

              <label className="flex items-center gap-2.5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={dontAskAgain}
                  onChange={(e) => setDontAskAgain(e.target.checked)}
                  className="accent-[#006045] h-3.5 w-3.5 cursor-pointer"
                />
                <span className="text-xs font-light text-[#1A1918]/60 tracking-tight">
                  Ne plus afficher ce message
                </span>
              </label>

              <div className="flex items-center justify-end gap-3">
                <button
                  type="button"
                  onClick={onBack}
                  className="text-xs font-light text-[#1A1918]/50 hover:text-[#1A1918] tracking-tight cursor-pointer"
                >
                  Annuler
                </button>
                <button
                  type="button"
                  onClick={launch}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-full bg-[#006045] text-white text-xs font-light tracking-tight hover:bg-[#004d37] transition-colors cursor-pointer"
                >
                  <Send className="w-3.5 h-3.5 stroke-[1.6]" />
                  Vas-y
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

    </div>
  );
}
