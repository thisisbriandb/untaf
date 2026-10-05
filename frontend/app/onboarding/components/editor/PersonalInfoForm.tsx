"use client";

import { Camera, User, Sparkles } from "lucide-react";
import { CVAuditData } from "../../types";

interface PersonalInfoFormProps {
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
  atsAudit: CVAuditData | null;
}

export function PersonalInfoForm({
  fullName,
  setFullName,
  email,
  setEmail,
  phone,
  setPhone,
  linkedinUrl,
  setLinkedinUrl,
  headline,
  setHeadline,
  summary,
  setSummary,
  userPhotoUrl,
  handlePhotoUpload,
  showPhotoOnCv,
  setShowPhotoOnCv,
  atsAudit,
}: PersonalInfoFormProps) {
  return (
    <div className="space-y-5">
      <div>
        <h3 className="text-sm font-bold text-foreground">
          Informations personnelles
        </h3>
        <p className="text-[11px] text-muted-foreground mt-0.5">
          Vos coordonnées et votre accroche professionnelle.
        </p>
      </div>

      {/* Photo */}
      <div className="flex items-center gap-4 p-3 rounded-xl bg-muted/40 border border-border/50">
        <div className="h-14 w-14 rounded-full bg-slate-200 dark:bg-slate-800 border-2 border-border flex items-center justify-center overflow-hidden shrink-0">
          {userPhotoUrl ? (
            <img
              src={userPhotoUrl}
              alt="Photo"
              className="h-full w-full object-cover"
            />
          ) : (
            <User className="h-6 w-6 text-muted-foreground" />
          )}
        </div>
        <div className="flex-1 space-y-1.5">
          <div className="flex items-center gap-2">
            <input
              type="file"
              accept="image/*"
              id="photo-upload-editor"
              onChange={handlePhotoUpload}
              className="hidden"
            />
            <label
              htmlFor="photo-upload-editor"
              className="cursor-pointer inline-flex h-8 items-center gap-1.5 rounded-lg border border-border bg-card px-3 text-xs font-semibold hover:bg-muted transition"
            >
              <Camera className="h-3.5 w-3.5 text-primary" />
              {userPhotoUrl ? "Changer la photo" : "Ajouter une photo"}
            </label>
            <label className="flex items-center gap-1.5 text-xs text-muted-foreground cursor-pointer select-none">
              <input
                type="checkbox"
                checked={showPhotoOnCv}
                onChange={(e) => setShowPhotoOnCv(e.target.checked)}
                className="rounded accent-primary"
              />
              Afficher sur le CV
            </label>
          </div>
          <p className="text-[11px] text-muted-foreground">
            Format JPG/PNG recommandé, photo professionnelle de préférence.
          </p>
        </div>
      </div>

      {/* Name & Email row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <label className="text-xs font-semibold text-foreground">
            Nom complet <span className="text-destructive">*</span>
          </label>
          <input
            type="text"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            placeholder="Jean Dupont"
            className="w-full rounded-xl border border-input bg-background py-2.5 px-3.5 text-xs transition focus:outline-none focus:ring-2 focus:ring-primary/40"
          />
        </div>
        <div className="space-y-1.5">
          <label className="text-xs font-semibold text-foreground">
            Email <span className="text-destructive">*</span>
          </label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="jean.dupont@email.com"
            className="w-full rounded-xl border border-input bg-background py-2.5 px-3.5 text-xs transition focus:outline-none focus:ring-2 focus:ring-primary/40"
          />
        </div>
      </div>

      {/* Phone & LinkedIn row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <label className="text-xs font-semibold text-foreground">
            Téléphone
          </label>
          <input
            type="tel"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="+33 6 12 34 56 78"
            className="w-full rounded-xl border border-input bg-background py-2.5 px-3.5 text-xs transition focus:outline-none focus:ring-2 focus:ring-primary/40"
          />
        </div>
        <div className="space-y-1.5">
          <label className="text-xs font-semibold text-foreground">
            LinkedIn
          </label>
          <input
            type="url"
            value={linkedinUrl}
            onChange={(e) => setLinkedinUrl(e.target.value)}
            placeholder="https://linkedin.com/in/jeandupont"
            className="w-full rounded-xl border border-input bg-background py-2.5 px-3.5 text-xs transition focus:outline-none focus:ring-2 focus:ring-primary/40"
          />
        </div>
      </div>

      {/* Headline */}
      <div className="space-y-1.5">
        <div className="flex justify-between items-center">
          <label className="text-xs font-semibold text-foreground">
            Titre professionnel <span className="text-destructive">*</span>
          </label>
          {atsAudit?.optimized_headline && (
            <button
              type="button"
              onClick={() => setHeadline(atsAudit.optimized_headline)}
              className="inline-flex items-center gap-1 text-[11px] font-semibold text-primary hover:underline"
            >
              <Sparkles className="h-3 w-3" />
              Suggestion IA
            </button>
          )}
        </div>
        <input
          type="text"
          value={headline}
          onChange={(e) => setHeadline(e.target.value)}
          placeholder="ex: Ingénieur Développeur Full-Stack"
          className="w-full rounded-xl border border-input bg-background py-2.5 px-3.5 text-xs font-semibold transition focus:outline-none focus:ring-2 focus:ring-primary/40"
        />
      </div>

      {/* Summary */}
      <div className="space-y-1.5">
        <div className="flex justify-between items-center">
          <label className="text-xs font-semibold text-foreground">
            Résumé professionnel
          </label>
          {atsAudit?.optimized_summary && (
            <button
              type="button"
              onClick={() => setSummary(atsAudit.optimized_summary)}
              className="inline-flex items-center gap-1 text-[11px] font-semibold text-primary hover:underline"
            >
              <Sparkles className="h-3 w-3" />
              Résumé optimisé IA
            </button>
          )}
        </div>
        <textarea
          rows={3}
          value={summary}
          onChange={(e) => setSummary(e.target.value)}
          placeholder="Présentez votre parcours, vos réalisations clés et votre valeur ajoutée..."
          className="w-full rounded-xl border border-input bg-background p-3 text-xs leading-relaxed transition focus:outline-none focus:ring-2 focus:ring-primary/40 resize-none"
        />
      </div>
    </div>
  );
}
