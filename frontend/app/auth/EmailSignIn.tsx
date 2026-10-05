"use client";

/**
 * Connexion par e-mail, sans mot de passe : un lien et un code.
 *
 * Le lien s'ouvre souvent dans un autre onglet ; la session y est créée puis
 * vue par cet onglet-ci (événement `storage`), qui reprend alors la main
 * (`onSignedIn`). Le code à 6 chiffres permet de rester sur place —
 * utile sur mobile, où le lien ouvre parfois un autre navigateur.
 */

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, Loader2, Mail } from "lucide-react";
import { onSessionChange, requestLoginLink, sessionEmail, verifyLogin } from "@/lib/auth";

export function EmailSignIn({
  initialEmail = "",
  onSignedIn,
  title = "Connecte-toi pour retrouver ton espace.",
  autoSend = false,
}: {
  initialEmail?: string;
  onSignedIn: () => void;
  title?: string;
  /** Envoie le lien dès l'affichage, quand l'adresse est déjà connue. */
  autoSend?: boolean;
}) {
  const [email, setEmail] = useState(initialEmail);
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const signedIn = useRef(false);
  const autoSent = useRef(false);

  // Déjà connecté, ou connexion faite dans un autre onglet (clic sur le lien) :
  // on reprend la main ici.
  useEffect(() => {
    const done = () => {
      if (signedIn.current) return;
      signedIn.current = true;
      onSignedIn();
    };
    if (sessionEmail()) done();
    return onSessionChange((on) => on && done());
  }, [onSignedIn]);

  const send = async (address: string) => {
    const target = address.trim().toLowerCase();
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(target)) {
      setError("Cette adresse ne semble pas valide.");
      return;
    }
    setBusy(true);
    setError(null);
    const err = await requestLoginLink(target);
    setBusy(false);
    if (err) {
      setError(
        err === "rate_limited"
          ? "Trop de demandes rapprochées. Réessaie dans quelques minutes."
          : err === "invalid"
            ? "Cette adresse ne semble pas valide."
            : "Je n'ai pas pu envoyer le lien. Réessaie dans un moment.",
      );
      return;
    }
    setSentTo(target);
  };

  useEffect(() => {
    if (autoSend && initialEmail && !autoSent.current) {
      autoSent.current = true;
      void send(initialEmail);
    }
    // Seul le premier rendu compte ici : la garde `autoSent` l'assure.
  }, [autoSend, initialEmail]);

  const verify = async () => {
    if (!sentTo) return;
    setBusy(true);
    setError(null);
    const ok = await verifyLogin({ email: sentTo, code: code.trim() });
    setBusy(false);
    if (!ok) setError("Ce code ne correspond pas, ou il a expiré.");
  };

  return (
    <div className="w-full max-w-[380px] space-y-5">
      <AnimatePresence mode="wait">
        {!sentTo ? (
          <motion.form
            key="email"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            onSubmit={(e) => {
              e.preventDefault();
              void send(email);
            }}
            className="space-y-4"
          >
            <p className="text-center text-lg font-normal text-[#1A1918]/85 tracking-tight">{title}</p>
            <div className="flex items-center bg-white border border-[#EDECEA] focus-within:border-[#161615] rounded-full pl-4 pr-1.5 py-1.5 shadow-sm transition-colors">
              <Mail className="h-4 w-4 text-[#1A1918]/45 shrink-0" />
              <input
                type="email"
                autoComplete="email"
                autoFocus
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="ton@email.fr"
                className="flex-1 bg-transparent px-3 text-sm font-light outline-none placeholder:text-[#1A1918]/50"
              />
              <button
                type="submit"
                disabled={busy || !email.trim()}
                aria-label="Recevoir un lien de connexion"
                className="p-2 rounded-full bg-[#006045] text-white hover:bg-[#004d37] disabled:opacity-30 cursor-pointer"
              >
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowRight className="h-4 w-4" />}
              </button>
            </div>
            <p className="text-center text-[11px] font-normal text-[#1A1918]/55 tracking-tight">
              Pas de mot de passe : je t&apos;envoie un lien et un code, depuis alice@alice-agent.fr.
            </p>
          </motion.form>
        ) : (
          <motion.div
            key="sent"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            className="space-y-4 text-center"
          >
            <p className="text-lg font-normal text-[#1A1918]/85 tracking-tight">Vérifie ta boîte mail.</p>
            <p className="text-sm font-light text-[#1A1918]/55 tracking-tight leading-relaxed">
              J&apos;ai envoyé un lien à <span className="text-[#1A1918]">{sentTo}</span>. Clique dessus —
              je t&apos;attends ici, cet onglet reprendra tout seul.
            </p>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void verify();
              }}
              className="flex items-center justify-center gap-2 pt-1"
            >
              <input
                inputMode="numeric"
                autoComplete="one-time-code"
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 10))}
                placeholder="ou le code reçu"
                className="w-40 text-center bg-white border border-[#EDECEA] focus:border-[#161615] rounded-full px-4 py-2 text-sm tracking-widest outline-none"
              />
              <button
                type="submit"
                disabled={busy || code.length < 6}
                className="px-4 py-2 rounded-full bg-[#006045] text-white hover:bg-[#004d37] text-xs disabled:opacity-30 cursor-pointer"
              >
                {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "Valider"}
              </button>
            </form>
            <div className="flex items-center justify-center gap-2 text-[11px] font-normal text-[#1A1918]/60">
              <span className="relative flex h-1.5 w-1.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#006045]/50" />
                <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-[#006045]" />
              </span>
              En attente de confirmation
            </div>
            <button
              type="button"
              onClick={() => {
                setSentTo(null);
                setCode("");
              }}
              className="text-[11px] font-normal text-[#1A1918]/55 hover:text-[#1A1918] cursor-pointer"
            >
              Changer d&apos;adresse ou renvoyer
            </button>
          </motion.div>
        )}
      </AnimatePresence>
      {error && <p className="text-center text-xs text-red-600/80">{error}</p>}
    </div>
  );
}
