import type { Stage } from "./pipeline-client";

/**
 * Une encre, plusieurs intensités ; le vert d'eau pour les bonnes nouvelles : plein quand la candidature attend
 * l'utilisateur, contour quand elle est prête, teinté quand elle avance
 * seule, estompé quand elle est close. Aucune couleur à apprendre.
 */
export const STAGE_TONE: Record<Stage, string> = {
  awaiting: "bg-[#161615] text-white",
  manual: "bg-[#161615] text-white",
  ready: "ring-1 ring-inset ring-[#161615]/30 text-[#161615]",
  simulated: "border border-dashed border-[#161615]/30 text-[#161615]/70",
  applied: "bg-[#006045]/10 text-[#006045]",
  interview: "bg-[#006045]/15 text-[#006045] font-medium",
  offer: "bg-[#006045] text-white font-medium",
  to_prepare: "bg-[#1A1918]/5 text-[#1A1918]/60",
  rejected: "bg-[#1A1918]/5 text-[#1A1918]/45",
  closed: "bg-[#1A1918]/5 text-[#1A1918]/45",
};
