"use client";

import { Check } from "lucide-react";
import { cn } from "@/lib/utils";
import { CVTemplate } from "../types";

interface FictionalCVCardProps {
  template: CVTemplate;
  isSelected: boolean;
  selectedColorHex: string;
  showPhoto: boolean;
  userPhotoUrl: string | null;
  onClick: () => void;
}

export function FictionalCVCard({
  template,
  isSelected,
  selectedColorHex,
  showPhoto,
  userPhotoUrl,
  onClick,
}: FictionalCVCardProps) {
  const isSidebar = template.layout === "left-sidebar" || template.layout === "creative";
  const isHeader = template.layout === "top-header";
  const photoToDisplay = userPhotoUrl || template.photo;

  return (
    <div
      onClick={onClick}
      className={cn(
        "group relative cursor-pointer flex flex-col rounded-2xl border bg-card p-3 transition-all duration-200 hover:-translate-y-1.5 hover:shadow-xl",
        isSelected
          ? "border-primary ring-2 ring-primary shadow-lg"
          : "border-border hover:border-muted-foreground/40"
      )}
    >
      {/* Top Selection Badge */}
      <div className="flex items-center justify-between pb-2 mb-2 border-b border-border/40">
        <span className="rounded bg-muted px-2 py-0.5 text-[11px] font-bold text-foreground">
          {template.badge}
        </span>
        {isSelected ? (
          <span className="inline-flex items-center gap-1 rounded-full bg-primary px-2.5 py-0.5 text-[11px] font-bold text-primary-foreground shadow-sm">
            <Check className="h-3 w-3" />
            Sélectionné
          </span>
        ) : (
          <span className="text-[11px] font-semibold text-muted-foreground group-hover:text-primary transition">
            Choisir ce modèle
          </span>
        )}
      </div>

      {/* Realistic Fictional A4 Document Visual Preview */}
      <div className="p-2 bg-slate-100 dark:bg-slate-900 rounded-xl">
        <div className="relative aspect-[3/4] w-full rounded-lg border border-slate-200 bg-white p-3 shadow-sm overflow-hidden text-[7px] text-slate-800 flex flex-col justify-between select-none">
          {/* Header element with Photo & Candidate Info */}
          {isHeader ? (
            <div
              className="p-2 rounded-t text-white -mx-3 -mt-3 mb-2 flex items-center gap-2"
              style={{ backgroundColor: selectedColorHex }}
            >
              {showPhoto && (
                <img
                  src={photoToDisplay}
                  alt={template.fictionalName}
                  className="h-8 w-8 rounded-full object-cover border border-white/50 shrink-0"
                />
              )}
              <div className="flex-1 overflow-hidden">
                <p className="font-extrabold uppercase text-[8px] tracking-tight truncate">
                  {template.fictionalName}
                </p>
                <p className="text-[6px] opacity-90 truncate">{template.fictionalRole}</p>
                <p className="text-[5px] opacity-75 truncate">{template.email} • {template.location}</p>
              </div>
            </div>
          ) : (
            <div className="border-b border-slate-200 pb-1.5 mb-1.5 flex items-center gap-2">
              {showPhoto && (
                <img
                  src={photoToDisplay}
                  alt={template.fictionalName}
                  className="h-8 w-8 rounded-full object-cover border border-slate-200 shrink-0"
                />
              )}
              <div className="flex-1 overflow-hidden">
                <p
                  className="font-extrabold uppercase text-[8.5px] tracking-tight truncate"
                  style={{ color: selectedColorHex }}
                >
                  {template.fictionalName}
                </p>
                <p className="text-[6px] text-slate-600 font-semibold truncate">
                  {template.fictionalRole}
                </p>
                <p className="text-[5px] text-slate-400 truncate">{template.email} • {template.location}</p>
              </div>
            </div>
          )}

          {/* Document Content Columns */}
          <div className="flex-1 flex gap-2">
            {isSidebar && (
              <div className="w-1/3 bg-slate-50 p-1 rounded border-r border-slate-100 space-y-1">
                <div>
                  <p className="font-bold text-[5.5px] uppercase tracking-wider mb-0.5" style={{ color: selectedColorHex }}>
                    Compétences
                  </p>
                  <div className="flex flex-wrap gap-0.5">
                    {template.skills.slice(0, 3).map((sk, i) => (
                      <span key={i} className="rounded-xs bg-slate-200 px-1 py-0.2 text-[4.5px] font-semibold">
                        {sk}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            )}

            <div className={cn("flex-1 space-y-1.5", isSidebar ? "w-2/3" : "w-full")}>
              <div>
                <p className="font-bold text-[5.5px] uppercase tracking-wider mb-0.5" style={{ color: selectedColorHex }}>
                  Profil Professionnel
                </p>
                <p className="text-[5px] text-slate-600 leading-tight line-clamp-2">
                  {template.summary}
                </p>
              </div>

              <div>
                <div className="flex justify-between items-center mb-0.5">
                  <span className="font-bold text-[5.5px] text-slate-800">Expérience Principale</span>
                  <span className="text-[4.5px] text-slate-400">2021 - Présent</span>
                </div>
                <p className="text-[5px] text-slate-500 leading-tight">
                  Conception & architecture de solutions logicielles scalables.
                </p>
              </div>

              {!isSidebar && (
                <div>
                  <p className="font-bold text-[5.5px] uppercase tracking-wider mb-0.5" style={{ color: selectedColorHex }}>
                    Compétences
                  </p>
                  <div className="flex flex-wrap gap-0.5">
                    {template.skills.slice(0, 4).map((sk, i) => (
                      <span key={i} className="rounded-xs bg-slate-100 px-1 py-0.2 text-[4.5px] font-semibold border border-slate-200">
                        {sk}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className="border-t border-slate-100 pt-0.5 mt-1 text-[5px] text-slate-400 flex justify-between">
            <span>{template.location}</span>
            <span>Typst cv-engine</span>
          </div>
        </div>
      </div>

      <div className="pt-2 px-1">
        <h5 className="font-bold text-xs text-foreground group-hover:text-primary transition">
          {template.name}
        </h5>
        <p className="text-[11px] text-muted-foreground mt-0.5 line-clamp-1">
          {template.description}
        </p>
      </div>
    </div>
  );
}
