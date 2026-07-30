"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { AnimatePresence } from "framer-motion";
import { API_BASE_URL } from "@/lib/config";
import { AlicePresence } from "../onboarding/components/AlicePresence";
import { TabType } from "./components/DashboardSidebar";
import { DashboardHeader } from "./components/DashboardHeader";
import { AliceView } from "./components/AliceView";
import { MissionView } from "./components/MissionView";
import { CandidaturesView } from "./components/CandidaturesView";
import { MessagesView } from "./components/MessagesView";
import { ParametresView } from "./components/ParametresView";
import { CanvasPanel } from "./components/CanvasPanel";
import { AliceProvider, useAlice } from "./alice-context";
import type { ReactNode } from "react";

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

/**
 * Largeur de lecture de la conversation. Resserrée quand le Canvas est ouvert
 * pour qu'aucune gouttière morte ne s'installe entre les deux panneaux.
 */
function ConversationColumn({ children }: { children: ReactNode }) {
  const { isCanvasOpen } = useAlice();
  return (
    <div
      className={`flex-1 min-w-0 flex flex-col overflow-hidden ${
        isCanvasOpen ? "max-w-3xl lg:max-w-[44rem]" : "max-w-3xl"
      }`}
    >
      {children}
    </div>
  );
}

export default function DashboardPage() {
  const router = useRouter();

  // Navigation Tab State
  const [activeTab, setActiveTab] = useState<TabType>("alice");

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
          fetch(`${API_BASE_URL}/api/candidates/${candidateId}`).catch(() => null),
          fetch(`${API_BASE_URL}/api/applications/?candidate_id=${candidateId}`).catch(
            () => null
          ),
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
      const res = await fetch(`${API_BASE_URL}/api/applications/${appId}/status`, {
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
    <AliceProvider
      candidateId={candidateId}
      onGoToConversation={() => setActiveTab("alice")}
    >
      <div className="h-[100dvh] bg-[#FAFAF8] text-[#1A1918] flex flex-col overflow-hidden">
        {/* ═══ Barre d'application, pleine largeur ═══ */}
        <DashboardHeader activeTab={activeTab} onSelectTab={setActiveTab} />

        {/* ═══ Ligne principale : conversation + canvas (dès lg) ═══ */}
        <main className="flex-1 min-h-0 flex justify-center overflow-hidden">
          <ConversationColumn>
            <div className="flex-1 min-h-0 w-full flex flex-col items-center justify-center px-4 md:px-8 pb-4 overflow-hidden">
              <AnimatePresence mode="wait">
                {activeTab === "alice" && <AliceView key="alice" userName={userName} />}

                {activeTab === "mission" && <MissionView key="mission" />}

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
          </ConversationColumn>

          {/* ═══ Colonne canvas (CV / Lettre) ═══ */}
          <CanvasPanel candidateId={candidateId} />
        </main>
      </div>
    </AliceProvider>
  );
}
