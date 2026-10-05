"use client";

import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence, LayoutGroup } from "framer-motion";
import { Bell, PanelLeft, Send, Settings } from "lucide-react";
import { cn } from "@/lib/utils";
import { fetchJournal, type MissionEvent } from "@/lib/mission-client";
import { markJournalRead } from "@/lib/pipeline-client";
import type { TabType } from "./DashboardSidebar";

// Deux lieux seulement : parler à Alice, suivre ses candidatures. Le mandat
// et les e-mails d'Alice se consultent depuis le rail des conversations.
const NAV: { id: TabType; label: string }[] = [
  { id: "alice", label: "Alice" },
  { id: "candidatures", label: "Candidatures" },
];

const IMPORTANT = new Set(["applied", "reply", "awaiting_approval", "error", "status_changed"]);

/** Assez vif pour qu'une fin de mission apparaisse sans recharger. */
const POLL_MS = 30_000;

const DOT: Record<string, string> = {
  applied: "bg-[#161615]",
  reply: "bg-[#161615]",
  awaiting_approval: "bg-[#161615]",
  letter_written: "bg-[#161615]/60",
  error: "bg-red-500",
};

function ago(iso: string): string {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return "à l'instant";
  if (diff < 3600) return `${Math.floor(diff / 60)} min`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} h`;
  return `${Math.floor(diff / 86400)} j`;
}

/**
 * Barre d'application — pleine largeur, au-dessus du split conversation/canvas.
 *
 * La cloche lit le journal réel d'Alice : ce qu'elle a fait depuis la dernière
 * visite, et ce qui attend une décision. Rien n'y est mis en scène.
 */
export function DashboardHeader({
  activeTab,
  onSelectTab,
  candidateId,
  awaitingCount = 0,
  sidebarOpen = false,
  onToggleSidebar,
}: {
  activeTab: TabType;
  onSelectTab: (tab: TabType) => void;
  candidateId: string | null;
  awaitingCount?: number;
  sidebarOpen?: boolean;
  onToggleSidebar?: () => void;
}) {
  const [events, setEvents] = useState<MissionEvent[]>([]);
  const [showNotifs, setShowNotifs] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!candidateId) return;
    const tick = () => {
      fetchJournal(candidateId, 12).then(setEvents);
    };
    tick();
    const id = setInterval(tick, POLL_MS);
    return () => clearInterval(id);
  }, [candidateId]);

  // Un clic à côté referme le panneau.
  useEffect(() => {
    if (!showNotifs) return;
    const close = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) setShowNotifs(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [showNotifs]);

  // La pastille ne s'allume que pour ce qui demande un regard : un envoi, une
  // réponse, une validation, un échec, un compte rendu. Une veille ou un
  // dossier préparé se consultent, ils ne réclament pas d'attention.
  const unread = events.filter((e) => !e.is_read && IMPORTANT.has(e.kind)).length;
  const badge = unread + (awaitingCount > 0 ? 1 : 0);

  const markAllRead = async () => {
    if (!candidateId) return;
    setEvents((prev) => prev.map((e) => ({ ...e, is_read: true })));
    await markJournalRead(candidateId);
  };

  return (
    // Trois colonnes : la navigation reste centrée sur la zone de contenu, que
    // le rail des conversations soit ouvert ou non.
    <header className="shrink-0 z-30 h-[68px] grid grid-cols-[auto_minmax(0,1fr)_auto] md:grid-cols-[1fr_auto_1fr] items-center gap-3 px-4 md:px-6 select-none">
      <div className="flex items-center gap-1.5 min-w-0">
      {/* Rail ouvert : la marque et le repli y sont déjà */}
      {onToggleSidebar && !sidebarOpen && (
        <button
          type="button"
          onClick={onToggleSidebar}
          aria-label={sidebarOpen ? "Masquer les conversations" : "Afficher les conversations"}
          title="Conversations"
          className={cn(
            "p-2 rounded-full transition-colors cursor-pointer",
            sidebarOpen ? "text-[#161615] bg-[#161615]/10" : "text-[#1A1918]/60 hover:text-[#1A1918] hover:bg-[#1A1918]/5",
          )}
        >
          <PanelLeft className="w-4 h-4 stroke-[1.4]" />
        </button>
      )}
      {!sidebarOpen && <button
        type="button"
        onClick={() => onSelectTab("alice")}
        className="hidden sm:block text-base md:text-lg font-medium text-[#1A1918] tracking-tight hover:opacity-80 transition-opacity cursor-pointer"
      >
        alice
      </button>}
      </div>

      {/* Navigation — l'indicateur glisse d'un onglet à l'autre */}
      <LayoutGroup id="dashboard-nav">
        <nav className="justify-self-center max-w-full flex items-center gap-0.5 rounded-full bg-[#1A1918]/[0.035] p-1 overflow-x-auto min-w-0 scrollbar-none">
          {NAV.map((item) => {
            const active = activeTab === item.id;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => onSelectTab(item.id)}
                className={cn(
                  "relative shrink-0 rounded-full px-2.5 sm:px-3 py-1.5 text-xs tracking-tight transition-colors cursor-pointer",
                  active ? "text-[#1A1918]" : "text-[#1A1918]/60 hover:text-[#1A1918]/80",
                )}
              >
                {active && (
                  <motion.span
                    layoutId="nav-pill"
                    className="absolute inset-0 rounded-full bg-white shadow-sm shadow-black/5"
                    transition={{ type: "spring", stiffness: 480, damping: 36 }}
                  />
                )}
                <span className="relative flex items-center gap-1.5">
                  {item.label}
                  {item.id === "candidatures" && awaitingCount > 0 && (
                    <motion.span
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      className="min-w-[16px] h-4 px-1 rounded-full bg-[#161615] text-white text-[10px] font-semibold flex items-center justify-center"
                    >
                      {awaitingCount}
                    </motion.span>
                  )}
                </span>
              </button>
            );
          })}
        </nav>
      </LayoutGroup>

      <div className="flex items-center justify-end gap-1">
        <div className="relative" ref={panelRef}>
          <button
            type="button"
            onClick={() => {
              const opening = !showNotifs;
              setShowNotifs(opening);
              // Ouvrir le panneau, c'est avoir vu : la pastille ne s'attarde pas.
              if (opening && unread > 0) setTimeout(() => void markAllRead(), 1200);
            }}
            aria-label="Notifications"
            className="relative p-2 rounded-full text-[#1A1918]/60 hover:text-[#1A1918] hover:bg-[#1A1918]/5 transition-colors cursor-pointer"
          >
            <motion.span
              key={badge}
              animate={badge > 0 ? { rotate: [0, -14, 12, -8, 0] } : {}}
              transition={{ duration: 0.6 }}
              className="block"
            >
              <Bell className="w-4 h-4 stroke-[1.4]" />
            </motion.span>
            <AnimatePresence>
              {badge > 0 && (
                <motion.span
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  exit={{ scale: 0 }}
                  className={cn(
                    "absolute top-1 right-1 min-w-[15px] h-[15px] px-1 rounded-full text-white text-[10px] font-bold flex items-center justify-center shadow-sm",
                    awaitingCount > 0 ? "bg-[#161615]" : "bg-[#161615]",
                  )}
                >
                  {badge > 9 ? "9+" : badge}
                </motion.span>
              )}
            </AnimatePresence>
          </button>

          <AnimatePresence>
            {showNotifs && (
              <motion.div
                initial={{ opacity: 0, y: 6, scale: 0.96 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 4, scale: 0.96 }}
                transition={{ type: "spring", stiffness: 420, damping: 32 }}
                style={{ transformOrigin: "top right" }}
                className="absolute right-0 mt-2 w-80 max-w-[calc(100vw-2rem)] z-50 bg-white border border-[#EDECEA] rounded-2xl shadow-lg p-3.5 space-y-2.5 text-xs font-normal text-[#1A1918] tracking-tight"
              >
                <div className="flex items-center justify-between pb-2 border-b border-[#1A1918]/8">
                  <span className="font-medium text-[#1A1918]">Ce que j&apos;ai fait</span>
                  {unread > 0 && (
                    <button
                      type="button"
                      onClick={markAllRead}
                      className="text-[11px] text-[#161615] hover:underline cursor-pointer"
                    >
                      Tout marquer comme lu
                    </button>
                  )}
                </div>

                {awaitingCount > 0 && (
                  <button
                    type="button"
                    onClick={() => {
                      setShowNotifs(false);
                      onSelectTab("candidatures");
                    }}
                    className="w-full flex items-center gap-2.5 p-2.5 rounded-xl bg-[#F4F3F0] border border-[#161615]/20 text-left cursor-pointer hover:bg-[#EAE9E5]/60 transition-colors"
                  >
                    <Send className="h-3.5 w-3.5 text-[#161615] shrink-0" />
                    <span className="flex-1">
                      {awaitingCount} candidature{awaitingCount > 1 ? "s attendent" : " attend"} ton feu vert
                    </span>
                    <span className="text-[#161615]">Voir →</span>
                  </button>
                )}

                <div className="max-h-80 overflow-y-auto scroll-discreet space-y-0.5">
                  {events.length === 0 ? (
                    <p className="py-3 text-[#1A1918]/60">Rien de neuf pour l&apos;instant.</p>
                  ) : (
                    events.map((e, i) => (
                      <motion.div
                        key={e.id}
                        initial={{ opacity: 0, x: 6 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: i * 0.025 }}
                        className={cn(
                          "flex items-start gap-2.5 p-2 rounded-xl",
                          !e.is_read && "bg-[#FAFAF8]",
                        )}
                      >
                        <span
                          className={cn(
                            "mt-1.5 h-1.5 w-1.5 rounded-full shrink-0",
                            DOT[e.kind] ?? "bg-[#1A1918]/20",
                          )}
                        />
                        <p className={cn("flex-1 leading-relaxed", e.is_read ? "text-[#1A1918]/55" : "text-[#1A1918]/85")}>
                          {e.summary}
                        </p>
                        <span className="text-[11px] text-[#1A1918]/45 shrink-0 pt-0.5">{ago(e.created_at)}</span>
                      </motion.div>
                    ))
                  )}
                </div>

                <button
                  type="button"
                  onClick={() => {
                    setShowNotifs(false);
                    onSelectTab("mission");
                  }}
                  className="w-full pt-2 border-t border-[#1A1918]/8 text-[11px] text-[#161615] hover:underline cursor-pointer text-left"
                >
                  Tout le journal de mission →
                </button>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        <button
          type="button"
          onClick={() => onSelectTab("parametres")}
          aria-label="Paramètres"
          className={`p-2 rounded-full transition-colors cursor-pointer ${
            activeTab === "parametres"
              ? "text-[#161615] bg-[#161615]/10"
              : "text-[#1A1918]/60 hover:text-[#1A1918] hover:bg-[#1A1918]/5"
          }`}
        >
          <Settings className="w-4 h-4 stroke-[1.4]" />
        </button>
      </div>
    </header>
  );
}
