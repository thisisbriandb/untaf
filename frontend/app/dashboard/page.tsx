"use client";

import { useCallback, useState, useEffect } from "react";
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
import { ToastProvider } from "./components/Toaster";
import { AliceProvider, useAlice } from "./alice-context";
import { fetchPipeline, type Pipeline } from "@/lib/pipeline-client";
import { AUTH_ENABLED, accessToken, signOut } from "@/lib/supabase";
import { clearLocalCandidate, destinationAfterSignIn } from "@/lib/session";
import type { ReactNode } from "react";
import { apiFetch } from "@/lib/api";

// ─── Interfaces ──────────────────────────────────────────────────────────────

interface Candidate {
  id: string;
  full_name: string;
  email: string;
  headline?: string;
  skills: string[];
}

const TABS: TabType[] = ["alice", "mission", "candidatures", "messages", "parametres"];

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
  const [loading, setLoading] = useState(true);
  /** Ce qui attend l'utilisateur — affiché en pastille sur la cloche. */
  const [awaitingCount, setAwaitingCount] = useState(0);

  // 1. Load Candidate ID from localStorage, and the tab from the URL: the
  //    e-mails d'Alice pointent sur `/dashboard?tab=candidatures`.
  //    Avec authentification, c'est le serveur qui dit quel profil appartient
  //    au compte connecté — le navigateur n'est plus une source de vérité.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const tab = params.get("tab") as TabType | null;
    if (tab && TABS.includes(tab)) setActiveTab(tab);

    if (!AUTH_ENABLED) {
      const storedId = localStorage.getItem("candidate_id");
      if (!storedId) {
        setLoading(false);
        return;
      }
      setCandidateId(storedId);
      return;
    }

    let alive = true;
    const here = window.location.pathname + window.location.search;
    accessToken().then(async (token) => {
      if (!alive) return;
      if (!token) {
        router.replace(`/login?next=${encodeURIComponent(here)}`);
        return;
      }
      const destination = await destinationAfterSignIn(here);
      if (!alive) return;
      if (destination === "/") {
        router.replace("/"); // connecté, mais pas encore de profil : onboarding
        return;
      }
      setCandidateId(localStorage.getItem("candidate_id"));
    });

    // Session révoquée en cours de route : retour à la connexion.
    const onUnauthorized = () => router.replace(`/login?next=${encodeURIComponent(here)}`);
    window.addEventListener("untaf:unauthorized", onUnauthorized);
    return () => {
      alive = false;
      window.removeEventListener("untaf:unauthorized", onUnauthorized);
    };
  }, [router]);

  /** L'onglet suit l'URL : un rechargement ou un lien partagé y ramène. */
  const selectTab = useCallback((tab: TabType) => {
    setActiveTab(tab);
    const url = new URL(window.location.href);
    if (tab === "alice") url.searchParams.delete("tab");
    else url.searchParams.set("tab", tab);
    window.history.replaceState(null, "", url);
  }, []);

  // 2. Fetch Candidate Profile from Backend
  useEffect(() => {
    if (!candidateId) return;

    const fetchData = async () => {
      try {
        const [candRes, pipeline] = await Promise.all([
          apiFetch(`${API_BASE_URL}/api/candidates/${candidateId}`).catch(() => null),
          fetchPipeline(candidateId),
        ]);

        if (candRes && candRes.ok) {
          setCandidate(await candRes.json());
        }
        if (pipeline) setAwaitingCount(pipeline.counts.awaiting ?? 0);
      } catch (err) {
        console.error("Error loading dashboard data:", err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [candidateId]);

  const handlePipelineChange = useCallback(
    (pipeline: Pipeline) => setAwaitingCount(pipeline.counts.awaiting ?? 0),
    [],
  );

  // Handle Logout
  const handleLogout = async () => {
    await signOut();
    clearLocalCandidate();
    router.push(AUTH_ENABLED ? "/login" : "/");
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

  const userName = candidate?.full_name || "";
  const userEmail = candidate?.email || "";

  return (
    <AliceProvider
      candidateId={candidateId}
      onGoToConversation={() => selectTab("alice")}
    >
      <ToastProvider>
      <div className="h-[100dvh] bg-[#FAFAF8] text-[#1A1918] flex flex-col overflow-hidden">
        {/* ═══ Barre d'application, pleine largeur ═══ */}
        <DashboardHeader
          activeTab={activeTab}
          onSelectTab={selectTab}
          candidateId={candidateId}
          awaitingCount={awaitingCount}
        />

        {/* ═══ Ligne principale : conversation + canvas (dès lg) ═══ */}
        <main className="flex-1 min-h-0 flex justify-center overflow-hidden">
          <ConversationColumn>
            <div className="flex-1 min-h-0 w-full flex flex-col items-center justify-center px-4 md:px-8 pb-4 overflow-hidden">
              <AnimatePresence mode="wait">
                {activeTab === "alice" && (
                  <AliceView key="alice" userName={userName} onSelectTab={selectTab} />
                )}

                {activeTab === "mission" && <MissionView key="mission" />}

                {activeTab === "candidatures" && (
                  <CandidaturesView
                    key="candidatures"
                    candidateId={candidateId}
                    onPipelineChange={handlePipelineChange}
                  />
                )}

                {activeTab === "messages" && (
                  <MessagesView key="messages" candidateId={candidateId} onSelectTab={selectTab} />
                )}

                {activeTab === "parametres" && (
                  <ParametresView
                    key="parametres"
                    candidateId={candidateId}
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
      </ToastProvider>
    </AliceProvider>
  );
}
