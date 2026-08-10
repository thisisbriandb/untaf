"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { ChevronDown, ChevronRight, ExternalLink, LogOut, Mail, Trash2 } from "lucide-react";
import { apiFetch, apiJson } from "@/lib/api";

interface ParametresViewProps {
  userName: string;
  userEmail: string;
  candidateId: string | null;
  onLogout: () => void;
}

interface SmtpSettings {
  smtp_email: string | null;
  configured: boolean;
}

/**
 * Le mot de passe d'application Gmail se génère ailleurs, sur un site que ni
 * l'utilisateur ni nous ne contrôlons — sans ce mini-tuto, la seule aide
 * possible est une phrase renvoyant vers une page Google que personne ne
 * connaît par cœur. Replié par défaut pour ne pas alourdir l'écran une fois
 * que l'utilisateur sait déjà comment faire.
 */
function SmtpTutorial() {
  const [open, setOpen] = useState(false);

  return (
    <div className="rounded-xl border border-[#1A1918]/8 overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-1.5 px-3.5 py-2.5 text-xs font-medium text-[#006045] hover:bg-[#006045]/5 transition-colors cursor-pointer"
      >
        {open ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
        Comment obtenir ce mot de passe ?
      </button>

      {open && (
        <ol className="px-4 pb-4 pt-1 space-y-3 text-xs text-[#1A1918]/60">
          <li className="flex gap-2.5">
            <span className="shrink-0 w-4 h-4 rounded-full bg-[#006045]/10 text-[#006045] text-[10px] font-semibold flex items-center justify-center mt-0.5">1</span>
            <span>
              Active la <strong className="text-[#1A1918]">validation en 2 étapes</strong> sur ton
              compte Google (obligatoire pour l'étape suivante) —{" "}
              <a
                href="https://myaccount.google.com/security"
                target="_blank"
                rel="noopener noreferrer"
                className="text-[#006045] hover:underline inline-flex items-center gap-0.5"
              >
                myaccount.google.com/security
                <ExternalLink className="h-2.5 w-2.5" />
              </a>
            </span>
          </li>
          <li className="flex gap-2.5">
            <span className="shrink-0 w-4 h-4 rounded-full bg-[#006045]/10 text-[#006045] text-[10px] font-semibold flex items-center justify-center mt-0.5">2</span>
            <span>
              Génère un <strong className="text-[#1A1918]">mot de passe d'application</strong> (donne-lui
              un nom, ex. « Alice ») —{" "}
              <a
                href="https://myaccount.google.com/apppasswords"
                target="_blank"
                rel="noopener noreferrer"
                className="text-[#006045] hover:underline inline-flex items-center gap-0.5"
              >
                myaccount.google.com/apppasswords
                <ExternalLink className="h-2.5 w-2.5" />
              </a>
              . Google affiche un code à 16 caractères — <strong className="text-[#1A1918]">copie-le
              tout de suite</strong>, il ne sera plus jamais réaffiché.
            </span>
          </li>
          <li className="flex gap-2.5">
            <span className="shrink-0 w-4 h-4 rounded-full bg-[#006045]/10 text-[#006045] text-[10px] font-semibold flex items-center justify-center mt-0.5">3</span>
            <span>
              Colle ce code ci-dessous, dans <strong className="text-[#1A1918]">« Mot de passe
              d'application »</strong> — ce n'est pas ton mot de passe Google habituel.
            </span>
          </li>
          <li className="pt-1 text-[#1A1918]/40 italic">
            La page n'apparaît pas ou renvoie une erreur ? La 2 étapes n'est pas encore activée
            (étape 1), ou ton compte est un compte professionnel dont l'administrateur a désactivé
            cette option.
          </li>
        </ol>
      )}
    </div>
  );
}

function SmtpSection({ candidateId }: { candidateId: string | null }) {
  const [settings, setSettings] = useState<SmtpSettings | null>(null);
  const [editing, setEditing] = useState(false);
  const [smtpEmail, setSmtpEmail] = useState("");
  const [appPassword, setAppPassword] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!candidateId) return;
    apiJson<SmtpSettings>(`/api/candidates/${candidateId}/smtp`)
      .then(setSettings)
      .catch(() => setSettings(null));
  }, [candidateId]);

  const handleSave = async () => {
    if (!candidateId || !smtpEmail.trim() || !appPassword.trim()) return;
    setIsSaving(true);
    setError(null);
    try {
      const updated = await apiJson<SmtpSettings>(`/api/candidates/${candidateId}/smtp`, {
        method: "PUT",
        body: JSON.stringify({ smtp_email: smtpEmail.trim(), app_password: appPassword }),
      });
      setSettings(updated);
      setEditing(false);
      setAppPassword("");
    } catch {
      setError("Impossible d'enregistrer — vérifie l'adresse et le mot de passe.");
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!candidateId) return;
    await apiFetch(`/api/candidates/${candidateId}/smtp`, { method: "DELETE" }).catch(() => null);
    setSettings({ smtp_email: null, configured: false });
  };

  return (
    <div className="space-y-3 pt-2">
      <div className="flex items-center gap-2">
        <Mail className="h-4 w-4 text-[#1A1918]/40" />
        <h3 className="text-sm font-medium text-[#1A1918]">Envoi d'emails</h3>
      </div>

      {settings?.configured && !editing ? (
        <div className="py-3.5 px-4 rounded-xl bg-[#FAFAF8] border border-[#1A1918]/8 flex items-center justify-between">
          <div>
            <p className="text-sm text-[#1A1918]">{settings.smtp_email}</p>
            <p className="text-[11px] text-[#1A1918]/40 mt-0.5">
              Tes candidatures partent depuis cette adresse.
            </p>
          </div>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => {
                setSmtpEmail(settings.smtp_email || "");
                setEditing(true);
              }}
              className="text-xs text-[#006045] hover:underline cursor-pointer px-2 py-1"
            >
              Modifier
            </button>
            <button
              type="button"
              onClick={handleDelete}
              aria-label="Retirer"
              className="p-1.5 rounded-lg text-red-500/70 hover:bg-red-50 hover:text-red-600 cursor-pointer"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      ) : (
        <div className="space-y-2.5 py-3.5 px-4 rounded-xl bg-[#FAFAF8] border border-[#1A1918]/8">
          <p className="text-[11px] text-[#1A1918]/40">
            Adresse Gmail + mot de passe d'application (pas ton mot de passe Google normal).
          </p>
          <SmtpTutorial />
          <input
            type="email"
            value={smtpEmail}
            onChange={(e) => setSmtpEmail(e.target.value)}
            placeholder="toi@gmail.com"
            autoComplete="email"
            className="w-full px-3.5 py-2.5 bg-white border border-[#EDECEA] rounded-xl text-sm placeholder:text-[#1A1918]/35 text-[#1A1918] focus:outline-none focus:border-[#006045] transition-all"
          />
          <input
            type="password"
            value={appPassword}
            onChange={(e) => setAppPassword(e.target.value)}
            placeholder="Mot de passe d'application"
            autoComplete="new-password"
            className="w-full px-3.5 py-2.5 bg-white border border-[#EDECEA] rounded-xl text-sm placeholder:text-[#1A1918]/35 text-[#1A1918] focus:outline-none focus:border-[#006045] transition-all"
          />
          {error && <p className="text-xs text-red-600/80">{error}</p>}
          <div className="flex gap-2 pt-1">
            <button
              type="button"
              onClick={handleSave}
              disabled={isSaving || !smtpEmail.trim() || !appPassword.trim()}
              className="px-4 py-2 rounded-xl bg-[#1A1918] text-white text-xs font-medium hover:bg-[#1A1918]/90 transition-all cursor-pointer disabled:opacity-40"
            >
              Enregistrer
            </button>
            {editing && (
              <button
                type="button"
                onClick={() => {
                  setEditing(false);
                  setError(null);
                }}
                className="px-4 py-2 rounded-xl text-xs font-medium text-[#1A1918]/50 hover:bg-[#1A1918]/5 transition-all cursor-pointer"
              >
                Annuler
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export function ParametresView({ userName, userEmail, candidateId, onLogout }: ParametresViewProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.35 }}
      className="w-full max-w-2xl text-left space-y-6 py-4"
    >
      <div>
        <h2 className="text-xl font-normal text-[#1A1918]">Paramètres du compte</h2>
        <p className="text-xs text-[#1A1918]/50 mt-0.5">
          Informations de ton profil et accès agent.
        </p>
      </div>

      <div className="space-y-3 text-sm">
        <div className="py-3.5 border-b border-[#1A1918]/8 flex justify-between">
          <span className="text-[#1A1918]/60">Nom complet</span>
          <span className="font-medium text-[#1A1918]">{userName}</span>
        </div>
        <div className="py-3.5 border-b border-[#1A1918]/8 flex justify-between">
          <span className="text-[#1A1918]/60">Email</span>
          <span className="font-medium text-[#1A1918]">{userEmail || "Non renseigné"}</span>
        </div>
      </div>

      <SmtpSection candidateId={candidateId} />

      <div className="pt-4 flex justify-start">
        <button
          type="button"
          onClick={onLogout}
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-medium text-red-600 hover:bg-red-50 transition-colors cursor-pointer border border-red-200"
        >
          <LogOut className="h-4 w-4" />
          Se déconnecter
        </button>
      </div>
    </motion.div>
  );
}
