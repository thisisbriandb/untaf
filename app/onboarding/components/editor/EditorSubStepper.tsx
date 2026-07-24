"use client";

import { cn } from "@/lib/utils";
import {
  User,
  Briefcase,
  GraduationCap,
  Zap,
  Globe,
  Check,
} from "lucide-react";
import { CvEditorSubStep, cvEditorSubSteps } from "../../types";

const iconMap: Record<string, React.ElementType> = {
  personal: User,
  experiences: Briefcase,
  education: GraduationCap,
  skills: Zap,
  languages: Globe,
};

interface EditorSubStepperProps {
  currentSubStep: CvEditorSubStep;
  onSelectSubStep: (step: CvEditorSubStep) => void;
  completedSubSteps: Set<CvEditorSubStep>;
}

export function EditorSubStepper({
  currentSubStep,
  onSelectSubStep,
  completedSubSteps,
}: EditorSubStepperProps) {
  const currentIndex = cvEditorSubSteps.findIndex(
    (s) => s.id === currentSubStep
  );

  return (
    <div className="w-full">
      {/* Desktop horizontal stepper */}
      <div className="hidden sm:flex items-center justify-between gap-1">
        {cvEditorSubSteps.map((step, idx) => {
          const Icon = iconMap[step.id];
          const isActive = step.id === currentSubStep;
          const isDone =
            completedSubSteps.has(step.id) && step.id !== currentSubStep;
          const isPast = idx < currentIndex;

          return (
            <button
              key={step.id}
              type="button"
              onClick={() => onSelectSubStep(step.id)}
              className={cn(
                "group relative flex items-center gap-2 rounded-xl px-3 py-2.5 text-xs font-semibold transition-all duration-200 flex-1 justify-center",
                isActive
                  ? "bg-primary text-primary-foreground shadow-md shadow-primary/20"
                  : isDone || isPast
                  ? "bg-primary/10 text-primary hover:bg-primary/15"
                  : "bg-muted/60 text-muted-foreground hover:bg-muted hover:text-foreground"
              )}
            >
              <span
                className={cn(
                  "flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold shrink-0 transition-all",
                  isActive
                    ? "bg-white/20 text-primary-foreground"
                    : isDone || isPast
                    ? "bg-primary/20 text-primary"
                    : "bg-muted-foreground/10 text-muted-foreground"
                )}
              >
                {isDone || isPast ? (
                  <Check className="h-3 w-3" />
                ) : Icon ? (
                  <Icon className="h-3 w-3" />
                ) : (
                  idx + 1
                )}
              </span>
              <span className="truncate hidden lg:inline">{step.label}</span>
              <span className="truncate lg:hidden">{step.shortLabel}</span>
            </button>
          );
        })}
      </div>

      {/* Mobile vertical stepper - compact pills */}
      <div className="flex sm:hidden overflow-x-auto gap-1.5 pb-1 -mx-1 px-1">
        {cvEditorSubSteps.map((step, idx) => {
          const isActive = step.id === currentSubStep;
          const isDone =
            completedSubSteps.has(step.id) && step.id !== currentSubStep;
          const isPast = idx < currentIndex;

          return (
            <button
              key={step.id}
              type="button"
              onClick={() => onSelectSubStep(step.id)}
              className={cn(
                "flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[11px] font-semibold transition-all whitespace-nowrap shrink-0",
                isActive
                  ? "bg-primary text-primary-foreground shadow-sm"
                  : isDone || isPast
                  ? "bg-primary/10 text-primary"
                  : "bg-muted text-muted-foreground"
              )}
            >
              {isDone || isPast ? (
                <Check className="h-3 w-3" />
              ) : (
                <span className="font-bold">{idx + 1}</span>
              )}
              {step.shortLabel}
            </button>
          );
        })}
      </div>

      {/* Progress bar */}
      <div className="mt-2 flex gap-0.5">
        {cvEditorSubSteps.map((step, idx) => (
          <div
            key={step.id}
            className={cn(
              "h-1 flex-1 rounded-full transition-all duration-300",
              idx <= currentIndex ? "bg-primary" : "bg-muted"
            )}
          />
        ))}
      </div>
    </div>
  );
}
