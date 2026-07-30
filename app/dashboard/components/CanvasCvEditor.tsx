"use client";

import { useCallback, useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Check, Download, Eye, Loader2, PenLine, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  cvEditorSubSteps,
  type CvEditorSubStep,
  type EducationEntry,
  type ExperienceEntry,
  type LanguageEntry,
} from "@/app/onboarding/types";
import { PersonalInfoForm } from "@/app/onboarding/components/editor/PersonalInfoForm";
import { ExperiencesForm } from "@/app/onboarding/components/editor/ExperiencesForm";
import { EducationForm } from "@/app/onboarding/components/editor/EducationForm";
import { SkillsForm } from "@/app/onboarding/components/editor/SkillsForm";
import { LanguagesForm } from "@/app/onboarding/components/editor/LanguagesForm";
import { CandidateCvPreview } from "@/app/onboarding/components/CandidateCvPreview";
import {
  downloadCvPdf,
  loadCvProfile,
  saveCvProfile,
  type CvProfile,
} from "@/lib/cv-profile";
import { useAlice } from "../alice-context";

/** Prompts sent straight into the Alice thread, tuned to the open section. */
const ALICE_PROMPTS: Record<CvEditorSubStep, string[]> = {
  personal: [
    "Optimise mon accroche pour les offres que tu m'as trouvées",
    "Réécris mon résumé de profil en plus percutant",
  ],
  experiences: [
    "Reformule mes expériences pour maximiser mon score ATS",
    "Quels résultats chiffrés devrais-je ajouter ?",
  ],
  education: ["Ma formation est-elle bien mise en valeur ?"],
  skills: [
    "Quelles compétences me manquent pour les offres du moment ?",
    "Audite mon CV",
  ],
  languages: ["Mon niveau de langue est-il un frein sur ces offres ?"],
};

type SaveState = "idle" | "saving" | "saved" | "error";

export function CanvasCvEditor({ candidateId }: { candidateId: string | null }) {
  const { submitQuery, sayAsAlice, isThinking } = useAlice();

  const [profile, setProfile] = useState<CvProfile | null>(null);
  const [subStep, setSubStep] = useState<CvEditorSubStep>("personal");
  const [pane, setPane] = useState<"form" | "preview">("form");
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [isExporting, setIsExporting] = useState(false);
  const [isDirty, setIsDirty] = useState(false);

  // Load the real candidate CV — no dummy data.
  useEffect(() => {
    if (!candidateId) return;
    let alive = true;
    loadCvProfile(candidateId).then((p) => {
      if (alive) setProfile(p);
    });
    return () => {
      alive = false;
    };
  }, [candidateId]);

  /** Adapter so the onboarding forms keep their `useState`-shaped setters. */
  const setField = useCallback(
    <K extends keyof CvProfile>(key: K) =>
      (value: CvProfile[K] | ((prev: CvProfile[K]) => CvProfile[K])) => {
        setIsDirty(true);
        setSaveState("idle");
        setProfile((prev) =>
          prev
            ? {
                ...prev,
                [key]:
                  typeof value === "function"
                    ? (value as (p: CvProfile[K]) => CvProfile[K])(prev[key])
                    : value,
              }
            : prev,
        );
      },
    [],
  );

  const handleSave = async () => {
    if (!profile || !candidateId) return;
    setSaveState("saving");
    const ok = await saveCvProfile(candidateId, profile);
    setSaveState(ok ? "saved" : "error");
    setIsDirty(false);

    // The edit lands in the conversation, not just in the panel.
    sayAsAlice(
      ok
        ? `C'est enregistré. Ton CV compte ${profile.experiences.length} expérience${profile.experiences.length > 1 ? "s" : ""} et ${profile.skills.length} compétence${profile.skills.length > 1 ? "s" : ""} — je le réutilise dès le prochain matching.`
        : "Je n'ai pas pu enregistrer côté serveur, j'ai gardé tes modifications en local. Réessaie dans un instant.",
      { mode: "cv_editor" },
    );
  };

  const handleExport = async () => {
    if (!profile) return;
    setIsExporting(true);
    try {
      await downloadCvPdf(profile);
      sayAsAlice("Ton CV est généré en PDF, le téléchargement est parti.");
    } catch {
      sayAsAlice("La compilation du PDF a échoué. Vérifie que le moteur cv-engine tourne.");
    } finally {
      setIsExporting(false);
    }
  };

  const askAlice = (question: string) => {
    void submitQuery(question);
  };

  if (!candidateId) {
    return (
      <div className="h-full flex items-center justify-center px-8 text-center">
        <p className="text-sm font-light text-[#1A1918]/50 tracking-tight">
          Je ne trouve pas ton profil. Reconnecte-toi pour éditer ton CV.
        </p>
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="h-full flex flex-col items-center justify-center gap-2.5">
        <Loader2 className="w-5 h-5 animate-spin text-[#006045]" />
        <p className="text-xs font-light text-[#1A1918]/50 tracking-tight">
          Je charge ton CV…
        </p>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col min-h-0">
      {/* ── Bascule Formulaire / Aperçu ── */}
      <div className="shrink-0 px-5 pt-4 pb-3 space-y-3 border-b border-[#1A1918]/8">
        <div className="flex items-center gap-1 p-0.5 rounded-full bg-[#1A1918]/4 w-fit">
          {(
            [
              { id: "form", label: "Éditer", icon: PenLine },
              { id: "preview", label: "Aperçu", icon: Eye },
            ] as const
          ).map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              type="button"
              onClick={() => setPane(id)}
              className={cn(
                "flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-light tracking-tight transition-colors cursor-pointer",
                pane === id
                  ? "bg-white text-[#1A1918] shadow-sm"
                  : "text-[#1A1918]/50 hover:text-[#1A1918]",
              )}
            >
              <Icon className="w-3.5 h-3.5 stroke-[1.5]" />
              {label}
            </button>
          ))}
        </div>

        {pane === "form" && (
          <div className="flex items-center gap-1.5 overflow-x-auto -mx-1 px-1 pb-0.5">
            {cvEditorSubSteps.map((step) => (
              <button
                key={step.id}
                type="button"
                onClick={() => setSubStep(step.id)}
                className={cn(
                  "shrink-0 px-3 py-1.5 rounded-full text-[11px] font-light tracking-tight transition-colors cursor-pointer border",
                  subStep === step.id
                    ? "border-[#006045]/40 text-[#006045] bg-[#006045]/6"
                    : "border-[#1A1918]/10 text-[#1A1918]/50 hover:text-[#1A1918] hover:border-[#1A1918]/25",
                )}
              >
                {step.shortLabel}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* ── Corps défilant ── */}
      <div className="scroll-discreet flex-1 min-h-0 overflow-y-auto px-5 py-5">
        {pane === "preview" ? (
          <div className="mx-auto w-full max-w-md">
            <CandidateCvPreview
              fluid
              fullName={profile.fullName}
              headline={profile.headline}
              summary={profile.summary}
              email={profile.email}
              linkedinUrl={profile.linkedinUrl}
              skills={profile.skills}
              experienceYears={profile.experienceYears}
              templateId={profile.templateId}
              selectedColorHex={profile.colorHex}
              showPhoto={profile.showPhotoOnCv}
              userPhotoUrl={profile.photoUrl}
              experiences={profile.experiences}
              education={profile.education}
              languages={profile.languages}
              phone={profile.phone}
            />
          </div>
        ) : (
          <motion.div
            key={subStep}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.18 }}
          >
            {subStep === "personal" && (
              <PersonalInfoForm
                fullName={profile.fullName}
                setFullName={setField("fullName")}
                email={profile.email}
                setEmail={setField("email")}
                phone={profile.phone}
                setPhone={setField("phone")}
                linkedinUrl={profile.linkedinUrl}
                setLinkedinUrl={setField("linkedinUrl")}
                headline={profile.headline}
                setHeadline={setField("headline")}
                summary={profile.summary}
                setSummary={setField("summary")}
                userPhotoUrl={profile.photoUrl}
                handlePhotoUpload={(e) => {
                  const file = e.target.files?.[0];
                  if (!file) return;
                  const reader = new FileReader();
                  reader.onload = (ev) =>
                    setField("photoUrl")((ev.target?.result as string) ?? null);
                  reader.readAsDataURL(file);
                }}
                showPhotoOnCv={profile.showPhotoOnCv}
                setShowPhotoOnCv={setField("showPhotoOnCv")}
                atsAudit={null}
              />
            )}
            {subStep === "experiences" && (
              <ExperiencesForm
                experiences={profile.experiences}
                setExperiences={
                  setField("experiences") as React.Dispatch<
                    React.SetStateAction<ExperienceEntry[]>
                  >
                }
              />
            )}
            {subStep === "education" && (
              <EducationForm
                education={profile.education}
                setEducation={
                  setField("education") as React.Dispatch<
                    React.SetStateAction<EducationEntry[]>
                  >
                }
              />
            )}
            {subStep === "skills" && (
              <SkillsForm
                skills={profile.skills}
                setSkills={
                  setField("skills") as React.Dispatch<React.SetStateAction<string[]>>
                }
                atsAudit={null}
              />
            )}
            {subStep === "languages" && (
              <LanguagesForm
                languages={profile.languages}
                setLanguages={
                  setField("languages") as React.Dispatch<
                    React.SetStateAction<LanguageEntry[]>
                  >
                }
              />
            )}
          </motion.div>
        )}
      </div>

      {/* ── Relais vers la conversation ── */}
      <div className="shrink-0 border-t border-[#1A1918]/8 bg-[#FAFAF8]">
        <div className="px-5 py-3 space-y-2">
          <div className="flex items-center gap-1.5">
            <Sparkles className="w-3 h-3 stroke-[1.6] text-[#006045] shrink-0" />
            <span className="text-[10px] font-mono uppercase tracking-wider text-[#1A1918]/40">
              Demander à Alice
            </span>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {ALICE_PROMPTS[subStep].map((q) => (
              <button
                key={q}
                type="button"
                onClick={() => askAlice(q)}
                disabled={isThinking}
                className="px-2.5 py-1.5 rounded-full border border-[#1A1918]/10 bg-white text-[11px] font-light text-[#1A1918]/65 tracking-tight hover:border-[#006045]/40 hover:text-[#006045] transition-colors cursor-pointer disabled:opacity-40"
              >
                {q}
              </button>
            ))}
          </div>
        </div>

        <div className="px-5 py-3 flex items-center justify-between gap-3 border-t border-[#1A1918]/6">
          <button
            type="button"
            onClick={handleExport}
            disabled={isExporting}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-full border border-[#1A1918]/15 hover:border-[#1A1918]/35 text-xs font-light text-[#1A1918] tracking-tight transition-colors cursor-pointer disabled:opacity-40"
          >
            {isExporting ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Download className="w-3.5 h-3.5 stroke-[1.5]" />
            )}
            PDF
          </button>

          <div className="flex items-center gap-2.5">
            <span className="text-[11px] font-light tracking-tight text-[#1A1918]/40">
              {saveState === "saved" && !isDirty
                ? "Enregistré"
                : saveState === "error"
                  ? "Sauvegarde locale seulement"
                  : isDirty
                    ? "Modifications non enregistrées"
                    : ""}
            </span>
            <button
              type="button"
              onClick={handleSave}
              disabled={saveState === "saving" || !isDirty}
              className="flex items-center gap-1.5 px-4 py-2 rounded-full bg-[#006045] text-white text-xs font-light tracking-tight hover:bg-[#004d37] transition-colors cursor-pointer disabled:opacity-30"
            >
              {saveState === "saving" ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Check className="w-3.5 h-3.5 stroke-[2]" />
              )}
              Enregistrer
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
