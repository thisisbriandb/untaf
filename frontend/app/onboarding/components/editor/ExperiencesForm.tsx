"use client";

import { Plus, Trash2, ChevronDown, ChevronUp } from "lucide-react";
import { ExperienceEntry } from "../../types";

interface ExperiencesFormProps {
  experiences: ExperienceEntry[];
  setExperiences: React.Dispatch<React.SetStateAction<ExperienceEntry[]>>;
}

function genId() {
  return Math.random().toString(36).substring(2, 9);
}

function emptyExp(): ExperienceEntry {
  return { id: genId(), jobTitle: "", company: "", location: "", startDate: "", endDate: "", isCurrent: false, highlights: [""] };
}

export function ExperiencesForm({ experiences, setExperiences }: ExperiencesFormProps) {
  const add = () => setExperiences((p) => [...p, emptyExp()]);
  const remove = (id: string) => setExperiences((p) => p.filter((e) => e.id !== id));

  const update = (id: string, field: keyof ExperienceEntry, value: any) => {
    setExperiences((p) => p.map((e) => {
      if (e.id !== id) return e;
      const u = { ...e, [field]: value };
      if (field === "isCurrent" && value) u.endDate = "present";
      return u;
    }));
  };

  const updateHL = (eid: string, i: number, v: string) => {
    setExperiences((p) => p.map((e) => {
      if (e.id !== eid) return e;
      const h = [...e.highlights]; h[i] = v;
      return { ...e, highlights: h };
    }));
  };

  const addHL = (eid: string) => setExperiences((p) => p.map((e) => e.id === eid ? { ...e, highlights: [...e.highlights, ""] } : e));
  const rmHL = (eid: string, i: number) => setExperiences((p) => p.map((e) => e.id === eid ? { ...e, highlights: e.highlights.filter((_, j) => j !== i) } : e));

  const move = (id: string, dir: "up" | "down") => {
    setExperiences((p) => {
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
          <h3 className="text-sm font-bold text-foreground">Expériences professionnelles</h3>
          <p className="text-[11px] text-muted-foreground mt-0.5">De la plus récente à la plus ancienne.</p>
        </div>
        <button type="button" onClick={add} className="inline-flex h-8 items-center gap-1.5 rounded-lg bg-primary px-3 text-xs font-semibold text-primary-foreground hover:brightness-110 transition shadow-sm">
          <Plus className="h-3.5 w-3.5" />Ajouter
        </button>
      </div>

      {experiences.length === 0 && (
        <div className="rounded-xl border-2 border-dashed border-border p-8 text-center">
          <p className="text-xs text-muted-foreground font-medium">Aucune expérience ajoutée.</p>
          <button type="button" onClick={add} className="mt-3 inline-flex items-center gap-1.5 text-xs font-semibold text-primary hover:underline">
            <Plus className="h-3.5 w-3.5" />Ajouter votre première expérience
          </button>
        </div>
      )}

      <div className="space-y-4">
        {experiences.map((exp, idx) => (
          <div key={exp.id} className="rounded-xl border border-border bg-card p-4 space-y-3 shadow-sm hover:shadow-md transition-shadow">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold text-muted-foreground uppercase tracking-wider">Expérience {idx + 1}</span>
              <div className="flex items-center gap-1">
                <button type="button" onClick={() => move(exp.id, "up")} disabled={idx === 0} className="p-1 rounded hover:bg-muted disabled:opacity-30 transition"><ChevronUp className="h-3.5 w-3.5" /></button>
                <button type="button" onClick={() => move(exp.id, "down")} disabled={idx === experiences.length - 1} className="p-1 rounded hover:bg-muted disabled:opacity-30 transition"><ChevronDown className="h-3.5 w-3.5" /></button>
                <button type="button" onClick={() => remove(exp.id)} className="p-1 rounded text-destructive/60 hover:text-destructive hover:bg-destructive/10 transition"><Trash2 className="h-3.5 w-3.5" /></button>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-[11px] font-semibold">Intitulé du poste</label>
                <input type="text" value={exp.jobTitle} onChange={(e) => update(exp.id, "jobTitle", e.target.value)} placeholder="ex: Développeur Full-Stack" className="w-full rounded-lg border border-input bg-background py-2 px-3 text-xs focus:outline-none focus:ring-2 focus:ring-primary/40" />
              </div>
              <div className="space-y-1">
                <label className="text-[11px] font-semibold">Entreprise</label>
                <input type="text" value={exp.company} onChange={(e) => update(exp.id, "company", e.target.value)} placeholder="ex: Acme Corp" className="w-full rounded-lg border border-input bg-background py-2 px-3 text-xs focus:outline-none focus:ring-2 focus:ring-primary/40" />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className="space-y-1">
                <label className="text-[11px] font-semibold">Lieu</label>
                <input type="text" value={exp.location} onChange={(e) => update(exp.id, "location", e.target.value)} placeholder="Paris, France" className="w-full rounded-lg border border-input bg-background py-2 px-3 text-xs focus:outline-none focus:ring-2 focus:ring-primary/40" />
              </div>
              <div className="space-y-1">
                <label className="text-[11px] font-semibold">Début</label>
                <input type="month" value={exp.startDate} onChange={(e) => update(exp.id, "startDate", e.target.value)} className="w-full rounded-lg border border-input bg-background py-2 px-3 text-xs focus:outline-none focus:ring-2 focus:ring-primary/40" />
              </div>
              <div className="space-y-1">
                <label className="text-[11px] font-semibold">Fin</label>
                <input type="month" value={exp.isCurrent ? "" : exp.endDate} onChange={(e) => update(exp.id, "endDate", e.target.value)} disabled={exp.isCurrent} className="w-full rounded-lg border border-input bg-background py-2 px-3 text-xs focus:outline-none focus:ring-2 focus:ring-primary/40 disabled:opacity-50" />
                <label className="flex items-center gap-1.5 text-[11px] text-muted-foreground cursor-pointer select-none">
                  <input type="checkbox" checked={exp.isCurrent} onChange={(e) => update(exp.id, "isCurrent", e.target.checked)} className="rounded accent-primary" />Poste actuel
                </label>
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-[11px] font-semibold">Réalisations clés</label>
              {exp.highlights.map((h, hIdx) => (
                <div key={hIdx} className="flex gap-2 items-start">
                  <span className="mt-2 text-[11px] text-muted-foreground font-mono shrink-0">•</span>
                  <input type="text" value={h} onChange={(e) => updateHL(exp.id, hIdx, e.target.value)} placeholder="Décrivez une réalisation..." className="flex-1 rounded-lg border border-input bg-background py-2 px-3 text-xs focus:outline-none focus:ring-2 focus:ring-primary/40" />
                  {exp.highlights.length > 1 && (
                    <button type="button" onClick={() => rmHL(exp.id, hIdx)} className="mt-1.5 p-1 text-muted-foreground hover:text-destructive transition"><Trash2 className="h-3 w-3" /></button>
                  )}
                </div>
              ))}
              <button type="button" onClick={() => addHL(exp.id)} className="inline-flex items-center gap-1 text-[11px] font-semibold text-primary hover:underline">
                <Plus className="h-3 w-3" />Ajouter un point
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
