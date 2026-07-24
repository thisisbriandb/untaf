"use client";

import { useState, useMemo } from "react";
import { motion } from "framer-motion";
import { ArrowLeft, ArrowRight, FileText } from "lucide-react";
import {
  CvEditorSubStep,
  cvEditorSubSteps,
  ExperienceEntry,
  EducationEntry,
  LanguageEntry,
  CVAuditData,
  ColorSwatch,
} from "../types";
import { EditorSubStepper } from "./editor/EditorSubStepper";
import { PersonalInfoForm } from "./editor/PersonalInfoForm";
import { ExperiencesForm } from "./editor/ExperiencesForm";
import { EducationForm } from "./editor/EducationForm";
import { SkillsForm } from "./editor/SkillsForm";
import { LanguagesForm } from "./editor/LanguagesForm";
import { CandidateCvPreview } from "./CandidateCvPreview";

interface Step2CvEditorProps {
  // Personal info
  fullName: string;
  setFullName: (v: string) => void;
  email: string;
  setEmail: (v: string) => void;
  phone: string;
  setPhone: (v: string) => void;
  linkedinUrl: string;
  setLinkedinUrl: (v: string) => void;
  headline: string;
  setHeadline: (v: string) => void;
  summary: string;
  setSummary: (v: string) => void;
  userPhotoUrl: string | null;
  handlePhotoUpload: (e: React.ChangeEvent<HTMLInputElement>) => void;
  showPhotoOnCv: boolean;
  setShowPhotoOnCv: (v: boolean) => void;
  // Experiences
  experiences: ExperienceEntry[];
  setExperiences: React.Dispatch<React.SetStateAction<ExperienceEntry[]>>;
  // Education
  education: EducationEntry[];
  setEducation: React.Dispatch<React.SetStateAction<EducationEntry[]>>;
  // Skills
  skills: string[];
  setSkills: React.Dispatch<React.SetStateAction<string[]>>;
  // Languages
  languages: LanguageEntry[];
  setLanguages: React.Dispatch<React.SetStateAction<LanguageEntry[]>>;
  // AI Audit
  atsAudit: CVAuditData | null;
  // Design
  experienceYears: number;
  selectedTemplate: string;
  activeColorSwatch: ColorSwatch;
}

export function Step2CvEditor(props: Step2CvEditorProps) {
  const [subStep, setSubStep] = useState<CvEditorSubStep>("personal");
  const [completedSubSteps, setCompletedSubSteps] = useState<Set<CvEditorSubStep>>(new Set());

  const currentIndex = cvEditorSubSteps.findIndex((s) => s.id === subStep);
  const isFirst = currentIndex === 0;
  const isLast = currentIndex === cvEditorSubSteps.length - 1;

  const goNext = () => {
    if (!isLast) {
      setCompletedSubSteps((prev) => new Set([...prev, subStep]));
      setSubStep(cvEditorSubSteps[currentIndex + 1].id);
    }
  };

  const goPrev = () => {
    if (!isFirst) {
      setSubStep(cvEditorSubSteps[currentIndex - 1].id);
    }
  };

  const handleSelectSubStep = (step: CvEditorSubStep) => {
    // Mark current as completed when navigating away
    if (step !== subStep) {
      setCompletedSubSteps((prev) => new Set([...prev, subStep]));
    }
    setSubStep(step);
  };

  // Current sub-step label
  const currentLabel = cvEditorSubSteps[currentIndex]?.label || "";

  // Memoized sub-step progress text
  const progressText = useMemo(
    () => `${currentIndex + 1} / ${cvEditorSubSteps.length}`,
    [currentIndex]
  );

  return (
    <motion.div
      key="step2"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      transition={{ duration: 0.2 }}
      className="space-y-4"
    >
      {/* Header */}
      <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-lg bg-primary/10 flex items-center justify-center">
              <FileText className="h-4 w-4 text-primary" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-foreground">Éditeur de CV</h2>
              <p className="text-[11px] text-muted-foreground">
                Complétez chaque section — l&apos;aperçu se met à jour en temps réel.
              </p>
            </div>
          </div>
          <span className="text-[11px] font-mono font-bold text-muted-foreground bg-muted px-2 py-0.5 rounded-md">
            {progressText}
          </span>
        </div>
        <EditorSubStepper
          currentSubStep={subStep}
          onSelectSubStep={handleSelectSubStep}
          completedSubSteps={completedSubSteps}
        />
      </div>

      {/* Split-pane layout */}
      <div className="flex flex-col lg:flex-row gap-4">
        {/* Left: Form panel */}
        <div className="w-full lg:w-[55%] rounded-2xl border border-border bg-card p-5 sm:p-6 shadow-sm min-h-[400px]">
          <motion.div
            key={subStep}
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 10 }}
            transition={{ duration: 0.15 }}
          >
            {subStep === "personal" && (
              <PersonalInfoForm
                fullName={props.fullName}
                setFullName={props.setFullName}
                email={props.email}
                setEmail={props.setEmail}
                phone={props.phone}
                setPhone={props.setPhone}
                linkedinUrl={props.linkedinUrl}
                setLinkedinUrl={props.setLinkedinUrl}
                headline={props.headline}
                setHeadline={props.setHeadline}
                summary={props.summary}
                setSummary={props.setSummary}
                userPhotoUrl={props.userPhotoUrl}
                handlePhotoUpload={props.handlePhotoUpload}
                showPhotoOnCv={props.showPhotoOnCv}
                setShowPhotoOnCv={props.setShowPhotoOnCv}
                atsAudit={props.atsAudit}
              />
            )}
            {subStep === "experiences" && (
              <ExperiencesForm
                experiences={props.experiences}
                setExperiences={props.setExperiences}
              />
            )}
            {subStep === "education" && (
              <EducationForm
                education={props.education}
                setEducation={props.setEducation}
              />
            )}
            {subStep === "skills" && (
              <SkillsForm
                skills={props.skills}
                setSkills={props.setSkills}
                atsAudit={props.atsAudit}
              />
            )}
            {subStep === "languages" && (
              <LanguagesForm
                languages={props.languages}
                setLanguages={props.setLanguages}
              />
            )}
          </motion.div>

          {/* Internal sub-step navigation */}
          <div className="mt-6 pt-4 border-t border-border flex items-center justify-between">
            <button
              type="button"
              onClick={goPrev}
              disabled={isFirst}
              className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-border bg-card px-4 text-xs font-semibold hover:bg-muted disabled:opacity-30 disabled:cursor-not-allowed transition"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              Précédent
            </button>

            <span className="text-[11px] text-muted-foreground font-medium hidden sm:block">
              {currentLabel}
            </span>

            {!isLast ? (
              <button
                type="button"
                onClick={goNext}
                className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-primary px-4 text-xs font-semibold text-primary-foreground hover:brightness-110 transition shadow-sm"
              >
                Suivant
                <ArrowRight className="h-3.5 w-3.5" />
              </button>
            ) : (
              <div className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-emerald-600 px-4 text-xs font-bold text-white shadow-sm">
                ✓ Section complète
              </div>
            )}
          </div>
        </div>

        {/* Right: Live CV Preview */}
        <div className="w-full lg:w-[45%] lg:sticky lg:top-4 lg:self-start">
          <div className="rounded-2xl border border-border bg-slate-100 dark:bg-slate-900 p-3 shadow-sm">
            <div className="flex items-center justify-between mb-2 px-1">
              <span className="text-[11px] font-bold text-muted-foreground uppercase tracking-wider">
                Aperçu en temps réel
              </span>
              <span className="text-[10px] text-muted-foreground font-mono">
                A4 — {props.selectedTemplate}
              </span>
            </div>
            <CandidateCvPreview
              fullName={props.fullName}
              headline={props.headline}
              summary={props.summary}
              email={props.email}
              linkedinUrl={props.linkedinUrl}
              skills={props.skills}
              experienceYears={props.experienceYears}
              templateId={props.selectedTemplate}
              selectedColorHex={props.activeColorSwatch.hex}
              showPhoto={props.showPhotoOnCv}
              userPhotoUrl={props.userPhotoUrl}
              experiences={props.experiences}
              education={props.education}
              languages={props.languages}
              phone={props.phone}
            />
          </div>
        </div>
      </div>
    </motion.div>
  );
}
