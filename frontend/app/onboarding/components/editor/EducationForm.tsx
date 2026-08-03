"use client";

import { Plus, Trash2, ChevronDown, ChevronUp } from "lucide-react";
import { EducationEntry } from "../../types";

interface EducationFormProps {
  education: EducationEntry[];
  setEducation: React.Dispatch<React.SetStateAction<EducationEntry[]>>;
}

function genId() { return Math.random().toString(36).substring(2, 9); }

function emptyEdu(): EducationEntry {
  return { id: genId(), degree: "", institution: "", location: "", startYear: "", endYear: "", description: "" };
}

export function EducationForm({ education, setEducation }: EducationFormProps) {
  const add = () => setEducation((p) => [...p, emptyEdu()]);
  const remove = (id: string) => setEducation((p) => p.filter((e) => e.id !== id));

  const update = (id: string, field: keyof EducationEntry, value: string) => {
    setEducation((p) => p.map((e) => e.id === id ? { ...e, [field]: value } : e));
  };

  const move = (id: string, dir: "up" | "down") => {
    setEducation((p) => {
      const i = p.findIndex((e) => e.id === id);
      const j = dir === "up" ? i - 1 : i + 1;
      if (j < 0 || j >= p.length) return p;
      const a = [...p]; [a[i], a[j]] = [a[j], a[i]]; return a;
    });
  };

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-bold text-foreground">Formation</h3>
          <p className="text-[11px] text-muted-foreground mt-0.5">Diplômes et certifications obtenus.</p>
        </div>
        <button type="button" onClick={add} className="inline-flex h-8 items-center gap-1.5 rounded-lg bg-primary px-3 text-xs font-semibold text-primary-foreground hover:brightness-110 transition shadow-sm">
          <Plus className="h-3.5 w-3.5" />Ajouter
        </button>
      </div>

      {education.length === 0 && (
        <div className="rounded-xl border-2 border-dashed border-border p-8 text-center">
          <p className="text-xs text-muted-foreground font-medium">Aucune formation ajoutée.</p>
          <button type="button" onClick={add} className="mt-3 inline-flex items-center gap-1.5 text-xs font-semibold text-primary hover:underline">
            <Plus className="h-3.5 w-3.5" />Ajouter une formation
          </button>
        </div>
      )}

      <div className="space-y-4">
        {education.map((edu, idx) => (
          <div key={edu.id} className="rounded-xl border border-border bg-card p-4 space-y-3 shadow-sm hover:shadow-md transition-shadow">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold text-muted-foreground uppercase tracking-wider">Formation {idx + 1}</span>
              <div className="flex items-center gap-1">
                <button type="button" onClick={() => move(edu.id, "up")} disabled={idx === 0} className="p-1 rounded hover:bg-muted disabled:opacity-30 transition"><ChevronUp className="h-3.5 w-3.5" /></button>
                <button type="button" onClick={() => move(edu.id, "down")} disabled={idx === education.length - 1} className="p-1 rounded hover:bg-muted disabled:opacity-30 transition"><ChevronDown className="h-3.5 w-3.5" /></button>
                <button type="button" onClick={() => remove(edu.id)} className="p-1 rounded text-destructive/60 hover:text-destructive hover:bg-destructive/10 transition"><Trash2 className="h-3.5 w-3.5" /></button>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-[11px] font-semibold">Diplôme / Certification</label>
                <input type="text" value={edu.degree} onChange={(e) => update(edu.id, "degree", e.target.value)} placeholder="ex: Master Informatique" className="w-full rounded-lg border border-input bg-background py-2 px-3 text-xs focus:outline-none focus:ring-2 focus:ring-primary/40" />
              </div>
              <div className="space-y-1">
                <label className="text-[11px] font-semibold">Établissement</label>
                <input type="text" value={edu.institution} onChange={(e) => update(edu.id, "institution", e.target.value)} placeholder="ex: Université Paris-Saclay" className="w-full rounded-lg border border-input bg-background py-2 px-3 text-xs focus:outline-none focus:ring-2 focus:ring-primary/40" />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className="space-y-1">
                <label className="text-[11px] font-semibold">Lieu</label>
                <input type="text" value={edu.location} onChange={(e) => update(edu.id, "location", e.target.value)} placeholder="Paris, France" className="w-full rounded-lg border border-input bg-background py-2 px-3 text-xs focus:outline-none focus:ring-2 focus:ring-primary/40" />
              </div>
              <div className="space-y-1">
                <label className="text-[11px] font-semibold">Année début</label>
                <input type="text" value={edu.startYear} onChange={(e) => update(edu.id, "startYear", e.target.value)} placeholder="2018" className="w-full rounded-lg border border-input bg-background py-2 px-3 text-xs focus:outline-none focus:ring-2 focus:ring-primary/40" />
              </div>
              <div className="space-y-1">
                <label className="text-[11px] font-semibold">Année fin</label>
                <input type="text" value={edu.endYear} onChange={(e) => update(edu.id, "endYear", e.target.value)} placeholder="2023" className="w-full rounded-lg border border-input bg-background py-2 px-3 text-xs focus:outline-none focus:ring-2 focus:ring-primary/40" />
              </div>
            </div>

            <div className="space-y-1">
              <label className="text-[11px] font-semibold">Description (optionnel)</label>
              <textarea rows={2} value={edu.description} onChange={(e) => update(edu.id, "description", e.target.value)} placeholder="Mention, spécialisation, projet de fin d'études..." className="w-full rounded-lg border border-input bg-background p-3 text-xs leading-relaxed focus:outline-none focus:ring-2 focus:ring-primary/40 resize-none" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
