"use client";

import { useEffect, useState } from "react";
import {
  Check, Download, ExternalLink, FileText, FolderDown, Loader2, PenLine, Send, Sparkles,
} from "lucide-react";
import { API_BASE_URL } from "@/lib/config";
import type { JobCardData } from "@/lib/alice-client";
import { Markdown } from "./Markdown";
import { ApplyPanel } from "./ApplyPanel";
import { FinishOnSite } from "./FinishOnSite";
import { useNarration } from "@/lib/use-narration";
import {
  packUrl, tailorDocuments, tailoredCvUrl, type TailoredDocuments,
} from "@/lib/tailor-client";
import { useAlice } from "../alice-context";
import { apiFetch } from "@/lib/api";
import { DownloadLink } from "./ProtectedFile";
import { openFile } from "@/lib/api";
import { cvTemplates } from "@/app/onboarding/types";
import { invalidateApplication, isSent, useApplicationState } from "@/lib/application-state";
import { chez, companyOf } from "@/lib/company";

function templateLabel(id: string): string {
  return cvTemplates.find((t) => t.id === id)?.name ?? id;
}

interface JobDetail {
  description_raw?: string | null;
  description_parsed?: Record<string, unknown> | null;
  salary_range?: string | null;
  experience_range?: string | null;
  department?: string | null;
  tech_stack?: string[] | null;
  apply_url?: string | null;
}

const CONTRACT_LABELS: Record<string, string> = {
  cdi: "CDI",
  cdd: "CDD",
  freelance: "Freelance",
  stage: "Stage",
  alternance: "Alternance",
};

const REMOTE_LABELS: Record<string, string> = {
  remote: "Remote",
  hybrid: "Hybride",
  onsite: "Présentiel",
};

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div className="space-y-0.5 min-w-0">
      <p className="text-[11px] font-mono uppercase tracking-wider text-[#1A1918]/50">
        {label}
      </p>
      <p className="text-xs font-normal text-[#1A1918]/75 tracking-tight truncate">
        {value}
      </p>
    </div>
  );
}

export function JobDetailCanvas({ job, autoApply = false }: { job: JobCardData; autoApply?: boolean }) {
  const { submitQuery, isThinking, candidateId, openCanvas, sayAsAlice, goToConversation } = useAlice();
  const [adapting, setAdapting] = useState(false);
  const [tailored, setTailored] = useState<TailoredDocuments | null>(null);
  const adaptingLabel = useNarration(adapting, [
    "Je relis l'offre…",
    "Je repère ce qu'elle attend dans ton parcours…",
    "Je réécris ton accroche et tes réalisations…",
    "Je rédige ta lettre…",
    "Je mets ton CV en page…",
  ]);
  // L'état du dossier vient du serveur, partagé avec toute l'interface : une
  // candidature déjà préparée (par une mission, depuis la liste…) ne se
  // « prépare » plus ici.
  const { state: appState } = useApplicationState(candidateId, job.id);

  /**
   * Adapte le CV et la lettre à CETTE offre. Les deux sont rangés sur la
   * candidature, pas sur le profil : les autres offres gardent le CV général,
   * et ce sont ces documents-là qui partiront à l'envoi.
   */
  const adaptDocuments = async () => {
    if (!candidateId) return;
    setAdapting(true);
    const docs = await tailorDocuments(candidateId, job.id);
    setAdapting(false);
    if (!docs) {
      sayAsAlice("Je n'ai pas réussi à adapter tes documents. Réessaie dans un instant.");
      return;
    }
    setTailored(docs);
    invalidateApplication(job.id);
    const letterRef = {
      mode: "cover_letter" as const,
      companyName: job.company_name,
      jobTitle: job.title,
      letter: docs.letter,
    };
    // Ce qu'adapter veut dire, dit sans détour : accroche et présentation
    // réécrites pour l'offre, compétences demandées mises en avant, tout le
    // parcours conservé. Et si le PDF d'origine ne pouvait pas être réécrit,
    // on le dit et on propose de choisir le modèle.
    const r = docs.report;
    const parts = [
      `J'ai adapté ton CV et ta lettre pour « ${job.title} »${chez(job.company_name)} : ` +
        `nouvelle accroche (« ${docs.cv.headline} »), présentation réécrite pour l'offre, ` +
        "compétences demandées mises en avant. Tout ton parcours est conservé.",
    ];
    if (r?.was_original_pdf) {
      parts.push(
        "Ton CV d'origine est un PDF que je ne peux pas réécrire : je l'ai donc mis en page " +
          `avec le modèle ${templateLabel(r.template_id)}. Choisis-en un autre si tu préfères.`,
      );
    } else if (r?.template_is_default) {
      parts.push(`Mise en page : modèle ${templateLabel(r.template_id)}, modifiable.`);
    }
    if (r?.missing_labels.length) {
      parts.push(
        `Il manque encore à ton CV : ${r.missing_labels.join(", ")}. Complète-les et ` +
          "je referai l'adaptation.",
      );
    }
    parts.push("Ton CV général n'a pas bougé.");
    sayAsAlice(
      parts.join(" "),
      r?.template_is_default || r?.was_original_pdf ? { mode: "cv_editor", pane: "design" } : letterRef,
    );
  };
  const [detail, setDetail] = useState<JobDetail | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  // La candidature remplace l'annonce dans le Canvas au lieu de s'y ajouter.
  const [applying, setApplying] = useState(false);

  useEffect(() => {
    let alive = true;
    setStatus("loading");
    setDetail(null);
    // « Postule » demandé à Alice : on ouvre directement la candidature.
    setApplying(autoApply);
    setTailored(null);

    apiFetch(`${API_BASE_URL}/api/jobs/${job.id}`)
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error(String(res.status)))))
      .then((data: JobDetail) => {
        if (!alive) return;
        setDetail(data);
        setStatus("ready");
      })
      .catch(() => {
        if (alive) setStatus("error");
      });

    return () => {
      alive = false;
    };
  }, [job.id, autoApply]);

  const prompts = [
    `Rédige-moi une lettre de motivation pour « ${job.title} »${chez(job.company_name)}`,
    `Pourquoi cette offre me correspond-elle à ${job.match_score}% ?`,
    `Qu'est-ce qui manque à mon CV pour ce poste ?`,
  ];

  const applyUrl = detail?.apply_url || job.source_url;
  const packReady = !!tailored || !!appState?.pack_ready;
  const letter = tailored?.letter ?? appState?.letter ?? null;
  const mode = appState?.apply_mode ?? job.apply_mode ?? "manual";
  const sent = isSent(appState);
  const awaiting = appState?.stage === "awaiting";
  const day = (iso: string | null | undefined) =>
    iso ? new Date(iso).toLocaleDateString("fr-FR", { day: "numeric", month: "long" }) : "";
  const primaryLabel = sent
    ? `Candidature envoyée${appState?.applied_at ? ` le ${day(appState.applied_at)}` : ""}`
    : awaiting
      ? "Valider l'envoi"
      : packReady
        ? mode === "manual" ? "Finir ma candidature sur le site" : "Envoyer ma candidature"
        : mode === "manual" ? "Préparer ma candidature" : "Préparer et envoyer ma candidature";
  const tags = [
    CONTRACT_LABELS[job.contract_type],
    REMOTE_LABELS[job.remote_policy],
  ].filter(Boolean);

  if (applying && candidateId) {
    return (
      <ApplyPanel
        candidateId={candidateId}
        jobId={job.id}
        companyName={job.company_name}
        jobTitle={job.title}
        onBack={() => setApplying(false)}
      />
    );
  }

  return (
    <div className="h-full flex flex-col min-h-0">
      {/* En-tête de l'offre */}
      <div className="shrink-0 px-5 pt-4 pb-4 border-b border-[#1A1918]/8 space-y-3">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 space-y-1">
            <h2 className="text-base font-normal text-[#1A1918] tracking-tight">
              {job.title}
            </h2>
            <p className="text-xs font-normal text-[#1A1918]/55 tracking-tight">
              {[companyOf(job.company_name) ?? "Employeur non communiqué", job.location].filter(Boolean).join(" · ")}
            </p>
          </div>
          <div className="shrink-0 text-right">
            <p className="text-lg font-light text-[#006045] tabular-nums leading-none">
              {job.match_score}%
            </p>
            <p className="text-[11px] font-mono uppercase tracking-wider text-[#1A1918]/50 pt-1">
              match
            </p>
          </div>
        </div>

        {tags.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {tags.map((t) => (
              <span
                key={t}
                className="px-2.5 py-1 rounded-full border border-[#1A1918]/10 text-[11px] font-normal text-[#1A1918]/60 tracking-tight"
              >
                {t}
              </span>
            ))}
          </div>
        )}

        {detail && (detail.salary_range || detail.experience_range || detail.department) && (
          <div className="grid grid-cols-3 gap-3 pt-1">
            {detail.salary_range && <Meta label="Salaire" value={detail.salary_range} />}
            {detail.experience_range && (
              <Meta label="Expérience" value={detail.experience_range} />
            )}
            {detail.department && <Meta label="Équipe" value={detail.department} />}
          </div>
        )}
      </div>

      {/* Description — rendue en Markdown */}
      <div className="scroll-discreet flex-1 min-h-0 overflow-y-auto px-5 py-5">
        {status === "loading" && (
          <div className="h-full flex flex-col items-center justify-center gap-2.5">
            <Loader2 className="w-5 h-5 animate-spin text-[#006045]" />
            <p className="text-xs font-normal text-[#1A1918]/50 tracking-tight">
              Je récupère l&apos;annonce…
            </p>
          </div>
        )}

        {status === "error" && (
          <p className="text-sm font-light text-[#1A1918]/50 tracking-tight">
            Je n&apos;ai pas pu charger le détail de cette offre. L&apos;annonce
            d&apos;origine reste accessible ci-dessous.
          </p>
        )}

        {status === "ready" && (
          <>
            {detail?.tech_stack && detail.tech_stack.length > 0 && (
              <div className="flex flex-wrap gap-1.5 pb-4 mb-4 border-b border-[#1A1918]/8">
                {detail.tech_stack.map((t) => (
                  <span
                    key={t}
                    className="px-2 py-1 rounded-md bg-[#006045]/8 text-[11px] font-normal text-[#006045] tracking-tight"
                  >
                    {t}
                  </span>
                ))}
              </div>
            )}
            <Markdown source={detail?.description_raw} />
          </>
        )}
      </div>

      {/* Relais vers la conversation + candidature */}
      <div className="shrink-0 border-t border-[#1A1918]/8 bg-[#FAFAF8]">
        <div className="px-5 py-3 space-y-2">
          <div className="flex items-center gap-1.5">
            <Sparkles className="w-3 h-3 stroke-[1.6] text-[#006045] shrink-0" />
            <span className="text-[11px] font-mono uppercase tracking-wider text-[#1A1918]/55">
              Demander à Alice
            </span>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {prompts.map((q) => (
              <button
                key={q}
                type="button"
                onClick={() => {
                  // La question part dans la conversation de cette offre.
                  void submitQuery(q, { job });
                  goToConversation();
                }}
                disabled={isThinking}
                className="px-2.5 py-1.5 rounded-full border border-[#1A1918]/10 bg-white text-[11px] font-normal text-[#1A1918]/65 tracking-tight hover:border-[#006045]/40 hover:text-[#006045] transition-colors cursor-pointer disabled:opacity-40 text-left"
              >
                {q}
              </button>
            ))}
          </div>
        </div>

        <div className="px-5 py-3 border-t border-[#1A1918]/6 space-y-2">
          {packReady && mode === "manual" && !sent && candidateId && !applyUrl.startsWith("import://") ? (
            <FinishOnSite
              candidateId={candidateId}
              jobId={job.id}
              companyName={job.company_name}
              url={applyUrl}
              variant="block"
            />
          ) : (
          <button
            type="button"
            onClick={() => {
              if (awaiting) {
                window.dispatchEvent(new CustomEvent("untaf:select-tab", { detail: "candidatures" }));
                return;
              }
              setApplying(true);
            }}
            disabled={!candidateId || sent}
            className="flex items-center justify-center gap-2 w-full px-4 py-2.5 rounded-full bg-[#006045] text-white text-xs font-normal tracking-tight hover:bg-[#004d37] transition-colors cursor-pointer disabled:opacity-40"
          >
            <Send className="w-3.5 h-3.5 stroke-[1.6]" />
            {sent ? <Check className="w-3.5 h-3.5 stroke-[2]" /> : null}
            {primaryLabel}
          </button>
          )}
          {!sent && (packReady || mode === "manual") && (
            <p className="text-[11px] font-normal text-[#1A1918]/55 text-center tracking-tight">
              {packReady
                ? `Dossier prêt${appState?.pack_ready_at ? ` depuis le ${day(appState.pack_ready_at)}` : ""} : CV adapté et lettre. `
                : ""}
              {mode === "manual"
                ? packReady
                  ? "Cette offre se postule sur le site de l'employeur : tout est rédigé, tu envoies."
                  : "Cette offre se postule sur le site de l'employeur : je prépare tout, tu envoies."
                : ""}
            </p>
          )}

          {/* Actions séparées : tout ne passe pas par la candidature complète. */}
          {tailored && candidateId && tailored.report && (
            <div className="space-y-1.5 rounded-xl bg-white border border-[#1A1918]/8 px-3 py-2.5">
              <p className="text-[11px] font-normal text-[#1A1918]/65 tracking-tight leading-relaxed">
                Accroche et présentation réécrites pour l&apos;offre, compétences demandées en tête,
                parcours complet conservé · modèle {templateLabel(tailored.report.template_id)}
              </p>
              {tailored.report.missing_labels.length > 0 && (
                <p className="text-[11px] font-normal text-[#006045] tracking-tight">
                  Manque encore : {tailored.report.missing_labels.join(", ")}.{" "}
                  <button
                    type="button"
                    onClick={() => openCanvas({ mode: "cv_editor", pane: "content" })}
                    className="underline cursor-pointer"
                  >
                    Compléter mon CV
                  </button>
                </p>
              )}
              <div className="flex items-center gap-3 pt-0.5">
                <button
                  type="button"
                  onClick={() => void openFile(tailoredCvUrl(candidateId, job.id))}
                  className="text-[11px] font-normal text-[#006045] hover:underline cursor-pointer"
                >
                  Aperçu du CV adapté
                </button>
                <button
                  type="button"
                  onClick={() => openCanvas({ mode: "cv_editor", pane: "design" })}
                  className="text-[11px] font-normal text-[#006045] hover:underline cursor-pointer"
                >
                  Changer de modèle
                </button>
              </div>
            </div>
          )}
          {packReady && candidateId ? (
            <div className="grid grid-cols-2 gap-2">
              <DownloadLink
                url={tailoredCvUrl(candidateId, job.id)}
                filename="CV.pdf"
                className="flex items-center justify-center gap-1.5 px-3 py-2 rounded-full border border-[#006045]/30 text-[11px] font-normal text-[#006045] tracking-tight hover:bg-[#006045]/5 transition-colors"
              >
                <Download className="w-3 h-3 stroke-[1.6]" />
                CV adapté (PDF)
              </DownloadLink>
              <button
                type="button"
                onClick={() => openCanvas({
                  mode: "cover_letter",
                  companyName: job.company_name,
                  jobTitle: job.title,
                  letter: letter ?? undefined,
                })}
                disabled={!letter}
                className="flex items-center justify-center gap-1.5 px-3 py-2 rounded-full border border-[#006045]/30 text-[11px] font-normal text-[#006045] tracking-tight hover:bg-[#006045]/5 transition-colors cursor-pointer"
              >
                <PenLine className="w-3 h-3 stroke-[1.6]" />
                Voir la lettre
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={adaptDocuments}
              disabled={adapting || !candidateId}
              className="flex items-center justify-center gap-1.5 w-full px-3 py-2 rounded-full border border-[#1A1918]/12 text-[11px] font-normal text-[#1A1918]/70 tracking-tight hover:border-[#006045]/40 hover:text-[#006045] transition-colors cursor-pointer disabled:opacity-40"
            >
              {adapting ? (
                <Loader2 className="w-3 h-3 animate-spin" />
              ) : (
                <FileText className="w-3 h-3 stroke-[1.6]" />
              )}
              {adapting ? adaptingLabel : "Adapter mon CV et ma lettre"}
            </button>
          )}
          <div className="flex items-center justify-center gap-4">
            {candidateId && (
              <DownloadLink
                url={packUrl(candidateId, job.id)}
                filename={`Candidature_${job.company_name}.zip`}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-[#1A1918]/12 text-[11px] font-normal text-[#1A1918]/70 hover:border-[#006045]/40 hover:text-[#006045] tracking-tight transition-colors"
              >
                <FolderDown className="w-3 h-3 stroke-[1.5]" />
                {packReady ? "Télécharger le dossier adapté" : "Préparer et télécharger le dossier"}
              </DownloadLink>
            )}
            {packReady && candidateId && (
              <button
                type="button"
                onClick={() => openCanvas({ mode: "review", job })}
                className="flex items-center gap-1.5 text-[11px] text-[#1A1918]/60 hover:text-[#006045] tracking-tight transition-colors cursor-pointer"
              >
                Relire ce qui a changé
              </button>
            )}
            {!applyUrl.startsWith("import://") && (
              <a
                href={applyUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1.5 text-[11px] font-normal text-[#1A1918]/55 hover:text-[#006045] tracking-tight transition-colors"
              >
                Voir l&apos;annonce d&apos;origine
                <ExternalLink className="w-3 h-3 stroke-[1.5]" />
              </a>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
