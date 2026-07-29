"use client";

import { motion } from "framer-motion";
import { Download, Check, MapPin, Plus, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { API_BASE_URL } from "@/lib/config";
import { useState } from "react";
import { cvTemplates, contractOptions, remoteOptions, ColorSwatch, ExperienceEntry, EducationEntry, LanguageEntry } from "../types";
import { CandidateCvPreview } from "./CandidateCvPreview";

interface Step4MatchingPreferencesProps {
  fullName: string;
  headline: string;
  summary: string;
  email: string;
  linkedinUrl: string;
  phone?: string;
  experiences?: ExperienceEntry[];
  education?: EducationEntry[];
  languages?: LanguageEntry[];
  skills: string[];
  experienceYears: number;
  setExperienceYears: (years: number) => void;
  selectedTemplate: string;
  activeColorSwatch: ColorSwatch;
  showPhotoOnCv: boolean;
  userPhotoUrl: string | null;
  contractTypes: string[];
  toggleContractType: (val: string) => void;
  remotePolicies: string[];
  toggleRemotePolicy: (val: string) => void;
  locations: string[];
  locationInput: string;
  setLocationInput: (val: string) => void;
  addLocation: () => void;
  removeLocation: (loc: string) => void;
}

export function Step4MatchingPreferences({
  fullName,
  headline,
  summary,
  email,
  linkedinUrl,
  phone,
  experiences = [],
  education = [],
  languages = [],
  skills,
  experienceYears,
  setExperienceYears,
  selectedTemplate,
  activeColorSwatch,
  showPhotoOnCv,
  userPhotoUrl,
  contractTypes,
  toggleContractType,
  remotePolicies,
  toggleRemotePolicy,
  locations,
  locationInput,
  setLocationInput,
  addLocation,
  removeLocation,
}: Step4MatchingPreferencesProps) {
  const [isDownloading, setIsDownloading] = useState(false);

  const handleDownloadPdf = async () => {
    setIsDownloading(true);
    try {
      const tpl = cvTemplates.find((t) => t.id === selectedTemplate);
      const photoUrlToSend = userPhotoUrl || tpl?.photo || null;

      const response = await fetch(`${API_BASE_URL}/api/candidates/download-cv`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          template_id: selectedTemplate,
          color_hex: activeColorSwatch?.hex || "#234C6A",
          show_photo: showPhotoOnCv,
          photo_url: photoUrlToSend,
          full_name: fullName || "Candidat",
          email: email || "candidat@email.com",
          phone: phone || null,
          headline: headline || "Professionnel",
          summary: summary || null,
          skills: skills || [],
          linkedin_url: linkedinUrl || null,
          location: locations[0] || "France",
          experiences: (experiences || []).map((exp) => ({
            jobTitle: exp.jobTitle,
            company: exp.company,
            location: exp.location,
            startDate: exp.startDate,
            endDate: exp.isCurrent ? "present" : exp.endDate,
            isCurrent: exp.isCurrent,
            description: "",
            highlights: exp.highlights || [],
          })),
          education: (education || []).map((edu) => ({
            degree: edu.degree,
            institution: edu.institution,
            location: edu.location,
            startYear: edu.startYear,
            endYear: edu.endYear,
          })),
          languages: (languages || []).map((l) => ({
            language: l.language,
            level: l.level,
          })),
        }),
      });

      if (!response.ok) {
        const errText = await response.text();
        console.error("CV engine error:", errText);
        throw new Error("Erreur lors de la génération du PDF par cv-engine.");
      }

      // Use arrayBuffer to avoid blob encoding issues
      const buffer = await response.arrayBuffer();
      const pdfBlob = new Blob([buffer], { type: "application/pdf" });
      const url = window.URL.createObjectURL(pdfBlob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `CV_${(fullName || "candidat").replace(/\s+/g, "_")}_${selectedTemplate}.pdf`;
      document.body.appendChild(a);
      a.click();
      setTimeout(() => {
        window.URL.revokeObjectURL(url);
        a.remove();
      }, 200);
    } catch (e) {
      console.error(e);
      alert("Erreur lors du téléchargement du PDF.");
    } finally {
      setIsDownloading(false);
    }
  };

  return (
    <motion.div
      key="step4"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      transition={{ duration: 0.2 }}
      className="space-y-6"
    >
      {/* PDF Mounted View & Export Header */}
      <div className="rounded-2xl border border-border bg-card p-5 flex items-center justify-between shadow-sm">
        <div>
          <h3 className="font-bold text-base text-foreground">Document CV Prêt pour l&apos;Exportation</h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            Modèle <span className="font-semibold text-primary">{selectedTemplate.toUpperCase()}</span> compilé avec <span className="font-semibold text-foreground">cv-engine</span>.
          </p>
        </div>
        <button
          type="button"
          onClick={handleDownloadPdf}
          disabled={isDownloading}
          className="inline-flex items-center gap-2 rounded-xl bg-primary px-4 py-2 text-xs font-bold text-primary-foreground shadow-sm hover:brightness-110 disabled:opacity-50"
        >
          <Download className="h-4 w-4" />
          {isDownloading ? "Génération en cours..." : "Télécharger mon PDF"}
        </button>
      </div>

      {/* Full Scale Document Mounted Canvas */}
      <div className="border border-border rounded-2xl shadow-xl p-3 bg-slate-100 dark:bg-slate-900">
        <CandidateCvPreview
          fullName={fullName}
          headline={headline}
          summary={summary}
          email={email}
          linkedinUrl={linkedinUrl}
          phone={phone}
          experiences={experiences}
          education={education}
          languages={languages}
          skills={skills}
          experienceYears={experienceYears}
          templateId={selectedTemplate}
          selectedColorHex={activeColorSwatch.hex}
          showPhoto={showPhotoOnCv}
          userPhotoUrl={userPhotoUrl}
        />
      </div>

      {/* Preferences Configuration Form */}
      <div className="rounded-2xl border border-border bg-card p-6 sm:p-8 space-y-6 shadow-sm">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-foreground">Critères de Recherche & Matching</h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Renseignez vos attentes pour déclencher l&apos;analyse des opportunités ciblées.
          </p>
        </div>

        <div className="space-y-2">
          <label className="text-xs font-semibold">Types de contrat recherchés</label>
          <div className="flex flex-wrap gap-2">
            {contractOptions.map((opt) => {
              const isSelected = contractTypes.includes(opt.value);
              return (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => toggleContractType(opt.value)}
                  className={cn(
                    "inline-flex h-9 items-center gap-1.5 rounded-full border px-4 text-xs font-semibold transition-all",
                    isSelected
                      ? "bg-primary border-primary text-primary-foreground shadow-sm"
                      : "bg-background border-border text-muted-foreground hover:border-muted-foreground/60"
                  )}
                >
                  {isSelected && <Check className="h-3 w-3" />}
                  {opt.label}
                </button>
              );
            })}
          </div>
        </div>

        <div className="space-y-2">
          <label className="text-xs font-semibold">Préférence de télétravail</label>
          <div className="flex flex-wrap gap-2">
            {remoteOptions.map((opt) => {
              const isSelected = remotePolicies.includes(opt.value);
              return (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => toggleRemotePolicy(opt.value)}
                  className={cn(
                    "inline-flex h-9 items-center gap-1.5 rounded-full border px-4 text-xs font-semibold transition-all",
                    isSelected
                      ? "bg-primary border-primary text-primary-foreground shadow-sm"
                      : "bg-background border-border text-muted-foreground hover:border-muted-foreground/60"
                  )}
                >
                  {isSelected && <Check className="h-3 w-3" />}
                  {opt.label}
                </button>
              );
            })}
          </div>
        </div>

        <div className="space-y-2">
          <div className="flex justify-between items-center text-xs font-semibold">
            <label>Années d&apos;expérience globalement</label>
            <span className="font-mono text-primary">{experienceYears} ans</span>
          </div>
          <input
            type="range"
            min="0"
            max="15"
            step="1"
            value={experienceYears}
            onChange={(e) => setExperienceYears(parseInt(e.target.value))}
            className="w-full accent-primary h-2 bg-muted rounded-lg appearance-none cursor-pointer"
          />
        </div>

        <div className="space-y-2">
          <label className="text-xs font-semibold">Villes recherchées</label>
          <div className="flex flex-wrap gap-1.5 mb-2">
            {locations.map((loc) => (
              <span
                key={loc}
                className="inline-flex h-7 items-center gap-1 rounded bg-muted px-2.5 text-xs font-medium"
              >
                {loc}
                <button
                  type="button"
                  onClick={() => removeLocation(loc)}
                  className="text-muted-foreground hover:text-foreground"
                >
                  <X className="h-3 w-3" />
                </button>
              </span>
            ))}
          </div>
          <div className="flex gap-2">
            <div className="relative flex-1">
              <MapPin className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
              <input
                type="text"
                placeholder="Ajouter une ville (ex: Paris, Lyon...)"
                value={locationInput}
                onChange={(e) => setLocationInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    addLocation();
                  }
                }}
                className="w-full rounded-lg border border-input bg-background py-2.5 pl-9 pr-3 text-xs focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>
            <button
              type="button"
              onClick={addLocation}
              className="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-muted text-foreground hover:bg-muted/80"
            >
              <Plus className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>
    </motion.div>
  );
}
