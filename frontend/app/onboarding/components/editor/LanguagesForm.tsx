"use client";

import { Plus, Trash2 } from "lucide-react";
import { LanguageEntry, languageLevels } from "../../types";

interface LanguagesFormProps {
  languages: LanguageEntry[];
  setLanguages: React.Dispatch<React.SetStateAction<LanguageEntry[]>>;
}

function genId() { return Math.random().toString(36).substring(2, 9); }

function emptyLang(): LanguageEntry {
  return { id: genId(), language: "", level: "Intermédiaire (B1)" };
}

export function LanguagesForm({ languages, setLanguages }: LanguagesFormProps) {
  const add = () => setLanguages((p) => [...p, emptyLang()]);
  const remove = (id: string) => setLanguages((p) => p.filter((l) => l.id !== id));

  const update = (id: string, field: keyof LanguageEntry, value: string) => {
    setLanguages((p) => p.map((l) => l.id === id ? { ...l, [field]: value } : l));
  };

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-bold text-foreground">Langues</h3>
          <p className="text-[11px] text-muted-foreground mt-0.5">Indiquez les langues que vous parlez et votre niveau.</p>
        </div>
        <button type="button" onClick={add} className="inline-flex h-8 items-center gap-1.5 rounded-lg bg-primary px-3 text-xs font-semibold text-primary-foreground hover:brightness-110 transition shadow-sm">
          <Plus className="h-3.5 w-3.5" />Ajouter
        </button>
      </div>

      {languages.length === 0 && (
        <div className="rounded-xl border-2 border-dashed border-border p-8 text-center">
          <p className="text-xs text-muted-foreground font-medium">Aucune langue ajoutée.</p>
          <button type="button" onClick={add} className="mt-3 inline-flex items-center gap-1.5 text-xs font-semibold text-primary hover:underline">
            <Plus className="h-3.5 w-3.5" />Ajouter une langue
          </button>
        </div>
      )}

      <div className="space-y-3">
        {languages.map((lang, idx) => (
          <div key={lang.id} className="flex items-center gap-3 rounded-xl border border-border bg-card p-3 shadow-sm">
            <span className="text-[11px] font-bold text-muted-foreground shrink-0 w-5 text-center">{idx + 1}</span>
            <div className="flex-1 grid grid-cols-1 sm:grid-cols-2 gap-3">
              <input
                type="text"
                value={lang.language}
                onChange={(e) => update(lang.id, "language", e.target.value)}
                placeholder="ex: Français, Anglais..."
                className="w-full rounded-lg border border-input bg-background py-2 px-3 text-xs focus:outline-none focus:ring-2 focus:ring-primary/40"
              />
              <select
                value={lang.level}
                onChange={(e) => update(lang.id, "level", e.target.value)}
                className="w-full rounded-lg border border-input bg-background py-2 px-3 text-xs focus:outline-none focus:ring-2 focus:ring-primary/40 appearance-none"
              >
                {languageLevels.map((lv) => (
                  <option key={lv} value={lv}>{lv}</option>
                ))}
              </select>
            </div>
            <button type="button" onClick={() => remove(lang.id)} className="p-1.5 rounded text-destructive/60 hover:text-destructive hover:bg-destructive/10 transition shrink-0">
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
