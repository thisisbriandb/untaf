"use client";

import { useCallback, useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Check, Download, FileText, Loader2, Palette, PenLine, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  colorSwatches,
  cvEditorSubSteps,
  cvTemplates,
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
  fetchCvDesign,
  loadCvProfile,
  resumeUrl,
  saveCvDesign,
  saveCvProfile,
  writeCvContent,
  type CvDesign,
  type CvProfile,
} from "@/lib/cv-profile";
import { useAlice } from "../alice-context";
import { openFile } from "@/lib/api";
import { useProtectedBlobUrl } from "./ProtectedFile";

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

/**
 * Volet mise en page.
 *
 * Trois principes tenus ici :
 *   - garder le CV d'origine est un choix de plein droit, pas un repli ;
 *   - aucun modèle n'est actif tant que le candidat n'en a pas désigné un ;
 *   - modèle et couleur sont indépendants — désigner un modèle n'impose pas
 *     sa palette, changer de couleur ne change pas de modèle.
 */
function CvDesignPane({
  design,
  profile,
  onChange,
}: {
  design: CvDesign | null;
  profile: CvProfile;
  onChange: (patch: Partial<Pick<CvDesign, "mode" | "template_id" | "color_hex" | "show_photo">>) => void;
}) {
  const mode = design?.mode ?? "template";
  const templateId = design?.template_id;
  const colorHex = design?.color_hex;

  return (
    <div className="space-y-7">
      {design?.has_original && (
        <div className="space-y-2.5">
          <p className="text-xs text-[#1A1918]/55 uppercase tracking-wider font-medium">
            Présentation
          </p>
          <div className="border-t border-b border-[#1A1918]/10 divide-y divide-[#1A1918]/8">
            {(
              [
                {
                  id: "original" as const,
                  label: "Garder mon CV d'origine",
                  detail: "Ton document tel quel. Tu peux modifier le contenu sans toucher à la mise en page.",
                },
                {
                  id: "template" as const,
                  label: "Utiliser un modèle",
                  detail: "Une mise en page générée à partir de ton contenu.",
                },
              ]
            ).map((opt) => (
              <button
                key={opt.id}
                type="button"
                onClick={() => onChange({ mode: opt.id })}
                className="w-full py-3.5 flex items-start gap-3 text-left cursor-pointer group"
              >
                <span
                  className={cn(
                    "mt-0.5 w-3.5 shrink-0 text-center text-sm transition-colors",
                    mode === opt.id ? "text-[#006045]" : "text-[#1A1918]/20",
                  )}
                >
                  {mode === opt.id ? "✓" : "—"}
                </span>
                <span className="min-w-0">
                  <span
                    className={cn(
                      "block text-sm tracking-tight transition-colors",
                      mode === opt.id
                        ? "text-[#1A1918]"
                        : "text-[#1A1918]/60 group-hover:text-[#1A1918]/70",
                    )}
                  >
                    {opt.label}
                  </span>
                  <span className="block text-xs font-normal text-[#1A1918]/55 tracking-tight mt-0.5">
                    {opt.detail}
                  </span>
                </span>
              </button>
            ))}
          </div>
        </div>
      )}

      {mode === "template" && (
        <>
          <div className="space-y-2.5">
            <div className="flex items-baseline justify-between gap-3">
              <p className="text-xs text-[#1A1918]/55 uppercase tracking-wider font-medium">
                Modèle
              </p>
              {!templateId && (
                <span className="text-[11px] font-normal text-[#1A1918]/50">
                  aucun choisi
                </span>
              )}
            </div>
            <div className="grid grid-cols-2 gap-2">
              {cvTemplates.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => onChange({ template_id: t.id })}
                  className={cn(
                    "px-3 py-2.5 rounded-xl border text-left transition-colors cursor-pointer",
                    templateId === t.id
                      ? "border-[#006045]/45 bg-[#006045]/6"
                      : "border-[#1A1918]/10 hover:border-[#1A1918]/28",
                  )}
                >
                  <span
                    className={cn(
                      "block text-xs tracking-tight",
                      templateId === t.id ? "text-[#006045]" : "text-[#1A1918]/75",
                    )}
                  >
                    {t.name}
                  </span>
                  <span className="block text-[11px] font-normal text-[#1A1918]/55 tracking-tight mt-0.5">
                    {t.tagline}
                  </span>
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-2.5">
            <p className="text-xs text-[#1A1918]/55 uppercase tracking-wider font-medium">
              Couleur
            </p>
            <div className="flex flex-wrap gap-2">
              {colorSwatches.map((sw) => (
                <button
                  key={sw.id}
                  type="button"
                  onClick={() => onChange({ color_hex: sw.hex })}
                  title={sw.name}
                  aria-label={sw.name}
                  className={cn(
                    "h-8 w-8 rounded-full transition-all cursor-pointer ring-offset-2",
                    colorHex === sw.hex
                      ? "ring-2 ring-[#1A1918]/40 scale-105"
                      : "ring-1 ring-[#1A1918]/10 hover:scale-105",
                  )}
                  style={{ backgroundColor: sw.hex }}
                />
              ))}
            </div>
          </div>

          <label className="flex items-center gap-2.5 cursor-pointer">
            <input
              type="checkbox"
              checked={design?.show_photo ?? false}
              onChange={(e) => onChange({ show_photo: e.target.checked })}
              className="accent-[#006045] h-3.5 w-3.5 cursor-pointer"
            />
            <span className="text-xs font-normal text-[#1A1918]/65 tracking-tight">
              Afficher ma photo
            </span>
          </label>

          {templateId ? (
            <div className="pt-1 space-y-2">
              <p className="text-xs text-[#1A1918]/55 uppercase tracking-wider font-medium">
                Aperçu
              </p>
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
                  templateId={templateId}
                  selectedColorHex={colorHex || "#234C6A"}
                  showPhoto={design?.show_photo ?? false}
                  userPhotoUrl={profile.photoUrl}
                  experiences={profile.experiences}
                  education={profile.education}
                  languages={profile.languages}
                  phone={profile.phone}
                />
              </div>
            </div>
          ) : (
            <p className="text-xs font-normal text-[#1A1918]/55 tracking-tight">
              Choisis un modèle pour voir le rendu. Rien n&apos;est appliqué tant
              que tu n&apos;as rien désigné.
            </p>
          )}
        </>
      )}
    </div>
  );
}

/** Onglet ouvert. « original » n'existe que si un CV a été déposé. */
type Pane = "original" | "content" | "design";

export function CanvasCvEditor({
  candidateId,
  initialPane,
}: {
  candidateId: string | null;
  /** Ouvre directement sur les modèles, par exemple après une adaptation. */
  initialPane?: Pane;
}) {
  const { submitQuery, sayAsAlice, isThinking } = useAlice();

  const [profile, setProfile] = useState<CvProfile | null>(null);
  const [design, setDesign] = useState<CvDesign | null>(null);
  const [subStep, setSubStep] = useState<CvEditorSubStep>("personal");
  const [pane, setPane] = useState<Pane>(initialPane ?? "content");
  // Le PDF d'origine est protégé : récupéré avec le jeton, affiché en local.
  const originalPdf = useProtectedBlobUrl(
    pane === "original" && candidateId ? resumeUrl(candidateId) : null,
  );
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [isExporting, setIsExporting] = useState(false);
  const [isDirty, setIsDirty] = useState(false);
  const [isWriting, setIsWriting] = useState(false);
  /** Ce qui distingue le candidat, tel qu'Alice l'a relevé dans son parcours. */
  const [differentiators, setDifferentiators] = useState<string[]>([]);

  // Load the real candidate CV — no dummy data.
  useEffect(() => {
    if (!candidateId) return;
    let alive = true;

    Promise.all([loadCvProfile(candidateId), fetchCvDesign(candidateId)]).then(
      ([p, d]) => {
        if (!alive) return;
        setProfile(p);
        setDesign(d);
        // Le CV déposé s'ouvre en premier tant qu'aucun modèle n'a été demandé.
        // Sauf si l'on a été ouvert exprès sur un autre volet (les modèles).
        if (!initialPane && d?.has_original && d.mode === "original") setPane("original");
      },
    );

    return () => {
      alive = false;
    };
  }, [candidateId, initialPane]);

  /** Un changement de présentation est toujours un geste explicite. */
  const updateDesign = useCallback(
    async (patch: Partial<Pick<CvDesign, "mode" | "template_id" | "color_hex" | "show_photo">>) => {
      if (!candidateId) return;
      setDesign((prev) => (prev ? { ...prev, ...patch, is_explicit: true } : prev));
      const saved = await saveCvDesign(candidateId, patch);
      if (saved) setDesign(saved);
    },
    [candidateId],
  );

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

  /**
   * En mode « original », on rend le document déposé — pas une version
   * regénérée. Exporter un modèle à quelqu'un qui a demandé à garder son CV
   * serait précisément l'imposition qu'on cherche à éviter.
   */
  const handleExport = async () => {
    if (!profile) return;

    if (design?.mode === "original" && design.has_original && candidateId) {
      void openFile(resumeUrl(candidateId));
      sayAsAlice("Je t'ai rouvert ton CV d'origine, tel que tu me l'as donné.");
      return;
    }

    setIsExporting(true);
    try {
      await downloadCvPdf({
        ...profile,
        // La mise en page fait foi côté serveur, pas la copie locale.
        templateId: design?.template_id || profile.templateId,
        colorHex: design?.color_hex || profile.colorHex,
        showPhotoOnCv: design?.show_photo ?? profile.showPhotoOnCv,
      });
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

  /**
   * Alice reprend l'accroche et la synthèse.
   *
   * Elle ne peut rien écrire de spécifique sans expériences : plutôt que de
   * livrer du passe-partout, on le dit et on renvoie vers la bonne section.
   */
  const handleWriteContent = async () => {
    if (!profile) return;

    if (!profile.experiences.length) {
      sayAsAlice(
        "Je n'ai aucune expérience dans ton CV — je ne peux écrire que du " +
        "générique avec ça. Ajoute tes postes et je m'en occupe.",
        { mode: "cv_editor" },
      );
      setSubStep("experiences");
      return;
    }

    setIsWriting(true);
    const content = await writeCvContent(profile);
    setIsWriting(false);

    if (!content) {
      sayAsAlice("Je n'ai pas réussi à rédiger. Réessaie dans un instant.");
      return;
    }

    setProfile((prev) =>
      prev ? { ...prev, headline: content.headline, summary: content.summary } : prev,
    );
    setIsDirty(true);
    setSaveState("idle");
    setDifferentiators(content.differentiators);

    sayAsAlice(
      content.source === "fallback"
        ? "J'ai assemblé les faits de ton parcours, mais je n'ai pas pu rédiger finement. Relis avant d'enregistrer."
        : `J'ai repris ton accroche et ta synthèse à partir de tes ${profile.experiences.length} expériences. Relis et enregistre.`,
      { mode: "cv_editor" },
    );
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
        <p className="text-xs font-normal text-[#1A1918]/50 tracking-tight">
          Je charge ton CV…
        </p>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col min-h-0">
      {/* ── Onglets : le CV d'origine, le contenu, la mise en page ── */}
      <div className="shrink-0 px-5 pt-4 pb-3 space-y-3 border-b border-[#1A1918]/8">
        <div className="flex items-center gap-1 p-0.5 rounded-full bg-[#1A1918]/4 w-fit">
          {(
            [
              ...(design?.has_original
                ? [{ id: "original" as const, label: "Mon CV", icon: FileText }]
                : []),
              { id: "content" as const, label: "Contenu", icon: PenLine },
              { id: "design" as const, label: "Mise en page", icon: Palette },
            ]
          ).map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              type="button"
              onClick={() => setPane(id)}
              className={cn(
                "flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-normal tracking-tight transition-colors cursor-pointer",
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

        {pane === "content" && (
          <div className="flex items-center gap-1.5 overflow-x-auto -mx-1 px-1 pb-0.5">
            {cvEditorSubSteps.map((step) => (
              <button
                key={step.id}
                type="button"
                onClick={() => setSubStep(step.id)}
                className={cn(
                  "shrink-0 px-3 py-1.5 rounded-full text-[11px] font-normal tracking-tight transition-colors cursor-pointer border",
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
        {pane === "original" && candidateId ? (
          /* Le document tel qu'il a été déposé — aucune mise en page appliquée. */
          <div className="h-full flex flex-col gap-3">
            <p className="text-[11px] font-normal text-[#1A1918]/60 tracking-tight shrink-0">
              {design?.original_filename} — ton document d&apos;origine, inchangé.
            </p>
            <object
              data={originalPdf ?? undefined}
              type="application/pdf"
              className="w-full flex-1 min-h-[28rem] rounded-xl border border-[#1A1918]/10 bg-white"
            >
              <div className="p-6 text-center space-y-3">
                <p className="text-sm font-light text-[#1A1918]/55 tracking-tight">
                  Ton navigateur n&apos;affiche pas les PDF ici.
                </p>
                <button
                  type="button"
                  onClick={() => void openFile(resumeUrl(candidateId))}
                  className="inline-block text-xs text-[#006045] hover:underline cursor-pointer"
                >
                  Ouvrir dans un onglet
                </button>
              </div>
            </object>
          </div>
        ) : pane === "design" ? (
          <CvDesignPane
            design={design}
            profile={profile}
            onChange={updateDesign}
          />
        ) : (
          <motion.div
            key={subStep}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.18 }}
          >
            {subStep === "personal" && (
              <div className="space-y-4">
                {/* Alice rédige à partir du parcours, pas à partir du vide. */}
                <div className="flex items-center justify-between gap-3 pb-3 border-b border-[#1A1918]/8">
                  <p className="text-xs font-normal text-[#1A1918]/50 tracking-tight">
                    Accroche et synthèse, écrites depuis tes expériences.
                  </p>
                  <button
                    type="button"
                    onClick={handleWriteContent}
                    disabled={isWriting}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-[#006045]/35 text-[#006045] text-xs font-normal tracking-tight hover:bg-[#006045]/6 transition-colors cursor-pointer disabled:opacity-40 shrink-0"
                  >
                    {isWriting ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Sparkles className="w-3.5 h-3.5 stroke-[1.6]" />
                    )}
                    {isWriting ? "Je rédige…" : "Alice s'en occupe"}
                  </button>
                </div>

                {differentiators.length > 0 && (
                  <div className="space-y-1.5 p-3.5 rounded-xl bg-[#006045]/5">
                    <p className="text-[11px] font-mono uppercase tracking-wider text-[#006045]/70">
                      Ce qui te distingue
                    </p>
                    {differentiators.map((d, i) => (
                      <p
                        key={i}
                        className="text-xs font-normal text-[#1A1918]/70 tracking-tight leading-relaxed"
                      >
                        — {d}
                      </p>
                    ))}
                  </div>
                )}

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
              </div>
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
            <span className="text-[11px] font-mono uppercase tracking-wider text-[#1A1918]/55">
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
                className="px-2.5 py-1.5 rounded-full border border-[#1A1918]/10 bg-white text-[11px] font-normal text-[#1A1918]/65 tracking-tight hover:border-[#006045]/40 hover:text-[#006045] transition-colors cursor-pointer disabled:opacity-40"
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
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-full border border-[#1A1918]/15 hover:border-[#1A1918]/35 text-xs font-normal text-[#1A1918] tracking-tight transition-colors cursor-pointer disabled:opacity-40"
          >
            {isExporting ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Download className="w-3.5 h-3.5 stroke-[1.5]" />
            )}
            PDF
          </button>

          <div className="flex items-center gap-2.5">
            <span className="text-[11px] font-normal tracking-tight text-[#1A1918]/55">
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
              className="flex items-center gap-1.5 px-4 py-2 rounded-full bg-[#006045] text-white text-xs font-normal tracking-tight hover:bg-[#004d37] transition-colors cursor-pointer disabled:opacity-30"
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
