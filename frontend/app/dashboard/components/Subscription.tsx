"use client";

import { useCallback, useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Loader2, X } from "lucide-react";
import {
  checkoutUrl, fetchBilling, portalUrl, type Billing, type PlanLimit, type UsageKind,
} from "@/lib/billing-client";
import { useToast } from "./Toaster";

const ORDER: UsageKind[] = ["pack", "mission", "spontaneous", "message"];

const INCLUDED = [
  "Des missions chaque jour, avec dossier adapté pour chaque offre",
  "Jusqu'à 15 candidatures spontanées par semaine",
  "Sans engagement : tu arrêtes quand tu as trouvé",
];

function day(iso: string | null): string {
  return iso ? new Date(iso).toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long" }) : "";
}

/** Ouvre la page de paiement, ou l'espace client si l'on est déjà abonné. */
function useGoTo(candidateId: string | null) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const go = useCallback(
    async (where: "checkout" | "portal") => {
      if (!candidateId) return;
      setBusy(true);
      try {
        const url = where === "checkout" ? await checkoutUrl(candidateId) : await portalUrl(candidateId);
        window.location.href = url;
      } catch (err) {
        toast((err as Error).message, "warning");
        setBusy(false);
      }
    },
    [candidateId, toast],
  );
  return { busy, go };
}

/** Bloc « Abonnement » des paramètres : formule, usage, gérer. */
export function PlanSection({ candidateId }: { candidateId: string | null }) {
  const [billing, setBilling] = useState<Billing | null>(null);
  const { busy, go } = useGoTo(candidateId);

  useEffect(() => {
    if (candidateId) fetchBilling(candidateId).then(setBilling);
  }, [candidateId]);

  if (!billing || !billing.enabled) return null;
  const weekly = billing.plan === "weekly";

  return (
    <section className="space-y-3">
      <p className="text-xs text-[#1A1918]/55 uppercase tracking-wider font-medium">Abonnement</p>
      <div className="border-t border-b border-[#1A1918]/10 divide-y divide-[#1A1918]/8">
        <div className="py-3.5 flex items-center justify-between gap-4">
          <div className="min-w-0">
            <p className="text-sm text-[#1A1918] tracking-tight">
              {weekly ? `Alice — ${billing.price_label}` : "Formule gratuite"}
            </p>
            <p className="text-xs font-normal text-[#1A1918]/60 tracking-tight">
              {weekly
                ? billing.cancelled
                  ? `Résilié : Alice reste active jusqu'au ${day(billing.ends_at)}.`
                  : billing.status === "past_due"
                    ? "Le dernier paiement a échoué : mets ta carte à jour pour continuer."
                    : `Prochain renouvellement le ${day(billing.renews_at)}.`
                : "De quoi essayer Alice pour de vrai, chaque semaine."}
            </p>
          </div>
          <button
            type="button"
            disabled={busy}
            onClick={() => go(weekly ? "portal" : "checkout")}
            className={
              weekly
                ? "shrink-0 inline-flex items-center gap-1.5 rounded-full border border-[#1A1918]/10 px-3 py-1.5 text-[11px] text-[#1A1918]/70 hover:border-[#006045]/40 hover:text-[#006045] transition-colors cursor-pointer disabled:opacity-50"
                : "shrink-0 inline-flex items-center gap-1.5 rounded-full bg-[#006045] px-3.5 py-1.5 text-[11px] text-white hover:bg-[#004d37] transition-colors cursor-pointer disabled:opacity-50"
            }
          >
            {busy && <Loader2 className="h-3 w-3 animate-spin" />}
            {weekly ? "Gérer (carte, factures, résiliation)" : `S'abonner — ${billing.price_label}`}
          </button>
        </div>
        {ORDER.map((kind) => {
          const u = billing.usage[kind];
          if (!u) return null;
          return (
            <div key={kind} className="py-2.5 flex items-center justify-between gap-4">
              <span className="text-xs text-[#1A1918]/60 tracking-tight first-letter:uppercase">
                {u.label} {u.window === "day" ? "aujourd'hui" : "sur 7 jours"}
              </span>
              <span className="text-xs tabular-nums text-[#1A1918]/80">
                {u.limit === 0 ? "avec l'abonnement" : `${u.used} / ${u.limit}`}
              </span>
            </div>
          );
        })}
      </div>
    </section>
  );
}

/**
 * La fenêtre qui s'ouvre quand une limite est atteinte, où que ce soit
 * (`untaf:plan-limit`, émis par apiFetch sur une réponse 402).
 */
export function UpgradeDialog({ candidateId }: { candidateId: string | null }) {
  const [limit, setLimit] = useState<PlanLimit | null>(null);
  const [billing, setBilling] = useState<Billing | null>(null);
  const { busy, go } = useGoTo(candidateId);
  const toast = useToast();

  useEffect(() => {
    const onLimit = (e: Event) => {
      const detail = (e as CustomEvent<PlanLimit | undefined>).detail;
      if (!detail || detail.code !== "plan_limit") return;
      setLimit(detail);
      if (candidateId) fetchBilling(candidateId).then(setBilling);
    };
    window.addEventListener("untaf:plan-limit", onLimit);
    return () => window.removeEventListener("untaf:plan-limit", onLimit);
  }, [candidateId]);

  // Retour de la page de paiement.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("abonnement") !== "merci") return;
    toast("Merci ! Ton abonnement est actif d'ici quelques secondes.");
    params.delete("abonnement");
    const rest = params.toString();
    window.history.replaceState(null, "", window.location.pathname + (rest ? `?${rest}` : ""));
  }, [toast]);

  const close = () => setLimit(null);

  return (
    <AnimatePresence>
      {limit && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-[#1A1918]/25 p-4"
          onClick={close}
        >
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-label="Abonnement Alice"
            initial={{ y: 16, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 8, opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={(e) => e.stopPropagation()}
            className="relative w-full max-w-sm rounded-2xl bg-white p-5 shadow-lg space-y-4 text-left"
          >
            <button
              type="button"
              onClick={close}
              aria-label="Fermer"
              className="absolute right-3 top-3 p-1 text-[#1A1918]/40 hover:text-[#1A1918] cursor-pointer"
            >
              <X className="h-4 w-4" />
            </button>
            <p className="text-sm text-[#1A1918] leading-relaxed pr-6">{limit.message}</p>
            {!limit.paid && (
              <>
                <ul className="space-y-1.5">
                  {INCLUDED.map((line) => (
                    <li key={line} className="text-xs text-[#1A1918]/65 tracking-tight">
                      ✓ {line}
                    </li>
                  ))}
                </ul>
                <button
                  type="button"
                  disabled={busy || billing?.enabled === false}
                  onClick={() => go("checkout")}
                  className="w-full inline-flex items-center justify-center gap-2 rounded-full bg-[#006045] px-4 py-2.5 text-sm text-white hover:bg-[#004d37] transition-colors cursor-pointer disabled:opacity-50"
                >
                  {busy && <Loader2 className="h-4 w-4 animate-spin" />}
                  S&apos;abonner{billing ? ` — ${billing.price_label}` : ""}
                </button>
                <p className="text-[11px] text-center text-[#1A1918]/50 tracking-tight">
                  Paiement sécurisé par Lemon Squeezy. Résiliable en un clic.
                </p>
              </>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
