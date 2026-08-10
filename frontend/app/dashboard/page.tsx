"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { AnimatePresence } from "framer-motion";
import { apiFetch, apiJson } from "@/lib/api";
import { AlicePresence } from "../onboarding/components/AlicePresence";
import { DashboardSidebar, TabType } from "./components/DashboardSidebar";
import { DashboardHeader } from "./components/DashboardHeader";
import { AliceView } from "./components/AliceView";
import { MissionView } from "./components/MissionView";
import { CandidaturesView } from "./components/CandidaturesView";
import { MessagesView } from "./components/MessagesView";
import { ParametresView } from "./components/ParametresView";
import { CanvasPanel } from "./components/CanvasPanel";
import { AliceProvider, useAlice } from "./alice-context";
import { useAuth } from "../auth-context";
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
  const { candidate, loading: authLoading, logout } = useAuth();

  // Navigation Tab State
  const [activeTab, setActiveTab] = useState<TabType>("alice");

  const [applications, setApplications] = useState<Application[]>([]);
  const [appsLoading, setAppsLoading] = useState(true);
  const [updatingAppId, setUpdatingAppId] = useState<string | null>(null);

  const candidateId = candidate?.id ?? null;

  // Redirige vers la connexion une fois qu'on sait vraiment que personne
  // n'est authentifié — jamais avant, sinon un utilisateur connecté verrait
  // un aller-retour visible vers /login à chaque chargement.
  useEffect(() => {
    if (!authLoading && !candidate) {
      router.push("/login");
    }
  }, [authLoading, candidate, router]);

  // Candidatures — dépendent du profil authentifié.
  useEffect(() => {
    if (!candidateId) {
      setAppsLoading(false);
      return;
    }

    apiJson<Application[]>(`/api/applications/`)
      .then(setApplications)
      .catch((err) => console.error("Error loading applications:", err))
      .finally(() => setAppsLoading(false));
  }, [candidateId]);

  const handleLogout = async () => {
    await logout();
    router.push("/");
  };

  // Handle Application Status Update
  const handleUpdateStatus = async (appId: string, newStatus: string) => {
    setUpdatingAppId(appId);
    try {
      const res = await apiFetch(`/api/applications/${appId}/status`, {
        method: "PATCH",
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

  if (authLoading || (candidate && appsLoading)) {
    return (
      <main className="min-h-screen bg-[#FAFAF8] flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <AlicePresence emotion="searching" />
          <p className="text-sm font-light text-[#1A1918]/60 tracking-tight">Je synchronise ton espace...</p>
        </div>
      </main>
    );
  }

  if (!candidate) {
    // Le useEffect ci-dessus redirige déjà — rien à afficher entre-temps.
    return null;
  }

  const userName = candidate.full_name || "Briand";
  const userEmail = candidate.email || "";

  return (
    <AliceProvider
      candidateId={candidateId}
      onGoToConversation={() => setActiveTab("alice")}
    >
      <DashboardSidebar
        activeTab={activeTab}
        onSelectTab={setActiveTab}
        applicationsCount={applications.length}
        userName={userName}
        userEmail={userEmail}
        onLogout={handleLogout}
      />
      <div className="h-[100dvh] bg-[#FAFAF8] text-[#1A1918] flex flex-col overflow-hidden pl-14">
        {/* ═══ Barre d'application, pleine largeur ═══ */}
        <DashboardHeader activeTab={activeTab} onSelectTab={setActiveTab} candidateId={candidateId} />

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
                  <MessagesView key="messages" candidateId={candidateId} />
                )}

                {activeTab === "parametres" && (
                  <ParametresView
                    key="parametres"
                    userName={userName}
                    userEmail={userEmail}
                    candidateId={candidateId}
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
