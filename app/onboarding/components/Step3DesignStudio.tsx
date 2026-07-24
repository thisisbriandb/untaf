"use client";

import { motion } from "framer-motion";
import { Check } from "lucide-react";
import { cn } from "@/lib/utils";
import { colorSwatches, cvTemplates, ColorSwatch } from "../types";
import { FictionalCVCard } from "./FictionalCVCard";

interface Step3DesignStudioProps {
  selectedTemplate: string;
  setSelectedTemplate: (tplId: string) => void;
  selectedColor: string;
  setSelectedColor: (colorId: string) => void;
  cvLanguage: "fr" | "en";
  setCvLanguage: (lang: "fr" | "en") => void;
  showPhotoOnCv: boolean;
  setShowPhotoOnCv: (show: boolean) => void;
  userPhotoUrl: string | null;
  activeColorSwatch: ColorSwatch;
}

export function Step3DesignStudio({
  selectedTemplate,
  setSelectedTemplate,
  selectedColor,
  setSelectedColor,
  cvLanguage,
  setCvLanguage,
  showPhotoOnCv,
  setShowPhotoOnCv,
  userPhotoUrl,
  activeColorSwatch,
}: Step3DesignStudioProps) {
  return (
    <motion.div
      key="step3"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      transition={{ duration: 0.2 }}
      className="space-y-6"
    >
      {/* Toolbar Controls */}
      <div className="rounded-2xl border border-border bg-card p-4 flex flex-wrap items-center justify-between gap-4 shadow-sm">
        <div>
          <h3 className="font-bold text-sm text-foreground">3. Studio de Design & Typographie Typst</h3>
          <p className="text-[11px] text-muted-foreground">
            Modèle sélectionné : <span className="font-semibold text-primary">{selectedTemplate.toUpperCase()}</span>
          </p>
        </div>

        <div className="flex items-center gap-4">
          {/* Photo Toggle */}
          <label className="flex items-center gap-1.5 text-xs font-semibold cursor-pointer select-none">
            <input
              type="checkbox"
              checked={showPhotoOnCv}
              onChange={(e) => setShowPhotoOnCv(e.target.checked)}
              className="rounded accent-primary"
            />
            Photo visible
          </label>

          {/* Language Selector */}
          <div className="flex items-center gap-1 bg-muted p-1 rounded-lg text-xs font-semibold">
            <button
              type="button"
              onClick={() => setCvLanguage("fr")}
              className={cn("px-2 py-0.5 rounded transition", cvLanguage === "fr" && "bg-card text-foreground shadow-xs")}
            >
              FR
            </button>
            <button
              type="button"
              onClick={() => setCvLanguage("en")}
              className={cn("px-2 py-0.5 rounded transition", cvLanguage === "en" && "bg-card text-foreground shadow-xs")}
            >
              EN
            </button>
          </div>

          {/* Color Swatches */}
          <div className="flex items-center gap-1">
            {colorSwatches.map((swatch) => (
              <button
                key={swatch.id}
                type="button"
                title={swatch.name}
                onClick={() => setSelectedColor(swatch.id)}
                className={cn(
                  "h-5 w-5 rounded-full transition-transform hover:scale-110 flex items-center justify-center",
                  swatch.bg,
                  selectedColor === swatch.id && "ring-2 ring-offset-2 ring-primary scale-110"
                )}
              >
                {selectedColor === swatch.id && <Check className="h-3 w-3 text-white" />}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Template Cards Selection Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
        {cvTemplates.map((template) => (
          <FictionalCVCard
            key={template.id}
            template={template}
            isSelected={selectedTemplate === template.id}
            selectedColorHex={activeColorSwatch.hex}
            showPhoto={showPhotoOnCv}
            userPhotoUrl={userPhotoUrl}
            onClick={() => setSelectedTemplate(template.id)}
          />
        ))}
      </div>
    </motion.div>
  );
}
