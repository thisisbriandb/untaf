"use client";

import { useEffect, useRef, useState } from "react";
import { Check, Copy, Download, Eye, Loader2, PenLine, PenTool, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import { Markdown } from "./Markdown";
import { SignaturePad } from "./SignaturePad";
import {
  downloadLetterPdf,
  emptyLetter,
  fetchSignature,
  saveSignature,
  type CoverLetter,
} from "@/lib/letter-client";
import { useAlice } from "../alice-context";

interface CoverLetterEditorProps {
  candidateId: string | null;
  companyName?: string;
  jobTitle?: string;
  letter?: CoverLetter;
}

export function CoverLetterEditor({
  candidateId,
  companyName = "Entreprise",
  jobTitle,
  letter: incoming,
}: CoverLetterEditorProps) {
  const { submitQuery, isThinking } = useAlice();

  const [letter, setLetter] = useState<CoverLetter>(
    incoming ?? emptyLetter(companyName, jobTitle),
  );
  const [pane, setPane] = useState<"edit" | "preview">(incoming ? "preview" : "edit");
  const [copied, setCopied] = useState(false);
  const [showSignaturePad, setShowSignaturePad] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  const documentRef = useRef<HTMLDivElement>(null);

  // Une lettre fraîchement rédigée remplace celle affichée.
  useEffect(() => {
    if (incoming) {
      setLetter(incoming);
      setPane("preview");
    }
  }, [incoming]);

  // La signature enregistrée est appliquée sans rien redemander.
  useEffect(() => {
    if (!candidateId || letter.signature_image) return;
    fetchSignature(candidateId).then((image) => {
      if (image) setLetter((prev) => ({ ...prev, signature_image: image }));
    });
  }, [candidateId, letter.signature_image]);

  const handleCopy = async () => {
    const plain = [
      letter.subject && `Objet : ${letter.subject}`,
      "",
      letter.salutation,
      "",
      letter.body,
      "",
      letter.closing,
      "",
      letter.signature_name,
    ]
      .filter((l) => l !== undefined)
      .join("\n");
    await navigator.clipboard.writeText(plain);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  /**
   * Le PDF est compilé par le serveur et téléchargé directement — plus de
   * boîte d'impression du navigateur, et un rendu identique partout.
   */
  const handleDownloadPdf = async () => {
    setIsDownloading(true);
    const ok = await downloadLetterPdf(letter);
    setIsDownloading(false);
    if (!ok) setDownloadError("Le PDF n'a pas pu être généré. Réessaie.");
    else setDownloadError(null);
  };

  const suggestions = [
    jobTitle ? `Rends la lettre pour « ${jobTitle} » plus concise` : "Rends cette lettre plus concise",
    "Appuie-toi davantage sur mes réalisations chiffrées",
    "Adopte un ton plus direct",
  ];

  const setField = <K extends keyof CoverLetter>(key: K, value: CoverLetter[K]) =>
    setLetter((prev) => ({ ...prev, [key]: value }));

  return (
    <div className="h-full flex flex-col min-h-0 font-light tracking-tight text-[#1A1918]">
      {/* ── En-tête ── */}
      <div className="shrink-0 px-5 pt-4 pb-3 border-b border-[#1A1918]/8 space-y-3">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-sm font-normal text-[#1A1918] truncate">
              {jobTitle || letter.subject || "Lettre de motivation"}
            </p>
            <p className="text-xs text-[#1A1918]/50 truncate">
              {letter.recipient_company || companyName}
              {letter.grounded_on_experiences === false && letter.source !== "empty" && (
                <span className="text-[#006045]/80"> · sans tes expériences</span>
              )}
            </p>
          </div>
          <div className="flex items-center gap-1.5 shrink-0">
            <button
              type="button"
              onClick={handleCopy}
              aria-label="Copier la lettre"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-[#1A1918]/12 hover:border-[#1A1918]/30 text-xs transition-colors cursor-pointer"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-[#006045]" /> : <Copy className="w-3.5 h-3.5" />}
              {copied ? "Copié" : "Copier"}
            </button>
            <button
              type="button"
              onClick={handleDownloadPdf}
              disabled={isDownloading}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-[#006045] hover:bg-[#004d37] text-white text-xs transition-colors cursor-pointer disabled:opacity-40"
            >
              {isDownloading ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Download className="w-3.5 h-3.5" />
              )}
              PDF
            </button>
          </div>
        </div>

        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-1 p-0.5 rounded-full bg-[#1A1918]/4 w-fit">
            {([
              { id: "edit", label: "Rédiger", icon: PenLine },
              { id: "preview", label: "Document", icon: Eye },
            ] as const).map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                type="button"
                onClick={() => setPane(id)}
                className={cn(
                  "flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs transition-colors cursor-pointer",
                  pane === id ? "bg-white text-[#1A1918] shadow-sm" : "text-[#1A1918]/50 hover:text-[#1A1918]",
                )}
              >
                <Icon className="w-3.5 h-3.5 stroke-[1.5]" />
                {label}
              </button>
            ))}
          </div>

          <button
            type="button"
            onClick={() => setShowSignaturePad((v) => !v)}
            className={cn(
              "flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-[11px] transition-colors cursor-pointer",
              letter.signature_image
                ? "border-[#006045]/35 text-[#006045]"
                : "border-[#1A1918]/12 text-[#1A1918]/55 hover:border-[#1A1918]/30",
            )}
          >
            <PenTool className="w-3.5 h-3.5 stroke-[1.5]" />
            {letter.signature_image ? "Signature enregistrée" : "Ajouter ma signature"}
          </button>
        </div>

        {downloadError && (
          <p className="text-[11px] text-red-600/80 tracking-tight">{downloadError}</p>
        )}

        {showSignaturePad && candidateId && (
          <div className="pt-1">
            <SignaturePad
              onCancel={() => setShowSignaturePad(false)}
              onSave={async (dataUrl) => {
                await saveSignature(candidateId, dataUrl);
                setField("signature_image", dataUrl);
                setShowSignaturePad(false);
              }}
            />
          </div>
        )}
      </div>

      {/* ── Corps ── */}
      <div className="flex-1 min-h-0 p-5">
        {pane === "edit" ? (
          <div className="scroll-discreet h-full overflow-y-auto space-y-3">
            <div className="space-y-1.5">
              <label className="text-[11px] font-mono uppercase tracking-wider text-[#1A1918]/55">
                Objet
              </label>
              <input
                type="text"
                value={letter.subject}
                onChange={(e) => setField("subject", e.target.value)}
                className="w-full px-3.5 py-2 rounded-xl border border-[#EDECEA] focus:border-[#006045] focus:outline-none bg-white text-sm"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-[11px] font-mono uppercase tracking-wider text-[#1A1918]/55">
                Corps de la lettre — Markdown
              </label>
              <textarea
                value={letter.body}
                onChange={(e) => setField("body", e.target.value)}
                spellCheck
                className="scroll-discreet w-full min-h-[22rem] p-4 rounded-xl border border-[#EDECEA] focus:border-[#006045] focus:outline-none bg-[#FAFAF8] text-sm leading-relaxed resize-none font-mono"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-[11px] font-mono uppercase tracking-wider text-[#1A1918]/55">
                Formule de politesse
              </label>
              <textarea
                rows={2}
                value={letter.closing}
                onChange={(e) => setField("closing", e.target.value)}
                className="w-full px-3.5 py-2 rounded-xl border border-[#EDECEA] focus:border-[#006045] focus:outline-none bg-white text-sm resize-none"
              />
            </div>
          </div>
        ) : (
          /* ── Le document, mis en page selon les conventions ── */
          <div className="scroll-discreet h-full overflow-y-auto rounded-xl border border-[#EDECEA] bg-white">
            <div
              ref={documentRef}
              className="px-10 py-9 text-[13px] leading-[1.65] text-[#1A1918]"
              style={{ fontFamily: 'Georgia, "Times New Roman", serif' }}
            >
              <div className="lm-head flex justify-between gap-12 mb-9">
                <div className="lm-block text-[11.5px] leading-[1.5]">
                  <strong className="block text-[13px] mb-0.5 font-semibold">
                    {letter.sender_name || "—"}
                  </strong>
                  {letter.sender_contact.map((c) => (
                    <div key={c} className="lm-muted text-[#55524f]">{c}</div>
                  ))}
                </div>
                <div className="lm-block text-[11.5px] leading-[1.5] text-right">
                  <strong className="block text-[13px] mb-0.5 font-semibold">
                    {letter.recipient_name}
                  </strong>
                  <div className="lm-muted text-[#55524f]">
                    {letter.recipient_company || companyName}
                  </div>
                </div>
              </div>

              <div className="lm-date text-right mb-7 text-[12px]">
                {letter.place ? `${letter.place}, le ${letter.date}` : `Le ${letter.date}`}
              </div>

              {letter.subject && (
                <p className="lm-subject mb-6">
                  <strong className="font-semibold">Objet :</strong> {letter.subject}
                </p>
              )}

              <p className="lm-salutation mb-4">{letter.salutation}</p>

              <div className="lm-body">
                <Markdown source={letter.body} className="text-[13px] text-[#1A1918]" />
              </div>

              <p className="lm-closing my-6">{letter.closing}</p>

              <div className="lm-sign text-right">
                {letter.signature_image && (
                  <img
                    src={letter.signature_image}
                    alt="Signature"
                    className="max-h-[68px] ml-auto mb-1"
                  />
                )}
                <span>{letter.signature_name || letter.sender_name}</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ── Relais vers la conversation ── */}
      <div className="shrink-0 border-t border-[#1A1918]/8 bg-[#FAFAF8] px-5 py-3 space-y-2">
        <div className="flex items-center gap-1.5">
          <Sparkles className="w-3 h-3 stroke-[1.6] text-[#006045] shrink-0" />
          <span className="text-[11px] font-mono uppercase tracking-wider text-[#1A1918]/55">
            Faire retravailler par Alice
          </span>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {suggestions.map((q) => (
            <button
              key={q}
              type="button"
              onClick={() => void submitQuery(q)}
              disabled={isThinking}
              className="px-2.5 py-1.5 rounded-full border border-[#1A1918]/10 bg-white text-[11px] font-normal text-[#1A1918]/65 tracking-tight hover:border-[#006045]/40 hover:text-[#006045] transition-colors cursor-pointer disabled:opacity-40 text-left"
            >
              {q}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
