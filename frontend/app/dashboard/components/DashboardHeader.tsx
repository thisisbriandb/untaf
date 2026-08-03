"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Bell, Settings } from "lucide-react";
import type { TabType } from "./DashboardSidebar";

/**
 * Barre d'application — pleine largeur, au-dessus du split conversation/canvas.
 * Elle garde « alice » en haut à gauche et les actions en haut à droite de
 * l'écran, sans jamais recouvrir le Canvas.
 */
export function DashboardHeader({
  activeTab,
  onSelectTab,
}: {
  activeTab: TabType;
  onSelectTab: (tab: TabType) => void;
}) {
  const [unreadCount, setUnreadCount] = useState(3);
  const [showNotifs, setShowNotifs] = useState(true);

  return (
    <header className="shrink-0 z-50 flex items-center justify-between px-6 md:px-10 py-4 select-none">
      <button
        type="button"
        onClick={() => onSelectTab("alice")}
        className="text-base md:text-lg font-medium text-[#1A1918] tracking-tight hover:opacity-80 transition-opacity cursor-pointer"
      >
        alice
      </button>

      <div className="flex items-center gap-1">
        {/* Notification Bell */}
        <div className="relative">
          <button
            type="button"
            onClick={() => setShowNotifs(!showNotifs)}
            aria-label="Notifications"
            className="relative p-2 rounded-full text-[#1A1918]/45 hover:text-[#1A1918] hover:bg-[#1A1918]/5 transition-colors cursor-pointer"
          >
            <Bell className="w-4 h-4 stroke-[1.4]" />
            {unreadCount > 0 && (
              <span className="absolute top-1 right-1 min-w-[15px] h-[15px] px-1 rounded-full bg-red-500 text-white text-[9px] font-bold flex items-center justify-center shadow-sm">
                {unreadCount}
              </span>
            )}
          </button>

          <AnimatePresence>
            {showNotifs && (
              <motion.div
                initial={{ opacity: 0, y: 6, scale: 0.95 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 4, scale: 0.95 }}
                transition={{ duration: 0.2 }}
                className="absolute right-0 mt-2 w-72 z-50 bg-white border border-[#EDECEA] rounded-2xl shadow-lg p-3.5 space-y-2.5 text-xs font-light text-[#1A1918] tracking-tight"
              >
                <div className="flex items-center justify-between pb-2 border-b border-[#1A1918]/8">
                  <span className="font-medium text-[#1A1918]">Notifications</span>
                  {unreadCount > 0 && (
                    <button
                      onClick={() => {
                        setUnreadCount(0);
                        setShowNotifs(false);
                      }}
                      className="text-[10px] text-[#006045] hover:underline cursor-pointer"
                    >
                      Tout marquer comme lu
                    </button>
                  )}
                </div>
                <div className="space-y-2">
                  <div className="p-2.5 rounded-xl bg-[#FAFAF8] space-y-0.5 border border-[#1A1918]/4">
                    <p className="font-normal text-[#006045]">Doctolib — Entretien</p>
                    <p className="text-[#1A1918]/60 text-[11px]">
                      Consultation de ton CV à 09:41
                    </p>
                  </div>
                  <div className="p-2.5 rounded-xl bg-[#FAFAF8] space-y-0.5 border border-[#1A1918]/4">
                    <p className="font-normal text-[#1A1918]">Alice</p>
                    <p className="text-[#1A1918]/60 text-[11px]">
                      8 candidatures adaptées ce matin
                    </p>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Settings */}
        <button
          type="button"
          onClick={() => onSelectTab("parametres")}
          aria-label="Paramètres"
          className={`p-2 rounded-full transition-colors cursor-pointer ${
            activeTab === "parametres"
              ? "text-[#006045] bg-[#006045]/10"
              : "text-[#1A1918]/45 hover:text-[#1A1918] hover:bg-[#1A1918]/5"
          }`}
        >
          <Settings className="w-4 h-4 stroke-[1.4]" />
        </button>
      </div>
    </header>
  );
}
