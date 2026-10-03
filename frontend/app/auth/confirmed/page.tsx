"use client";

/**
 * Atterrissage du lien de connexion.
 *
 * Souvent ouvert dans un nouvel onglet alors que l'onboarding attend dans le
 * premier : la session créée ici y est partagée automatiquement. On le dit,
 * pour que l'utilisateur ne recommence pas tout dans cet onglet-ci.
 */

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Check, Loader2 } from "lucide-react";
import { AlicePresence } from "../../onboarding/components/AlicePresence";
import { supabase } from "@/lib/supabase";
import { destinationAfterSignIn } from "@/lib/session";

export default function ConfirmedPage() {
  const router = useRouter();
  const [state, setState] = useState<"waiting" | "ok" | "failed">("waiting");

  useEffect(() => {
    if (!supabase) {
      router.replace("/");
      return;
    }
    const { data } = supabase.auth.onAuthStateChange((_event, session) => {
      if (session) setState("ok");
    });
    // Lien expiré ou déjà utilisé : aucune session n'arrive.
    const timeout = setTimeout(
      () => setState((s) => (s === "waiting" ? "failed" : s)),
      6000,
    );
    return () => {
      data.subscription.unsubscribe();
      clearTimeout(timeout);
    };
  }, [router]);

  return (
    <main className="min-h-[100dvh] bg-[#FAFAF8] flex flex-col items-center justify-center gap-6 px-6 text-center">
      <AlicePresence emotion={state === "ok" ? "happy" : "thinking"} />
      {state === "waiting" && (
        <p className="flex items-center gap-2 text-sm font-light text-[#1A1918]/55">
          <Loader2 className="h-4 w-4 animate-spin text-[#006045]" /> Je vérifie ton lien…
        </p>
      )}
      {state === "ok" && (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-4 max-w-sm">
          <p className="flex items-center justify-center gap-2 text-xl font-normal text-[#1A1918]/85 tracking-tight">
            <Check className="h-5 w-5 text-[#006045]" /> C&apos;est confirmé.
          </p>
          <p className="text-sm font-light text-[#1A1918]/55 leading-relaxed">
            Si tu as un autre onglet ouvert avec moi, retourne-y : il a déjà repris. Sinon, on
            continue ici.
          </p>
          <button
            type="button"
            onClick={async () => router.replace(await destinationAfterSignIn())}
            className="px-5 py-2.5 rounded-full bg-[#006045] text-white text-sm cursor-pointer hover:bg-[#004d38]"
          >
            Continuer ici
          </button>
        </motion.div>
      )}
      {state === "failed" && (
        <div className="space-y-3 max-w-sm">
          <p className="text-lg font-normal text-[#1A1918]/85">Ce lien n&apos;est plus valable.</p>
          <p className="text-sm font-light text-[#1A1918]/55">Il a peut-être déjà servi, ou il a expiré.</p>
          <button
            type="button"
            onClick={() => router.replace("/login")}
            className="px-5 py-2.5 rounded-full bg-[#006045] text-white text-sm cursor-pointer"
          >
            Recevoir un nouveau lien
          </button>
        </div>
      )}
    </main>
  );
}
