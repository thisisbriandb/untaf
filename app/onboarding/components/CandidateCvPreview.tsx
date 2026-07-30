"use client";

import { useEffect, useState, useTransition } from "react";
import { cvTemplates, ExperienceEntry, EducationEntry, LanguageEntry } from "../types";
import { Loader2 } from "lucide-react";
import { API_BASE_URL } from "@/lib/config";

interface CandidateCvPreviewProps {
  fullName: string;
  headline: string;
  summary: string;
  email: string;
  linkedinUrl: string;
  skills: string[];
  experienceYears: number;
  templateId: string;
  selectedColorHex: string;
  showPhoto: boolean;
  userPhotoUrl: string | null;
  experiences?: ExperienceEntry[];
  education?: EducationEntry[];
  languages?: LanguageEntry[];
  phone?: string;
  /**
   * Size the sheet from its container (A4 aspect ratio) instead of the fixed
   * 780px frame, and drop the chrome. Used inside the Canvas, where the panel
   * width is a fraction of the viewport.
   */
  fluid?: boolean;
}

export function CandidateCvPreview({
  fullName,
  headline,
  summary,
  email,
  linkedinUrl,
  skills,
  experienceYears,
  templateId,
  selectedColorHex,
  showPhoto,
  userPhotoUrl,
  experiences = [],
  education = [],
  languages = [],
  phone,
  fluid = false,
}: CandidateCvPreviewProps) {
  const tpl = cvTemplates.find((t) => t.id === templateId) || cvTemplates[0];
  const photoToDisplay = userPhotoUrl || tpl.photo;

  const [svgContent, setSvgContent] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    const timer = setTimeout(async () => {
      setLoading(true);
      setError(null);
      try {
        const payload = {
          template_id: templateId,
          color_hex: selectedColorHex,
          show_photo: showPhoto,
          photo_url: photoToDisplay,
          full_name: fullName,
          headline: headline,
          summary: summary,
          email: email,
          phone: phone,
          location: "France",
          skills: skills,
          experiences: experiences.map((exp) => ({
            jobTitle: exp.jobTitle,
            company: exp.company,
            location: exp.location,
            startDate: exp.startDate,
            endDate: exp.endDate,
            isCurrent: exp.isCurrent,
            highlights: exp.highlights,
          })),
          education: education.map((edu) => ({
            degree: edu.degree,
            institution: edu.institution,
            location: edu.location,
            startYear: edu.startYear,
            endYear: edu.endYear,
            description: edu.description,
          })),
          languages: languages.map((lang) => ({
            language: lang.language,
            level: lang.level,
          })),
        };

        const res = await fetch(`${API_BASE_URL}/api/candidates/render-preview-svg`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

        if (!res.ok) {
          throw new Error("Erreur de génération SVG");
        }

        const text = await res.text();
        if (isMounted) {
          setSvgContent(text);
          setLoading(false);
        }
      } catch (err: any) {
        if (isMounted) {
          console.error("Preview SVG error:", err);
          setError("Impossible de charger l'aperçu Typst.");
          setLoading(false);
        }
      }
    }, 200);

    return () => {
      isMounted = false;
      clearTimeout(timer);
    };
  }, [
    fullName,
    headline,
    summary,
    email,
    linkedinUrl,
    skills,
    experienceYears,
    templateId,
    selectedColorHex,
    showPhoto,
    photoToDisplay,
    experiences,
    education,
    languages,
    phone,
  ]);

  if (fluid) {
    return (
      <div className="w-full aspect-[1/1.4142] bg-white rounded-lg border border-[#1A1918]/10 shadow-sm overflow-hidden relative">
        {loading && (
          <div className="absolute inset-0 bg-white/70 backdrop-blur-[1px] z-10 flex flex-col items-center justify-center gap-2">
            <Loader2 className="h-5 w-5 animate-spin text-[#006045]" />
            <span className="text-[11px] font-light text-[#1A1918]/55 tracking-tight">
              Rendu en cours…
            </span>
          </div>
        )}
        {error && !svgContent ? (
          <div className="absolute inset-0 flex items-center justify-center p-6 text-center text-xs font-light text-[#1A1918]/45 tracking-tight">
            {error}
          </div>
        ) : svgContent ? (
          <div
            className="w-full h-full [&>svg]:w-full [&>svg]:h-full [&>svg]:block"
            dangerouslySetInnerHTML={{ __html: svgContent }}
          />
        ) : null}
      </div>
    );
  }

  return (
    <div className="w-full max-w-[600px] mx-auto min-h-[780px] bg-white shadow-2xl rounded-lg border border-slate-200 overflow-hidden flex flex-col justify-between relative ring-1 ring-slate-900/5 transition-all">
      {/* Indicator header */}
      <div className="bg-slate-900 text-slate-200 px-4 py-2 flex items-center justify-between text-xs border-b border-slate-800">
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse"></span>
          <span className="font-semibold tracking-wide uppercase text-[11px] text-slate-300">Aperçu Typst Temps Réel (Source Unique)</span>
        </div>
        <span className="text-[10px] text-slate-400 font-mono">100% Fidèle au PDF</span>
      </div>

      {/* Main container for SVG */}
      <div className="relative flex-1 bg-slate-100 flex items-center justify-center p-2 min-h-[720px]">
        {loading && (
          <div className="absolute inset-0 bg-white/60 backdrop-blur-[1px] z-10 flex flex-col items-center justify-center gap-2 text-slate-600 transition-opacity">
            <Loader2 className="h-7 w-7 animate-spin text-slate-800" />
            <span className="text-xs font-medium text-slate-700">Rendu Typst en cours...</span>
          </div>
        )}

        {error && !svgContent ? (
          <div className="p-6 text-center text-rose-500 text-xs font-medium">
            {error}
          </div>
        ) : svgContent ? (
          <div
            className="w-full h-full flex items-center justify-center [&>svg]:w-full [&>svg]:h-auto [&>svg]:max-h-[740px] [&>svg]:shadow-md [&>svg]:rounded-sm"
            dangerouslySetInnerHTML={{ __html: svgContent }}
          />
        ) : null}
      </div>

      {/* Footer info */}
      <div className="border-t border-slate-200 bg-white px-4 py-2 flex items-center justify-between text-[11px] text-slate-500 font-mono">
        <span>Moteur Typst • Format Vectoriel SVG</span>
        <span>A4 • Parité Visuelle 100%</span>
      </div>
    </div>
  );
}

