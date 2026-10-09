"use client";

/**
 * L'allure des CV, choisie une fois à l'inscription : modèle, couleur, photo.
 *
 * Sans cette étape, tous les dossiers partaient sur le modèle par défaut, sans
 * photo, et le candidat ne le découvrait qu'en ouvrant un dossier. Le choix
 * est enregistré au profil à l'activation : chaque CV adapté le suit, qu'il
 * soit préparé depuis la conversation, une mission ou le Canvas.
 */

import { useRef, useState } from "react";
import { Camera, Check, Maximize2, Trash2, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { shrinkPhoto } from "@/lib/cv-profile";
import { colorSwatches, cvTemplates } from "../types";
import { CandidateCvPreview } from "./CandidateCvPreview";

export interface CvLook {
  templateId: string;
  colorHex: string;
  /** Photo en data URL (réduite dans le navigateur), ou null. */
  photo: string | null;
  showPhoto: boolean;
}

/** Ce que l'aperçu montre du candidat (le profil de l'inscription). */
interface PreviewProfile {
  firstName: string;
  lastName: string;
  headline: string;
  email: string;
  phone: string;
  summary: string;
  skills: string[];
  experienceYears: number | null;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  experiences: any[];
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  education: any[];
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  languages: any[];
}

export const DEFAULT_LOOK: CvLook = {
  templateId: "classic",
  colorHex: "#1B3C53",
  photo: null,
  showPhoto: false,
};

/** Les modèles proposés d'abord : peu de choix, des styles bien distincts. */
const FEATURED = ["classic", "minimalist", "tech", "executive"];

export function CvLookStep({
  profile,
  value,
  onChange,
  onContinue,
}: {
  profile: PreviewProfile;
  value: CvLook;
  onChange: (look: CvLook) => void;
  onContinue: () => void;
}) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [photoError, setPhotoError] = useState<string | null>(null);
  const [showAll, setShowAll] = useState(false);
  const [zoom, setZoom] = useState(false);

  const featured = cvTemplates.filter((t) => FEATURED.includes(t.id));
  const templates = showAll || featured.length < 2 ? cvTemplates : featured;

  const onPhoto = async (file: File | undefined) => {
    if (!file) return;
    try {
      const photo = await shrinkPhoto(file);
      setPhotoError(null);
      onChange({ ...value, photo, showPhoto: true });
    } catch {
      setPhotoError("Je n'arrive pas à lire cette image : choisis un JPEG ou un PNG.");
    }
  };

  // Le vrai CV du candidat, avec son allure : dans la carte, et en grand.
  const preview = (
    <CandidateCvPreview
      fluid
      fullName={`${profile.firstName} ${profile.lastName}`.trim()}
      headline={profile.headline}
      summary={profile.summary}
      email={profile.email}
      phone={profile.phone}
      linkedinUrl=""
      skills={profile.skills}
      experienceYears={profile.experienceYears ?? 0}
      experiences={profile.experiences}
      education={profile.education}
      languages={profile.languages}
      templateId={value.templateId}
      selectedColorHex={value.colorHex}
      showPhoto={value.showPhoto && Boolean(value.photo)}
      userPhotoUrl={value.photo}
    />
  );

  return (
    <div className="w-full mx-auto grid gap-6 md:grid-cols-[minmax(0,1fr)_260px] text-left">
      {/* Sur mobile, le haut du CV suffit à juger l'allure (en-tête, couleur,
          photo) : on le limite pour garder les réglages à portée de pouce.
          « Agrandir » montre la page entière. */}
      <div className="relative rounded-2xl border border-[#1A1918]/8 bg-white p-3 overflow-hidden max-h-[46vh] md:max-h-none">
        <div className="pointer-events-none absolute inset-x-0 bottom-0 h-10 bg-gradient-to-t from-white to-transparent md:hidden" />
        <button
          type="button"
          onClick={() => setZoom(true)}
          className="absolute right-3 top-3 z-10 inline-flex items-center gap-1 rounded-full bg-white/90 border border-[#1A1918]/10 px-2.5 py-1 text-[11px] text-[#1A1918]/70 hover:text-[#006045] cursor-pointer"
        >
          <Maximize2 className="h-3 w-3" /> Agrandir
        </button>
        {preview}
      </div>

      {zoom && (
        <div
          className="fixed inset-0 z-[80] bg-[#1A1918]/40 flex items-start justify-center overflow-y-auto p-4 md:p-10"
          onClick={() => setZoom(false)}
        >
          <div className="relative w-full max-w-[760px] rounded-2xl bg-white p-4" onClick={(e) => e.stopPropagation()}>
            <button
              type="button"
              onClick={() => setZoom(false)}
              aria-label="Fermer"
              className="absolute right-3 top-3 z-10 p-1.5 rounded-full bg-white border border-[#1A1918]/10 text-[#1A1918]/60 hover:text-[#1A1918] cursor-pointer"
            >
              <X className="h-4 w-4" />
            </button>
            {preview}
          </div>
        </div>
      )}

      <div className="space-y-5">
        <section className="space-y-2">
          <p className="text-[11px] uppercase tracking-wider text-[#1A1918]/55 font-medium">Modèle</p>
          <div className="flex flex-wrap gap-1.5">
            {templates.map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => onChange({ ...value, templateId: t.id })}
                className={cn(
                  "rounded-full border px-3 py-1.5 text-xs tracking-tight cursor-pointer transition-colors",
                  value.templateId === t.id
                    ? "border-[#006045] bg-[#006045]/8 text-[#006045]"
                    : "border-[#1A1918]/10 text-[#1A1918]/70 hover:border-[#006045]/40",
                )}
              >
                {t.name}
              </button>
            ))}
          </div>
          {!showAll && cvTemplates.length > templates.length && (
            <button
              type="button"
              onClick={() => setShowAll(true)}
              className="text-[11px] text-[#1A1918]/50 hover:text-[#006045] cursor-pointer"
            >
              voir les {cvTemplates.length} modèles
            </button>
          )}
        </section>

        <section className="space-y-2">
          <p className="text-[11px] uppercase tracking-wider text-[#1A1918]/55 font-medium">Couleur</p>
          <div className="flex gap-2">
            {colorSwatches.map((c) => (
              <button
                key={c.id}
                type="button"
                aria-label={c.name}
                title={c.name}
                onClick={() => onChange({ ...value, colorHex: c.hex })}
                className="h-7 w-7 rounded-full border border-white shadow-sm cursor-pointer flex items-center justify-center"
                style={{ backgroundColor: c.hex }}
              >
                {value.colorHex === c.hex && <Check className="h-3.5 w-3.5 text-white" />}
              </button>
            ))}
          </div>
        </section>

        <section className="space-y-2">
          <p className="text-[11px] uppercase tracking-wider text-[#1A1918]/55 font-medium">Photo</p>
          <input
            ref={fileRef}
            type="file"
            accept="image/jpeg,image/png"
            className="hidden"
            onChange={(e) => void onPhoto(e.target.files?.[0])}
          />
          {value.photo ? (
            <div className="flex items-center gap-3">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={value.photo} alt="Ta photo" className="h-12 w-12 rounded-full object-cover" />
              <button
                type="button"
                onClick={() => onChange({ ...value, photo: null, showPhoto: false })}
                className="inline-flex items-center gap-1 text-xs text-[#1A1918]/60 hover:text-red-600 cursor-pointer"
              >
                <Trash2 className="h-3.5 w-3.5" /> Retirer
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              className="inline-flex items-center gap-2 rounded-full border border-[#1A1918]/10 px-3 py-1.5 text-xs text-[#1A1918]/70 hover:border-[#006045]/40 hover:text-[#006045] cursor-pointer"
            >
              <Camera className="h-3.5 w-3.5" /> Ajouter une photo
            </button>
          )}
          <p className="text-[11px] text-[#1A1918]/50 tracking-tight">
            Facultative. En France, beaucoup de recruteurs l&apos;apprécient ; d&apos;autres préfèrent sans.
          </p>
          {photoError && <p className="text-[11px] text-red-600">{photoError}</p>}
        </section>

        {/* Toujours visible sur mobile, sans avoir à descendre. */}
        <div className="sticky bottom-3 z-10 md:static">
          <button
            type="button"
            onClick={onContinue}
            className="w-full rounded-full bg-[#006045] px-4 py-2.5 text-sm text-white shadow-lg md:shadow-none hover:bg-[#004d37] transition-colors cursor-pointer"
          >
            C&apos;est mon style
          </button>
        </div>
        <p className="text-[11px] text-[#1A1918]/50 text-center tracking-tight">
          Tous tes dossiers suivront ce choix. Tu pourras le changer à tout moment.
        </p>
      </div>
    </div>
  );
}
