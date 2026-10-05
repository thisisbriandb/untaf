"use client";

import { motion, AnimatePresence } from "framer-motion";
import { Check, Palette } from "lucide-react";
import { cn } from "@/lib/utils";
import { colorSwatches, cvTemplates, ColorSwatch, ExperienceEntry, EducationEntry, LanguageEntry } from "../types";
import { CandidateCvPreview } from "./CandidateCvPreview";

interface Step3DesignStudioProps {
  selectedTemplate: string;
  setSelectedTemplate: (tplId: string) => void;
  selectedColor: string;
  setSelectedColor: (colorId: string) => void;
  cvLanguage: "fr" | "en";
  setCvLanguage: (lang: "fr" | "en") => void;
  showPhotoOnCv: boolean;
  setShowPhotoOnCv: (show: boolean) => void;
  userPhotoUrl: string | null;
  activeColorSwatch: ColorSwatch;
  // Candidate real data for live preview
  fullName: string;
  headline: string;
  summary: string;
  email: string;
  phone?: string;
  linkedinUrl: string;
  skills: string[];
  experienceYears: number;
  experiences?: ExperienceEntry[];
  education?: EducationEntry[];
  languages?: LanguageEntry[];
}

export function Step3DesignStudio({
  selectedTemplate,
  setSelectedTemplate,
  selectedColor,
  setSelectedColor,
  cvLanguage,
  setCvLanguage,
  showPhotoOnCv,
  setShowPhotoOnCv,
  userPhotoUrl,
  activeColorSwatch,
  fullName,
  headline,
  summary,
  email,
  phone,
  linkedinUrl,
  skills,
  experienceYears,
  experiences = [],
  education = [],
  languages = [],
}: Step3DesignStudioProps) {
  const currentTpl = cvTemplates.find((t) => t.id === selectedTemplate) || cvTemplates[0];

  return (
    <motion.div
      key="step3"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      transition={{ duration: 0.2 }}
      className="space-y-6"
    >
      {/* Toolbar Controls */}
      <div className="rounded-2xl border border-border bg-card p-4 flex flex-wrap items-center justify-between gap-4 shadow-sm">
        <div>
          <h3 className="font-bold text-sm text-foreground flex items-center gap-2">
            <div className="h-7 w-7 rounded-lg bg-primary/10 flex items-center justify-center">
              <Palette className="h-3.5 w-3.5 text-primary" />
            </div>
            Studio de Design & Typographie
          </h3>
          <p className="text-[11px] text-muted-foreground mt-0.5">
            Choisissez un modèle et une couleur — l&apos;aperçu se met à jour en temps réel avec vos données.
          </p>
        </div>

        <div className="flex items-center gap-4">
          {/* Photo Toggle */}
          <label className="flex items-center gap-1.5 text-xs font-semibold cursor-pointer select-none">
            <input
              type="checkbox"
              checked={showPhotoOnCv}
              onChange={(e) => setShowPhotoOnCv(e.target.checked)}
              className="rounded accent-primary"
            />
            Photo visible
          </label>

          {/* Language Selector */}
          <div className="flex items-center gap-1 bg-muted p-1 rounded-lg text-xs font-semibold">
            <button
              type="button"
              onClick={() => setCvLanguage("fr")}
              className={cn("px-2 py-0.5 rounded transition", cvLanguage === "fr" && "bg-card text-foreground shadow-xs")}
            >
              FR
            </button>
            <button
              type="button"
              onClick={() => setCvLanguage("en")}
              className={cn("px-2 py-0.5 rounded transition", cvLanguage === "en" && "bg-card text-foreground shadow-xs")}
            >
              EN
            </button>
          </div>

          {/* Color Swatches */}
          <div className="flex items-center gap-1">
            {colorSwatches.map((swatch) => (
              <button
                key={swatch.id}
                type="button"
                title={swatch.name}
                onClick={() => setSelectedColor(swatch.id)}
                className={cn(
                  "h-5 w-5 rounded-full transition-transform hover:scale-110 flex items-center justify-center",
                  swatch.bg,
                  selectedColor === swatch.id && "ring-2 ring-offset-2 ring-primary scale-110"
                )}
              >
                {selectedColor === swatch.id && <Check className="h-3 w-3 text-white" />}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Split layout: Template selector + Live Preview */}
      <div className="flex flex-col lg:flex-row gap-6 items-start">
        {/* Left: Template Selector (compact cards) */}
        <div className="w-full lg:w-[280px] lg:shrink-0 space-y-2">
          <p className="text-[11px] font-bold text-muted-foreground uppercase tracking-wider px-1">
            Modèles disponibles
          </p>
          <div className="grid grid-cols-2 lg:grid-cols-1 gap-2">
            {cvTemplates.map((template) => {
              const isActive = selectedTemplate === template.id;
              return (
                <button
                  key={template.id}
                  type="button"
                  onClick={() => setSelectedTemplate(template.id)}
                  className={cn(
                    "group w-full text-left rounded-xl border p-3 transition-all duration-150",
                    isActive
                      ? "border-primary bg-primary/5 ring-1 ring-primary shadow-sm"
                      : "border-border bg-card hover:border-muted-foreground/40 hover:bg-muted/30"
                  )}
                >
                  <div className="flex items-center gap-2.5">
                    {/* Mini layout icon */}
                    <div
                      className={cn(
                        "h-9 w-7 rounded border flex flex-col overflow-hidden shrink-0 transition",
                        isActive ? "border-primary/50" : "border-slate-200 dark:border-slate-700"
                      )}
                    >
                      {/* Mini header bar */}
                      <div
                        className="h-2 w-full"
                        style={{ backgroundColor: isActive ? activeColorSwatch.hex : "#cbd5e1" }}
                      />
                      {/* Mini content area */}
                      <div className="flex-1 flex gap-px p-px">
                        {(template.layout === "left-sidebar" || template.layout === "creative") ? (
                          <>
                            <div className="w-1/3 bg-slate-100 dark:bg-slate-700 rounded-xs" />
                            <div className="flex-1 space-y-px">
                              <div className="h-1 bg-slate-200 dark:bg-slate-600 rounded-xs" />
                              <div className="h-1 bg-slate-200 dark:bg-slate-600 rounded-xs w-3/4" />
                              <div className="h-1 bg-slate-200 dark:bg-slate-600 rounded-xs w-1/2" />
                            </div>
                          </>
                        ) : (
                          <div className="flex-1 space-y-px">
                            <div className="h-1 bg-slate-200 dark:bg-slate-600 rounded-xs" />
                            <div className="h-1 bg-slate-200 dark:bg-slate-600 rounded-xs w-3/4" />
                            <div className="h-1 bg-slate-200 dark:bg-slate-600 rounded-xs w-1/2" />
                            <div className="h-1 bg-slate-200 dark:bg-slate-600 rounded-xs w-2/3" />
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="flex-1 min-w-0">
                      <p className={cn(
                        "text-xs font-bold truncate transition",
                        isActive ? "text-primary" : "text-foreground group-hover:text-primary"
                      )}>
                        {template.name}
                      </p>
                      <p className="text-[11px] text-muted-foreground truncate">
                        {template.badge} — {template.tagline}
                      </p>
                    </div>

                    {isActive && (
                      <div className="shrink-0">
                        <div className="h-5 w-5 rounded-full bg-primary flex items-center justify-center">
                          <Check className="h-3 w-3 text-primary-foreground" />
                        </div>
                      </div>
                    )}
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Right: Live CV Preview with real candidate data */}
        <div className="flex-1 w-full">
          <div className="flex items-center justify-between mb-2 px-1">
            <span className="text-[11px] font-bold text-muted-foreground uppercase tracking-wider">
              Aperçu temps réel — vos données
            </span>
            <span className="text-[11px] text-muted-foreground font-mono">
              A4 — {currentTpl.name}
            </span>
          </div>
          <div className="rounded-2xl border border-border bg-slate-100/90 dark:bg-slate-900/90 p-3 shadow-sm">
            <AnimatePresence mode="wait">
              <motion.div
                key={selectedTemplate + selectedColor}
                initial={{ opacity: 0, scale: 0.98 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.98 }}
                transition={{ duration: 0.15 }}
              >
                <CandidateCvPreview
                  fullName={fullName}
                  headline={headline}
                  summary={summary}
                  email={email}
                  linkedinUrl={linkedinUrl}
                  phone={phone}
                  skills={skills}
                  experienceYears={experienceYears}
                  templateId={selectedTemplate}
                  selectedColorHex={activeColorSwatch.hex}
                  showPhoto={showPhotoOnCv}
                  userPhotoUrl={userPhotoUrl}
                  experiences={experiences}
                  education={education}
                  languages={languages}
                />
              </motion.div>
            </AnimatePresence>
          </div>
        </div>
      </div>
    </motion.div>
  );
}
