"use client";

import { Plus, X, Sparkles } from "lucide-react";
import { useState } from "react";
import { CVAuditData } from "../../types";

interface SkillsFormProps {
  skills: string[];
  setSkills: React.Dispatch<React.SetStateAction<string[]>>;
  atsAudit: CVAuditData | null;
}

export function SkillsForm({ skills, setSkills, atsAudit }: SkillsFormProps) {
  const [input, setInput] = useState("");

  const addSkill = () => {
    const val = input.trim();
    if (val && !skills.includes(val)) {
      setSkills((p) => [...p, val]);
      setInput("");
    }
  };

  const removeSkill = (s: string) => setSkills((p) => p.filter((x) => x !== s));

  const addSuggested = (s: string) => {
    if (!skills.includes(s)) setSkills((p) => [...p, s]);
  };

  return (
    <div className="space-y-5">
      <div>
        <h3 className="text-sm font-bold text-foreground">Compétences</h3>
        <p className="text-[11px] text-muted-foreground mt-0.5">
          Ajoutez vos compétences techniques et transversales. Les mots-clés pertinents augmentent votre score ATS.
        </p>
      </div>

      {/* Input */}
      <div className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addSkill(); } }}
          placeholder="ex: React, Python, Gestion de projet..."
          className="flex-1 rounded-xl border border-input bg-background py-2.5 px-3.5 text-xs transition focus:outline-none focus:ring-2 focus:ring-primary/40"
        />
        <button type="button" onClick={addSkill} className="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-foreground hover:brightness-110 transition shrink-0">
          <Plus className="h-4 w-4" />
        </button>
      </div>

      {/* Tags */}
      <div className="flex flex-wrap gap-1.5">
        {skills.map((s) => (
          <span key={s} className="inline-flex h-7 items-center gap-1 rounded-lg bg-primary/10 text-primary px-2.5 text-xs font-semibold">
            {s}
            <button type="button" onClick={() => removeSkill(s)} className="text-primary/60 hover:text-primary">
              <X className="h-3 w-3" />
            </button>
          </span>
        ))}
        {skills.length === 0 && (
          <p className="text-[11px] text-muted-foreground italic">Aucune compétence ajoutée. Tapez ci-dessus pour commencer.</p>
        )}
      </div>

      {/* AI Suggestions */}
      {atsAudit?.suggested_skills && atsAudit.suggested_skills.length > 0 && (
        <div className="rounded-xl border border-[#161615]/20 bg-[#161615]/5 p-3.5 space-y-2">
          <div className="flex items-center gap-1.5">
            <Sparkles className="h-3.5 w-3.5 text-[#161615]" />
            <span className="text-[11px] font-bold text-[#161615] dark:text-[#5E5D59]">Compétences recommandées par l&apos;IA</span>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {atsAudit.suggested_skills.filter((s) => !skills.includes(s)).map((sk) => (
              <button key={sk} type="button" onClick={() => addSuggested(sk)} className="inline-flex items-center gap-1 rounded-md border border-[#161615]/30 bg-[#161615]/10 px-2.5 py-1 text-[11px] font-semibold text-[#161615] hover:bg-[#161615]/20 transition">
                <Plus className="h-3 w-3" />{sk}
              </button>
            ))}
            {atsAudit.suggested_skills.filter((s) => !skills.includes(s)).length === 0 && (
              <p className="text-[11px] text-[#161615]/60 italic">Toutes les suggestions ont été ajoutées ✓</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
