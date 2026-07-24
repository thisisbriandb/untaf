"use client";

import { cn } from "@/lib/utils";
import { cvTemplates, ExperienceEntry, EducationEntry, LanguageEntry } from "../types";

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
  // New structured data
  experiences?: ExperienceEntry[];
  education?: EducationEntry[];
  languages?: LanguageEntry[];
  phone?: string;
}

function formatDate(d: string): string {
  if (!d || d === "present") return "Présent";
  const [year, month] = d.split("-");
  const months = ["Jan", "Fév", "Mar", "Avr", "Mai", "Jun", "Jul", "Aoû", "Sep", "Oct", "Nov", "Déc"];
  return month ? `${months[parseInt(month) - 1]} ${year}` : year;
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
}: CandidateCvPreviewProps) {
  const tpl = cvTemplates.find((t) => t.id === templateId) || cvTemplates[0];
  const isSidebar = tpl.layout === "left-sidebar" || tpl.layout === "creative";
  const photoToDisplay = userPhotoUrl || tpl.photo;

  const hasExperiences = experiences.length > 0 && experiences.some((e) => e.jobTitle || e.company);
  const hasEducation = education.length > 0 && education.some((e) => e.degree || e.institution);
  const hasLanguages = languages.length > 0 && languages.some((l) => l.language);

  return (
    <div className="w-full rounded-xl border border-border bg-white text-slate-900 shadow-md overflow-hidden text-xs transition-all">
      {/* Header */}
      <div
        className={cn("p-5 border-b text-white flex items-center justify-between")}
        style={{ backgroundColor: selectedColorHex }}
      >
        <div className="flex-1 min-w-0">
          <h2 className="text-lg font-extrabold tracking-tight truncate">{fullName || "Votre Nom"}</h2>
          <p className="text-xs font-medium opacity-90 mt-0.5 truncate">{headline || "Titre professionnel"}</p>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[11px] opacity-80 mt-2">
            <span>{email || "email@example.com"}</span>
            {phone && <span>• {phone}</span>}
            {linkedinUrl && <span className="truncate max-w-[140px]">• {linkedinUrl}</span>}
            {!hasExperiences && <span>• Expérience: {experienceYears} ans</span>}
          </div>
        </div>
        {showPhoto && (
          <img
            src={photoToDisplay}
            alt={fullName}
            className="h-14 w-14 rounded-full object-cover border-2 border-white/80 shadow-md shrink-0 hidden sm:block"
          />
        )}
      </div>

      <div className={cn("p-5 space-y-4", isSidebar ? "grid grid-cols-3 gap-5 space-y-0" : "")}>
        {/* Main column */}
        <div className={cn(isSidebar ? "col-span-2 space-y-4" : "space-y-4")}>
          {/* Summary */}
          {(summary || !hasExperiences) && (
            <div>
              <h3
                className="font-bold text-xs uppercase tracking-wider border-b pb-1 mb-1.5"
                style={{ color: selectedColorHex, borderColor: selectedColorHex + "40" }}
              >
                Profil Professionnel
              </h3>
              <p className="text-xs leading-relaxed text-slate-700">
                {summary ||
                  "Professionnel expérimenté spécialisé dans la conception et le déploiement d'applications web performantes. Expertise reconnue en architecture logicielle, optimisation de code et travail en équipe projet."}
              </p>
            </div>
          )}

          {/* Experiences */}
          <div>
            <h3
              className="font-bold text-xs uppercase tracking-wider border-b pb-1 mb-1.5"
              style={{ color: selectedColorHex, borderColor: selectedColorHex + "40" }}
            >
              {hasExperiences ? "Expériences Professionnelles" : "Expérience Majeure"}
            </h3>
            {hasExperiences ? (
              <div className="space-y-3">
                {experiences.filter((e) => e.jobTitle || e.company).map((exp) => (
                  <div key={exp.id}>
                    <div className="flex justify-between font-semibold text-slate-800 text-xs">
                      <span>{exp.jobTitle || "Intitulé du poste"}</span>
                      <span className="text-[11px] text-slate-500 shrink-0 ml-2">
                        {formatDate(exp.startDate)} — {exp.isCurrent ? "Présent" : formatDate(exp.endDate)}
                      </span>
                    </div>
                    <p className="text-xs text-slate-500 font-medium">
                      {exp.company}{exp.location ? ` · ${exp.location}` : ""}
                    </p>
                    {exp.highlights.filter((h) => h.trim()).length > 0 && (
                      <ul className="list-disc list-inside text-xs text-slate-600 mt-1 space-y-0.5">
                        {exp.highlights.filter((h) => h.trim()).map((h, i) => (
                          <li key={i}>{h}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="space-y-2">
                <div>
                  <div className="flex justify-between font-semibold text-slate-800 text-xs">
                    <span>Ingénieur Développeur Senior</span>
                    <span className="text-[11px] text-slate-500">2022 - Présent</span>
                  </div>
                  <p className="text-xs text-slate-500 font-medium">Développement & Architecture Logicielle</p>
                  <ul className="list-disc list-inside text-xs text-slate-600 mt-1 space-y-0.5">
                    <li>Conception d&apos;architectures web scalables et optimisation des temps de réponse.</li>
                    <li>Mise en œuvre des bonnes pratiques de code et déploiement continu.</li>
                  </ul>
                </div>
              </div>
            )}
          </div>

          {/* Education */}
          {hasEducation && (
            <div>
              <h3
                className="font-bold text-xs uppercase tracking-wider border-b pb-1 mb-1.5"
                style={{ color: selectedColorHex, borderColor: selectedColorHex + "40" }}
              >
                Formation
              </h3>
              <div className="space-y-2">
                {education.filter((e) => e.degree || e.institution).map((edu) => (
                  <div key={edu.id}>
                    <div className="flex justify-between font-semibold text-slate-800 text-xs">
                      <span>{edu.degree}</span>
                      <span className="text-[11px] text-slate-500 shrink-0 ml-2">
                        {edu.startYear}{edu.endYear ? ` — ${edu.endYear}` : ""}
                      </span>
                    </div>
                    <p className="text-xs text-slate-500 font-medium">
                      {edu.institution}{edu.location ? ` · ${edu.location}` : ""}
                    </p>
                    {edu.description && (
                      <p className="text-xs text-slate-600 mt-0.5">{edu.description}</p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Sidebar / Skills column */}
        <div className={cn(isSidebar ? "col-span-1 border-l border-slate-200 pl-4 space-y-4" : "space-y-4")}>
          <div>
            <h3
              className="font-bold text-xs uppercase tracking-wider border-b pb-1 mb-1.5"
              style={{ color: selectedColorHex, borderColor: selectedColorHex + "40" }}
            >
              Compétences Clés
            </h3>
            <div className="flex flex-wrap gap-1 mt-1">
              {(skills.length > 0 ? skills : ["TypeScript", "React", "Node.js", "Python", "SQL"]).map((sk, idx) => (
                <span
                  key={idx}
                  className="rounded bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-700 border border-slate-200"
                >
                  {sk}
                </span>
              ))}
            </div>
          </div>

          <div>
            <h3
              className="font-bold text-xs uppercase tracking-wider border-b pb-1 mb-1.5"
              style={{ color: selectedColorHex, borderColor: selectedColorHex + "40" }}
            >
              Langues{!hasEducation && " & Formation"}
            </h3>
            {hasLanguages ? (
              <div className="space-y-0.5">
                {languages.filter((l) => l.language).map((l) => (
                  <p key={l.id} className="text-xs text-slate-600">
                    {l.language} <span className="text-slate-400">— {l.level}</span>
                  </p>
                ))}
              </div>
            ) : (
              <>
                <p className="text-xs text-slate-600">Français (Native) • Anglais (Professionnel)</p>
                {!hasEducation && (
                  <p className="text-xs text-slate-500 mt-0.5">Diplôme d&apos;Ingénieur en Informatique</p>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
