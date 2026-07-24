"use client";

import { useState, useEffect, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { AnimatePresence } from "framer-motion";
import { Loader2, AlertCircle, CheckCircle2, X } from "lucide-react";

import { CVAuditData, colorSwatches, ExperienceEntry, EducationEntry, LanguageEntry } from "./types";
import { StepperHeader } from "./components/StepperHeader";
import { WelcomeChoiceStep } from "./components/WelcomeChoiceStep";
import { Step1ImportDiagnostic } from "./components/Step1ImportDiagnostic";
import { Step2CvEditor } from "./components/Step2CvEditor";
import { Step3DesignStudio } from "./components/Step3DesignStudio";
import { Step4MatchingPreferences } from "./components/Step4MatchingPreferences";
import { MatchingScreen } from "./components/MatchingScreen";
import { NavigationBar } from "./components/NavigationBar";

function OnboardingForm() {
  const router = useRouter();
  const searchParams = useSearchParams();

  // Choice state: null (Welcome screen), "studio" (full refonte studio flow), "bypass" (direct matching with current CV)
  const [userFlowChoice, setUserFlowChoice] = useState<"studio" | "bypass" | null>(null);

  // Step tracker (1: Import, 2: Éditeur CV, 3: Studio Design Typst, 4: Matching & Export)
  const [step, setStep] = useState(1);

  // Candidate identity
  const [fullName, setFullName] = useState("evelinbrid");
  const [email, setEmail] = useState("evelinbrid@gmail.com");
  const [phone, setPhone] = useState("");
  const [userPhotoUrl, setUserPhotoUrl] = useState<string | null>(null);
  const [showPhotoOnCv, setShowPhotoOnCv] = useState(true);

  // Step 1: CV Import & LinkedIn
  const [linkedinUrl, setLinkedinUrl] = useState("");
  const [cvFile, setCvFile] = useState<File | null>(null);
  const [dragActive, setDragActive] = useState(false);

  // Quick Builder
  const [showQuickBuilder, setShowQuickBuilder] = useState(false);
  const [quickRole, setQuickRole] = useState("");
  const [quickCompany, setQuickCompany] = useState("");
  const [quickSkillsInput, setQuickSkillsInput] = useState("");

  // Step 2: CV Editor structured data
  const [headline, setHeadline] = useState("Ingénieur Full-Stack");
  const [summary, setSummary] = useState("");
  const [experiences, setExperiences] = useState<ExperienceEntry[]>([]);
  const [education, setEducation] = useState<EducationEntry[]>([]);
  const [languages, setLanguages] = useState<LanguageEntry[]>([
    { id: "fr", language: "Français", level: "Langue maternelle" },
    { id: "en", language: "Anglais", level: "Professionnel (B2)" },
  ]);

  // Step 2 & 3: Audit & Design Selection
  const [atsAudit, setAtsAudit] = useState<CVAuditData | null>(null);
  const [selectedTemplate, setSelectedTemplate] = useState("minimalist");
  const [selectedColor, setSelectedColor] = useState("indigo");
  const [cvLanguage, setCvLanguage] = useState<"fr" | "en">("fr");
  const [, setIsAuditing] = useState(false);

  // Step 4 Preferences
  const [contractTypes, setContractTypes] = useState<string[]>(["cdi"]);
  const [remotePolicies, setRemotePolicies] = useState<string[]>(["hybrid"]);
  const [locations, setLocations] = useState<string[]>(["Paris"]);
  const [locationInput, setLocationInput] = useState("");
  const [experienceYears, setExperienceYears] = useState(3);
  const [skills, setSkills] = useState<string[]>(["TypeScript", "React", "Node.js", "Python"]);
  const [skillInput, setSkillInput] = useState("");

  // Parsing State
  const [isParsingCv, setIsParsingCv] = useState(false);
  const [autoFilledBanner, setAutoFilledBanner] = useState<string | null>(null);

  // Submission State
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [matchingProgress, setMatchingProgress] = useState(0);
  const [matchingStatus, setMatchingStatus] = useState("");
  const [errorMsg, setErrorMsg] = useState("");

  const activeColorSwatch = colorSwatches.find((c) => c.id === selectedColor) || colorSwatches[0];

  // Prefill params
  useEffect(() => {
    const emailParam = searchParams.get("email");
    if (emailParam) setEmail(emailParam);
    const nameParam = searchParams.get("name");
    if (nameParam) setFullName(nameParam);
  }, [searchParams]);

  // Trigger ATS Audit API (Gemini Flash)
  const triggerAtsAudit = async (profilePayload: any) => {
    setIsAuditing(true);
    try {
      const res = await fetch("http://localhost:8010/api/candidates/audit-cv", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(profilePayload),
      });

      if (res.ok) {
        const audit = await res.json();
        setAtsAudit(audit);
        if (audit.optimized_headline) setHeadline(audit.optimized_headline);
        if (audit.optimized_summary) setSummary(audit.optimized_summary);
        if (audit.suggested_skills && audit.suggested_skills.length > 0) {
          setSkills((prev) => Array.from(new Set([...prev, ...audit.suggested_skills])));
        }
      }
    } catch (err) {
      console.error("Erreur lors de l'analyse du profil:", err);
    } finally {
      setIsAuditing(false);
    }
  };

  // Extract CV API
  const extractCvData = async (file: File) => {
    setIsParsingCv(true);
    setAutoFilledBanner(null);
    try {
      const formData = new FormData();
      formData.append("file", file);

      const res = await fetch("http://localhost:8010/api/candidates/parse-resume", {
        method: "POST",
        body: formData,
      });

      if (res.ok) {
        const data = await res.json();
        if (data.full_name) setFullName(data.full_name);
        if (data.email) setEmail(data.email);
        if (data.linkedin_url) setLinkedinUrl(data.linkedin_url);
        if (data.headline) setHeadline(data.headline);
        if (data.phone) setPhone(data.phone);
        if (data.skills && data.skills.length > 0) {
          setSkills((prev) => Array.from(new Set([...prev, ...data.skills])));
        }
        if (data.experience_years !== null && data.experience_years !== undefined) {
          setExperienceYears(Math.min(15, Math.max(0, Math.round(data.experience_years))));
        }

        setAutoFilledBanner(
          "Profil extrait automatiquement. Votre nom, contact, profil LinkedIn et compétences ont été identifiés."
        );

      }
    } catch (err) {
      console.error("Erreur d'extraction CV:", err);
    } finally {
      setIsParsingCv(false);
    }
  };

  const processCvFile = (file: File) => {
    if (file.type === "application/pdf" || file.name.endsWith(".pdf")) {
      setCvFile(file);
      extractCvData(file);
    } else {
      alert("Seuls les fichiers PDF sont acceptés.");
    }
  };

  // Photo upload simulator/handler
  const handlePhotoUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      const url = URL.createObjectURL(file);
      setUserPhotoUrl(url);
    }
  };

  // Drag & drop
  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      processCvFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      processCvFile(e.target.files[0]);
    }
  };

  // Quick Builder
  const handleQuickBuilderSubmit = () => {
    const extractedSkills = quickSkillsInput
      .split(",")
      .map((s) => s.trim())
      .filter((s) => s.length > 0);

    if (extractedSkills.length > 0) {
      setSkills((prev) => Array.from(new Set([...prev, ...extractedSkills])));
    }

    const payload = {
      full_name: fullName || "evelinbrid",
      email: email || "evelinbrid@gmail.com",
      headline: quickRole || "Développeur Full-Stack",
      skills: extractedSkills.length > 0 ? extractedSkills : ["React", "Python"],
      experience_years: experienceYears,
      preferred_locations: locations.length > 0 ? locations : ["Paris"],
    };

    triggerAtsAudit(payload);
    setStep(2);
  };

  // Tag handlers
  const addLocation = () => {
    if (locationInput.trim() && !locations.includes(locationInput.trim())) {
      setLocations([...locations, locationInput.trim()]);
      setLocationInput("");
    }
  };

  const removeLocation = (loc: string) => {
    setLocations(locations.filter((l) => l !== loc));
  };

  const removeSkill = (skill: string) => {
    setSkills(skills.filter((s) => s !== skill));
  };

  const toggleContractType = (val: string) => {
    if (contractTypes.includes(val)) {
      setContractTypes(contractTypes.filter((c) => c !== val));
    } else {
      setContractTypes([...contractTypes, val]);
    }
  };

  const toggleRemotePolicy = (val: string) => {
    if (remotePolicies.includes(val)) {
      setRemotePolicies(remotePolicies.filter((r) => r !== val));
    } else {
      setRemotePolicies([...remotePolicies, val]);
    }
  };

  // Step validations
  const validateStep1 = () => {
    return !isParsingCv && (cvFile !== null || linkedinUrl.trim().startsWith("http") || showQuickBuilder);
  };

  const validateStep2 = () => headline.trim().length > 2;
  const validateStep3 = () => true;

  const validateStep4 = () => {
    return contractTypes.length > 0 && remotePolicies.length > 0 && skills.length > 0;
  };

  const buildAuditPayload = () => ({
    full_name: fullName || "evelinbrid",
    email: email || "evelinbrid@gmail.com",
    linkedin_url: linkedinUrl || null,
    headline: headline || "Développeur Full-Stack",
    skills: skills.length > 0 ? skills : ["React", "Python"],
    experience_years: experienceYears,
    preferred_locations: locations.length > 0 ? locations : ["Paris"],
    resume_raw: cvFile
      ? `Fichier importé : ${cvFile.name} (${(cvFile.size / 1024).toFixed(1)} KB)`
      : null,
  });

  const handleNext = () => {
    if (step === 1) {
      triggerAtsAudit(buildAuditPayload());
    }

    setStep(step + 1);
  };

  // Submit flow
  const handleSubmit = async () => {
    if (!validateStep4()) return;

    setIsSubmitting(true);
    setErrorMsg("");

    const interval = setInterval(() => {
      setMatchingProgress((prev) => {
        const next = prev + 1;
        if (next < 35) {
          setMatchingStatus("Génération du CV final via cv-engine (Typst)...");
        } else if (next < 70) {
          setMatchingStatus("Analyse des offres d'emploi cachées et calcul des scores d'adéquation...");
        } else if (next < 99) {
          setMatchingStatus("Préparation de votre tableau de bord de candidats...");
        }
        if (next >= 99) {
          clearInterval(interval);
          return 99;
        }
        return next;
      });
    }, 25);

    try {
      const payload = {
        full_name: fullName,
        email: email,
        phone: phone || null,
        github_url: null,
        linkedin_url: linkedinUrl || null,
        website_url: null,
        headline: headline || "Ingénieur Full-Stack",
        skills: skills,
        experience_years: experienceYears,
        preferred_locations: locations.length > 0 ? locations : ["Paris"],
        preferred_remote_policies: remotePolicies,
        preferred_contract_types: contractTypes,
        resume_raw: cvFile
          ? `Fichier importé : ${cvFile.name} (${(cvFile.size / 1024).toFixed(1)} KB)`
          : `Profil optimisé via Untaf Studio`,
      };

      const response = await fetch("http://localhost:8010/api/candidates/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      if (response.ok) {
        const candidate = await response.json();
        localStorage.setItem("candidate_id", candidate.id);

        setMatchingProgress(100);
        setMatchingStatus("Validation réussie ! Redirection vers le tableau de bord...");
        setTimeout(() => {
          router.push("/dashboard");
        }, 800);
      } else if (response.status === 409) {
        const listResponse = await fetch("http://localhost:8010/api/candidates/");
        if (listResponse.ok) {
          const list = await listResponse.json();
          const existing = list.find((c: any) => c.email.toLowerCase() === email.toLowerCase());
          if (existing) {
            localStorage.setItem("candidate_id", existing.id);
            setMatchingProgress(100);
            setMatchingStatus("Profil identifié. Chargement du tableau de bord...");
            setTimeout(() => {
              router.push("/dashboard");
            }, 800);
            return;
          }
        }
        throw new Error("L'adresse email est déjà enregistrée.");
      } else {
        const err = await response.json();
        throw new Error(err.detail || "Une erreur est survenue lors de l'enregistrement.");
      }
    } catch (e: any) {
      clearInterval(interval);
      setIsSubmitting(false);
      setMatchingProgress(0);
      setErrorMsg(e.message || "Impossible de joindre le serveur. Veuillez réessayer.");
    }
  };

  return (
    <div className="min-h-screen w-full bg-slate-50 dark:bg-slate-950 py-10 px-4 sm:px-6 lg:px-8 text-foreground">
      <div className={step === 2 && userFlowChoice !== null && !isSubmitting ? "max-w-7xl mx-auto space-y-8" : "max-w-5xl mx-auto space-y-8"}>
        {/* Header Component */}
        <StepperHeader
          fullName={fullName}
          email={email}
          step={step}
          userFlowChoice={userFlowChoice}
          isSubmitting={isSubmitting}
          onSelectStep={(s) => setStep(s)}
        />

        {/* STEP 0: WELCOME SCREEN */}
        {userFlowChoice === null && (
          <WelcomeChoiceStep
            onSelectStudio={() => setUserFlowChoice("studio")}
            onSelectBypass={() => {
              setUserFlowChoice("bypass");
              setStep(4);
            }}
          />
        )}

        {/* Error Alert Box */}
        {errorMsg && (
          <div className="flex gap-2 rounded-xl bg-destructive/10 p-4 text-sm text-destructive">
            <AlertCircle className="h-5 w-5 shrink-0" />
            <p className="font-medium">{errorMsg}</p>
          </div>
        )}

        {/* Auto-filled Success Alert Box */}
        {autoFilledBanner && (
          <div className="flex items-start justify-between gap-2 rounded-xl bg-card border border-border p-3.5 text-xs font-medium text-foreground shadow-sm">
            <div className="flex gap-2 items-center">
              <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-500" />
              <p>{autoFilledBanner}</p>
            </div>
            <button
              type="button"
              onClick={() => setAutoFilledBanner(null)}
              className="text-muted-foreground hover:text-foreground shrink-0"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        )}

        {/* Form Stages Section Orchestrator */}
        <AnimatePresence mode="wait">
          {/* Matching Screen */}
          {isSubmitting && (
            <MatchingScreen
              matchingProgress={matchingProgress}
              matchingStatus={matchingStatus}
            />
          )}

          {/* STEP 1: IMPORT */}
          {userFlowChoice !== null && !isSubmitting && step === 1 && (
            <Step1ImportDiagnostic
              linkedinUrl={linkedinUrl}
              setLinkedinUrl={setLinkedinUrl}
              cvFile={cvFile}
              isParsingCv={isParsingCv}
              dragActive={dragActive}
              handleDrag={handleDrag}
              handleDrop={handleDrop}
              handleFileChange={handleFileChange}
              userPhotoUrl={userPhotoUrl}
              handlePhotoUpload={handlePhotoUpload}
              showPhotoOnCv={showPhotoOnCv}
              setShowPhotoOnCv={setShowPhotoOnCv}
              showQuickBuilder={showQuickBuilder}
              setShowQuickBuilder={setShowQuickBuilder}
              quickRole={quickRole}
              setQuickRole={setQuickRole}
              quickCompany={quickCompany}
              setQuickCompany={setQuickCompany}
              quickSkillsInput={quickSkillsInput}
              setQuickSkillsInput={setQuickSkillsInput}
              handleQuickBuilderSubmit={handleQuickBuilderSubmit}
            />
          )}

          {/* STEP 2: CV EDITOR (SPLIT-PANE) */}
          {userFlowChoice !== null && !isSubmitting && step === 2 && (
            <Step2CvEditor
              fullName={fullName}
              setFullName={setFullName}
              email={email}
              setEmail={setEmail}
              phone={phone}
              setPhone={setPhone}
              linkedinUrl={linkedinUrl}
              setLinkedinUrl={setLinkedinUrl}
              headline={headline}
              setHeadline={setHeadline}
              summary={summary}
              setSummary={setSummary}
              userPhotoUrl={userPhotoUrl}
              handlePhotoUpload={handlePhotoUpload}
              showPhotoOnCv={showPhotoOnCv}
              setShowPhotoOnCv={setShowPhotoOnCv}
              experiences={experiences}
              setExperiences={setExperiences}
              education={education}
              setEducation={setEducation}
              skills={skills}
              setSkills={setSkills}
              languages={languages}
              setLanguages={setLanguages}
              atsAudit={atsAudit}
              experienceYears={experienceYears}
              selectedTemplate={selectedTemplate}
              activeColorSwatch={activeColorSwatch}
            />
          )}

          {/* STEP 3: STUDIO DESIGN TYPST */}
          {userFlowChoice !== null && !isSubmitting && step === 3 && (
            <Step3DesignStudio
              selectedTemplate={selectedTemplate}
              setSelectedTemplate={setSelectedTemplate}
              selectedColor={selectedColor}
              setSelectedColor={setSelectedColor}
              cvLanguage={cvLanguage}
              setCvLanguage={setCvLanguage}
              showPhotoOnCv={showPhotoOnCv}
              setShowPhotoOnCv={setShowPhotoOnCv}
              userPhotoUrl={userPhotoUrl}
              activeColorSwatch={activeColorSwatch}
            />
          )}

          {/* STEP 4: FINALIZATION, PDF EXPORT & JOB MATCHING */}
          {userFlowChoice !== null && !isSubmitting && step === 4 && (
            <Step4MatchingPreferences
              fullName={fullName}
              headline={headline}
              summary={summary}
              email={email}
              linkedinUrl={linkedinUrl}
              skills={skills}
              experienceYears={experienceYears}
              setExperienceYears={setExperienceYears}
              selectedTemplate={selectedTemplate}
              activeColorSwatch={activeColorSwatch}
              showPhotoOnCv={showPhotoOnCv}
              userPhotoUrl={userPhotoUrl}
              contractTypes={contractTypes}
              toggleContractType={toggleContractType}
              remotePolicies={remotePolicies}
              toggleRemotePolicy={toggleRemotePolicy}
              locations={locations}
              locationInput={locationInput}
              setLocationInput={setLocationInput}
              addLocation={addLocation}
              removeLocation={removeLocation}
            />
          )}
        </AnimatePresence>

        {/* Navigation Controls Bar */}
        {userFlowChoice !== null && !isSubmitting && (
          <NavigationBar
            step={step}
            onPrev={() => setStep(step - 1)}
            onResetChoice={() => setUserFlowChoice(null)}
            onNext={handleNext}
            onSubmit={handleSubmit}
            canNext={
              step === 1
                ? validateStep1()
                : step === 2
                ? validateStep2()
                : validateStep3()
            }
            canSubmit={validateStep4()}
          />
        )}
      </div>
    </div>
  );
}

export default function OnboardingPage() {
  return (
    <main className="min-h-screen bg-slate-50 dark:bg-slate-950">
      <Suspense
        fallback={
          <div className="flex min-h-screen items-center justify-center flex-col gap-3">
            <Loader2 className="h-10 w-10 animate-spin text-primary" />
            <p className="text-sm text-muted-foreground">Chargement du studio Untaf...</p>
          </div>
        }
      >
        <OnboardingForm />
      </Suspense>
    </main>
  );
}
