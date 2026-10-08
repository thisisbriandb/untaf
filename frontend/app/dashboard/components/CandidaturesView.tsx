"use client";

/**
 * Candidatures — le suivi de bout en bout.
 *
 * De l'offre retenue à la réponse du recruteur, chaque candidature affiche son
 * étape et le seul geste qui reste à faire : valider un envoi, télécharger le
 * pack pour finir à la main, noter un entretien, relancer. Ce qui attend
 * l'utilisateur passe devant ; le reste se consulte.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { AnimatePresence, LayoutGroup, motion } from "framer-motion";
import {
  Check, ChevronDown, Eye, Copy, FolderDown, Loader2, Mail, RefreshCw,
  Send, Sparkles, X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { packUrl } from "@/lib/tailor-client";
import {
  approveAll,
  approveDispatch,
  fetchPipeline,
  followupMailto,
  markFollowup,
  prepareFollowup,
  rejectDispatch,
  STAGE_LABELS,
  updateApplicationStatus,
  type ApplicationStatus,
  type Followup,
  type Pipeline,
  type PipelineItem,
  type Stage,
} from "@/lib/pipeline-client";
import { APPLY_MODE_LABELS } from "@/lib/alice-client";
import { useAlice } from "../alice-context";
import { STAGE_TONE } from "@/lib/stage-tone";
import { DownloadLink } from "./ProtectedFile";
import { useToast } from "./Toaster";
import { FinishOnSite } from "./FinishOnSite";
import { invalidateApplication } from "@/lib/application-state";
import { chez, companyOf } from "@/lib/company";

// ── Filtres ───────────────────────────────────────────────────────────────

type Filter = "all" | "todo" | "ready" | "sent" | "replies";

const FILTERS: { id: Filter; label: string; stages: Stage[] | null }[] = [
  { id: "all", label: "Tout", stages: null },
  { id: "todo", label: "À faire", stages: ["awaiting", "manual", "simulated"] },
  { id: "ready", label: "Préparées", stages: ["to_prepare", "ready"] },
  { id: "sent", label: "Envoyées", stages: ["applied"] },
  { id: "replies", label: "Réponses", stages: ["interview", "offer", "rejected", "closed"] },
];

/** Ce qui attend l'utilisateur passe devant, le reste suit par score. */
const PRIORITY: Record<Stage, number> = {
  awaiting: 0, manual: 1, simulated: 2, interview: 3, offer: 3, applied: 4,
  ready: 5, to_prepare: 6, rejected: 8, closed: 8,
};

function when(iso: string | null): string {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("fr-FR", { day: "numeric", month: "short" });
}

// ── Fragments ─────────────────────────────────────────────────────────────

function ScoreRing({ score }: { score: number }) {
  const r = 15;
  const c = 2 * Math.PI * r;
  return (
    <div className="relative h-10 w-10 shrink-0" title={`${score} % de correspondance`}>
      <svg viewBox="0 0 36 36" className="h-10 w-10 -rotate-90">
        <circle cx="18" cy="18" r={r} fill="none" stroke="#1A1918" strokeOpacity="0.07" strokeWidth="2.5" />
        <motion.circle
          cx="18" cy="18" r={r} fill="none" stroke="#006045" strokeWidth="2.5" strokeLinecap="round"
          strokeDasharray={c}
          initial={{ strokeDashoffset: c }}
          animate={{ strokeDashoffset: c * (1 - Math.min(100, score) / 100) }}
          transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
        />
      </svg>
      <span className="absolute inset-0 flex items-center justify-center text-[11px] tabular-nums text-[#1A1918]/70">
        {score}
      </span>
    </div>
  );
}

function ActionButton({
  onClick, children, tone = "ghost", busy, disabled,
}: {
  onClick?: () => void;
  children: React.ReactNode;
  tone?: "primary" | "ghost" | "danger";
  busy?: boolean;
  disabled?: boolean;
}) {
  return (
    <motion.button
      type="button"
      whileTap={{ scale: 0.96 }}
      onClick={onClick}
      disabled={busy || disabled}
      className={cn(
        "inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full px-3 py-1.5 text-[11px] tracking-tight transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-default",
        tone === "primary" && "bg-[#006045] text-white hover:bg-[#004d37]",
        tone === "ghost" && "border border-[#1A1918]/10 text-[#1A1918]/70 hover:border-[#006045]/40 hover:text-[#006045]",
        tone === "danger" && "text-[#1A1918]/60 hover:text-red-600 hover:bg-red-50",
      )}
    >
      {busy && <Loader2 className="h-3 w-3 animate-spin" />}
      {children}
    </motion.button>
  );
}

// ── Relance ───────────────────────────────────────────────────────────────

function FollowupPanel({
  candidateId, item, onChange,
}: {
  candidateId: string;
  item: PipelineItem;
  onChange: () => void;
}) {
  const toast = useToast();
  const [draft, setDraft] = useState<Followup | null>(item.followup.body ? item.followup : null);
  const [loading, setLoading] = useState(!item.followup.body);

  const load = useCallback(async (regenerate = false) => {
    setLoading(true);
    const f = await prepareFollowup(candidateId, item.application_id, regenerate);
    if (f) setDraft(f);
    else toast("Je n'ai pas pu rédiger la relance.", "warning");
    setLoading(false);
  }, [candidateId, item.application_id, toast]);

  // Première rédaction à l'ouverture, si aucune n'existe encore.
  useEffect(() => {
    if (item.followup.body) return;
    let alive = true;
    prepareFollowup(candidateId, item.application_id).then((f) => {
      if (!alive) return;
      if (f) setDraft(f);
      else toast("Je n'ai pas pu rédiger la relance.", "warning");
      setLoading(false);
    });
    return () => {
      alive = false;
    };
  }, [candidateId, item.application_id, item.followup.body, toast]);

  const mark = async (status: "sent" | "dismissed") => {
    await markFollowup(candidateId, item.application_id, status);
    toast(status === "sent" ? "Relance notée comme envoyée." : "Relance écartée.", status === "sent" ? "success" : "info");
    onChange();
  };

  if (loading || !draft) {
    return (
      <div className="flex items-center gap-2 py-3 text-xs font-normal text-[#1A1918]/50">
        <Loader2 className="h-3.5 w-3.5 animate-spin text-[#006045]" />
        Je rédige une relance courte et polie…
      </div>
    );
  }

  return (
    <div className="space-y-2.5 rounded-xl bg-[#FAFAF8] border border-[#1A1918]/6 p-3">
      <input
        value={draft.subject ?? ""}
        onChange={(e) => setDraft({ ...draft, subject: e.target.value })}
        className="w-full bg-transparent text-xs font-medium text-[#1A1918] outline-none"
      />
      <textarea
        value={draft.body ?? ""}
        onChange={(e) => setDraft({ ...draft, body: e.target.value })}
        rows={7}
        className="w-full resize-y bg-transparent text-xs font-normal leading-relaxed text-[#1A1918]/80 outline-none"
      />
      <div className="flex flex-wrap items-center gap-1.5">
        <a
          href={followupMailto(draft)}
          className="inline-flex items-center gap-1.5 rounded-full bg-[#006045] px-3 py-1.5 text-[11px] text-white hover:bg-[#004d37]"
        >
          <Mail className="h-3 w-3" />
          {draft.to ? `Écrire à ${draft.to}` : "Ouvrir ma messagerie"}
        </a>
        <ActionButton
          onClick={async () => {
            await navigator.clipboard.writeText(`${draft.subject}\n\n${draft.body}`);
            toast("Relance copiée.");
          }}
        >
          <Copy className="h-3 w-3" /> Copier
        </ActionButton>
        <ActionButton onClick={() => load(true)}>
          <RefreshCw className="h-3 w-3" /> Réécrire
        </ActionButton>
        <span className="flex-1" />
        <ActionButton onClick={() => mark("sent")}>
          <Check className="h-3 w-3" /> C&apos;est envoyé
        </ActionButton>
        <ActionButton tone="danger" onClick={() => mark("dismissed")}>Écarter</ActionButton>
      </div>
    </div>
  );
}

// ── Ligne ─────────────────────────────────────────────────────────────────

const OUTCOMES: { status: ApplicationStatus; label: string }[] = [
  { status: "interview", label: "Entretien" },
  { status: "offer", label: "Offre" },
  { status: "rejected", label: "Refus" },
];

/** Corriger un statut, y compris revenir d'un refus ou d'une offre posés par erreur. */
const CORRECTIONS: { status: ApplicationStatus; label: string }[] = [
  { status: "applied", label: "Envoyée" },
  { status: "interview", label: "Entretien" },
  { status: "offer", label: "Offre" },
  { status: "rejected", label: "Refusée" },
  { status: "closed", label: "Close" },
];

function Row({
  candidateId, item, onRefresh,
}: {
  candidateId: string;
  item: PipelineItem;
  onRefresh: () => void;
}) {
  const toast = useToast();
  const { openCanvas } = useAlice();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [showFollowup, setShowFollowup] = useState(false);
  const [fixing, setFixing] = useState(false);

  const run = async (key: string, action: () => Promise<unknown>) => {
    setBusy(key);
    await action();
    setBusy(null);
    invalidateApplication(item.job_id);
    onRefresh();
  };

  const approve = () =>
    run("approve", async () => {
      const d = await approveDispatch(candidateId, item.dispatch!.id);
      if (!d) return toast("L'envoi n'a pas pu partir.", "warning");
      if (d.status === "sent") toast(`Candidature envoyée${chez(item.company_name)}.`);
      else if (d.status === "simulated") toast(`Répétition : rien n'est parti (${d.error}).`, "info");
      else toast(`Non abouti : ${d.error ?? "erreur inconnue"}`, "warning");
    });

  const setOutcome = (status: ApplicationStatus, label: string) =>
    run(status, async () => {
      const ok = await updateApplicationStatus(item.application_id, status);
      toast(ok ? `${label} noté pour « ${item.title} ».` : "Changement non enregistré.", ok ? "success" : "warning");
    });

  const correct = (status: ApplicationStatus, label: string) =>
    run(`fix-${status}`, async () => {
      const ok = await updateApplicationStatus(item.application_id, status, "corrigé à la main");
      toast(ok ? `Statut corrigé : ${label}.` : "Changement non enregistré.", ok ? "success" : "warning");
      if (ok) setFixing(false);
    });

  const jobCard = {
    id: item.job_id,
    title: item.title,
    company_name: item.company_name,
    location: item.location ?? "",
    match_score: item.match_score,
    contract_type: item.contract_type,
    remote_policy: item.remote_policy,
    source_url: item.source_url ?? "",
    status: item.status,
    apply_mode: item.apply_mode,
  };

  const openJob = () =>
    openCanvas({
      mode: "job_detail",
      job: {
        id: item.job_id,
        title: item.title,
        company_name: item.company_name,
        location: item.location ?? "",
        match_score: item.match_score,
        contract_type: item.contract_type,
        remote_policy: item.remote_policy,
        source_url: item.source_url ?? "",
        status: item.status,
        apply_mode: item.apply_mode,
      },
    });

  // Avant l'envoi, dire qui appuiera sur « envoyer » — c'est la promesse.
  const modeLabel = ["to_prepare", "ready"].includes(item.stage) ? APPLY_MODE_LABELS[item.apply_mode] : null;
  const subtitle = [companyOf(item.company_name) ?? "Employeur non communiqué", item.location, modeLabel].filter(Boolean).join(" · ");
  const detail =
    item.stage === "applied" && item.applied_at
      ? `Envoyée le ${when(item.applied_at)}${item.dispatch?.destination && item.dispatch.channel === "email" ? ` à ${item.dispatch.destination}` : ""}`
      : item.dispatch?.error && ["awaiting", "manual", "simulated"].includes(item.stage)
        ? item.dispatch.error
        : null;

  return (
    <motion.li
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, x: -12, transition: { duration: 0.18 } }}
      transition={{ type: "spring", stiffness: 380, damping: 34 }}
      className="py-3.5"
    >
      <div className="flex items-start gap-3">
        <ScoreRing score={item.match_score} />

        <div className="min-w-0 flex-1 space-y-1.5">
          <div className="flex items-start justify-between gap-3">
            <button type="button" onClick={openJob} className="min-w-0 text-left cursor-pointer group">
              <p className="text-sm text-[#1A1918] tracking-tight truncate group-hover:text-[#006045] transition-colors">
                {item.title}
              </p>
              <p className="text-[11px] font-normal text-[#1A1918]/50 tracking-tight truncate">{subtitle}</p>
            </button>
            <motion.span
              key={item.stage}
              initial={{ scale: 0.85, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              className={cn("shrink-0 rounded-full px-2 py-0.5 text-[11px] tracking-tight", STAGE_TONE[item.stage])}
            >
              {STAGE_LABELS[item.stage]}
            </motion.span>
          </div>

          {detail && (
            <p className="text-[11px] font-normal text-[#1A1918]/60 tracking-tight leading-relaxed">{detail}</p>
          )}

          {/* ── Le geste qui reste ── */}
          <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
            {item.stage === "awaiting" && item.dispatch && (
              <>
                <ActionButton onClick={() => openCanvas({ mode: "review", job: jobCard })}>
                  <Eye className="h-3 w-3" /> Relire
                </ActionButton>
                <ActionButton tone="primary" onClick={approve} busy={busy === "approve"}>
                  <Send className="h-3 w-3" /> Valider l&apos;envoi
                </ActionButton>
                <ActionButton
                  tone="danger"
                  busy={busy === "reject"}
                  onClick={() =>
                    run("reject", async () => {
                      await rejectDispatch(candidateId, item.dispatch!.id);
                      toast("Je ne l'enverrai pas.", "info");
                    })
                  }
                >
                  <X className="h-3 w-3" /> Refuser
                </ActionButton>
              </>
            )}

            {(item.stage === "to_prepare" || item.stage === "ready") && (
              <ActionButton tone={item.stage === "ready" ? "primary" : "ghost"} onClick={openJob}>
                {item.stage === "ready" ? <Send className="h-3 w-3" /> : <Sparkles className="h-3 w-3" />}
                {item.stage === "ready" ? "Postuler" : "Préparer le pack"}
              </ActionButton>
            )}

            {(item.stage === "manual" || item.stage === "simulated") &&
              item.dispatch?.channel === "email" && item.dispatch.mailto && (
                <a
                  href={item.dispatch.mailto}
                  className="inline-flex items-center gap-1.5 rounded-full bg-[#006045] px-3 py-1.5 text-[11px] text-white hover:bg-[#004d37]"
                >
                  <Mail className="h-3 w-3" /> Envoyer depuis ma messagerie
                </a>
              )}

            {(item.stage === "manual" || item.stage === "simulated") &&
              item.dispatch?.channel !== "email" && item.source_url && (
              <FinishOnSite
                candidateId={candidateId}
                jobId={item.job_id}
                companyName={item.company_name}
                url={item.source_url}
                onDone={onRefresh}
              />
            )}

            {(item.pack_ready || item.dispatch) && (
              <DownloadLink
                url={packUrl(candidateId, item.job_id)}
                filename={`Candidature_${item.company_name}.zip`}
                className="inline-flex items-center gap-1.5 rounded-full border border-[#1A1918]/10 px-3 py-1.5 text-[11px] text-[#1A1918]/70 hover:border-[#006045]/40 hover:text-[#006045] transition-colors"
              >
                <FolderDown className="h-3 w-3" /> Pack
              </DownloadLink>
            )}

            {item.followup.due && (
              <ActionButton tone="primary" onClick={() => setShowFollowup((v) => !v)}>
                <Mail className="h-3 w-3" /> Relancer · {item.followup.days_since_applied} j
              </ActionButton>
            )}

            {(item.stage === "applied" || item.stage === "interview") &&
              OUTCOMES.filter((o) => o.status !== item.status).map((o) => (
                <ActionButton key={o.status} busy={busy === o.status} onClick={() => setOutcome(o.status, o.label)}>
                  {o.label}
                </ActionButton>
              ))}

            {["interview", "offer", "rejected", "closed"].includes(item.stage) && (
              <ActionButton onClick={() => setFixing((v) => !v)}>
                {fixing ? "Annuler" : "Corriger le statut"}
              </ActionButton>
            )}
            {fixing &&
              CORRECTIONS.filter((c) => c.status !== item.status).map((c) => (
                <ActionButton key={c.status} busy={busy === `fix-${c.status}`} onClick={() => correct(c.status, c.label)}>
                  {c.label}
                </ActionButton>
              ))}

            {/* « Finir sur le site » demande déjà au retour ; sinon, le geste reste là. */}
            {(item.stage === "ready" || (["manual", "simulated"].includes(item.stage) && !item.source_url)) && (
              <ActionButton busy={busy === "applied"} onClick={() => setOutcome("applied", "Envoi")}>
                <Check className="h-3 w-3" /> J&apos;ai postulé
              </ActionButton>
            )}

            {item.timeline.length > 0 && (
              <button
                type="button"
                onClick={() => setOpen((v) => !v)}
                aria-label="Historique"
                className="ml-auto p-1 rounded-full text-[#1A1918]/50 hover:text-[#1A1918] cursor-pointer"
              >
                <ChevronDown className={cn("h-3.5 w-3.5 transition-transform", open && "rotate-180")} />
              </button>
            )}
          </div>

          <AnimatePresence initial={false}>
            {showFollowup && (
              <motion.div
                key="followup"
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                className="overflow-hidden pt-1"
              >
                <FollowupPanel
                  candidateId={candidateId}
                  item={item}
                  onChange={() => {
                    setShowFollowup(false);
                    onRefresh();
                  }}
                />
              </motion.div>
            )}
            {open && (
              <motion.ol
                key="timeline"
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                className="overflow-hidden border-l border-[#1A1918]/10 ml-1 pl-3 space-y-1.5 pt-1"
              >
                {[...item.timeline].reverse().map((t, i) => (
                  <li key={`${t.at}-${i}`} className="text-[11px] font-normal text-[#1A1918]/55 tracking-tight">
                    <span className="text-[#1A1918]/75">{STAGE_LABELS[t.status as Stage] ?? t.status}</span>
                    {" · "}
                    {when(t.at)}
                    {t.note ? ` — ${t.note}` : ""}
                  </li>
                ))}
              </motion.ol>
            )}
          </AnimatePresence>
        </div>
      </div>
    </motion.li>
  );
}

// ── Vue ───────────────────────────────────────────────────────────────────

export function CandidaturesView({
  candidateId,
  onPipelineChange,
}: {
  candidateId: string | null;
  onPipelineChange?: (pipeline: Pipeline) => void;
}) {
  const toast = useToast();
  const [pipeline, setPipeline] = useState<Pipeline | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [approvingAll, setApprovingAll] = useState(false);

  const refresh = useCallback(async () => {
    if (!candidateId) return;
    const p = await fetchPipeline(candidateId);
    if (p) {
      setPipeline(p);
      onPipelineChange?.(p);
    }
  }, [candidateId, onPipelineChange]);

  useEffect(() => {
    if (!candidateId) return;
    let alive = true;
    fetchPipeline(candidateId).then((p) => {
      if (!alive || !p) return;
      setPipeline(p);
      onPipelineChange?.(p);
    });
    return () => {
      alive = false;
    };
  }, [candidateId, onPipelineChange]);

  const items = useMemo(() => {
    const stages = FILTERS.find((f) => f.id === filter)?.stages;
    return (pipeline?.items ?? [])
      .filter((i) => !stages || stages.includes(i.stage) || (filter === "todo" && i.followup.due))
      .sort((a, b) =>
        Number(b.followup.due) - Number(a.followup.due) ||
        PRIORITY[a.stage] - PRIORITY[b.stage] ||
        b.match_score - a.match_score,
      );
  }, [pipeline, filter]);

  const counts = pipeline?.counts ?? {};
  const awaiting = counts.awaiting ?? 0;
  const countFor = (f: (typeof FILTERS)[number]) =>
    f.stages
      ? f.stages.reduce((n, s) => n + (counts[s] ?? 0), 0) + (f.id === "todo" ? counts.followup_due ?? 0 : 0)
      : pipeline?.items.length ?? 0;

  const handleApproveAll = async () => {
    if (!candidateId) return;
    setApprovingAll(true);
    const r = await approveAll(candidateId);
    setApprovingAll(false);
    if (!r) return toast("La validation groupée a échoué.", "warning");
    if (r.sent) toast(`${r.sent} candidature${r.sent > 1 ? "s envoyées" : " envoyée"}.`);
    if (r.simulated) toast(`${r.simulated} en répétition : rien n'est parti.`, "info");
    if (r.failed) toast(`${r.failed} non abouti${r.failed > 1 ? "s" : ""} — pack disponible pour finir à la main.`, "warning");
    invalidateApplication();
    void refresh();
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.35 }}
      className="scroll-discreet w-full h-full overflow-y-auto"
    >
      <div className="w-full max-w-[640px] mx-auto space-y-5 py-2 pb-10 text-left">
        <div className="flex items-end justify-between gap-4">
          <div>
            <h2 className="text-xl font-normal text-[#1A1918] tracking-tight">Candidatures</h2>
            <p className="text-xs text-[#1A1918]/50 mt-0.5 tracking-tight">
              De l&apos;offre retenue à la réponse : où en est chacune, et ce qui reste à faire.
            </p>
          </div>
          <button
            type="button"
            onClick={() => void refresh()}
            aria-label="Rafraîchir"
            className="p-2 rounded-full text-[#1A1918]/50 hover:text-[#1A1918] hover:bg-[#1A1918]/5 transition-colors cursor-pointer"
          >
            <RefreshCw className="h-3.5 w-3.5" />
          </button>
        </div>

        {/* ── File de validation ── */}
        <AnimatePresence>
          {awaiting > 0 && (
            <motion.div
              initial={{ opacity: 0, y: -6, height: 0 }}
              animate={{ opacity: 1, y: 0, height: "auto" }}
              exit={{ opacity: 0, y: -6, height: 0 }}
              className="overflow-hidden"
            >
              <div className="flex items-center justify-between gap-3 rounded-2xl border border-[#006045]/25 bg-[#F4F3F0]/60 px-4 py-3">
                <div className="flex items-center gap-2.5 min-w-0">
                  <span className="relative flex h-2 w-2 shrink-0">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#006045]/50" />
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-[#006045]" />
                  </span>
                  <p className="text-xs text-[#1A1918]/80 tracking-tight">
                    {awaiting} candidature{awaiting > 1 ? "s attendent" : " attend"} ton feu vert. Tout est
                    rédigé.
                  </p>
                </div>
                <ActionButton tone="primary" onClick={handleApproveAll} busy={approvingAll}>
                  <Send className="h-3 w-3" /> Tout valider
                </ActionButton>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* ── Filtres ── */}
        <LayoutGroup>
          <div className="flex gap-1 overflow-x-auto scrollbar-none">
            {FILTERS.map((f) => {
              const active = f.id === filter;
              const n = countFor(f);
              return (
                <button
                  key={f.id}
                  type="button"
                  onClick={() => setFilter(f.id)}
                  className={cn(
                    "relative shrink-0 whitespace-nowrap rounded-full px-3 py-1.5 text-[11px] tracking-tight transition-colors cursor-pointer",
                    active ? "text-white" : "text-[#1A1918]/55 hover:text-[#1A1918]",
                  )}
                >
                  {active && (
                    <motion.span
                      layoutId="candidatures-filter"
                      className="absolute inset-0 rounded-full bg-[#1A1918]"
                      transition={{ type: "spring", stiffness: 500, damping: 38 }}
                    />
                  )}
                  <span className="relative">
                    {f.label}
                    {n > 0 && <span className={cn("ml-1 tabular-nums", active ? "text-white/60" : "text-[#1A1918]/50")}>{n}</span>}
                  </span>
                </button>
              );
            })}
          </div>
        </LayoutGroup>

        {/* ── Liste ── */}
        {!pipeline ? (
          <div className="space-y-3 pt-2">
            {[0, 1, 2].map((i) => (
              <div key={i} className="flex items-center gap-3 animate-pulse">
                <div className="h-10 w-10 rounded-full bg-[#1A1918]/6" />
                <div className="flex-1 space-y-1.5">
                  <div className="h-3 w-2/3 rounded bg-[#1A1918]/6" />
                  <div className="h-2.5 w-1/3 rounded bg-[#1A1918]/5" />
                </div>
              </div>
            ))}
          </div>
        ) : items.length === 0 ? (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="py-10 space-y-1.5">
            <p className="text-sm font-light text-[#1A1918]/60 tracking-tight">
              {filter === "all" ? "Aucune candidature pour l'instant." : "Rien ici pour le moment."}
            </p>
            <p className="text-xs font-normal text-[#1A1918]/55 tracking-tight">
              {filter === "all"
                ? "Confie-moi une mission depuis la conversation : je retiens les offres et je prépare les packs."
                : "Tout ce qui demande ton attention apparaîtra ici."}
            </p>
          </motion.div>
        ) : (
          candidateId && (
            <ul className="divide-y divide-[#1A1918]/8 border-t border-b border-[#1A1918]/10">
              <AnimatePresence initial={false}>
                {items.map((item) => (
                  <Row key={item.application_id} candidateId={candidateId} item={item} onRefresh={refresh} />
                ))}
              </AnimatePresence>
            </ul>
          )
        )}
      </div>
    </motion.div>
  );
}
