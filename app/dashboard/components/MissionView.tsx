"use client";

import { motion } from "framer-motion";

interface MissionViewProps {
  headline?: string;
}

export function MissionView({ headline }: MissionViewProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.35 }}
      className="w-full max-w-[700px] mx-auto space-y-6 py-2"
    >
      <div>
        <h2 className="text-xl font-normal text-[#1A1918]">Paramètres de la mission</h2>
        <p className="text-xs text-[#1A1918]/50 mt-0.5">
          Alice utilise ces critères pour cibler et adapter tes candidatures.
        </p>
      </div>

      <div className="border-t border-b border-[#1A1918]/10 divide-y divide-[#1A1918]/8 text-sm">
        <div className="py-4 flex justify-between items-center">
          <div>
            <p className="text-xs text-[#1A1918]/40 uppercase tracking-wider font-medium">Objectif</p>
            <p className="font-medium text-[#1A1918] mt-0.5">
              {headline || "Alternance / CDI Développeur Informaticien"}
            </p>
          </div>
        </div>

        <div className="py-4 flex justify-between items-center">
          <div>
            <p className="text-xs text-[#1A1918]/40 uppercase tracking-wider font-medium">Localisation ciblée</p>
            <p className="font-medium text-[#1A1918] mt-0.5">Rennes / Paris / Télétravail</p>
          </div>
        </div>

        <div className="py-4 flex justify-between items-center">
          <div>
            <p className="text-xs text-[#1A1918]/40 uppercase tracking-wider font-medium">Disponibilité</p>
            <p className="font-medium text-[#1A1918] mt-0.5">Septembre / Immédiate</p>
          </div>
        </div>

        <div className="py-4 flex justify-between items-center">
          <div>
            <p className="text-xs text-[#1A1918]/40 uppercase tracking-wider font-medium">Autonomie d&apos;Alice</p>
            <p className="font-medium text-[#006045] mt-0.5">Auto-postuler pour les matchs ≥ 85%</p>
          </div>
        </div>
      </div>
    </motion.div>
  );
}
