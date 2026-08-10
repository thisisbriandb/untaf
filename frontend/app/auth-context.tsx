"use client";

/**
 * Qui est connecté — source unique de vérité, dérivée de GET /auth/me.
 *
 * Remplace la lecture directe de `localStorage.candidate_id` : l'identité
 * n'est jamais lue sans vérification, elle vient toujours d'une réponse du
 * serveur qui a déjà validé le cookie de session.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { apiFetch, apiJson, ApiError } from "@/lib/api";

export interface Candidate {
  id: string;
  full_name: string;
  email: string;
  headline?: string;
  skills: string[];
}

interface AuthContextValue {
  candidate: Candidate | null;
  loading: boolean;
  refresh: () => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [candidate, setCandidate] = useState<Candidate | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const me = await apiJson<Candidate>("/api/auth/me");
      setCandidate(me);
      // Cache non-sensible, uniquement pour construire des URLs plus vite
      // au prochain chargement — jamais relu comme preuve d'identité.
      localStorage.setItem("candidate_id", me.id);
    } catch (err) {
      setCandidate(null);
      if (!(err instanceof ApiError && err.status === 401)) {
        console.error("Auth check failed:", err);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const logout = useCallback(async () => {
    await apiFetch("/api/auth/logout", { method: "POST" }).catch(() => null);
    localStorage.removeItem("candidate_id");
    setCandidate(null);
  }, []);

  const value = useMemo(
    () => ({ candidate, loading, refresh, logout }),
    [candidate, loading, refresh, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
