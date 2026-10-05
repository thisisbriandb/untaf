"use client";

import { motion } from "framer-motion";
import { ArrowRight, CheckCircle2 } from "lucide-react";

interface WelcomeChoiceStepProps {
  onSelectStudio: () => void;
  onSelectBypass: () => void;
}

export function WelcomeChoiceStep({
  onSelectStudio,
  onSelectBypass,
}: WelcomeChoiceStepProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-3xl border border-border bg-card p-8 space-y-8 shadow-xl text-center"
    >
      <div className="max-w-2xl mx-auto space-y-3">
        <h2 className="text-3xl font-extrabold tracking-tight text-foreground">
          Optimisez vos chances de décrocher des entretiens
        </h2>

        <p className="text-sm text-muted-foreground leading-relaxed">
          Créez un CV optimisé pour les recruteurs et les systèmes ATS afin
          d'améliorer vos opportunités professionnelles.
        </p>
      </div>

      {/* Strategic Options Choice */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 text-left max-w-4xl mx-auto">
        {/* Option A: Full Refonte Studio */}
        <div
          onClick={onSelectStudio}
          className="group relative cursor-pointer flex flex-col justify-between rounded-2xl border-2 border-primary/60 bg-primary/5 p-6 transition-all duration-300 hover:-translate-y-1 hover:border-primary hover:shadow-xl"
        >
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="rounded-full bg-primary px-3 py-0.5 text-[11px] font-bold text-primary-foreground">
                Recommandé
              </span>
            </div>

            <h3 className="font-extrabold text-lg text-foreground group-hover:text-primary transition">
              Lancer la refonte intelligente de mon CV
            </h3>

            <p className="text-xs text-muted-foreground leading-relaxed">
              Choisissez un modèle professionnel, personnalisez votre CV
              automatiquement et optimisez-le pour les recruteurs.
            </p>
          </div>

          <div className="mt-6 flex items-center gap-2 text-xs font-bold text-primary group-hover:translate-x-1 transition">
            <span>Optimiser mon CV</span>
            <ArrowRight className="h-4 w-4" />
          </div>
        </div>

        {/* Option B: Direct Matching */}
        <div
          onClick={onSelectBypass}
          className="group relative cursor-pointer flex-col justify-between rounded-2xl border border-border bg-card p-6 transition-all duration-300 hover:-translate-y-1 hover:border-muted-foreground/50 hover:shadow-lg flex"
        >
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="h-10 w-10 rounded-xl bg-muted text-muted-foreground flex items-center justify-center font-bold">
                <CheckCircle2 className="h-5 w-5" />
              </div>

              <span className="rounded-full bg-muted px-2.5 py-0.5 text-[11px] font-bold text-muted-foreground">
                Accès direct
              </span>
            </div>

            <h3 className="font-extrabold text-lg text-foreground group-hover:text-primary transition">
              Conserver mon CV actuel
            </h3>

            <p className="text-xs text-muted-foreground leading-relaxed">
              Vous êtes satisfait de votre CV ? Accédez directement aux
              opportunités qui correspondent à votre profil.
            </p>
          </div>

          <div className="mt-6 flex items-center gap-2 text-xs font-bold text-muted-foreground group-hover:text-foreground transition">
            <span>Voir les opportunités</span>
            <ArrowRight className="h-4 w-4" />
          </div>
        </div>
      </div>
    </motion.div>
  );
}