"use client";

import { motion } from "framer-motion";
import { LogOut } from "lucide-react";

interface ParametresViewProps {
  userName: string;
  userEmail: string;
  onLogout: () => void;
}

export function ParametresView({ userName, userEmail, onLogout }: ParametresViewProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.35 }}
      className="w-full max-w-2xl text-left space-y-6 py-4"
    >
      <div>
        <h2 className="text-xl font-normal text-[#1A1918]">Paramètres du compte</h2>
        <p className="text-xs text-[#1A1918]/50 mt-0.5">
          Informations de ton profil et accès agent.
        </p>
      </div>

      <div className="space-y-3 text-sm">
        <div className="py-3.5 border-b border-[#1A1918]/8 flex justify-between">
          <span className="text-[#1A1918]/60">Nom complet</span>
          <span className="font-medium text-[#1A1918]">{userName}</span>
        </div>
        <div className="py-3.5 border-b border-[#1A1918]/8 flex justify-between">
          <span className="text-[#1A1918]/60">Email</span>
          <span className="font-medium text-[#1A1918]">{userEmail || "Non renseigné"}</span>
        </div>
      </div>

      <div className="pt-4 flex justify-start">
        <button
          type="button"
          onClick={onLogout}
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-medium text-red-600 hover:bg-red-50 transition-colors cursor-pointer border border-red-200"
        >
          <LogOut className="h-4 w-4" />
          Se déconnecter
        </button>
      </div>
    </motion.div>
  );
}
