"use client";

import { useState, useMemo, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";
import {
  ArrowLeft,
  ArrowRight,
  FileText,
  PanelRightOpen,
  PanelRightClose,
  Eye,
  FileCheck,
  ExternalLink,
} from "lucide-react";
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
  setSelectedTemplate?: (templateId: string) => void;
  activeColorSwatch: ColorSwatch;
  // Original uploaded CV file (optional)
  cvFile?: File | null;
}

export function Step2CvEditor(props: Step2CvEditorProps) {
  const [subStep, setSubStep] = useState<CvEditorSubStep>("personal");
  const [completedSubSteps, setCompletedSubSteps] = useState<Set<CvEditorSubStep>>(new Set());

  // Layout & sidebar state
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [activePreviewTab, setActivePreviewTab] = useState<"template" | "original">("template");

  // Read original PDF file safely as Data URL (base64) so browser blob isn't revoked
  const [pdfDataUrl, setPdfDataUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!props.cvFile) {
      setPdfDataUrl(null);
      return;
    }

    let isMounted = true;

    if (props.cvFile.type === "application/pdf" || props.cvFile.name.endsWith(".pdf")) {
      const reader = new FileReader();
      reader.onload = (e) => {
        if (isMounted && e.target?.result) {
          setPdfDataUrl(e.target.result as string);
        }
      };
      reader.readAsDataURL(props.cvFile);
    } else {
      const objectUrl = URL.createObjectURL(props.cvFile);
      if (isMounted) setPdfDataUrl(objectUrl);
    }

    return () => {
      isMounted = false;
    };
  }, [props.cvFile]);

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
    if (step !== subStep) {
      setCompletedSubSteps((prev) => new Set([...prev, subStep]));
    }
    setSubStep(step);
  };

  const currentLabel = cvEditorSubSteps[currentIndex]?.label || "";

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
      {/* Header with SubStepper & Sidebar Toggle */}
      <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
        <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
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

          <div className="flex items-center gap-2">
            {/* Sidebar toggle button to save space in the center */}
            <button
              type="button"
              onClick={() => setIsSidebarOpen(!isSidebarOpen)}
              className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-1.5 text-xs font-semibold hover:bg-muted text-foreground transition shadow-xs"
              title={isSidebarOpen ? "Masquer le volet latéral d'aperçu" : "Afficher le volet latéral d'aperçu"}
            >
              {isSidebarOpen ? (
                <>
                  <PanelRightClose className="h-3.5 w-3.5 text-primary" />
                  <span className="hidden sm:inline">Masquer l&apos;aperçu</span>
                </>
              ) : (
                <>
                  <PanelRightOpen className="h-3.5 w-3.5 text-primary" />
                  <span>Visualiser le CV</span>
                  {props.cvFile && (
                    <span className="ml-1 rounded bg-primary/10 px-1.5 py-0.5 text-[11px] font-bold text-primary">
                      PDF
                    </span>
                  )}
                </>
              )}
            </button>

            <span className="text-[11px] font-mono font-bold text-muted-foreground bg-muted px-2 py-1 rounded-md">
              {progressText}
            </span>
          </div>
        </div>

        <EditorSubStepper
          currentSubStep={subStep}
          onSelectSubStep={handleSelectSubStep}
          completedSubSteps={completedSubSteps}
        />
      </div>

      {/* Main Content: Split-pane layout or Full-width editor */}
      <div className="flex flex-col lg:flex-row gap-6 items-start">
        {/* Form Panel */}
        <div
          className={
            isSidebarOpen
              ? "w-full lg:w-[48%] shrink-0 rounded-2xl border border-border bg-card p-5 sm:p-6 shadow-sm min-h-[400px] transition-all duration-300"
              : "w-full max-w-4xl mx-auto rounded-2xl border border-border bg-card p-5 sm:p-6 shadow-sm min-h-[400px] transition-all duration-300"
          }
        >
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
              <div className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-[#006045] px-4 text-xs font-bold text-white shadow-sm">
                ✓ Section complète
              </div>
            )}
          </div>
        </div>

        {/* Right Sidebar: Multi-tab Preview Panel */}
        <AnimatePresence>
          {isSidebarOpen && (
            <motion.div
              initial={{ opacity: 0, x: 20, width: 0 }}
              animate={{ opacity: 1, x: 0, width: "100%" }}
              exit={{ opacity: 0, x: 20, width: 0 }}
              transition={{ duration: 0.25 }}
              className="w-full lg:w-[52%] flex-1 lg:sticky lg:top-4 lg:self-start space-y-3"
            >
              <div className="rounded-2xl border border-border bg-slate-100/90 dark:bg-slate-900/90 p-3.5 shadow-sm space-y-3 max-h-[760px] overflow-y-auto">
                {/* Sidebar Navigation Tabs */}
                <div className="flex items-center justify-between border-b border-border pb-2 px-1">
                  <div className="flex items-center gap-1.5 bg-slate-200/80 dark:bg-slate-800/80 p-1 rounded-xl">
                    <button
                      type="button"
                      onClick={() => setActivePreviewTab("template")}
                      className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-semibold transition ${activePreviewTab === "template"
                          ? "bg-card text-foreground shadow-xs"
                          : "text-muted-foreground hover:text-foreground"
                        }`}
                    >
                      <FileText className="h-3.5 w-3.5 text-primary" />
                      Aperçu Untaf
                    </button>

                    <button
                      type="button"
                      onClick={() => setActivePreviewTab("original")}
                      className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-semibold transition ${activePreviewTab === "original"
                          ? "bg-card text-foreground shadow-xs"
                          : "text-muted-foreground hover:text-foreground"
                        }`}
                    >
                      <FileCheck className="h-3.5 w-3.5 text-[#006045]" />
                      CV Original
                      {props.cvFile && (
                        <span className="h-2 w-2 rounded-full bg-[#006045] animate-pulse" />
                      )}
                    </button>
                  </div>

                  <button
                    type="button"
                    onClick={() => setIsSidebarOpen(false)}
                    className="text-muted-foreground hover:text-foreground p-1 rounded-lg hover:bg-muted transition"
                    title="Masquer la barre latérale"
                  >
                    <PanelRightClose className="h-4 w-4" />
                  </button>
                </div>

                {/* Tab 1 Content: Live Template Preview */}
                {activePreviewTab === "template" && (
                  <div>

                    <div className="flex items-center justify-between mb-2 px-1">
                      <span className="text-[11px] font-bold text-muted-foreground uppercase tracking-wider">
                        Rendu en temps réel
                      </span>
                      <span className="text-[11px] text-muted-foreground font-mono">
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
                )}

                {/* Tab 2 Content: Original Uploaded PDF CV */}
                {activePreviewTab === "original" && (
                  <div className="space-y-2">
                    {props.cvFile && pdfDataUrl ? (
                      <div>
                        <div className="flex items-center justify-between mb-2 px-1">
                          <span className="text-[11px] font-bold text-muted-foreground uppercase tracking-wider truncate max-w-[200px]">
                            {props.cvFile.name}
                          </span>
                          <a
                            href={pdfDataUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 text-[11px] font-semibold text-primary hover:underline"
                          >
                            <span>Plein écran</span>
                            <ExternalLink className="h-3 w-3" />
                          </a>
                        </div>
                        <div className="w-full h-[620px] rounded-xl overflow-hidden border border-border bg-white shadow-inner">
                          <object
                            data={pdfDataUrl}
                            type="application/pdf"
                            className="w-full h-full border-none"
                          >
                            <iframe
                              src={pdfDataUrl}
                              title="Aperçu CV Original PDF"
                              className="w-full h-full border-none"
                            />
                          </object>
                        </div>
                      </div>
                    ) : (
                      <div className="rounded-xl border border-dashed border-border bg-card p-6 text-center space-y-3 min-h-[300px] flex flex-col items-center justify-center">
                        <div className="h-10 w-10 rounded-full bg-muted flex items-center justify-center text-muted-foreground">
                          <Eye className="h-5 w-5" />
                        </div>
                        <div>
                          <h4 className="text-xs font-bold text-foreground">
                            Aucun fichier CV PDF importé
                          </h4>
                          <p className="text-[11px] text-muted-foreground mt-1 max-w-xs mx-auto">
                            Vous avez choisi la création rapide ou la saisie manuelle.
                            Utilisez l&apos;onglet &quot;Aperçu Untaf&quot; pour voir la mise en page générée.
                          </p>
                        </div>
                        {props.linkedinUrl && (
                          <div className="pt-2">
                            <span className="text-[11px] font-semibold text-primary bg-primary/10 px-3 py-1 rounded-full">
                              Profil LinkedIn : {props.linkedinUrl}
                            </span>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}
