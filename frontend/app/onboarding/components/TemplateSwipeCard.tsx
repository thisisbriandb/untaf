"use client";

import { useState, useEffect } from "react";
import { motion, useMotionValue, useTransform } from "framer-motion";
import { Heart, X, Sparkles, Check } from "lucide-react";
import { cvTemplates } from "../types";
import { apiFetch } from "@/lib/api";
import { API_BASE_URL } from "@/lib/config";

interface TemplateSwipeCardProps {
  template: (typeof cvTemplates)[0];
  candidateData: any;
  onMatch: (templateId: string) => void;
  onPass: () => void;
  isTopCard: boolean;
}

export function TemplateSwipeCard({
  template,
  candidateData,
  onMatch,
  onPass,
  isTopCard,
}: TemplateSwipeCardProps) {
  const [svgContent, setSvgContent] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  const x = useMotionValue(0);
  const rotate = useTransform(x, [-200, 200], [-12, 12]);
  const opacity = useTransform(x, [-200, -100, 0, 100, 200], [0.4, 1, 1, 1, 0.4]);
  
  // Badge overlay indicators on drag
  const matchBadgeOpacity = useTransform(x, [10, 100], [0, 1]);
  const passBadgeOpacity = useTransform(x, [-100, -10], [1, 0]);

  useEffect(() => {
    let isMounted = true;
    const fetchSvg = async () => {
      try {
        const payload = {
          template_id: template.id,
          color_hex: "#161615",
          show_photo: candidateData.showPhoto ?? true,
          photo_url: candidateData.photoUrl || template.photo,
          full_name: candidateData.fullName || "Briand Bataillon",
          headline: candidateData.headline || "Développeur Full-Stack",
          summary: candidateData.summary || "Spécialiste dans la conception d'applications web robustes et réactives.",
          email: candidateData.email || "briand@example.com",
          phone: candidateData.phone || "06 12 34 56 78",
          location: "France",
          skills: candidateData.skills || ["React", "Python", "Typst", "FastAPI"],
          experiences: candidateData.experiences || [],
          education: candidateData.education || [],
          languages: candidateData.languages || [],
        };

        const res = await apiFetch(`${API_BASE_URL}/api/candidates/render-preview-svg`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

        if (res.ok) {
          const text = await res.text();
          if (isMounted) {
            setSvgContent(text);
            setLoading(false);
          }
        }
      } catch (err) {
        console.error("Erreur de chargement SVG Swipe:", err);
      }
    };

    fetchSvg();
    return () => {
      isMounted = false;
    };
  }, [template.id, candidateData]);

  const handleDragEnd = (_: any, info: any) => {
    if (info.offset.x > 120) {
      onMatch(template.id);
    } else if (info.offset.x < -120) {
      onPass();
    }
  };

  if (!isTopCard) {
    return (
      <div className="absolute inset-0 bg-white rounded-3xl border border-[#EFECE6] shadow-md p-4 flex flex-col items-center justify-center text-[#1A1918]/60 scale-95 opacity-50 pointer-events-none">
        <span className="font-serif text-lg font-medium">{template.name}</span>
      </div>
    );
  }

  return (
    <motion.div
      style={{ x, rotate, opacity }}
      drag="x"
      dragConstraints={{ left: 0, right: 0 }}
      onDragEnd={handleDragEnd}
      className="absolute inset-0 bg-white rounded-3xl border border-[#EFECE6] shadow-xl p-5 flex flex-col justify-between cursor-grab active:cursor-grabbing touch-none overflow-hidden select-none z-20"
    >
      {/* Visual Badges overlay during drag */}
      <motion.div
        style={{ opacity: matchBadgeOpacity }}
        className="absolute top-8 left-8 z-30 bg-[#161615] text-white px-4 py-1.5 rounded-full font-sans font-bold text-xs uppercase tracking-wider flex items-center gap-1.5 shadow-lg pointer-events-none"
      >
        <Heart className="h-4 w-4 fill-white" />
        <span>Match !</span>
      </motion.div>

      <motion.div
        style={{ opacity: passBadgeOpacity }}
        className="absolute top-8 right-8 z-30 bg-rose-600 text-white px-4 py-1.5 rounded-full font-sans font-bold text-xs uppercase tracking-wider flex items-center gap-1.5 shadow-lg pointer-events-none"
      >
        <X className="h-4 w-4" />
        <span>Suivant</span>
      </motion.div>

      {/* Header Info */}
      <div className="flex items-center justify-between border-b border-[#EFECE6] pb-3 shrink-0">
        <div>
          <span className="text-[11px] font-sans uppercase tracking-widest text-[#161615] font-semibold">
            Modèle Typst {template.layout}
          </span>
          <h3 className="text-xl font-serif font-bold text-[#1A1918]">{template.name}</h3>
        </div>
        <div className="h-8 w-8 rounded-full bg-[#F4F1EA] flex items-center justify-center text-[#161615]">
          <Sparkles className="h-4 w-4" />
        </div>
      </div>

      {/* Live SVG Container */}
      <div className="relative flex-1 bg-[#FBF9F5] rounded-xl my-3 p-2 overflow-hidden flex items-center justify-center border border-[#EFECE6]/60">
        {loading ? (
          <div className="flex flex-col items-center justify-center gap-3 p-6 text-center text-xs text-[#1A1918]/70 font-sans">
            <div className="relative flex items-center justify-center">
              <div className="h-10 w-10 border-3 border-[#161615]/20 border-t-[#161615] rounded-full animate-spin"></div>
              <Sparkles className="h-4 w-4 text-[#161615] absolute" />
            </div>
            <div className="space-y-1">
              <span className="font-semibold text-[#1A1918] block font-serif">Rendu Typst Vectoriel en cours</span>
              <span className="text-[11px] text-[#1A1918]/50 block">Compilation du template {template.name}...</span>
            </div>
          </div>
        ) : svgContent ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.3 }}
            className="w-full h-full flex items-center justify-center [&>svg]:w-full [&>svg]:h-auto [&>svg]:max-h-[380px] [&>svg]:shadow-sm [&>svg]:rounded"
            dangerouslySetInnerHTML={{ __html: svgContent }}
          />
        ) : (
          <div className="text-xs text-[#1A1918]/60 font-sans">Aperçu indisponible</div>
        )}
      </div>

      {/* Action Buttons */}
      <div className="flex items-center justify-center gap-6 pt-2 shrink-0">
        <button
          onClick={() => !loading && onPass()}
          disabled={loading}
          type="button"
          className="h-12 w-12 rounded-full border border-[#EFECE6] bg-[#FBF9F5] text-slate-500 flex items-center justify-center hover:bg-rose-50 hover:border-rose-200 hover:text-rose-600 transition-all shadow-sm active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed"
          title="Passer au suivant"
        >
          <X className="h-5 w-5" />
        </button>

        <button
          onClick={() => !loading && onMatch(template.id)}
          disabled={loading}
          type="button"
          className="h-14 px-6 rounded-full bg-[#161615] text-white flex items-center justify-center gap-2 font-sans font-medium text-sm hover:bg-[#000000] transition-all shadow-md active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <Heart className="h-5 w-5 fill-white" />
          <span>{loading ? "Chargement du modèle..." : "Choisir ce modèle"}</span>
        </button>
      </div>
    </motion.div>
  );
}
