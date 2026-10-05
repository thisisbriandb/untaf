"use client";

/**
 * Relire avant d'envoyer.
 *
 * Ce qui part en ton nom doit pouvoir se relire : ce que l'adaptation a
 * changé dans ton CV (accroche, points forts, réalisations reformulées, avant
 * et après), la lettre telle qu'elle partira — modifiable ici — puis le feu
 * vert. C'est ce qui rend le mode « envoie-le » acceptable.
 */

import { useState } from "react";
import { motion } from "framer-motion";
import { Check, Eye, Loader2, Send } from "lucide-react";
import type { JobCardData } from "@/lib/alice-client";
import { openFile } from "@/lib/api";
import { approveDispatch } from "@/lib/pipeline-client";
import { tailoredCvUrl } from "@/lib/tailor-client";
import { invalidateApplication, isSent, saveLetter, useApplicationState } from "@/lib/application-state";
import type { CoverLetter } from "@/lib/letter-client";
import { useAlice } from "../alice-context";
import { useToast } from "./Toaster";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-2">
      <p className="text-[11px] uppercase tracking-[0.12em] text-[#1A1918]/55 font-medium">{title}</p>
      {children}
    </section>
  );
}

function BeforeAfter({ before, after }: { before?: string | null; after?: string | null }) {
  if (!after) return null;
  return (
    <div className="space-y-1">
      {before && before !== after && (
        <p className="text-[12px] text-[#1A1918]/45 line-through decoration-[#1A1918]/25">{before}</p>
      )}
      <p className="text-[13px] text-[#161615] leading-relaxed">{after}</p>
    </div>
  );
}

export function ReviewPanel({ job }: { job: JobCardData }) {
  const { candidateId, openCanvas } = useAlice();
  const toast = useToast();
  const { state } = useApplicationState(candidateId, job.id);
  // Le brouillon n'existe que pendant l'édition ; sinon, la lettre du dossier.
  const [draft, setDraft] = useState<CoverLetter | null>(null);
  const dirty = draft !== null;
  const letter = draft ?? state?.letter ?? null;
  const setLetter = (l: CoverLetter) => setDraft(l);
  const setDirty = (d: boolean) => { if (!d) setDraft(null); };
  const [saving, setSaving] = useState(false);
  const [sending, setSending] = useState(false);

  const c = state?.changes;
  const awaiting = state?.stage === "awaiting" && state.dispatch_id;
  const sent = isSent(state);

  const save = async () => {
    if (!candidateId || !letter) return false;
    setSaving(true);
    const ok = await saveLetter(candidateId, job.id, letter);
    setSaving(false);
    if (!ok) {
      toast("La lettre n'a pas pu être enregistrée.", "warning");
      return false;
    }
    setDirty(false);
    return true;
  };

  const approve = async () => {
    if (!candidateId || !state?.dispatch_id) return;
    setSending(true);
    if (dirty && !(await save())) return setSending(false);
    const d = await approveDispatch(candidateId, state.dispatch_id);
    setSending(false);
    invalidateApplication(job.id);
    if (!d) return toast("L'envoi n'a pas pu partir.", "warning");
    if (d.status === "sent") toast(`Candidature envoyée chez ${job.company_name}.`);
    else if (d.status === "simulated") toast(`Rien n'est parti : ${d.error ?? "envoi non configuré"}.`, "info");
    else toast(d.error ?? "L'envoi n'a pas abouti — ton dossier reste prêt.", "warning");
  };

  if (!state) {
    return (
      <div className="h-full flex items-center justify-center">
        <Loader2 className="h-5 w-5 animate-spin text-[#161615]" />
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col min-h-0">
      <div className="shrink-0 px-5 pt-4 pb-3 border-b border-[#1A1918]/8">
        <p className="text-base text-[#161615] tracking-tight">Relire avant l&apos;envoi</p>
        <p className="text-xs text-[#1A1918]/60">{job.title} · {job.company_name}</p>
      </div>

      <div className="scroll-discreet flex-1 min-h-0 overflow-y-auto px-5 py-5 space-y-6">
        {!c ? (
          <p className="text-sm text-[#1A1918]/60">
            Le dossier n&apos;est pas encore rédigé pour cette offre.
          </p>
        ) : (
          <>
            <Section title="Ton accroche">
              <BeforeAfter before={c.headline_before} after={c.headline_after} />
            </Section>

            {c.strengths.length > 0 && (
              <Section title="Points forts pour ce poste — nouveau">
                <ul className="space-y-1">
                  {c.strengths.map((s) => (
                    <li key={s} className="flex gap-2 text-[13px] text-[#161615]">
                      <span className="mt-2 h-1 w-1 rounded-full bg-[#161615] shrink-0" />
                      {s}
                    </li>
                  ))}
                </ul>
              </Section>
            )}

            {c.summary_after && (
              <Section title="Présentation">
                <BeforeAfter before={c.summary_before} after={c.summary_after} />
              </Section>
            )}

            {c.experiences.length > 0 && (
              <Section title="Réalisations reformulées pour l'offre">
                <div className="space-y-4">
                  {c.experiences.map((e) => (
                    <div key={`${e.company}-${e.title}`} className="space-y-1.5">
                      <p className="text-[12px] text-[#1A1918]/70">
                        {e.title}{e.company && ` · ${e.company}`}
                      </p>
                      {e.before.length > 0 && (
                        <ul className="space-y-0.5">
                          {e.before.map((b) => (
                            <li key={b} className="text-[12px] text-[#1A1918]/45 line-through decoration-[#1A1918]/25">{b}</li>
                          ))}
                        </ul>
                      )}
                      <ul className="space-y-0.5">
                        {e.after.map((a) => (
                          <li key={a} className="flex gap-2 text-[13px] text-[#161615]">
                            <span className="mt-2 h-1 w-1 rounded-full bg-[#161615] shrink-0" />
                            {a}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
                <p className="text-[11px] text-[#1A1918]/55">
                  Reformulées depuis ton parcours : rien n&apos;y a été ajouté.
                </p>
              </Section>
            )}

            {c.skills_first.length > 0 && (
              <Section title="Compétences mises en avant">
                <div className="flex flex-wrap gap-1.5">
                  {c.skills_first.map((s) => (
                    <span key={s} className="rounded-full bg-[#161615]/[0.06] px-2.5 py-1 text-[12px] text-[#161615]">{s}</span>
                  ))}
                </div>
              </Section>
            )}

            {candidateId && (
              <button
                type="button"
                onClick={() => void openFile(tailoredCvUrl(candidateId, job.id))}
                className="inline-flex items-center gap-1.5 text-[12px] text-[#161615] underline-offset-2 hover:underline cursor-pointer"
              >
                <Eye className="h-3.5 w-3.5" /> Voir le CV adapté tel qu&apos;il partira
              </button>
            )}
          </>
        )}

        {letter && (
          <Section title="Ta lettre — modifiable">
            <input
              value={letter.subject}
              onChange={(e) => setLetter({ ...letter, subject: e.target.value })}
              className="w-full rounded-xl border border-[#1A1918]/12 bg-white px-3 py-2 text-[13px] text-[#161615] outline-none focus:border-[#161615]/40"
            />
            <textarea
              value={letter.body}
              onChange={(e) => setLetter({ ...letter, body: e.target.value })}
              rows={12}
              className="w-full rounded-xl border border-[#1A1918]/12 bg-white px-3 py-2.5 text-[13px] leading-relaxed text-[#161615] outline-none focus:border-[#161615]/40 resize-y"
            />
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => void save()}
                disabled={!dirty || saving}
                className="inline-flex items-center gap-1.5 rounded-full border border-[#1A1918]/15 px-3 py-1.5 text-[12px] text-[#161615] hover:border-[#161615]/40 cursor-pointer disabled:opacity-40"
              >
                {saving ? <Loader2 className="h-3 w-3 animate-spin" /> : <Check className="h-3 w-3" />}
                {dirty ? "Enregistrer la lettre" : "Lettre enregistrée"}
              </button>
              <button
                type="button"
                onClick={() => openCanvas({ mode: "cover_letter", companyName: job.company_name, jobTitle: job.title, letter })}
                className="text-[12px] text-[#1A1918]/60 hover:text-[#161615] cursor-pointer"
              >
                Mise en page de la lettre
              </button>
            </div>
          </Section>
        )}
      </div>

      <div className="shrink-0 border-t border-[#1A1918]/8 px-5 py-3 bg-[#FAFAF8]">
        {sent ? (
          <p className="flex items-center justify-center gap-1.5 text-[12px] text-[#161615]">
            <Check className="h-3.5 w-3.5" /> Candidature envoyée
          </p>
        ) : awaiting ? (
          <motion.button
            type="button"
            whileTap={{ scale: 0.98 }}
            onClick={approve}
            disabled={sending}
            className="w-full inline-flex items-center justify-center gap-2 rounded-full bg-[#161615] px-4 py-2.5 text-xs text-white hover:bg-black cursor-pointer disabled:opacity-50"
          >
            {sending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
            {dirty ? "Enregistrer et envoyer" : "C'est bon, envoie"}
          </motion.button>
        ) : (
          <button
            type="button"
            onClick={() => openCanvas({ mode: "job_detail", job })}
            className="w-full rounded-full border border-[#1A1918]/15 px-4 py-2.5 text-xs text-[#161615] hover:border-[#161615]/40 cursor-pointer"
          >
            Revenir à l&apos;offre
          </button>
        )}
      </div>
    </div>
  );
}
