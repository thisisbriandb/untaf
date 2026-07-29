"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { Bell, Settings } from "lucide-react";
import { API_BASE_URL } from "@/lib/config";
import { AlicePresence } from "../onboarding/components/AlicePresence";
import { DashboardSidebar, TabType } from "./components/DashboardSidebar";
import { AliceView } from "./components/AliceView";
import { MissionView } from "./components/MissionView";
import { CandidaturesView } from "./components/CandidaturesView";
import { MessagesView } from "./components/MessagesView";
import { ParametresView } from "./components/ParametresView";

// ─── Interfaces ──────────────────────────────────────────────────────────────

interface Application {
  id: string;
  candidate_id: string;
  job_posting_id: string;
  status: string;
  match_score: number;
  created_at: string;
  job_posting: any;
}

interface Candidate {
  id: string;
  full_name: string;
  email: string;
  headline?: string;
  skills: string[];
}

export default function DashboardPage() {
  const router = useRouter();

  // Navigation Tab State
  const [activeTab, setActiveTab] = useState<TabType>("alice");

  // Notifications State (Open by default when notifications exist)
  const [unreadCount, setUnreadCount] = useState(3);
  const [showNotifs, setShowNotifs] = useState(true);

  // Data States
  const [candidateId, setCandidateId] = useState<string | null>(null);
  const [candidate, setCandidate] = useState<Candidate | null>(null);
  const [applications, setApplications] = useState<Application[]>([]);
  const [loading, setLoading] = useState(true);
  const [updatingAppId, setUpdatingAppId] = useState<string | null>(null);

  // 1. Load Candidate ID from localStorage or fallback
  useEffect(() => {
    const storedId = localStorage.getItem("candidate_id");
    if (!storedId) {
      setLoading(false);
      return;
    }
    setCandidateId(storedId);
  }, []);

  // 2. Fetch Candidate Profile & Applications from Backend
  useEffect(() => {
    if (!candidateId) return;

    const fetchData = async () => {
      try {
        const [candRes, appsRes] = await Promise.all([
          fetch(`${API_BASE_URL}/candidates/${candidateId}`).catch(() => null),
          fetch(`${API_BASE_URL}/candidates/${candidateId}/applications`).catch(() => null),
        ]);

        if (candRes && candRes.ok) {
          const candData = await candRes.json();
          setCandidate(candData);
        }

        if (appsRes && appsRes.ok) {
          const appsData = await appsRes.json();
          setApplications(appsData);
        }
      } catch (err) {
        console.error("Error loading dashboard data:", err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [candidateId]);

  // Handle Logout
  const handleLogout = () => {
    localStorage.removeItem("candidate_id");
    localStorage.removeItem("candidate_email");
    localStorage.removeItem("candidate_name");
    router.push("/");
  };

  // Handle Application Status Update
  const handleUpdateStatus = async (appId: string, newStatus: string) => {
    setUpdatingAppId(appId);
    try {
      const res = await fetch(`${API_BASE_URL}/applications/${appId}/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: newStatus }),
      });

      if (res.ok) {
        setApplications((prev) =>
          prev.map((app) => (app.id === appId ? { ...app, status: newStatus } : app))
        );
      }
    } catch (err) {
      console.error("Failed to update status:", err);
    } finally {
      setUpdatingAppId(null);
    }
  };

  if (loading) {
    return (
      <main className="min-h-screen bg-[#FAFAF8] flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <AlicePresence emotion="searching" />
          <p className="text-sm font-light text-[#1A1918]/60 tracking-tight">Je synchronise ton espace...</p>
        </div>
      </main>
    );
  }

  const userName = candidate?.full_name || "Briand";
  const userEmail = candidate?.email || "";

  return (
    <main className="min-h-screen bg-[#FAFAF8] text-[#1A1918] flex relative">
      {/* ═══ Top Left Header App Title ("alice") ═══ */}
      <div className="fixed top-5 left-6 md:left-10 z-50 select-none">
        <button
          type="button"
          onClick={() => setActiveTab("alice")}
          className="text-base md:text-lg font-medium text-[#1A1918] tracking-tight hover:opacity-80 transition-opacity cursor-pointer"
        >
          alice
        </button>
      </div>

      {/* ═══ Discreet Top-Right Action Icons (Settings + Notification Bell) ═══ */}
      <div className="fixed top-5 right-6 md:right-10 z-50 flex items-center gap-1">
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

          {/* Discreet Notification Popover */}
          <AnimatePresence>
            {showNotifs && (
              <motion.div
                initial={{ opacity: 0, y: 6, scale: 0.95 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 4, scale: 0.95 }}
                transition={{ duration: 0.2 }}
                className="absolute right-0 mt-2 w-72 bg-white border border-[#EDECEA] rounded-2xl shadow-lg p-3.5 space-y-2.5 text-xs font-light text-[#1A1918] tracking-tight"
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
                    <p className="text-[#1A1918]/60 text-[11px]">Consultation de ton CV à 09:41</p>
                  </div>
                  <div className="p-2.5 rounded-xl bg-[#FAFAF8] space-y-0.5 border border-[#1A1918]/4">
                    <p className="font-normal text-[#1A1918]">Alice</p>
                    <p className="text-[#1A1918]/60 text-[11px]">8 candidatures adaptées ce matin</p>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Settings Icon Button */}
        <button
          type="button"
          onClick={() => setActiveTab("parametres")}
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

      {/* ═══ Main Center Canvas (Full Screen Centered) ═══ */}
      <div className="flex-1 min-h-screen flex flex-col items-center justify-center py-10 px-4 md:px-8 w-full">
        <AnimatePresence mode="wait">
          {activeTab === "alice" && (
            <AliceView key="alice" userName={userName} />
          )}

          {activeTab === "mission" && (
            <MissionView key="mission" headline={candidate?.headline} />
          )}

          {activeTab === "candidatures" && (
            <CandidaturesView
              key="candidatures"
              applications={applications}
              updatingAppId={updatingAppId}
              onUpdateStatus={handleUpdateStatus}
            />
          )}

          {activeTab === "messages" && (
            <MessagesView key="messages" userName={userName} />
          )}

          {activeTab === "parametres" && (
            <ParametresView
              key="parametres"
              userName={userName}
              userEmail={userEmail}
              onLogout={handleLogout}
            />
          )}
        </AnimatePresence>
      </div>
    </main>
  );
}
