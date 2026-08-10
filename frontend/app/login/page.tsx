"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { motion } from "framer-motion";
import { ArrowRight, Loader2 } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { useAuth } from "../auth-context";

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const { refresh } = useAuth();

  const [email, setEmail] = useState(params.get("email") ?? "");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(
    params.get("reason") === "exists"
      ? "Un compte existe déjà avec cet email — connecte-toi."
      : null,
  );

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim() || !password) return;

    setIsSubmitting(true);
    setError(null);

    try {
      const res = await apiFetch("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ email: email.trim(), password }),
      });

      if (!res.ok) {
        setError("Email ou mot de passe incorrect.");
        return;
      }

      await refresh();
      router.push("/dashboard");
    } catch {
      setError("Impossible de se connecter pour le moment.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <motion.form
        onSubmit={handleSubmit}
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35 }}
        className="w-full max-w-sm space-y-6"
      >
        <div className="text-center space-y-1">
          <h1 className="text-xl font-medium text-[#1A1918]">alice</h1>
          <p className="text-sm text-[#1A1918]/50">Content de te revoir.</p>
        </div>

        <div className="space-y-3">
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="ton@email.com"
            autoComplete="email"
            className="w-full px-3.5 py-2.5 bg-white border border-[#EDECEA] rounded-xl text-sm placeholder:text-[#1A1918]/35 text-[#1A1918] focus:outline-none focus:border-[#006045] transition-all"
          />
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Mot de passe"
            autoComplete="current-password"
            className="w-full px-3.5 py-2.5 bg-white border border-[#EDECEA] rounded-xl text-sm placeholder:text-[#1A1918]/35 text-[#1A1918] focus:outline-none focus:border-[#006045] transition-all"
          />
        </div>

        {error && <p className="text-center text-xs text-red-600/80">{error}</p>}

        <button
          type="submit"
          disabled={isSubmitting || !email.trim() || !password}
          className="w-full inline-flex items-center justify-center gap-2.5 py-3 px-6 rounded-xl bg-[#1A1918] text-white hover:bg-[#1A1918]/90 font-medium text-sm transition-all cursor-pointer disabled:opacity-40"
        >
          <span>Se connecter</span>
          {isSubmitting ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <ArrowRight className="h-4 w-4" />
          )}
        </button>

        <p className="text-center text-xs text-[#1A1918]/40">
          Pas encore de compte ?{" "}
          <a href="/onboarding" className="text-[#006045] hover:underline">
            Commencer
          </a>
        </p>
      </motion.form>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}
