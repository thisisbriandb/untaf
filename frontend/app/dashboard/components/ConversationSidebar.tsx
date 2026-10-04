"use client";

/**
 * Les conversations, rangées : le fil général avec Alice, puis une
 * conversation par offre, sous le nom de l'entreprise.
 *
 * Chaque conversation d'offre garde son propre contexte (l'annonce, le
 * dossier, ce qui s'est dit) : parler de Doctolib ne pollue pas ce qui se dit
 * sur Alan. Les chiffres, eux, restent communs — ils viennent de la base à
 * chaque tour, pas de la conversation.
 *
 * Chaque entreprise porte l'état de son dossier (prêt, à valider, envoyé) :
 * la barre dit où en est chaque candidature, pas seulement qu'on en a parlé.
 * Sans conversation d'offre, elle propose les dossiers prêts plutôt qu'un
 * vide.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { AnimatePresence, LayoutGroup, motion } from "framer-motion";
import { ArrowRight, FolderOpen, Plus, Search, Trash2, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { deleteConversation, type ConversationSummary } from "@/lib/alice-client";
import { fetchPipeline, STAGE_LABELS, type PipelineItem, type Stage } from "@/lib/pipeline-client";
import { useAlice } from "../alice-context";

function when(iso: string): string {
  const d = new Date(iso);
  const days = Math.floor((Date.now() - d.getTime()) / 86_400_000);
  if (days === 0) return d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
  if (days === 1) return "hier";
  if (days < 7) return d.toLocaleDateString("fr-FR", { weekday: "short" });
  return d.toLocaleDateString("fr-FR", { day: "numeric", month: "short" });
}

/** Teintes douces, stables par entreprise : on reconnaît Alan d'un coup d'œil. */
const TINTS = [
  ["#E8F3EE", "#006045"], ["#EEF0FB", "#3B4BA8"], ["#FBF1E6", "#A2561B"],
  ["#F6ECF4", "#8E3A7C"], ["#E9F4F7", "#21708A"], ["#F3F1E4", "#6F6524"],
];

function tint(name: string) {
  let h = 0;
  for (const ch of name) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return TINTS[h % TINTS.length];
}

function initials(name: string) {
  const words = name.replace(/[^\p{L}\p{N} ]/gu, " ").split(/\s+/).filter(Boolean);
  return ((words[0]?.[0] ?? "?") + (words[1]?.[0] ?? "")).toUpperCase();
}

function Monogram({ name, size = "md" }: { name: string; size?: "sm" | "md" }) {
  const [bg, fg] = tint(name || "?");
  return (
    <span
      className={cn(
        "shrink-0 rounded-xl flex items-center justify-center font-medium tracking-tight",
        size === "md" ? "h-8 w-8 text-[11px]" : "h-6 w-6 text-[9px] rounded-lg",
      )}
      style={{ backgroundColor: bg, color: fg }}
    >
      {initials(name)}
    </span>
  );
}

const STAGE_TONE: Partial<Record<Stage, string>> = {
  ready: "bg-[#006045]/10 text-[#006045]",
  awaiting: "bg-amber-500/15 text-amber-700",
  manual: "bg-orange-500/10 text-orange-700",
  simulated: "bg-sky-500/10 text-sky-700",
  applied: "bg-[#006045] text-white",
  interview: "bg-violet-500/15 text-violet-700",
  offer: "bg-[#006045] text-white",
};

const PACK_STAGES: Stage[] = ["ready", "awaiting", "manual", "simulated"];

function Row({
  c, index, active, stage, onSelect, onRemove,
}: {
  c: ConversationSummary;
  index: number;
  active: boolean;
  stage?: Stage;
  onSelect: (c: ConversationSummary) => void;
  onRemove: (c: ConversationSummary) => void;
}) {
    const company = c.company_name || c.title;
    return (
      <motion.div
        layout
        initial={{ opacity: 0, x: -8 }}
        animate={{ opacity: 1, x: 0 }}
        exit={{ opacity: 0, x: -8 }}
        transition={{ delay: Math.min(index, 8) * 0.03, type: "spring", stiffness: 420, damping: 34 }}
        className="group relative"
      >
        {active && (
          <motion.span
            layoutId="conversation-active"
            className="absolute inset-0 rounded-xl bg-white shadow-[0_1px_3px_rgba(26,25,24,0.08)] border border-[#1A1918]/[0.06]"
            transition={{ type: "spring", stiffness: 480, damping: 38 }}
          />
        )}
        <div className="relative flex items-center gap-2.5 rounded-xl px-2 py-2 hover:bg-[#1A1918]/[0.03] transition-colors">
          <button
            type="button"
            onClick={() => onSelect(c)}
            className="min-w-0 flex-1 flex items-center gap-2.5 text-left cursor-pointer"
          >
            {c.job_id ? (
              <Monogram name={company} />
            ) : (
              <span className="shrink-0 h-8 w-8 rounded-xl bg-[#006045] text-white flex items-center justify-center text-[12px] font-medium">
                a
              </span>
            )}
            <span className="min-w-0 flex-1">
              <span className="flex items-center gap-1.5">
                <span className={cn("truncate text-[13px] tracking-tight", active ? "text-[#1A1918]" : "text-[#1A1918]/80")}>
                  {c.job_id ? company : c.title}
                </span>
                <span className="ml-auto shrink-0 text-[10px] font-light text-[#1A1918]/35 group-hover:opacity-0 transition-opacity">
                  {when(c.updated_at)}
                </span>
              </span>
              <span className="flex items-center gap-1.5 mt-0.5">
                {stage && STAGE_TONE[stage] && (
                  <span className={cn("shrink-0 rounded-full px-1.5 py-px text-[9px] tracking-tight", STAGE_TONE[stage])}>
                    {STAGE_LABELS[stage]}
                  </span>
                )}
                <span className="truncate text-[11px] font-light text-[#1A1918]/45">
                  {c.job_id ? c.job_title || c.title : "Conversation générale"}
                </span>
              </span>
            </span>
          </button>
          <button
            type="button"
            aria-label="Supprimer la conversation"
            onClick={() => onRemove(c)}
            className="absolute right-2 top-2 p-1 rounded-full text-[#1A1918]/30 opacity-0 group-hover:opacity-100 hover:text-red-600 hover:bg-red-50 cursor-pointer transition-opacity"
          >
            <Trash2 className="h-3 w-3" />
          </button>
        </div>
      </motion.div>
    );
  }

function Heading({ children, count }: { children: React.ReactNode; count?: number }) {
  return (
    <p className="flex items-center gap-1.5 px-2 pb-1.5 text-[10px] uppercase tracking-[0.12em] text-[#1A1918]/40 font-medium">
      {children}
      {count ? <span className="text-[#1A1918]/25 tabular-nums">{count}</span> : null}
    </p>
  );
}

export function ConversationSidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  const {
    candidateId, conversations, conversationId, openConversation, newConversation,
    refreshConversations, goToConversation, openCanvas,
  } = useAlice();
  const [query, setQuery] = useState("");
  const [pipeline, setPipeline] = useState<PipelineItem[]>([]);

  const loadPipeline = useCallback(async () => {
    if (!candidateId) return;
    const p = await fetchPipeline(candidateId);
    if (p) setPipeline(p.items);
  }, [candidateId]);

  // Relu à l'ouverture et dès qu'un dossier change ailleurs dans l'interface.
  useEffect(() => {
    if (!open) return;
    void loadPipeline();
    const onChange = () => void loadPipeline();
    window.addEventListener("untaf:application-changed", onChange);
    return () => window.removeEventListener("untaf:application-changed", onChange);
  }, [open, loadPipeline]);

  const stageByJob = useMemo(
    () => new Map(pipeline.map((i) => [i.job_id, i.stage] as const)),
    [pipeline],
  );

  const q = query.trim().toLowerCase();
  const matches = (c: ConversationSummary) =>
    !q || [c.title, c.company_name, c.job_title].some((v) => v?.toLowerCase().includes(q));
  const general = conversations.filter((c) => !c.job_id && matches(c));
  const byJob = conversations.filter((c) => c.job_id && matches(c));

  // Dossiers prêts dont on n'a pas encore parlé : de quoi démarrer.
  const discussed = new Set(conversations.map((c) => c.job_id).filter(Boolean));
  const readyPacks = pipeline
    .filter((i) => i.pack_ready && PACK_STAGES.includes(i.stage) && !discussed.has(i.job_id))
    .slice(0, 4);
  const counts = {
    ready: pipeline.filter((i) => i.pack_ready && PACK_STAGES.includes(i.stage)).length,
    sent: pipeline.filter((i) => ["applied", "interview", "offer"].includes(i.stage)).length,
  };

  const select = (c: ConversationSummary) => {
    void openConversation(c.id);
    goToConversation();
    if (window.innerWidth < 1024) onClose();
  };

  const remove = async (c: ConversationSummary) => {
    if (!candidateId) return;
    await deleteConversation(candidateId, c.id);
    if (c.id === conversationId) newConversation();
    void refreshConversations();
  };

  const openJob = (i: PipelineItem) => {
    openCanvas({
      mode: "job_detail",
      job: {
        id: i.job_id, title: i.title, company_name: i.company_name, location: i.location ?? "",
        match_score: i.match_score, contract_type: i.contract_type, remote_policy: i.remote_policy,
        source_url: i.source_url ?? "", status: i.status, apply_mode: i.apply_mode,
      },
    });
    goToConversation();
    if (window.innerWidth < 1024) onClose();
  };

  return (
    <AnimatePresence>
      {open && (
        <motion.aside
          initial={{ x: -28, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          exit={{ x: -28, opacity: 0 }}
          transition={{ type: "spring", stiffness: 420, damping: 36 }}
          className="fixed lg:static left-2 top-[68px] bottom-2 z-40 w-[280px] shrink-0 lg:ml-3 lg:mb-3 flex flex-col rounded-2xl bg-[#F4F3F0] border border-[#1A1918]/[0.06] shadow-[0_8px_30px_rgba(26,25,24,0.06)] lg:shadow-none overflow-hidden"
        >
          {/* En-tête */}
          <div className="px-3 pt-3 pb-2 space-y-2.5">
            <div className="flex items-center justify-between px-1">
              <p className="text-[13px] font-medium text-[#1A1918] tracking-tight">Conversations</p>
              <button
                type="button"
                onClick={onClose}
                aria-label="Fermer"
                className="p-1.5 rounded-full text-[#1A1918]/35 hover:text-[#1A1918] hover:bg-[#1A1918]/5 cursor-pointer"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
            <motion.button
              type="button"
              whileTap={{ scale: 0.98 }}
              onClick={() => {
                newConversation();
                goToConversation();
                if (window.innerWidth < 1024) onClose();
              }}
              className="w-full flex items-center justify-center gap-1.5 rounded-xl bg-[#006045] px-3 py-2 text-[12px] text-white hover:bg-[#004d37] transition-colors cursor-pointer shadow-sm shadow-[#006045]/20"
            >
              <Plus className="h-3.5 w-3.5" /> Nouvelle conversation
            </motion.button>
            {conversations.length > 4 && (
              <label className="flex items-center gap-2 rounded-xl bg-white/70 border border-[#1A1918]/[0.06] px-2.5 py-1.5">
                <Search className="h-3 w-3 text-[#1A1918]/35" />
                <input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Une entreprise, un poste…"
                  className="w-full bg-transparent text-[12px] text-[#1A1918] placeholder:text-[#1A1918]/30 outline-none"
                />
              </label>
            )}
          </div>

          <LayoutGroup id="conversations">
            <div className="scroll-discreet flex-1 overflow-y-auto px-2 pb-4 space-y-5">
              {/* Par entreprise d'abord : c'est là que vivent les candidatures */}
              <section>
                <Heading count={byJob.length}>Par entreprise</Heading>
                <AnimatePresence initial={false}>
                  {byJob.map((c, i) => <Row
                      key={c.id} c={c} index={i} active={c.id === conversationId}
                      stage={c.job_id ? stageByJob.get(c.job_id) : undefined}
                      onSelect={select} onRemove={(x) => void remove(x)}
                    />)}
                </AnimatePresence>

                {byJob.length === 0 && !q && (
                  readyPacks.length > 0 ? (
                    <div className="space-y-1 px-1">
                      <p className="px-1 pb-1 text-[11px] font-light text-[#1A1918]/45 leading-relaxed">
                        Tes dossiers prêts. Ouvre-en un pour en parler : la conversation se rangera ici.
                      </p>
                      {readyPacks.map((i, idx) => (
                        <motion.button
                          key={i.application_id}
                          type="button"
                          onClick={() => openJob(i)}
                          initial={{ opacity: 0, y: 4 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ delay: idx * 0.04 }}
                          className="w-full flex items-center gap-2.5 rounded-xl px-2 py-2 text-left border border-dashed border-[#1A1918]/12 hover:border-[#006045]/40 hover:bg-white/60 transition-colors cursor-pointer group"
                        >
                          <Monogram name={i.company_name || i.title} size="sm" />
                          <span className="min-w-0 flex-1">
                            <span className="block truncate text-[12px] text-[#1A1918]/80">
                              {i.company_name || "Entreprise non précisée"}
                            </span>
                            <span className="block truncate text-[10px] font-light text-[#1A1918]/40">{i.title}</span>
                          </span>
                          <ArrowRight className="h-3 w-3 text-[#1A1918]/25 group-hover:text-[#006045] transition-colors" />
                        </motion.button>
                      ))}
                    </div>
                  ) : (
                    <p className="px-2 text-[11px] font-light text-[#1A1918]/40 leading-relaxed">
                      Pose une question depuis une offre : la conversation se range ici, sous le nom de
                      l&apos;entreprise, avec l&apos;état de ton dossier.
                    </p>
                  )
                )}
              </section>

              <section>
                <Heading count={general.length}>Avec Alice</Heading>
                <AnimatePresence initial={false}>
                  {general.map((c, i) => <Row
                      key={c.id} c={c} index={i} active={c.id === conversationId}
                      stage={c.job_id ? stageByJob.get(c.job_id) : undefined}
                      onSelect={select} onRemove={(x) => void remove(x)}
                    />)}
                </AnimatePresence>
                {general.length === 0 && (
                  <p className="px-2 text-[11px] font-light text-[#1A1918]/40">
                    {q ? "Aucun résultat." : "Pas encore de conversation."}
                  </p>
                )}
              </section>
            </div>
          </LayoutGroup>

          {/* Où en sont les dossiers — un raccourci, pas un tableau de bord */}
          {(counts.ready > 0 || counts.sent > 0) && (
            <button
              type="button"
              onClick={() => {
                window.dispatchEvent(new CustomEvent("untaf:select-tab", { detail: "candidatures" }));
                if (window.innerWidth < 1024) onClose();
              }}
              className="m-2 mt-0 flex items-center gap-2.5 rounded-xl bg-white/80 border border-[#1A1918]/[0.06] px-3 py-2.5 text-left hover:border-[#006045]/30 transition-colors cursor-pointer group"
            >
              <FolderOpen className="h-3.5 w-3.5 text-[#006045]" />
              <span className="flex-1 text-[11px] text-[#1A1918]/70 tracking-tight">
                <span className="tabular-nums text-[#1A1918]">{counts.ready}</span> dossier{counts.ready > 1 ? "s" : ""} prêt{counts.ready > 1 ? "s" : ""}
                {" · "}
                <span className="tabular-nums text-[#1A1918]">{counts.sent}</span> envoyée{counts.sent > 1 ? "s" : ""}
              </span>
              <ArrowRight className="h-3 w-3 text-[#1A1918]/30 group-hover:text-[#006045] transition-colors" />
            </button>
          )}
        </motion.aside>
      )}
    </AnimatePresence>
  );
}
