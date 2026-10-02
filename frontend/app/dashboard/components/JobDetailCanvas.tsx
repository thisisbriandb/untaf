"use client";

import { useEffect, useState } from "react";
import {
  Download, ExternalLink, FileText, FolderDown, Loader2, PenLine, Send, Sparkles,
} from "lucide-react";
import { API_BASE_URL } from "@/lib/config";
import type { JobCardData } from "@/lib/alice-client";
import { Markdown } from "./Markdown";
import { ApplyPanel } from "./ApplyPanel";
import {
  packUrl, tailorDocuments, tailoredCvUrl, type TailoredDocuments,
} from "@/lib/tailor-client";
import { useAlice } from "../alice-context";

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
      <p className="text-[10px] font-mono uppercase tracking-wider text-[#1A1918]/35">
        {label}
      </p>
      <p className="text-xs font-light text-[#1A1918]/75 tracking-tight truncate">
        {value}
      </p>
    </div>
  );
}

export function JobDetailCanvas({ job }: { job: JobCardData }) {
  const { submitQuery, isThinking, candidateId, openCanvas, sayAsAlice } = useAlice();
  const [adapting, setAdapting] = useState(false);
  const [tailored, setTailored] = useState<TailoredDocuments | null>(null);

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
    const letterRef = {
      mode: "cover_letter" as const,
      companyName: job.company_name,
      jobTitle: job.title,
      letter: docs.letter,
    };
    sayAsAlice(
      `J'ai adapté ton CV et ta lettre pour « ${job.title} » chez ${job.company_name}. ` +
      `Nouvelle accroche : « ${docs.cv.headline} ». Ton CV général n'a pas bougé.`,
      letterRef,
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
    setApplying(false);
    setTailored(null);

    fetch(`${API_BASE_URL}/api/jobs/${job.id}`)
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
  }, [job.id]);

  const prompts = [
    `Rédige-moi une lettre de motivation pour « ${job.title} » chez ${job.company_name}`,
    `Pourquoi cette offre me correspond-elle à ${job.match_score}% ?`,
    `Qu'est-ce qui manque à mon CV pour ce poste ?`,
  ];

  const applyUrl = detail?.apply_url || job.source_url;
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
            <p className="text-xs font-light text-[#1A1918]/55 tracking-tight">
              {job.company_name} · {job.location}
            </p>
          </div>
          <div className="shrink-0 text-right">
            <p className="text-lg font-light text-[#006045] tabular-nums leading-none">
              {job.match_score}%
            </p>
            <p className="text-[10px] font-mono uppercase tracking-wider text-[#1A1918]/35 pt-1">
              match
            </p>
          </div>
        </div>

        {tags.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {tags.map((t) => (
              <span
                key={t}
                className="px-2.5 py-1 rounded-full border border-[#1A1918]/10 text-[11px] font-light text-[#1A1918]/60 tracking-tight"
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
            <p className="text-xs font-light text-[#1A1918]/50 tracking-tight">
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
                    className="px-2 py-1 rounded-md bg-[#006045]/8 text-[11px] font-light text-[#006045] tracking-tight"
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
            <span className="text-[10px] font-mono uppercase tracking-wider text-[#1A1918]/40">
              Demander à Alice
            </span>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {prompts.map((q) => (
              <button
                key={q}
                type="button"
                onClick={() => void submitQuery(q)}
                disabled={isThinking}
                className="px-2.5 py-1.5 rounded-full border border-[#1A1918]/10 bg-white text-[11px] font-light text-[#1A1918]/65 tracking-tight hover:border-[#006045]/40 hover:text-[#006045] transition-colors cursor-pointer disabled:opacity-40 text-left"
              >
                {q}
              </button>
            ))}
          </div>
        </div>

        <div className="px-5 py-3 border-t border-[#1A1918]/6 space-y-2">
          <button
            type="button"
            onClick={() => setApplying(true)}
            disabled={!candidateId}
            className="flex items-center justify-center gap-2 w-full px-4 py-2.5 rounded-full bg-[#006045] text-white text-xs font-light tracking-tight hover:bg-[#004d37] transition-colors cursor-pointer disabled:opacity-40"
          >
            <Send className="w-3.5 h-3.5 stroke-[1.6]" />
            Postuler
          </button>

          {/* Actions séparées : tout ne passe pas par la candidature complète. */}
          {tailored && candidateId ? (
            <div className="grid grid-cols-2 gap-2">
              <a
                href={tailoredCvUrl(candidateId, job.id)}
                className="flex items-center justify-center gap-1.5 px-3 py-2 rounded-full border border-[#006045]/30 text-[11px] font-light text-[#006045] tracking-tight hover:bg-[#006045]/5 transition-colors"
              >
                <Download className="w-3 h-3 stroke-[1.6]" />
                CV adapté (PDF)
              </a>
              <button
                type="button"
                onClick={() => openCanvas({
                  mode: "cover_letter",
                  companyName: job.company_name,
                  jobTitle: job.title,
                  letter: tailored.letter,
                })}
                className="flex items-center justify-center gap-1.5 px-3 py-2 rounded-full border border-[#006045]/30 text-[11px] font-light text-[#006045] tracking-tight hover:bg-[#006045]/5 transition-colors cursor-pointer"
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
              className="flex items-center justify-center gap-1.5 w-full px-3 py-2 rounded-full border border-[#1A1918]/12 text-[11px] font-light text-[#1A1918]/70 tracking-tight hover:border-[#006045]/40 hover:text-[#006045] transition-colors cursor-pointer disabled:opacity-40"
            >
              {adapting ? (
                <Loader2 className="w-3 h-3 animate-spin" />
              ) : (
                <FileText className="w-3 h-3 stroke-[1.6]" />
              )}
              {adapting ? "J'adapte ton CV et ta lettre…" : "Adapter mon CV et ma lettre"}
            </button>
          )}
          <div className="flex items-center justify-center gap-4">
            {candidateId && (
              <a
                href={packUrl(candidateId, job.id)}
                className="flex items-center gap-1.5 text-[11px] font-light text-[#1A1918]/40 hover:text-[#006045] tracking-tight transition-colors"
              >
                <FolderDown className="w-3 h-3 stroke-[1.5]" />
                Pack candidature (ZIP)
              </a>
            )}
            {!applyUrl.startsWith("import://") && (
              <a
                href={applyUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1.5 text-[11px] font-light text-[#1A1918]/40 hover:text-[#006045] tracking-tight transition-colors"
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
