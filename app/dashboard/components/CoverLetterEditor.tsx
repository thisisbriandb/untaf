"use client";

import { useEffect, useRef, useState } from "react";
import { Check, Copy, Download, Eye, PenLine, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import { Markdown } from "./Markdown";
import { useAlice } from "../alice-context";

interface CoverLetterEditorProps {
  companyName?: string;
  jobTitle?: string;
  initialContent?: string;
}

const EMPTY_LETTER = `Madame, Monsieur,

_Demande à Alice de rédiger cette lettre, ou écris-la ici._

Cordialement,`;

export function CoverLetterEditor({
  companyName = "Entreprise",
  jobTitle,
  initialContent,
}: CoverLetterEditorProps) {
  const { submitQuery, isThinking } = useAlice();

  const [content, setContent] = useState(initialContent || EMPTY_LETTER);
  const [pane, setPane] = useState<"edit" | "preview">(
    initialContent ? "preview" : "edit"
  );
  const [copied, setCopied] = useState(false);

  const previewRef = useRef<HTMLDivElement>(null);

  // Une nouvelle lettre rédigée par Alice doit remplacer celle affichée : sans
  // ça, rouvrir le Canvas pour une autre offre garderait le texte précédent.
  useEffect(() => {
    if (initialContent) {
      setContent(initialContent);
      setPane("preview");
    }
  }, [initialContent]);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  /**
   * Export : on imprime le rendu déjà à l'écran plutôt que de refaire un
   * chemin Markdown → HTML. Un seul convertisseur, donc un seul comportement.
   */
  const handleDownloadPdf = () => {
    const rendered = previewRef.current?.innerHTML;
    if (!rendered) {
      setPane("preview");
      return;
    }

    const printWindow = window.open("", "_blank");
    if (!printWindow) return;

    const title = jobTitle ? `${jobTitle} — ${companyName}` : companyName;

    printWindow.document.write(`
      <!DOCTYPE html>
      <html lang="fr">
        <head>
          <meta charset="utf-8" />
          <title>Lettre de motivation — ${title}</title>
          <style>
            body {
              font-family: Georgia, 'Times New Roman', serif;
              max-width: 17cm;
              margin: 2.5cm auto;
              color: #1A1918;
              line-height: 1.7;
              font-size: 12pt;
            }
            p { margin: 0 0 1em; }
            ul, ol { margin: 0 0 1em; padding-left: 1.2em; }
            li { margin-bottom: 0.4em; }
            li > span:first-child { display: none; }
            strong { font-weight: 600; }
            a { color: #006045; }
            blockquote {
              border-left: 2px solid #006045;
              padding-left: 1em;
              margin-left: 0;
              font-style: italic;
            }
          </style>
        </head>
        <body>${rendered}</body>
      </html>
    `);
    printWindow.document.close();
    printWindow.focus();
    printWindow.print();
  };

  const suggestions = [
    jobTitle
      ? `Rends la lettre pour « ${jobTitle} » plus concise`
      : "Rends cette lettre plus concise",
    "Insiste davantage sur mes compétences techniques",
    "Adopte un ton plus direct",
  ];

  return (
    <div className="h-full flex flex-col min-h-0 font-light tracking-tight text-[#1A1918]">
      {/* ── En-tête ── */}
      <div className="shrink-0 px-5 pt-4 pb-3 border-b border-[#1A1918]/8 space-y-3">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-sm font-normal text-[#1A1918] truncate">
              {jobTitle || "Lettre de motivation"}
            </p>
            <p className="text-xs text-[#1A1918]/50 truncate">{companyName}</p>
          </div>
          <div className="flex items-center gap-1.5 shrink-0">
            <button
              type="button"
              onClick={handleCopy}
              aria-label="Copier la lettre"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-[#1A1918]/12 hover:border-[#1A1918]/30 text-xs transition-colors cursor-pointer"
            >
              {copied ? (
                <Check className="w-3.5 h-3.5 text-[#006045]" />
              ) : (
                <Copy className="w-3.5 h-3.5" />
              )}
              {copied ? "Copié" : "Copier"}
            </button>
            <button
              type="button"
              onClick={handleDownloadPdf}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-[#006045] hover:bg-[#004d37] text-white text-xs transition-colors cursor-pointer"
            >
              <Download className="w-3.5 h-3.5" />
              PDF
            </button>
          </div>
        </div>

        <div className="flex items-center gap-1 p-0.5 rounded-full bg-[#1A1918]/4 w-fit">
          {(
            [
              { id: "edit", label: "Rédiger", icon: PenLine },
              { id: "preview", label: "Aperçu", icon: Eye },
            ] as const
          ).map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              type="button"
              onClick={() => setPane(id)}
              className={cn(
                "flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs transition-colors cursor-pointer",
                pane === id
                  ? "bg-white text-[#1A1918] shadow-sm"
                  : "text-[#1A1918]/50 hover:text-[#1A1918]"
              )}
            >
              <Icon className="w-3.5 h-3.5 stroke-[1.5]" />
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* ── Corps ── */}
      <div className="flex-1 min-h-0 p-5">
        {pane === "edit" ? (
          <textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder="Rédige ta lettre en Markdown…"
            spellCheck
            className="scroll-discreet w-full h-full p-4 rounded-xl border border-[#EDECEA] focus:border-[#006045] focus:outline-none bg-[#FAFAF8] text-sm font-light text-[#1A1918] leading-relaxed resize-none tracking-tight font-mono"
          />
        ) : (
          <div className="scroll-discreet h-full overflow-y-auto rounded-xl border border-[#EDECEA] bg-white p-6">
            <div ref={previewRef}>
              <Markdown source={content} className="text-[#1A1918]/85" />
            </div>
          </div>
        )}
      </div>

      {/* ── Relais vers la conversation ── */}
      <div className="shrink-0 border-t border-[#1A1918]/8 bg-[#FAFAF8] px-5 py-3 space-y-2">
        <div className="flex items-center gap-1.5">
          <Sparkles className="w-3 h-3 stroke-[1.6] text-[#006045] shrink-0" />
          <span className="text-[10px] font-mono uppercase tracking-wider text-[#1A1918]/40">
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
              className="px-2.5 py-1.5 rounded-full border border-[#1A1918]/10 bg-white text-[11px] font-light text-[#1A1918]/65 tracking-tight hover:border-[#006045]/40 hover:text-[#006045] transition-colors cursor-pointer disabled:opacity-40 text-left"
            >
              {q}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
