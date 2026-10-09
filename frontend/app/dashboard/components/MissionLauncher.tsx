"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ArrowRight, Loader2, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { AlicePresence } from "@/app/onboarding/components/AlicePresence";
import { COUNTS, startRun, type MissionRun } from "@/lib/mission-run-client";
import { fetchBilling } from "@/lib/billing-client";

const SEND_PREF = "alice_mission_send";
const SPONTANEOUS_PREF = "alice_mission_spontaneous";
const SPONTANEOUS_COUNTS = [0, 3, 5];

function rememberedSpontaneous(): number {
  try {
    const v = Number(localStorage.getItem(SPONTANEOUS_PREF));
    return SPONTANEOUS_COUNTS.includes(v) ? v : 3;
  } catch {
    return 3;
  }
}

/** Le dernier choix d'envoi : on ne repose pas la question à chaque mission. */
function rememberedSend(): boolean {
  try {
    return localStorage.getItem(SEND_PREF) === "1";
  } catch {
    return false;
  }
}

/**
 * Confier une mission — un seul écran.
 *
 * Préparer et postuler ne sont pas deux missions : on ne postule pas sans
 * dossier, et un dossier qu'Alice peut envoyer n'a pas à attendre. Alice
 * prépare donc toujours tout, puis envoie ce qui peut partir. La seule vraie
 * question est celle du feu vert : envoyer directement, ou présenter d'abord.
 */
export function MissionLauncher({
  candidateId,
  onLaunched,
  onClose,
}: {
  candidateId: string;
  onLaunched: (run: MissionRun) => void;
  onClose: () => void;
}) {
  const [count, setCount] = useState(5);
  const [spontaneous, setSpontaneous] = useState(rememberedSpontaneous);
  const [allowSend, setAllowSend] = useState(rememberedSend);
  const [isLaunching, setIsLaunching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Limite de la formule : la fenêtre d'abonnement prend le relais (sauf si
  // c'est l'assistant lui-même qui la propose : il reste ouvert dessous).
  useEffect(() => {
    const onLimit = (e: Event) => {
      if (!(e as CustomEvent<{ fromLauncher?: boolean }>).detail?.fromLauncher) onClose();
    };
    window.addEventListener("untaf:plan-limit", onLimit);
    return () => window.removeEventListener("untaf:plan-limit", onLimit);
  }, [onClose]);

  // Les spontanées font partie de l'abonnement : en gratuit, le choix reste
  // visible mais verrouillé, avec ce qu'il apporterait.
  const [spontaneousLocked, setSpontaneousLocked] = useState(false);
  useEffect(() => {
    void fetchBilling(candidateId).then((b) => {
      const locked = Boolean(b?.enabled && b.usage.spontaneous && b.usage.spontaneous.limit === 0);
      setSpontaneousLocked(locked);
      if (locked) setSpontaneous(0);
    });
  }, [candidateId]);

  const offerSpontaneous = () =>
    window.dispatchEvent(new CustomEvent("untaf:plan-limit", {
      detail: {
        code: "plan_limit", kind: "spontaneous", used: 0, limit: 0, paid: false, fromLauncher: true,
        message: "Avec l'abonnement, j'écris chaque semaine à 15 entreprises de ton métier qui "
          + "recrutent sans publier d'annonce, à l'adresse qu'elles donnent sur leur site.",
      },
    }));

  const launch = async () => {
    setIsLaunching(true);
    setError(null);
    try {
      localStorage.setItem(SEND_PREF, allowSend ? "1" : "0");
      localStorage.setItem(SPONTANEOUS_PREF, String(spontaneous));
    } catch {
      /* préférence de confort seulement */
    }
    const run = await startRun(candidateId, {
      title: "Mes candidatures",
      objective: "apply",
      count,
      spontaneous,
      allowed_actions: { send: allowSend },
    });
    setIsLaunching(false);

    if (!run) {
      setError("Je n'ai pas pu démarrer. Une mission est peut-être déjà en cours.");
      return;
    }
    onLaunched(run);
  };

  const prompt = "Je prépare tes candidatures, puis j'envoie ce qui peut partir.";
  const body = (
    <div className="space-y-6">
      {/* Combien */}
      <div className="space-y-2.5">
        <p className="text-center text-xs text-[#1A1918]/55 uppercase tracking-wider font-medium">
          Sur combien d&apos;offres
        </p>
        <div className="flex justify-center gap-2">
          {COUNTS.map((n) => (
            <motion.button
              key={n}
              type="button"
              whileTap={{ scale: 0.95 }}
              onClick={() => setCount(n)}
              className={cn(
                "px-5 py-2 rounded-full border text-sm transition-colors cursor-pointer",
                count === n
                  ? "border-[#006045] bg-[#006045]/8 text-[#006045]"
                  : "border-[#1A1918]/12 text-[#1A1918]/60 hover:border-[#1A1918]/30 hover:text-[#1A1918]",
              )}
            >
              {n}
            </motion.button>
          ))}
        </div>
        <p className="text-center text-[11px] font-normal text-[#1A1918]/55">
          Les meilleures de tes offres retenues, celles que je peux envoyer en premier.
        </p>
      </div>

      {/* Les entreprises qui recrutent sans offre publiée */}
      <div className="space-y-2.5">
        <p className="text-center text-xs text-[#1A1918]/55 uppercase tracking-wider font-medium">
          Candidatures spontanées
        </p>
        <div className="flex justify-center gap-2">
          {SPONTANEOUS_COUNTS.map((n) => (
            <motion.button
              key={n}
              type="button"
              whileTap={{ scale: 0.95 }}
              onClick={() => (spontaneousLocked && n > 0 ? offerSpontaneous() : setSpontaneous(n))}
              className={cn(
                "px-4 py-2 rounded-full border text-sm transition-colors cursor-pointer",
                spontaneousLocked && n > 0 && "opacity-60",
                spontaneous === n
                  ? "border-[#006045] bg-[#006045]/8 text-[#006045]"
                  : "border-[#1A1918]/12 text-[#1A1918]/60 hover:border-[#1A1918]/30 hover:text-[#1A1918]",
              )}
            >
              {n === 0 ? "Aucune" : spontaneousLocked ? `🔒 ${n}` : n}
            </motion.button>
          ))}
        </div>
        <p className="text-center text-[11px] font-normal text-[#1A1918]/55 leading-relaxed">
          J&apos;écris aux entreprises de ton métier près de chez toi, à l&apos;adresse de recrutement
          qu&apos;elles publient sur leur site, avec une lettre qui parle d&apos;elles.
        </p>
      </div>

      {/* Le feu vert */}
      <div className="space-y-2.5">
        <p className="text-center text-xs text-[#1A1918]/55 uppercase tracking-wider font-medium">
          Quand un dossier peut partir
        </p>
        <div className="grid grid-cols-2 gap-2">
          {[
            { send: false, label: "Montre-le-moi d'abord", detail: "Tu valides d'un clic." },
            { send: true, label: "Envoie-le", detail: "Dans ton quota hebdomadaire." },
          ].map((opt) => (
            <motion.button
              key={String(opt.send)}
              type="button"
              whileTap={{ scale: 0.98 }}
              onClick={() => setAllowSend(opt.send)}
              className={cn(
                "p-3 rounded-2xl border text-left transition-colors cursor-pointer",
                allowSend === opt.send
                  ? "border-[#006045] bg-[#006045]/[0.06]"
                  : "border-[#1A1918]/10 hover:border-[#1A1918]/25",
              )}
            >
              <span className={cn("block text-sm", allowSend === opt.send ? "text-[#006045]" : "text-[#1A1918]")}>
                {opt.label}
              </span>
              <span className="block text-[11px] font-normal text-[#1A1918]/60 mt-0.5">{opt.detail}</span>
            </motion.button>
          ))}
        </div>
      </div>

      {/* Le contrat, dit en clair avant de partir */}
      <p className="text-xs font-normal text-[#1A1918]/50 text-center leading-relaxed tracking-tight">
        Pour chaque offre : CV adapté et lettre. Les offres qui se postulent sur le site de
        l&apos;employeur restent prêtes à finir avec l&apos;extension. Les candidatures spontanées
        partent seulement à une adresse publiée par l&apos;entreprise, quelques-unes par jour. Tu peux fermer l&apos;onglet, je t&apos;écris
        quand c&apos;est fini.
      </p>

      {error && <p className="text-xs text-red-600/80 text-center">{error}</p>}

      <div className="flex justify-center">
        <button
          type="button"
          onClick={launch}
          disabled={isLaunching}
          className="group inline-flex items-center gap-2.5 py-3 px-7 rounded-full bg-[#006045] text-white hover:bg-[#004d37] text-sm transition-all cursor-pointer disabled:opacity-40"
        >
          <span>Vas-y, je te laisse faire</span>
          {isLaunching ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
          )}
        </button>
      </div>
    </div>
  );

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-[60] flex items-center justify-center bg-[#FAFAF8]/92 backdrop-blur-sm px-6"
    >
      <button
        type="button"
        onClick={onClose}
        aria-label="Fermer"
        className="absolute top-5 right-6 p-2 rounded-full text-[#1A1918]/55 hover:text-[#1A1918] hover:bg-[#1A1918]/5 transition-colors cursor-pointer"
      >
        <X className="w-4 h-4 stroke-[1.4]" />
      </button>

      <motion.div
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
        className="w-full max-w-[440px] flex flex-col items-center gap-6"
      >
        <AlicePresence emotion={isLaunching ? "working" : "listening"} />

        <AnimatePresence mode="wait">
          <motion.p
            key="prompt"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.3 }}
            className="text-center text-lg md:text-xl font-normal text-[#1A1918]/85 tracking-tight"
          >
            {prompt}
          </motion.p>
        </AnimatePresence>

        <AnimatePresence mode="wait">
          <motion.div
            key="body"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.3 }}
            className="w-full"
          >
            {body}
          </motion.div>
        </AnimatePresence>

      </motion.div>
    </motion.div>
  );
}
