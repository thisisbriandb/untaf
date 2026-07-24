"use client";

import { ArrowLeft, ArrowRight } from "lucide-react";

interface NavigationBarProps {
  step: number;
  onPrev: () => void;
  onResetChoice: () => void;
  onNext: () => void;
  onSubmit: () => void;
  canNext: boolean;
  canSubmit: boolean;
}

export function NavigationBar({
  step,
  onPrev,
  onResetChoice,
  onNext,
  onSubmit,
  canNext,
  canSubmit,
}: NavigationBarProps) {
  return (
    <div className="mt-8 flex justify-between gap-4 border-t border-border pt-6">
      {step > 1 ? (
        <button
          type="button"
          onClick={onPrev}
          className="inline-flex h-11 items-center gap-1.5 rounded-xl border border-border bg-card px-5 text-xs font-semibold hover:bg-muted cursor-pointer"
        >
          <ArrowLeft className="h-4 w-4" />
          Précédent
        </button>
      ) : (
        <button
          type="button"
          onClick={onResetChoice}
          className="inline-flex h-11 items-center gap-1.5 rounded-xl border border-border bg-card px-5 text-xs font-semibold hover:bg-muted cursor-pointer"
        >
          <ArrowLeft className="h-4 w-4" />
          Retour au choix d&apos;accueil
        </button>
      )}

      {step < 4 ? (
        <button
          type="button"
          onClick={onNext}
          disabled={!canNext}
          className="inline-flex h-11 items-center gap-1.5 rounded-xl bg-primary px-6 text-xs font-semibold text-primary-foreground transition hover:brightness-110 disabled:opacity-50 shadow-md shadow-primary/15 cursor-pointer"
        >
          Suivant
          <ArrowRight className="h-4 w-4" />
        </button>
      ) : (
        <button
          type="button"
          onClick={onSubmit}
          disabled={!canSubmit}
          className="inline-flex h-11 items-center gap-1.5 rounded-xl bg-primary px-7 text-xs font-bold text-primary-foreground shadow-lg shadow-primary/20 transition hover:brightness-110 disabled:opacity-50 cursor-pointer"
        >
          Valider mon profil & Lancer le Matching
          <ArrowRight className="h-4 w-4" />
        </button>
      )}
    </div>
  );
}
