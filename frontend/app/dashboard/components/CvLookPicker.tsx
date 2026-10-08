"use client";

/**
 * La mise en page du CV, là où elle compte : au moment de relire ce qui part.
 *
 * Le candidat voit quel modèle sert à son CV adapté (le classique tant qu'il
 * n'en a pas choisi), s'il porte sa photo, et peut tout changer ici, avec
 * l'aperçu du vrai CV — celui qui partira. Les dossiers pas encore envoyés
 * suivent son choix (côté serveur).
 */

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Camera, Check, ChevronDown, Loader2, Trash2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { colorSwatches, cvTemplates } from "@/app/onboarding/types";
import {
  deletePhoto, fetchCvDesign, saveCvDesign, shrinkPhoto, uploadPhoto, type CvDesign,
} from "@/lib/cv-profile";
import { tailoredCvUrl } from "@/lib/tailor-client";
import { useProtectedBlobUrl } from "./ProtectedFile";
import { useToast } from "./Toaster";

export function templateName(id: string | null | undefined) {
  return cvTemplates.find((t) => t.id === id)?.name ?? "Classic Encadré";
}

export function CvLookPicker({
  candidateId,
  jobId,
  defaultOpen = false,
  withPreview = true,
}: {
  candidateId: string;
  /** Offre dont on montre le CV adapté en aperçu. */
  jobId?: string;
  defaultOpen?: boolean;
  withPreview?: boolean;
}) {
  const toast = useToast();
  const [design, setDesign] = useState<CvDesign | null>(null);
  const [open, setOpen] = useState(defaultOpen);
  const [busy, setBusy] = useState(false);
  const [version, setVersion] = useState(0);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let alive = true;
    void fetchCvDesign(candidateId).then((d) => alive && setDesign(d));
    return () => { alive = false; };
  }, [candidateId]);

  // L'aperçu est le vrai CV adapté, recomposé après chaque changement.
  const previewUrl = withPreview && open && jobId
    ? `${tailoredCvUrl(candidateId, jobId)}/preview?v=${version}`
    : null;
  const preview = useProtectedBlobUrl(previewUrl);

  const apply = async (patch: Partial<Pick<CvDesign, "mode" | "template_id" | "color_hex" | "show_photo">>) => {
    setBusy(true);
    const saved = await saveCvDesign(candidateId, { mode: "template", ...patch });
    setBusy(false);
    if (!saved) return toast("Je n'ai pas pu enregistrer ce choix.", "warning");
    setDesign(saved);
    setVersion((v) => v + 1);
  };

  const onPhoto = async (file: File | undefined) => {
    if (!file) return;
    setBusy(true);
    try {
      const ok = await uploadPhoto(candidateId, await shrinkPhoto(file));
      if (!ok) throw new Error();
      setDesign(await fetchCvDesign(candidateId));
      setVersion((v) => v + 1);
      toast("Photo ajoutée à tes CV.");
    } catch {
      toast("Photo refusée : choisis une image JPEG ou PNG.", "warning");
    } finally {
      setBusy(false);
    }
  };

  const removePhoto = async () => {
    setBusy(true);
    const ok = await deletePhoto(candidateId);
    setBusy(false);
    if (!ok) return toast("Je n'ai pas pu retirer la photo.", "warning");
    setDesign(await fetchCvDesign(candidateId));
    setVersion((v) => v + 1);
  };

  if (!design) return null;
  const current = design.effective_template_id;
  const photoLabel = design.has_photo ? (design.show_photo ? "avec ta photo" : "sans photo") : "sans photo";

  return (
    <div className="rounded-xl bg-white border border-[#1A1918]/8">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-2 px-3 py-2.5 text-left cursor-pointer"
      >
        <span className="text-[12px] text-[#161615] tracking-tight">
          Mise en page : <span className="text-[#006045]">{templateName(current)}</span>
          <span className="text-[#1A1918]/55"> · {photoLabel}</span>
          {!design.is_explicit && <span className="text-[#1A1918]/45"> · choisie par défaut</span>}
        </span>
        <span className="ml-auto inline-flex items-center gap-1 text-[11px] text-[#006045]">
          {busy && <Loader2 className="h-3 w-3 animate-spin" />}
          {open ? "Fermer" : "Changer"}
          <ChevronDown className={cn("h-3 w-3 transition-transform", open && "rotate-180")} />
        </span>
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden"
          >
            <div className="px-3 pb-3 space-y-4 border-t border-[#1A1918]/6 pt-3">
              {design.mode === "original" && design.has_original && (
                <p className="text-[11px] text-[#1A1918]/60 tracking-tight">
                  Ton CV d&apos;origine reste disponible tel quel ; un CV adapté à une offre est
                  forcément recomposé, avec le modèle ci-dessous.
                </p>
              )}

              <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5">
                {cvTemplates.map((t) => (
                  <button
                    key={t.id}
                    type="button"
                    disabled={busy}
                    onClick={() => void apply({ template_id: t.id })}
                    className={cn(
                      "px-2.5 py-2 rounded-lg border text-left transition-colors cursor-pointer disabled:opacity-60",
                      current === t.id ? "border-[#006045]/50 bg-[#006045]/6" : "border-[#1A1918]/10 hover:border-[#1A1918]/30",
                    )}
                  >
                    <span className={cn("flex items-center gap-1 text-[11.5px] tracking-tight", current === t.id ? "text-[#006045]" : "text-[#1A1918]/80")}>
                      {current === t.id && <Check className="h-3 w-3" />}
                      {t.name}
                    </span>
                    <span className="block text-[10.5px] text-[#1A1918]/50 tracking-tight">{t.tagline}</span>
                  </button>
                ))}
              </div>

              <div className="flex flex-wrap items-center gap-2">
                {colorSwatches.map((sw) => (
                  <button
                    key={sw.id}
                    type="button"
                    disabled={busy}
                    onClick={() => void apply({ color_hex: sw.hex })}
                    title={sw.name}
                    aria-label={sw.name}
                    className={cn(
                      "h-6 w-6 rounded-full cursor-pointer ring-offset-2 transition-all",
                      design.color_hex === sw.hex ? "ring-2 ring-[#1A1918]/40" : "ring-1 ring-[#1A1918]/10 hover:scale-105",
                    )}
                    style={{ backgroundColor: sw.hex }}
                  />
                ))}
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <input
                  ref={fileRef}
                  type="file"
                  accept="image/jpeg,image/png"
                  className="hidden"
                  onChange={(e) => { void onPhoto(e.target.files?.[0]); e.target.value = ""; }}
                />
                {design.has_photo ? (
                  <>
                    <label className="inline-flex items-center gap-2 text-[12px] text-[#1A1918]/75 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={design.show_photo}
                        disabled={busy}
                        onChange={(e) => void apply({ show_photo: e.target.checked })}
                        className="accent-[#006045] h-3.5 w-3.5"
                      />
                      Afficher ma photo
                    </label>
                    <button type="button" onClick={() => fileRef.current?.click()} className="text-[11px] text-[#006045] hover:underline cursor-pointer">
                      Changer de photo
                    </button>
                    <button type="button" onClick={() => void removePhoto()} className="inline-flex items-center gap-1 text-[11px] text-[#1A1918]/55 hover:text-[#161615] cursor-pointer">
                      <Trash2 className="h-3 w-3" /> Retirer
                    </button>
                  </>
                ) : (
                  <button
                    type="button"
                    onClick={() => fileRef.current?.click()}
                    disabled={busy}
                    className="inline-flex items-center gap-1.5 rounded-full border border-[#1A1918]/15 px-3 py-1.5 text-[11px] text-[#161615] hover:border-[#161615]/40 cursor-pointer"
                  >
                    <Camera className="h-3 w-3" /> Ajouter ma photo
                  </button>
                )}
              </div>

              {withPreview && jobId && (
                <div className="space-y-1">
                  <p className="text-[10.5px] uppercase tracking-wider text-[#1A1918]/50">Aperçu du CV qui partira</p>
                  {preview ? (
                    // eslint-disable-next-line @next/next/no-img-element -- aperçu protégé, servi en blob
                    <img
                      src={preview}
                      alt="Première page du CV adapté"
                      className={cn(
                        "w-full rounded-lg border border-[#1A1918]/10 bg-white transition-opacity",
                        busy && "opacity-60",
                      )}
                    />
                  ) : (
                    <div className="h-[26rem] rounded-lg border border-[#1A1918]/10 bg-[#FAFAF8] flex items-center justify-center">
                      <Loader2 className="h-4 w-4 animate-spin text-[#006045]" />
                    </div>
                  )}
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
