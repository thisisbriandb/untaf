"use client";

/**
 * Une seule chose à faire, la plus utile, au lieu d'un tableau de bord.
 *
 * L'accueil empilait un appel à l'action, quatre raccourcis, une carte de
 * mission et le fil : trop pour quelqu'un qui arrive. On ne garde que le
 * prochain geste qui fait avancer une candidature — dans cet ordre : valider
 * ce qui est prêt à partir, relancer, envoyer les dossiers prêts, et à défaut
 * confier une mission.
 */

import { motion } from "framer-motion";
import { ArrowRight, FolderCheck, Mail, Radar, Send } from "lucide-react";
import type { Pipeline } from "@/lib/pipeline-client";

type Action = {
  key: string;
  icon: typeof Send;
  title: string;
  detail: string;
  cta: string;
  tone: "amber" | "green";
  onClick: () => void;
};

export function NextAction({
  pipeline,
  onOpenCandidatures,
  onLaunchMission,
}: {
  pipeline: Pipeline | null;
  onOpenCandidatures: () => void;
  onLaunchMission: () => void;
}) {
  const c = pipeline?.counts ?? {};
  const awaiting = c.awaiting ?? 0;
  const followups = c.followup_due ?? 0;
  const ready = (c.ready ?? 0) + (c.manual ?? 0) + (c.simulated ?? 0);

  const s = (n: number, one: string, many: string) => (n > 1 ? many : one);

  const action: Action =
    awaiting > 0
      ? {
          key: "awaiting", icon: Send, tone: "amber",
          title: `${awaiting} ${s(awaiting, "candidature attend", "candidatures attendent")} ton feu vert`,
          detail: "CV adapté et lettre prêts. Rien ne part sans toi.",
          cta: "Valider", onClick: onOpenCandidatures,
        }
      : followups > 0
        ? {
            key: "followups", icon: Mail, tone: "green",
            title: `${followups} ${s(followups, "relance est prête", "relances sont prêtes")}`,
            detail: "Sans réponse depuis une semaine : un message court relance le recruteur.",
            cta: "Relancer", onClick: onOpenCandidatures,
          }
        : ready > 0
          ? {
              key: "ready", icon: FolderCheck, tone: "green",
              title: `${ready} ${s(ready, "dossier prêt", "dossiers prêts")} à envoyer`,
              detail: "Je les ai préparés ; il reste à finir l'envoi sur le site de l'employeur.",
              cta: "Voir", onClick: onOpenCandidatures,
            }
          : {
              key: "mission", icon: Radar, tone: "green",
              title: "Confie-moi une mission",
              detail: "Je cherche, j'adapte ton CV pour chaque offre et je postule — tu valides.",
              cta: "Commencer", onClick: onLaunchMission,
            };

  const Icon = action.icon;
  return (
    <motion.button
      key={action.key}
      type="button"
      onClick={action.onClick}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -1 }}
      whileTap={{ scale: 0.99 }}
      className={`group w-full flex items-center gap-3.5 text-left px-4 py-3.5 rounded-2xl border transition-colors cursor-pointer ${
        action.tone === "amber"
          ? "border-amber-500/25 bg-amber-50/60 hover:border-amber-500/45"
          : "border-[#006045]/20 bg-[#006045]/[0.04] hover:border-[#006045]/40"
      }`}
    >
      <span
        className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full ${
          action.tone === "amber" ? "bg-amber-500/15 text-amber-700" : "bg-[#006045]/10 text-[#006045]"
        }`}
      >
        <Icon className="h-4 w-4 stroke-[1.6]" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-sm text-[#1A1918] tracking-tight">{action.title}</span>
        <span className="block text-xs font-light text-[#1A1918]/50 tracking-tight">{action.detail}</span>
      </span>
      <span className="flex shrink-0 items-center gap-1 text-xs text-[#006045]">
        {action.cta}
        <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
      </span>
    </motion.button>
  );
}
