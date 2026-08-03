"use client";

import { User } from "lucide-react";
import { cn } from "@/lib/utils";

interface StepperHeaderProps {
  fullName: string;
  email: string;
  step: number;
  userFlowChoice: "studio" | "bypass" | null;
  isSubmitting: boolean;
  onSelectStep: (step: number) => void;
}

export function StepperHeader({
  fullName,
  email,
  step,
  userFlowChoice,
  isSubmitting,
  onSelectStep,
}: StepperHeaderProps) {
  return (
    <div className="space-y-6">
      {/* Top App Header */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4 border-b border-border pb-5">
        <div className="flex items-center gap-3">
          <div>
            <h1 className="text-xl font-bold tracking-tight text-foreground">Untaf</h1>
          </div>
        </div>

        <div className="flex items-center gap-2 rounded-xl bg-muted px-3.5 py-2 text-xs font-semibold text-muted-foreground">
          <User className="h-4 w-4" />
          <span>{fullName} ({email})</span>
        </div>
      </div>

      {/* STEPPER PROGRESS BAR (Visible inside Studio Flow) */}
      {userFlowChoice !== null && !isSubmitting && (
        <div>
          <div className="flex justify-between text-xs font-semibold text-muted-foreground">
            <span className={cn(step >= 1 && "text-primary")}>1. Importation & Diagnostic</span>
            <span className={cn(step >= 2 && "text-primary")}>2. Choix du Modèle & Style</span>
            <span className={cn(step >= 3 && "text-primary")}>3. Éditeur de CV</span>
            <span className={cn(step >= 4 && "text-primary")}>4. Matching & Offres</span>
          </div>
          <div className="mt-2 flex gap-2">
            {[1, 2, 3, 4].map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => onSelectStep(s)}
                className={cn(
                  "h-2 flex-1 rounded-full transition-all duration-300",
                  step >= s ? "bg-primary" : "bg-muted"
                )}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
