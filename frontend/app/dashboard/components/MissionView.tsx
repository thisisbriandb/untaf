"use client";

import { useCallback, useEffect, useState } from "react";
import { motion } from "framer-motion";
import { ArrowRight, FolderOpen, Loader2, Pause, Play, Radar, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  fetchJournal,
  fetchMission,
  updateMission,
  type AutonomyLevel,
  type Mission,
  type MissionEvent,
} from "@/lib/mission-client";
import { fetchPipeline } from "@/lib/pipeline-client";
import { useAlice } from "../alice-context";

// ── Libellés ───────────────────────────────────────────────────────────────

const AUTONOMY: { id: AutonomyLevel; label: string; detail: string }[] = [
  {
    id: "propose",
    label: "Alice propose",
    detail: "Elle présélectionne, tu valides chaque envoi.",
  },
  {
    id: "auto_above",
    label: "Alice postule au-dessus d'un seuil",
    detail: "Envoi automatique sur le haut du panier, proposition en dessous.",
  },
  {
    id: "full",
    label: "Alice gère",
    detail: "Envoi automatique dans les limites de ton mandat.",
  },
];

const FAMILY_LABELS: Record<string, string> = {
  software: "Tech / Dév", data: "Data / IA", product: "Produit",
  design: "Design", sales: "Commercial", marketing: "Marketing",
  support: "Support client", hr: "RH", finance: "Finance",
  ops: "Ops / Logistique", legal: "Juridique", health: "Santé",
  engineering: "Ingénierie",
};

const LANGUAGE_LABELS: Record<string, string> = {
  fr: "Français", en: "Anglais", de: "Allemand",
  es: "Espagnol", it: "Italien", nl: "Néerlandais", pt: "Portugais",
};

const REMOTE_LABELS: Record<string, string> = {
  remote: "Remote", hybrid: "Hybride", onsite: "Sur site",
};

const CONTRACT_LABELS: Record<string, string> = {
  cdi: "CDI", cdd: "CDD", freelance: "Freelance",
  stage: "Stage", alternance: "Alternance", interim: "Intérim",
};

const EVENT_DOT: Record<string, string> = {
  scan: "bg-[#1A1918]/25",
  shortlist: "bg-[#161615]",
  letter_written: "bg-[#161615]/70",
  applied: "bg-[#161615]",
  awaiting_approval: "bg-[#161615]",
  error: "bg-red-500",
};

/** Les dossiers vivent dans Candidatures : on y emmène plutôt que de les décrire. */
function openCandidatures() {
  window.dispatchEvent(new CustomEvent("untaf:select-tab", { detail: "candidatures" }));
}

function relativeTime(iso: string): string {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return "à l'instant";
  if (diff < 3600) return `il y a ${Math.floor(diff / 60)} min`;
  if (diff < 86400) return `il y a ${Math.floor(diff / 3600)} h`;
  if (diff < 604800) return `il y a ${Math.floor(diff / 86400)} j`;
  return new Date(iso).toLocaleDateString("fr-FR", { day: "numeric", month: "short" });
}

// ── Fragments ──────────────────────────────────────────────────────────────

function Stat({ value, label }: { value: number; label: string }) {
  return (
    <div className="space-y-0.5">
      <p className="text-2xl font-light text-[#1A1918] tabular-nums leading-none">
        {value}
      </p>
      <p className="text-[11px] font-normal text-[#1A1918]/60 tracking-tight">{label}</p>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="py-3.5 flex items-start justify-between gap-4">
      <p className="text-xs text-[#1A1918]/55 uppercase tracking-wider font-medium shrink-0 pt-0.5">
        {label}
      </p>
      <div className="text-sm text-[#1A1918] text-right min-w-0">{children}</div>
    </div>
  );
}

function labelList(values: string[], map: Record<string, string>, empty: string) {
  if (!values?.length) return <span className="text-[#1A1918]/50">{empty}</span>;
  return <span>{values.map((v) => map[v] ?? v).join(" · ")}</span>;
}

// ── Vue ────────────────────────────────────────────────────────────────────

export function MissionView() {
  const { candidateId, submitQuery, goToConversation } = useAlice();

  /** Poser la question ET basculer sur le fil : la réponse y arrivera. */
  const askAlice = (question: string) => {
    goToConversation();
    void submitQuery(question);
  };
  const [mission, setMission] = useState<Mission | null>(null);
  const [journal, setJournal] = useState<MissionEvent[]>([]);
  const [readyPacks, setReadyPacks] = useState(0);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    if (!candidateId) {
      setLoading(false);
      return;
    }
    const [m, j, p] = await Promise.all([
      fetchMission(candidateId),
      fetchJournal(candidateId, 40),
      fetchPipeline(candidateId),
    ]);
    setMission(m);
    setJournal(j);
    // Prêts mais pas encore partis : ce que l'utilisateur vient chercher ici.
    setReadyPacks(
      p?.items.filter((i) => i.pack_ready && ["ready", "manual", "simulated", "awaiting"].includes(i.stage)).length ?? 0,
    );
    setLoading(false);
  }, [candidateId]);

  useEffect(() => {
    void load();
  }, [load]);

  const patch = async (changes: Parameters<typeof updateMission>[1]) => {
    if (!candidateId || !mission) return;
    setSaving(true);
    // Optimiste : le réglage doit répondre au clic, pas au réseau.
    setMission({ ...mission, ...changes } as Mission);
    await updateMission(candidateId, changes);
    await load();
    setSaving(false);
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center gap-2.5 py-16">
        <Loader2 className="w-5 h-5 animate-spin text-[#161615]" />
        <p className="text-xs font-normal text-[#1A1918]/50 tracking-tight">
          Je charge ta mission…
        </p>
      </div>
    );
  }

  if (!mission) {
    return (
      <p className="text-sm font-light text-[#1A1918]/50 tracking-tight text-center py-16">
        Je ne trouve pas ta mission. Reconnecte-toi.
      </p>
    );
  }

  const { criteria: c, stats } = mission;
  const isPaused = mission.status === "paused";
  const lastScan = journal.find((e) => e.kind === "scan");
  const reasons = Object.entries(lastScan?.payload?.top_reasons ?? {})
    .sort((a, b) => b[1] - a[1])
    .slice(0, 4);

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.35 }}
      className="scroll-discreet w-full h-full overflow-y-auto"
    >
      <div className="w-full max-w-[640px] mx-auto space-y-8 py-2 pb-8">
        {/* ═══ En-tête ═══ */}
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-normal text-[#1A1918] tracking-tight">
              {mission.title}
            </h2>
            <p className="text-xs text-[#1A1918]/50 mt-0.5 tracking-tight">
              {isPaused
                ? "En pause — je ne cherche plus."
                : mission.last_run_at
                  ? `Dernière veille ${relativeTime(mission.last_run_at)}.`
                  : "Veille pas encore lancée."}
            </p>
          </div>
          <button
            type="button"
            onClick={() => patch({ status: isPaused ? "active" : "paused" })}
            disabled={saving}
            className={cn(
              "flex items-center gap-1.5 px-3.5 py-2 rounded-full border text-xs font-normal tracking-tight transition-colors cursor-pointer shrink-0 disabled:opacity-40",
              isPaused
                ? "border-[#161615]/40 text-[#161615] hover:bg-[#161615]/6"
                : "border-[#1A1918]/12 text-[#1A1918]/60 hover:border-[#1A1918]/30 hover:text-[#1A1918]"
            )}
          >
            {isPaused ? <Play className="w-3.5 h-3.5" /> : <Pause className="w-3.5 h-3.5" />}
            {isPaused ? "Reprendre" : "Mettre en pause"}
          </button>
        </div>

        {/* ═══ Compteurs ═══ */}
        <div className="grid grid-cols-4 gap-4 py-5 border-t border-b border-[#1A1918]/10">
          <Stat value={stats.scanned_last_run} label="offres vues" />
          <Stat value={stats.shortlisted} label="retenues" />
          <Stat value={stats.applied} label="envoyées" />
          <Stat value={stats.interviews} label="entretiens" />
        </div>

        {/* ═══ Dossiers prêts ═══ */}
        {readyPacks > 0 && (
          <motion.button
            type="button"
            onClick={openCandidatures}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            whileTap={{ scale: 0.99 }}
            className="w-full flex items-center gap-3 p-4 rounded-2xl bg-[#161615]/[0.06] border border-[#161615]/15 text-left cursor-pointer hover:bg-[#161615]/10 transition-colors"
          >
            <FolderOpen className="h-4 w-4 text-[#161615] shrink-0" />
            <span className="flex-1 min-w-0">
              <span className="block text-sm text-[#1A1918] tracking-tight">
                {readyPacks} dossier{readyPacks > 1 ? "s prêts" : " prêt"}
              </span>
              <span className="block text-xs font-normal text-[#1A1918]/50 tracking-tight">
                CV adapté et lettre pour chaque offre, à télécharger ou envoyer depuis Candidatures.
              </span>
            </span>
            <span className="inline-flex items-center gap-1 text-xs text-[#161615] shrink-0">
              Voir <ArrowRight className="h-3 w-3" />
            </span>
          </motion.button>
        )}

        {/* ═══ Autonomie ═══ */}
        <section className="space-y-3">
          <p className="text-xs text-[#1A1918]/55 uppercase tracking-wider font-medium">
            Jusqu&apos;où je peux aller
          </p>
          <div className="divide-y divide-[#1A1918]/8 border-t border-b border-[#1A1918]/10">
            {AUTONOMY.map((level) => {
              const active = mission.autonomy === level.id;
              return (
                <button
                  key={level.id}
                  type="button"
                  onClick={() => patch({ autonomy: level.id })}
                  disabled={saving}
                  className="w-full py-3.5 flex items-start gap-3 text-left cursor-pointer group disabled:opacity-50"
                >
                  <span
                    className={cn(
                      "mt-0.5 w-3.5 shrink-0 text-center text-sm transition-colors",
                      active ? "text-[#161615]" : "text-[#1A1918]/20"
                    )}
                  >
                    {active ? "✓" : "—"}
                  </span>
                  <span className="min-w-0">
                    <span
                      className={cn(
                        "block text-sm tracking-tight transition-colors",
                        active ? "text-[#1A1918]" : "text-[#1A1918]/60 group-hover:text-[#1A1918]/70"
                      )}
                    >
                      {level.label}
                    </span>
                    <span className="block text-xs font-normal text-[#1A1918]/55 tracking-tight mt-0.5">
                      {level.detail}
                    </span>
                  </span>
                </button>
              );
            })}
          </div>

          {mission.autonomy === "auto_above" && (
            <div className="flex items-center justify-between gap-4 pt-1">
              <span className="text-xs font-normal text-[#1A1918]/55 tracking-tight">
                Seuil d&apos;envoi automatique
              </span>
              <div className="flex items-center gap-3 flex-1 max-w-[260px]">
                <input
                  type="range"
                  min={50}
                  max={100}
                  step={5}
                  value={mission.auto_apply_min_score}
                  onChange={(e) =>
                    setMission({ ...mission, auto_apply_min_score: Number(e.target.value) })
                  }
                  onMouseUp={(e) =>
                    patch({ auto_apply_min_score: Number((e.target as HTMLInputElement).value) })
                  }
                  className="flex-1 accent-[#161615] h-1 cursor-pointer"
                />
                <span className="text-sm text-[#161615] tabular-nums w-10 text-right">
                  {mission.auto_apply_min_score}%
                </span>
              </div>
            </div>
          )}

          <div className="flex items-center justify-between gap-4">
            <span className="text-xs font-normal text-[#1A1918]/55 tracking-tight">
              Maximum de candidatures par semaine
            </span>
            <div className="flex items-center gap-3 flex-1 max-w-[260px]">
              <input
                type="range"
                min={0}
                max={50}
                step={5}
                value={mission.weekly_quota}
                onChange={(e) => setMission({ ...mission, weekly_quota: Number(e.target.value) })}
                onMouseUp={(e) =>
                  patch({ weekly_quota: Number((e.target as HTMLInputElement).value) })
                }
                className="flex-1 accent-[#161615] h-1 cursor-pointer"
              />
              <span className="text-sm text-[#161615] tabular-nums w-10 text-right">
                {mission.weekly_quota}
              </span>
            </div>
          </div>
          <p className="text-[11px] font-normal text-[#1A1918]/50 tracking-tight">
            {stats.quota_remaining} envoi{stats.quota_remaining > 1 ? "s" : ""} restant
            {stats.quota_remaining > 1 ? "s" : ""} cette semaine.
          </p>
        </section>

        {/* ═══ Mandat ═══ */}
        <section className="space-y-3">
          <div className="flex items-baseline justify-between gap-3">
            <p className="text-xs text-[#1A1918]/55 uppercase tracking-wider font-medium">
              Mon mandat
            </p>
            {!mission.criteria_is_explicit && (
              <span className="text-[11px] font-normal text-[#1A1918]/50">
                déduit de ton profil
              </span>
            )}
          </div>
          <div className="border-t border-b border-[#1A1918]/10 divide-y divide-[#1A1918]/8">
            <Row label="Métier">{labelList(c.job_families, FAMILY_LABELS, "tous")}</Row>
            <Row label="Contrat">{labelList(c.contract_types, CONTRACT_LABELS, "tous")}</Row>
            <Row label="Zone">
              {c.countries?.length ? c.countries.join(" · ") : <span className="text-[#1A1918]/50">sans limite</span>}
            </Row>
            <Row label="Villes">
              {c.locations?.length ? c.locations.join(" · ") : <span className="text-[#1A1918]/50">indifférent</span>}
            </Row>
            <Row label="Rythme">{labelList(c.remote_policies, REMOTE_LABELS, "indifférent")}</Row>
            <Row label="Langues">{labelList(c.languages, LANGUAGE_LABELS, "toutes")}</Row>
          </div>

          {/* Pourquoi si peu d'offres — la question que le mandat pose toujours */}
          {reasons.length > 0 && (
            <div className="pt-1 space-y-1.5">
              <p className="text-[11px] font-normal text-[#1A1918]/55 tracking-tight">
                Sur la dernière veille, j&apos;ai écarté :
              </p>
              {reasons.map(([motif, n]) => (
                <p key={motif} className="text-xs font-normal text-[#1A1918]/55 tracking-tight">
                  <span className="tabular-nums text-[#1A1918]/70">{n}</span> offres — {motif}
                </p>
              ))}
              <button
                type="button"
                onClick={() => askAlice("Pourquoi j'ai si peu d'offres ? Que dois-je changer à mon mandat ?")}
                className="text-xs font-normal text-[#161615] hover:underline tracking-tight pt-1 cursor-pointer"
              >
                En parler à Alice →
              </button>
            </div>
          )}
        </section>

        {/* ═══ Journal ═══ */}
        <section className="space-y-3">
          <div className="flex items-center gap-1.5">
            <Radar className="w-3 h-3 stroke-[1.6] text-[#161615]" />
            <p className="text-xs text-[#1A1918]/55 uppercase tracking-wider font-medium">
              Ce que j&apos;ai fait
            </p>
          </div>

          {journal.length === 0 ? (
            <p className="text-sm font-light text-[#1A1918]/55 tracking-tight py-2">
              Rien à raconter pour l&apos;instant.
            </p>
          ) : (
            <div className="space-y-0 border-t border-[#1A1918]/10">
              {journal.map((e) => (
                <div
                  key={e.id}
                  {...(e.kind === "letter_written" && {
                    role: "button",
                    tabIndex: 0,
                    onClick: openCandidatures,
                    onKeyDown: (ev: React.KeyboardEvent) => ev.key === "Enter" && openCandidatures(),
                    title: "Voir le dossier dans Candidatures",
                  })}
                  className={cn(
                    "flex items-start gap-3 py-3 border-b border-[#1A1918]/6",
                    e.kind === "letter_written" && "cursor-pointer group hover:bg-[#161615]/[0.03]",
                  )}
                >
                  <span
                    className={cn(
                      "mt-1.5 h-1.5 w-1.5 rounded-full shrink-0",
                      EVENT_DOT[e.kind] ?? "bg-[#1A1918]/20"
                    )}
                  />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-light text-[#1A1918]/75 leading-relaxed tracking-tight">
                      {e.summary}
                      {e.kind === "letter_written" && (
                        <span className="ml-1.5 text-xs text-[#161615] opacity-60 group-hover:opacity-100 transition-opacity">
                          Voir →
                        </span>
                      )}
                    </p>
                  </div>
                  <span className="text-[11px] font-normal text-[#1A1918]/45 tracking-tight shrink-0 pt-0.5">
                    {relativeTime(e.created_at)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* ═══ Relais conversation ═══ */}
        <div className="flex flex-wrap gap-1.5 pt-1">
          <Sparkles className="w-3 h-3 stroke-[1.6] text-[#161615] mt-1.5 shrink-0" />
          {[
            "Fais-moi le bilan de la semaine",
            "Qu'est-ce que tu as fait aujourd'hui ?",
          ].map((q) => (
            <button
              key={q}
              type="button"
              onClick={() => askAlice(q)}
              className="px-2.5 py-1.5 rounded-full border border-[#1A1918]/10 bg-white text-[11px] font-normal text-[#1A1918]/65 tracking-tight hover:border-[#161615]/40 hover:text-[#161615] transition-colors cursor-pointer"
            >
              {q}
            </button>
          ))}
        </div>
      </div>
    </motion.div>
  );
}
