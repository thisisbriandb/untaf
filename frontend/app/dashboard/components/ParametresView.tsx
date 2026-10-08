"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Loader2, LogOut, Send } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  fetchNotificationSettings,
  saveNotificationPrefs,
  sendTestNotification,
  type DigestPeriod,
  type NotificationPrefs,
  type NotificationSettings,
} from "@/lib/pipeline-client";
import { useToast } from "./Toaster";
import { PlanSection } from "./Subscription";

interface ParametresViewProps {
  candidateId: string | null;
  userName: string;
  userEmail: string;
  onLogout: () => void;
}

const TOGGLES: { key: keyof NotificationPrefs; label: string; detail: string }[] = [
  { key: "mission_report", label: "Fin de mission", detail: "Mon compte rendu, et ce qui t'attend." },
  { key: "awaiting_approval", label: "Candidatures à valider", detail: "Quand un envoi attend ton feu vert." },
  { key: "application_sent", label: "Candidature envoyée", detail: "Confirmation de chaque envoi réel." },
  { key: "followups", label: "Relances", detail: "Quand une candidature reste sans réponse." },
];

const DIGESTS: { id: DigestPeriod; label: string }[] = [
  { id: "off", label: "Jamais" },
  { id: "daily", label: "Chaque soir" },
  { id: "weekly", label: "Le lundi" },
];

function Switch({ on, onChange, disabled }: { on: boolean; onChange: () => void; disabled?: boolean }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      onClick={onChange}
      disabled={disabled}
      className={cn(
        "relative h-5 w-9 shrink-0 rounded-full transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-default",
        on ? "bg-[#006045]" : "bg-[#1A1918]/15",
      )}
    >
      <motion.span
        layout
        transition={{ type: "spring", stiffness: 600, damping: 34 }}
        className={cn("absolute top-0.5 h-4 w-4 rounded-full bg-white shadow-sm", on ? "right-0.5" : "left-0.5")}
      />
    </button>
  );
}

export function ParametresView({ candidateId, userName, userEmail, onLogout }: ParametresViewProps) {
  const toast = useToast();
  const [settings, setSettings] = useState<NotificationSettings | null>(null);
  const [testing, setTesting] = useState(false);

  useEffect(() => {
    if (!candidateId) return;
    fetchNotificationSettings(candidateId).then(setSettings);
  }, [candidateId]);

  const update = async (changes: Partial<NotificationPrefs>) => {
    if (!candidateId || !settings) return;
    const prefs = { ...settings.prefs, ...changes };
    // Optimiste : un interrupteur répond au doigt, pas au réseau.
    setSettings({ ...settings, prefs });
    const saved = await saveNotificationPrefs(candidateId, prefs);
    if (!saved) {
      toast("Réglage non enregistré.", "warning");
      setSettings(settings);
    }
  };

  const test = async () => {
    if (!candidateId) return;
    setTesting(true);
    const record = await sendTestNotification(candidateId);
    setTesting(false);
    if (!record) toast("L'essai a échoué.", "warning");
    else if (record.status === "sent") toast(`E-mail d'essai envoyé à ${settings?.recipient}.`);
    else if (record.status === "simulated") toast("Aucun service d'e-mail configuré : rien n'est parti.", "info");
    else toast(`Échec d'envoi : ${record.error ?? "inconnu"}`, "warning");
  };

  const prefs = settings?.prefs;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.35 }}
      className="scroll-discreet w-full h-full overflow-y-auto"
    >
      <div className="w-full max-w-[640px] mx-auto text-left space-y-8 py-2 pb-10">
        <div>
          <h2 className="text-xl font-normal text-[#1A1918] tracking-tight">Paramètres</h2>
          <p className="text-xs text-[#1A1918]/50 mt-0.5 tracking-tight">
            Ton profil, et ce qu&apos;Alice a le droit de t&apos;écrire.
          </p>
        </div>

        <section className="text-sm border-t border-b border-[#1A1918]/10 divide-y divide-[#1A1918]/8">
          <div className="py-3.5 flex justify-between gap-4">
            <span className="text-[#1A1918]/60">Nom complet</span>
            <span className="font-medium text-[#1A1918]">{userName || "—"}</span>
          </div>
          <div className="py-3.5 flex justify-between gap-4">
            <span className="text-[#1A1918]/60">Email</span>
            <span className="font-medium text-[#1A1918] truncate">{userEmail || "Non renseigné"}</span>
          </div>
        </section>

        <PlanSection candidateId={candidateId} />

        {/* ═══ Notifications ═══ */}
        <section className="space-y-3">
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs text-[#1A1918]/55 uppercase tracking-wider font-medium">
              Notifications par e-mail
            </p>
            {prefs && <Switch on={prefs.enabled} onChange={() => update({ enabled: !prefs.enabled })} />}
          </div>

          {settings && !settings.delivery_configured && (
            <p className="text-[11px] font-normal text-[#006045] bg-[#F4F3F0] border border-[#006045]/20 rounded-xl px-3 py-2 tracking-tight">
              Aucun service d&apos;envoi n&apos;est configuré sur ce serveur : tes réglages sont
              enregistrés, mais rien ne partira tant que Resend ou SMTP ne sont pas renseignés.
            </p>
          )}

          {!prefs ? (
            <div className="space-y-2">
              {[0, 1, 2].map((i) => (
                <div key={i} className="h-10 rounded-xl bg-[#1A1918]/5 animate-pulse" />
              ))}
            </div>
          ) : (
            <motion.div
              animate={{ opacity: prefs.enabled ? 1 : 0.45 }}
              className="border-t border-b border-[#1A1918]/10 divide-y divide-[#1A1918]/8"
            >
              {TOGGLES.map((t) => (
                <div key={t.key} className="py-3 flex items-center justify-between gap-4">
                  <div className="min-w-0">
                    <p className="text-sm text-[#1A1918] tracking-tight">{t.label}</p>
                    <p className="text-xs font-normal text-[#1A1918]/60 tracking-tight">{t.detail}</p>
                  </div>
                  <Switch
                    on={Boolean(prefs[t.key])}
                    disabled={!prefs.enabled}
                    onChange={() => update({ [t.key]: !prefs[t.key] } as Partial<NotificationPrefs>)}
                  />
                </div>
              ))}

              <div className="py-3 flex items-center justify-between gap-4">
                <div className="min-w-0">
                  <p className="text-sm text-[#1A1918] tracking-tight">Rapport d&apos;activité</p>
                  <p className="text-xs font-normal text-[#1A1918]/60 tracking-tight">
                    Offres retenues, envois, réponses — seulement s&apos;il y a du nouveau.
                  </p>
                </div>
                <div className="flex shrink-0 rounded-full bg-[#1A1918]/5 p-0.5">
                  {DIGESTS.map((d) => (
                    <button
                      key={d.id}
                      type="button"
                      disabled={!prefs.enabled}
                      onClick={() => update({ digest: d.id })}
                      className={cn(
                        "relative rounded-full px-2.5 py-1 text-[11px] tracking-tight cursor-pointer disabled:cursor-default",
                        prefs.digest === d.id ? "text-[#1A1918]" : "text-[#1A1918]/60",
                      )}
                    >
                      {prefs.digest === d.id && (
                        <motion.span
                          layoutId="digest-pill"
                          className="absolute inset-0 rounded-full bg-white shadow-sm"
                          transition={{ type: "spring", stiffness: 500, damping: 36 }}
                        />
                      )}
                      <span className="relative">{d.label}</span>
                    </button>
                  ))}
                </div>
              </div>
            </motion.div>
          )}

          {settings && (
            <div className="flex items-center justify-between gap-3 pt-1">
              <p className="text-[11px] font-normal text-[#1A1918]/55 tracking-tight truncate">
                Envoyées à {settings.recipient}
              </p>
              <button
                type="button"
                onClick={test}
                disabled={testing}
                className="inline-flex items-center gap-1.5 rounded-full border border-[#1A1918]/10 px-3 py-1.5 text-[11px] text-[#1A1918]/70 hover:border-[#006045]/40 hover:text-[#006045] transition-colors cursor-pointer disabled:opacity-50"
              >
                {testing ? <Loader2 className="h-3 w-3 animate-spin" /> : <Send className="h-3 w-3" />}
                M&apos;envoyer un essai
              </button>
            </div>
          )}
        </section>

        <div className="pt-2 flex justify-start">
          <button
            type="button"
            onClick={onLogout}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-medium text-red-600 hover:bg-red-50 transition-colors cursor-pointer border border-red-200"
          >
            <LogOut className="h-4 w-4" />
            Se déconnecter
          </button>
        </div>
      </div>
    </motion.div>
  );
}
