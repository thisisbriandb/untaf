"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { ArrowRight, Loader2, X } from "lucide-react";
import { AlicePresence } from "@/app/onboarding/components/AlicePresence";
import { importJob, MIN_OFFER_LENGTH, type ImportedJob } from "@/lib/tailor-client";

/**
 * Coller une offre trouvée ailleurs.
 *
 * L'annonce rejoint la liste du candidat quel que soit son score : c'est lui
 * qui l'a choisie. Le score est rendu quand même, avec ses motifs.
 */
export function ImportJobDialog({
  candidateId,
  onClose,
  onImported,
}: {
  candidateId: string;
  onClose: () => void;
  onImported: (job: ImportedJob) => void;
}) {
  const [text, setText] = useState("");
  const [url, setUrl] = useState("");
  const [isImporting, setIsImporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const tooShort = text.trim().length < MIN_OFFER_LENGTH;

  const submit = async () => {
    if (tooShort || isImporting) return;
    setIsImporting(true);
    setError(null);
    const job = await importJob(candidateId, text.trim(), url.trim() || undefined);
    setIsImporting(false);
    if (job) onImported(job);
    else setError("Je n'ai pas réussi à lire cette offre. Réessaie dans un instant.");
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-[60] flex items-center justify-center bg-[#FAFAF8]/92 backdrop-blur-sm px-4"
    >
      <button
        type="button"
        onClick={onClose}
        aria-label="Fermer"
        className="absolute top-5 right-6 p-2 rounded-full text-[#1A1918]/55 hover:text-[#1A1918] hover:bg-[#1A1918]/5 transition-colors cursor-pointer"
      >
        <X className="w-4 h-4 stroke-[1.4]" />
      </button>

      <motion.div
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
        className="w-full max-w-[560px] flex flex-col items-center gap-5"
      >
        <AlicePresence emotion={isImporting ? "working" : "listening"} />

        <p className="text-center text-lg md:text-xl font-normal text-[#1A1918]/85 tracking-tight">
          {isImporting ? "Je lis l'annonce…" : "Colle l'offre qui t'intéresse"}
        </p>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            void submit();
          }}
          className="w-full space-y-3"
        >
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Le texte complet de l'annonce : intitulé, entreprise, missions, profil recherché…"
            rows={10}
            maxLength={30000}
            disabled={isImporting}
            autoFocus
            aria-label="Texte de l'offre"
            className="w-full resize-none rounded-2xl border border-[#EDECEA] bg-white px-4 py-3 text-sm font-light text-[#1A1918] placeholder:text-[#1A1918]/50 tracking-tight focus:outline-none focus:border-[#161615] disabled:opacity-60"
          />
          <input
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="Lien de l'annonce (facultatif)"
            maxLength={2000}
            disabled={isImporting}
            aria-label="Lien de l'annonce"
            className="w-full rounded-full border border-[#EDECEA] bg-white px-4 py-2.5 text-sm font-light text-[#1A1918] placeholder:text-[#1A1918]/50 tracking-tight focus:outline-none focus:border-[#161615] disabled:opacity-60"
          />

          {error && (
            <p className="text-xs font-normal text-[#B42318] tracking-tight text-center">{error}</p>
          )}

          <button
            type="submit"
            disabled={tooShort || isImporting}
            className="flex items-center justify-center gap-2 w-full px-4 py-3 rounded-full bg-[#006045] text-white text-sm font-light tracking-tight hover:bg-[#004d37] transition-colors cursor-pointer disabled:opacity-40"
          >
            {isImporting ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <ArrowRight className="w-4 h-4 stroke-[1.6]" />
            )}
            {isImporting ? "Analyse en cours" : "Ajouter à ma liste"}
          </button>
        </form>
      </motion.div>
    </motion.div>
  );
}
