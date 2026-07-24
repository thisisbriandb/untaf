"use client";

import { motion } from "framer-motion";
import {
  FileText,
  UploadCloud,
  Loader2,
  Camera,
  User,
  PenTool,
} from "lucide-react";
import { cn } from "@/lib/utils";

const LinkedinIcon = (props: React.SVGProps<SVGSVGElement>) => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    {...props}
  >
    <path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z" />
    <rect width="4" height="12" x="2" y="9" />
    <circle cx="4" cy="4" r="2" />
  </svg>
);

interface Step1ImportDiagnosticProps {
  linkedinUrl: string;
  setLinkedinUrl: (url: string) => void;
  cvFile: File | null;
  isParsingCv: boolean;
  dragActive: boolean;
  handleDrag: (e: React.DragEvent) => void;
  handleDrop: (e: React.DragEvent) => void;
  handleFileChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  userPhotoUrl: string | null;
  handlePhotoUpload: (e: React.ChangeEvent<HTMLInputElement>) => void;
  showPhotoOnCv: boolean;
  setShowPhotoOnCv: (show: boolean) => void;
  showQuickBuilder: boolean;
  setShowQuickBuilder: (show: boolean) => void;
  quickRole: string;
  setQuickRole: (role: string) => void;
  quickCompany: string;
  setQuickCompany: (company: string) => void;
  quickSkillsInput: string;
  setQuickSkillsInput: (skills: string) => void;
  handleQuickBuilderSubmit: () => void;
}

export function Step1ImportDiagnostic({
  linkedinUrl,
  setLinkedinUrl,
  cvFile,
  isParsingCv,
  dragActive,
  handleDrag,
  handleDrop,
  handleFileChange,
  userPhotoUrl,
  handlePhotoUpload,
  showPhotoOnCv,
  setShowPhotoOnCv,
  showQuickBuilder,
  setShowQuickBuilder,
  quickRole,
  setQuickRole,
  quickCompany,
  setQuickCompany,
  quickSkillsInput,
  setQuickSkillsInput,
  handleQuickBuilderSubmit,
}: Step1ImportDiagnosticProps) {
  return (
    <motion.div
      key="step1"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      transition={{ duration: 0.2 }}
      className="space-y-6"
    >
      <div className="rounded-2xl border border-border bg-card p-6 sm:p-8 space-y-6 shadow-sm">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-foreground">1. Importez votre CV</h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Choisissez une seule méthode : déposez votre CV au format PDF, ou renseignez
            votre profil LinkedIn.
          </p>
        </div>

        {!showQuickBuilder ? (
          <div className="max-w-md mx-auto space-y-4">
            {/* LinkedIn Input */}
            <div className="space-y-1.5">
              <label className="text-xs font-semibold">Profil LinkedIn</label>
              <div className="relative">
                <LinkedinIcon className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  type="url"
                  placeholder="https://linkedin.com/in/evelinbrid"
                  value={linkedinUrl}
                  onChange={(e) => setLinkedinUrl(e.target.value)}
                  disabled={!!cvFile}
                  className="w-full rounded-xl border border-input bg-background py-3 pl-10 pr-4 text-xs transition focus:outline-none focus:ring-2 focus:ring-primary/40 disabled:opacity-50 disabled:cursor-not-allowed"
                />
              </div>
            </div>

            {/* OU Divider */}
            <div className="flex items-center gap-3 py-1">
              <div className="h-px flex-1 bg-border" />
              <span className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
                ou
              </span>
              <div className="h-px flex-1 bg-border" />
            </div>

            {/* PDF Upload */}
            <div className="space-y-1.5">
              <label className="text-xs font-semibold">Votre CV PDF</label>
              <div
                onDragEnter={handleDrag}
                onDragOver={handleDrag}
                onDragLeave={handleDrag}
                onDrop={linkedinUrl ? undefined : handleDrop}
                className={cn(
                  "flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-6 text-center transition",
                  linkedinUrl
                    ? "opacity-50 cursor-not-allowed border-border bg-muted/20"
                    : "cursor-pointer hover:bg-muted/40",
                  dragActive && !linkedinUrl ? "border-primary bg-primary/5" : "border-border",
                  cvFile ? "bg-muted/40" : "bg-background"
                )}
              >
                <input
                  type="file"
                  accept=".pdf"
                  id="cv-upload"
                  onChange={handleFileChange}
                  disabled={!!linkedinUrl}
                  className="hidden"
                />
                <label
                  htmlFor="cv-upload"
                  className={cn("w-full", linkedinUrl ? "cursor-not-allowed" : "cursor-pointer")}
                >
                  {isParsingCv ? (
                    <div className="flex flex-col items-center py-2">
                      <Loader2 className="h-8 w-8 animate-spin text-primary" />
                      <p className="mt-2 text-xs font-semibold text-foreground">
                        Analyse du CV...
                      </p>
                    </div>
                  ) : cvFile ? (
                    <div className="flex flex-col items-center">
                      <FileText className="h-8 w-8 text-primary" />
                      <p className="mt-1.5 text-xs font-semibold truncate max-w-[200px]">
                        {cvFile.name}
                      </p>
                      <p className="text-[11px] text-muted-foreground mt-0.5">
                        {(cvFile.size / (1024 * 1024)).toFixed(2)} MB · PDF
                      </p>
                    </div>
                  ) : (
                    <div className="flex flex-col items-center">
                      <UploadCloud className="h-8 w-8 text-muted-foreground" />
                      <p className="mt-1.5 text-xs font-semibold">
                        Déposez votre CV PDF ici
                      </p>
                      <p className="text-[11px] text-muted-foreground mt-0.5">
                        ou cliquez pour sélectionner un fichier
                      </p>
                    </div>
                  )}
                </label>
              </div>
            </div>

            {/* Photo Profile Uploader */}
            <div className="pt-2 space-y-2 border-t border-border">
              <label className="text-xs font-semibold flex items-center justify-between">
                <span className="flex items-center gap-1.5">
                  <Camera className="h-3.5 w-3.5 text-primary" />
                  Photo de profil (optionnelle)
                </span>
                <span className="text-[11px] text-muted-foreground font-normal">
                  Format JPG/PNG
                </span>
              </label>
              <div className="flex items-center gap-3">
                <div className="h-11 w-11 rounded-full bg-slate-200 dark:bg-slate-800 border border-border flex items-center justify-center overflow-hidden shrink-0">
                  {userPhotoUrl ? (
                    <img src={userPhotoUrl} alt="Photo" className="h-full w-full object-cover" />
                  ) : (
                    <User className="h-5 w-5 text-muted-foreground" />
                  )}
                </div>
                <input
                  type="file"
                  accept="image/*"
                  id="photo-upload"
                  onChange={handlePhotoUpload}
                  className="hidden"
                />
                <label
                  htmlFor="photo-upload"
                  className="cursor-pointer inline-flex h-8 items-center gap-1.5 rounded-lg border border-border bg-card px-3 text-xs font-semibold hover:bg-muted"
                >
                  Charger une photo
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
            </div>

            <div className="pt-1 text-center">
              <button
                type="button"
                onClick={() => setShowQuickBuilder(true)}
                className="inline-flex items-center gap-1.5 text-xs font-semibold text-primary hover:underline"
              >
                <PenTool className="h-3.5 w-3.5" />
                Créer mon CV sans fichier
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h4 className="font-semibold text-sm">Création express en 60 secondes</h4>
              <button
                type="button"
                onClick={() => setShowQuickBuilder(false)}
                className="text-xs text-muted-foreground hover:text-foreground"
              >
                Retour
              </button>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-semibold">Poste visé</label>
              <input
                type="text"
                placeholder="ex: Ingénieur Développeur Full-Stack"
                value={quickRole}
                onChange={(e) => setQuickRole(e.target.value)}
                className="w-full rounded-lg border border-input bg-background py-2.5 px-3 text-xs"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-semibold">Dernière expérience ou projet</label>
              <input
                type="text"
                placeholder="ex: Application Web SaaS"
                value={quickCompany}
                onChange={(e) => setQuickCompany(e.target.value)}
                className="w-full rounded-lg border border-input bg-background py-2.5 px-3 text-xs"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-semibold">Compétences principales (séparées par des virgules)</label>
              <input
                type="text"
                placeholder="ex: TypeScript, React, Python"
                value={quickSkillsInput}
                onChange={(e) => setQuickSkillsInput(e.target.value)}
                className="w-full rounded-lg border border-input bg-background py-2.5 px-3 text-xs"
              />
            </div>

            <button
              type="button"
              onClick={handleQuickBuilderSubmit}
              className="w-full inline-flex h-10 items-center justify-center gap-1.5 rounded-xl bg-primary text-xs font-semibold text-primary-foreground hover:brightness-110"
            >
              Créer mon CV
            </button>
          </div>
        )}
      </div>
    </motion.div>
  );
}