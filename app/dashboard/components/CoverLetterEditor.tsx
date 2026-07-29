"use client";

import { useState } from "react";
import { Copy, Check, Download } from "lucide-react";

interface CoverLetterEditorProps {
  companyName?: string;
  initialContent?: string;
  onClose?: () => void;
}

const DEFAULT_LETTER = `Madame, Monsieur,

C'est avec un grand intérêt que je vous adresse ma candidature pour le poste de Développeur Full Stack au sein de votre entreprise.

Fort de mon expérience dans la conception d'applications web modernes et performantes (React, TypeScript, FastAPI), j'ai suivi avec attention l'évolution de vos projets et serais ravi d'apporter mes compétences à vos équipes.

Restant à votre entière disposition pour un échange.

Cordialement,
[Ton Nom]`;

export function CoverLetterEditor({
  companyName = "Entreprise",
  initialContent = DEFAULT_LETTER,
}: CoverLetterEditorProps) {
  const [content, setContent] = useState(initialContent);
  const [copied, setCopied] = useState(false);
  const [isExporting, setIsExporting] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownloadPdf = () => {
    setIsExporting(true);
    // Trigger browser print/pdf generation smoothly
    const printWindow = window.open("", "_blank");
    if (!printWindow) {
      setIsExporting(false);
      return;
    }

    printWindow.document.write(`
      <!DOCTYPE html>
      <html>
        <head>
          <title>Lettre de Motivation — ${companyName}</title>
          <style>
            body {
              font-family: system-ui, -apple-system, sans-serif;
              padding: 40px;
              color: #1A1918;
              line-height: 1.6;
              white-space: pre-wrap;
              font-size: 14px;
            }
          </style>
        </head>
        <body>${content}</body>
      </html>
    `);
    printWindow.document.close();
    printWindow.print();
    setIsExporting(false);
  };

  return (
    <div className="flex flex-col h-full space-y-4 font-light tracking-tight text-[#1A1918]">
      {/* Header Actions */}
      <div className="flex items-center justify-between pb-3 border-b border-[#1A1918]/8">
        <div>
          <h2 className="text-base font-medium text-[#1A1918]">
            Lettre de Motivation
          </h2>
          <p className="text-xs text-[#1A1918]/50">{companyName}</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleCopy}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-[#1A1918]/15 hover:border-[#1A1918]/30 text-xs text-[#1A1918] transition-colors cursor-pointer"
          >
            {copied ? (
              <Check className="w-3.5 h-3.5 text-[#006045]" />
            ) : (
              <Copy className="w-3.5 h-3.5" />
            )}
            <span>{copied ? "Copié" : "Copier"}</span>
          </button>
          <button
            type="button"
            onClick={handleDownloadPdf}
            disabled={isExporting}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-[#006045] hover:bg-[#004d37] text-white text-xs transition-colors cursor-pointer"
          >
            <Download className="w-3.5 h-3.5" />
            <span>PDF</span>
          </button>
        </div>
      </div>

      {/* Editor Area */}
      <div className="flex-1 min-h-[350px] relative">
        <textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder="Rédige ou édite ta lettre..."
          className="w-full h-full p-4 rounded-xl border border-[#EDECEA] focus:border-[#006045] focus:outline-none bg-[#FAFAF8] text-sm font-light text-[#1A1918] leading-relaxed resize-none tracking-tight"
        />
      </div>
    </div>
  );
}
