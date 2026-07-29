"use client";

import { motion } from "framer-motion";

interface MessagesViewProps {
  userName: string;
}

export function MessagesView({ userName }: MessagesViewProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.35 }}
      className="w-full max-w-2xl text-left space-y-6 py-4"
    >
      <div>
        <h2 className="text-xl font-normal text-[#1A1918]">Messages &amp; Réponses</h2>
        <p className="text-xs text-[#1A1918]/50 mt-0.5">
          Les recruteurs qui ont répondu à Alice pour tes candidatures.
        </p>
      </div>

      <div className="p-5 rounded-2xl bg-white border border-[#EDECEA] space-y-2 text-left shadow-sm">
        <div className="flex justify-between items-center">
          <span className="text-xs font-semibold text-[#006045]">Doctolib • Recrutement</span>
          <span className="text-[11px] text-[#1A1918]/40">Aujourd&apos;hui 10:18</span>
        </div>
        <p className="text-xs md:text-sm font-medium text-[#1A1918] leading-relaxed">
          &quot;Bonjour {userName}, nous avons bien reçu ton CV et serions ravis d&apos;échanger avec toi lors d&apos;un premier entretien.&quot;
        </p>
      </div>
    </motion.div>
  );
}
