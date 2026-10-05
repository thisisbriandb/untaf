"use client";

import { motion } from "framer-motion";
import { Sparkles, Plus, X } from "lucide-react";
import { CVAuditData } from "../types";

interface Step2ContentEditorProps {
  headline: string;
  setHeadline: (h: string) => void;
  summary: string;
  setSummary: (s: string) => void;
  skills: string[];
  setSkills: React.Dispatch<React.SetStateAction<string[]>>;
  removeSkill: (s: string) => void;
  atsAudit: CVAuditData | null;
}

export function Step2ContentEditor({
  headline,
  setHeadline,
  summary,
  setSummary,
  skills,
  setSkills,
  removeSkill,
  atsAudit,
}: Step2ContentEditorProps) {
  return (
    <motion.div
      key="step2"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      transition={{ duration: 0.2 }}
      className="space-y-6"
    >
      <div className="rounded-2xl border border-border bg-card p-6 sm:p-8 space-y-6 shadow-sm">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-foreground">
            2. Éditeur & Assistance Rédactionnelle IA
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Ajustez et enrichissez votre titre, résumé et compétences recommandées par Gemini.
          </p>
        </div>

        {/* Headline input with AI Suggestion */}
        <div className="space-y-2">
          <div className="flex justify-between items-center">
            <label className="text-xs font-semibold">Titre professionnel (Accroche)</label>
            {atsAudit?.optimized_headline && (
              <button
                type="button"
                onClick={() => setHeadline(atsAudit.optimized_headline)}
                className="inline-flex items-center gap-1 text-[11px] font-semibold text-primary hover:underline"
              >
                <Sparkles className="h-3 w-3" />
                Appliquer la suggestion IA
              </button>
            )}
          </div>
          <input
            type="text"
            value={headline}
            onChange={(e) => setHeadline(e.target.value)}
            className="w-full rounded-xl border border-input bg-background py-3 px-4 text-xs font-semibold transition focus:outline-none focus:ring-2 focus:ring-primary/40"
          />
        </div>

        {/* Summary input with AI Suggestion */}
        <div className="space-y-2">
          <div className="flex justify-between items-center">
            <label className="text-xs font-semibold">Profil Professionnel & Synthèse</label>
            {atsAudit?.optimized_summary && (
              <button
                type="button"
                onClick={() => setSummary(atsAudit.optimized_summary)}
                className="inline-flex items-center gap-1 text-[11px] font-semibold text-primary hover:underline"
              >
                <Sparkles className="h-3 w-3" />
                Appliquer le résumé optimisé
              </button>
            )}
          </div>
          <textarea
            rows={4}
            value={summary}
            onChange={(e) => setSummary(e.target.value)}
            placeholder="Résumez votre parcours, vos réalisations clés et votre valeur ajoutée..."
            className="w-full rounded-xl border border-input bg-background p-3 text-xs leading-relaxed transition focus:outline-none focus:ring-2 focus:ring-primary/40 resize-none"
          />
        </div>

        {/* Skills Manager with Suggested Tags */}
        <div className="space-y-3">
          <label className="text-xs font-semibold">Compétences Clés & Mots-Clés Recruteur</label>
          <div className="flex flex-wrap gap-1.5">
            {skills.map((s) => (
              <span
                key={s}
                className="inline-flex h-7 items-center gap-1 rounded bg-primary/10 text-primary px-2.5 text-xs font-semibold"
              >
                {s}
                <button
                  type="button"
                  onClick={() => removeSkill(s)}
                  className="text-primary hover:text-primary-foreground"
                >
                  <X className="h-3 w-3" />
                </button>
              </span>
            ))}
          </div>

          {atsAudit?.suggested_skills && atsAudit.suggested_skills.length > 0 && (
            <div className="pt-2 space-y-1.5">
              <p className="text-[11px] font-medium text-muted-foreground">Compétences recommandées par l&apos;IA :</p>
              <div className="flex flex-wrap gap-1.5">
                {atsAudit.suggested_skills.map((sk) => (
                  <button
                    key={sk}
                    type="button"
                    onClick={() => {
                      if (!skills.includes(sk)) setSkills([...skills, sk]);
                    }}
                    className="inline-flex items-center gap-1 rounded-md border border-[#161615]/30 bg-[#161615]/10 px-2 py-0.5 text-[11px] font-semibold text-[#161615] hover:bg-[#161615]/20"
                  >
                    <Plus className="h-3 w-3" />
                    {sk}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
}
