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
import { ArrowRight, Briefcase, FolderOpen, Mail, PanelLeft, Search, Settings, SlidersHorizontal, SquarePen, Trash2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { deleteConversation, type ConversationSummary } from "@/lib/alice-client";
import { fetchPipeline, STAGE_LABELS, type PipelineItem, type Stage } from "@/lib/pipeline-client";
import { useAlice } from "../alice-context";
import { STAGE_TONE } from "@/lib/stage-tone";
import { AliceAvatar } from "@/app/onboarding/components/AliceSilhouette";
import { companyOf } from "@/lib/company";
import { fetchInbox, onInboxChanged } from "@/lib/inbox-client";

function when(iso: string): string {
  const d = new Date(iso);
  const days = Math.floor((Date.now() - d.getTime()) / 86_400_000);
  if (days === 0) return d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
  if (days === 1) return "hier";
  if (days < 7) return d.toLocaleDateString("fr-FR", { weekday: "short" });
  return d.toLocaleDateString("fr-FR", { day: "numeric", month: "short" });
}

/** Gris chauds, stables par entreprise : distincts sans ajouter de couleur. */
const TINTS = [
  ["#ECEBE7", "#006045"], ["#E3E2DD", "#006045"], ["#D9D8D2", "#006045"],
  ["#006045", "#FAFAF8"], ["#3A3936", "#FAFAF8"], ["#F4F3F0", "#006045"],
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

function Monogram({ name, size = "md" }: { name: string | null; size?: "sm" | "md" }) {
  // Employeur non communiqué : une mallette plutôt que des initiales sans sens.
  if (!name) {
    return (
      <span className={cn(
        "shrink-0 flex items-center justify-center bg-[#ECEBE7] text-[#1A1918]/55",
        size === "md" ? "h-8 w-8 rounded-xl" : "h-6 w-6 rounded-lg",
      )}>
        <Briefcase className={size === "md" ? "h-3.5 w-3.5" : "h-3 w-3"} />
      </span>
    );
  }
  const [bg, fg] = tint(name);
  return (
    <span
      className={cn(
        "shrink-0 rounded-xl flex items-center justify-center font-medium tracking-tight",
        size === "md" ? "h-8 w-8 text-[11px]" : "h-6 w-6 text-[10px] rounded-lg",
      )}
      style={{ backgroundColor: bg, color: fg }}
    >
      {initials(name)}
    </span>
  );
}

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
    const employer = companyOf(c.company_name);
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
              <Monogram name={employer} />
            ) : (
              <AliceAvatar size={32} />
            )}
            <span className="min-w-0 flex-1">
              <span className="flex items-center gap-1.5">
                <span className={cn("truncate text-[13px] tracking-tight", active ? "text-[#1A1918]" : "text-[#1A1918]/80")}>
                  {c.job_id ? employer ?? c.job_title ?? c.title : c.title}
                </span>
                <span className="ml-auto shrink-0 text-[11px] font-normal text-[#1A1918]/50 group-hover:opacity-0 transition-opacity">
                  {when(c.updated_at)}
                </span>
              </span>
              <span className="flex items-center gap-1.5 mt-0.5">
                {stage && STAGE_TONE[stage] && (
                  <span className={cn("shrink-0 rounded-full px-1.5 py-px text-[10px] tracking-tight", STAGE_TONE[stage])}>
                    {STAGE_LABELS[stage]}
                  </span>
                )}
                <span className="truncate text-[11px] font-normal text-[#1A1918]/60">
                  {c.job_id ? (employer ? c.job_title || c.title : "Employeur non communiqué") : "Conversation générale"}
                </span>
              </span>
            </span>
          </button>
          <button
            type="button"
            aria-label="Supprimer la conversation"
            onClick={() => onRemove(c)}
            className="absolute right-2 top-2 p-1 rounded-full text-[#1A1918]/45 opacity-0 group-hover:opacity-100 hover:text-red-600 hover:bg-red-50 cursor-pointer transition-opacity"
          >
            <Trash2 className="h-3 w-3" />
          </button>
        </div>
      </motion.div>
    );
  }

function Heading({ children, count }: { children: React.ReactNode; count?: number }) {
  return (
    <p className="flex items-center gap-1.5 px-2 pb-1.5 text-[11px] uppercase tracking-[0.12em] text-[#1A1918]/55 font-medium">
      {children}
      {count ? <span className="text-[#1A1918]/40 tabular-nums">{count}</span> : null}
    </p>
  );
}

export function ConversationSidebar({
  open, onClose, userName = "",
}: {
  open: boolean;
  onClose: () => void;
  userName?: string;
}) {
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

  // Réponses de recruteurs non lues : relues à l'ouverture, à la lecture d'un
  // message et toutes les deux minutes.
  const [unread, setUnread] = useState(0);
  useEffect(() => {
    if (!open || !candidateId) return;
    const load = () => void fetchInbox(candidateId).then((b) => b && setUnread(b.unread));
    load();
    const timer = setInterval(load, 120_000);
    const off = onInboxChanged(load);
    return () => { clearInterval(timer); off(); };
  }, [open, candidateId]);

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

  const isMobile = () => window.innerWidth < 1024;
  const goTab = (tab: string) => {
    window.dispatchEvent(new CustomEvent("untaf:select-tab", { detail: tab }));
    if (isMobile()) onClose();
  };
  const [searching, setSearching] = useState(false);

  // Rail pleine hauteur, collé au bord gauche, comme une barre d'application :
  // le contenu glisse à côté plutôt que d'être recouvert (dès lg). Sur mobile,
  // le rail passe par-dessus, avec un voile pour le refermer.
  return (
    <AnimatePresence initial={false}>
      {open && (
        <>
          <motion.div
            key="veil"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 z-40 bg-[#1A1918]/20 lg:hidden"
          />
        <motion.aside
          key="rail"
          initial={{ width: 0, opacity: 0 }}
          animate={{ width: 272, opacity: 1 }}
          exit={{ width: 0, opacity: 0 }}
          transition={{ type: "spring", stiffness: 380, damping: 40 }}
          className="fixed lg:relative inset-y-0 left-0 z-50 shrink-0 h-full overflow-hidden bg-[#F4F3F0] border-r border-[#1A1918]/[0.07]"
        >
          <div className="w-[272px] h-full flex flex-col">
          {/* Marque et repli, à la place qu'ils occupent dans l'en-tête */}
          <div className="h-[68px] shrink-0 flex items-center justify-between px-4">
            <button
              type="button"
              onClick={() => goTab("alice")}
              className="text-base md:text-lg font-medium text-[#1A1918] tracking-tight cursor-pointer hover:opacity-80"
            >
              alice
            </button>
            <div className="flex items-center gap-0.5">
              <button
                type="button"
                onClick={() => setSearching((v) => !v)}
                aria-label="Rechercher une conversation"
                className={cn(
                  "p-2 rounded-full transition-colors cursor-pointer",
                  searching ? "text-[#006045] bg-[#006045]/10" : "text-[#1A1918]/60 hover:text-[#1A1918] hover:bg-[#1A1918]/5",
                )}
              >
                <Search className="h-4 w-4 stroke-[1.4]" />
              </button>
              <button
                type="button"
                onClick={onClose}
                aria-label="Masquer les conversations"
                className="p-2 rounded-full text-[#1A1918]/60 hover:text-[#1A1918] hover:bg-[#1A1918]/5 cursor-pointer"
              >
                <PanelLeft className="h-4 w-4 stroke-[1.4]" />
              </button>
            </div>
          </div>

          <div className="px-2 pb-2 space-y-0.5">
            <button
              type="button"
              onClick={() => {
                newConversation();
                goToConversation();
                if (isMobile()) onClose();
              }}
              className="w-full flex items-center gap-2.5 rounded-xl px-2.5 py-2 text-[13px] text-[#1A1918]/85 hover:bg-[#1A1918]/[0.05] transition-colors cursor-pointer"
            >
              <SquarePen className="h-4 w-4 stroke-[1.5] text-[#1A1918]/70" /> Nouvelle conversation
            </button>
            <button
              type="button"
              onClick={() => goTab("candidatures")}
              className="w-full flex items-center gap-2.5 rounded-xl px-2.5 py-2 text-[13px] text-[#1A1918]/85 hover:bg-[#1A1918]/[0.05] transition-colors cursor-pointer"
            >
              <FolderOpen className="h-4 w-4 stroke-[1.5] text-[#1A1918]/70" />
              <span className="flex-1 text-left">Mes dossiers</span>
              {counts.ready > 0 && (
                <span className="rounded-full bg-[#006045]/12 px-1.5 py-px text-[11px] tabular-nums text-[#006045]">
                  {counts.ready}
                </span>
              )}
            </button>
            <button
              type="button"
              onClick={() => goTab("mission")}
              className="w-full flex items-center gap-2.5 rounded-xl px-2.5 py-2 text-[13px] text-[#1A1918]/85 hover:bg-[#1A1918]/[0.05] transition-colors cursor-pointer"
            >
              <SlidersHorizontal className="h-4 w-4 stroke-[1.5] text-[#1A1918]/70" /> Mon mandat
            </button>
            <button
              type="button"
              onClick={() => goTab("messages")}
              className="w-full flex items-center gap-2.5 rounded-xl px-2.5 py-2 text-[13px] text-[#1A1918]/85 hover:bg-[#1A1918]/[0.05] transition-colors cursor-pointer"
            >
              <Mail className="h-4 w-4 stroke-[1.5] text-[#1A1918]/70" />
              <span className="flex-1 text-left">Messages</span>
              {unread > 0 && (
                <span className="rounded-full bg-[#006045] px-1.5 py-px text-[11px] tabular-nums text-white">
                  {unread}
                </span>
              )}
            </button>
            <AnimatePresence initial={false}>
              {searching && (
                <motion.label
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  className="flex items-center gap-2 overflow-hidden rounded-xl bg-white border border-[#1A1918]/[0.08] px-2.5 py-1.5 mt-1"
                >
                  <Search className="h-3 w-3 text-[#1A1918]/50" />
                  <input
                    autoFocus
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="Une entreprise, un poste…"
                    className="w-full bg-transparent text-[12px] text-[#1A1918] placeholder:text-[#1A1918]/45 outline-none"
                  />
                </motion.label>
              )}
            </AnimatePresence>
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
                      <p className="px-1 pb-1 text-[11px] font-normal text-[#1A1918]/60 leading-relaxed">
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
                          <Monogram name={companyOf(i.company_name)} size="sm" />
                          <span className="min-w-0 flex-1">
                            <span className="block truncate text-[12px] text-[#1A1918]/80">
                              {companyOf(i.company_name) ?? i.title}
                            </span>
                            <span className="block truncate text-[11px] font-normal text-[#1A1918]/55">
                              {companyOf(i.company_name) ? i.title : "Employeur non communiqué"}
                            </span>
                          </span>
                          <ArrowRight className="h-3 w-3 text-[#1A1918]/40 group-hover:text-[#006045] transition-colors" />
                        </motion.button>
                      ))}
                    </div>
                  ) : (
                    <p className="px-2 text-[11px] font-normal text-[#1A1918]/55 leading-relaxed">
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
                  <p className="px-2 text-[11px] font-normal text-[#1A1918]/55">
                    {q ? "Aucun résultat." : "Pas encore de conversation."}
                  </p>
                )}
              </section>
            </div>
          </LayoutGroup>

          {/* Le compte, en bas, comme partout ailleurs */}
          <div className="shrink-0 border-t border-[#1A1918]/[0.06] p-2">
            <div className="flex items-center gap-2.5 rounded-xl px-2 py-2">
              <span className="h-8 w-8 shrink-0 rounded-full bg-[#006045] text-white flex items-center justify-center text-[11px] font-medium">
                {initials(userName || "Toi")}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[13px] text-[#1A1918] tracking-tight">{userName || "Mon compte"}</span>
                <span className="block truncate text-[11px] font-normal text-[#1A1918]/60">
                  {counts.ready} dossier{counts.ready > 1 ? "s" : ""} prêt{counts.ready > 1 ? "s" : ""} · {counts.sent} envoyée{counts.sent > 1 ? "s" : ""}
                </span>
              </span>
              <button
                type="button"
                onClick={() => goTab("parametres")}
                aria-label="Paramètres"
                className="p-1.5 rounded-full text-[#1A1918]/55 hover:text-[#1A1918] hover:bg-[#1A1918]/5 cursor-pointer"
              >
                <Settings className="h-4 w-4 stroke-[1.4]" />
              </button>
            </div>
          </div>
          </div>
        </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
