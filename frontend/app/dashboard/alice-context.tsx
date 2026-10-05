"use client";

/**
 * Shared state for the Alice thread and the Canvas.
 *
 * The Canvas is not a separate app: it is an artifact Alice opened. Both live
 * here so the editor can talk back into the conversation (and the conversation
 * can reopen an artifact) without prop-drilling through the dashboard.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  fetchConversationMessages,
  fetchConversations,
  sendMessageToAlice,
  type ConversationSummary,
  type JobCardData,
  type StoredMessage,
  type UiBlock,
} from "@/lib/alice-client";
import { fetchMission } from "@/lib/mission-client";
import { fetchPipeline, type Pipeline } from "@/lib/pipeline-client";
import type { CoverLetter } from "@/lib/letter-client";
import type { AliceEmotion } from "../onboarding/components/AlicePresence";

export type CanvasMode = "cv_editor" | "cover_letter" | "job_detail" | "review";

/** What the Canvas is currently showing — mode plus everything it needs. */
export type CanvasPayload =
  | { mode: "cv_editor"; pane?: "original" | "content" | "design" }
  | { mode: "cover_letter"; companyName?: string; jobTitle?: string; letter?: CoverLetter }
  | { mode: "job_detail"; job: JobCardData; autoApply?: boolean }
  | { mode: "review"; job: JobCardData };

export function canvasLabel(payload: CanvasPayload): string {
  switch (payload.mode) {
    case "cv_editor":
      return payload.pane === "design" ? "Modèles de CV" : "Éditeur de CV";
    case "review":
      return `Relire — ${payload.job.company_name}`;
    case "cover_letter":
      if (payload.jobTitle) return `Lettre — ${payload.jobTitle}`;
      return payload.companyName
        ? `Lettre de motivation — ${payload.companyName}`
        : "Lettre de motivation";
    case "job_detail":
      return payload.job.title;
  }
}

export interface ChatMessage {
  id: string;
  sender: "alice" | "user";
  text: string;
  timestamp?: string;
  uiBlocks?: UiBlock[];
  /** Chip rendered under the message that (re)opens the Canvas artifact. */
  canvasRef?: CanvasPayload;
}

interface AliceContextValue {
  candidateId: string | null;
  /** Ramène l'utilisateur sur le fil — une réponse d'Alice ne sert à rien
   *  s'il est resté sur un autre onglet. */
  goToConversation: () => void;

  // Conversation
  messages: ChatMessage[];
  isThinking: boolean;
  emotion: AliceEmotion;
  /** True once the user has said anything — drives the hero → thread layout. */
  hasConversation: boolean;
  /** `job` : la question porte sur cette offre — elle part dans SA conversation. */
  submitQuery: (text: string, opts?: { job?: JobCardData }) => Promise<void>;
  /** Post a line as Alice without a round-trip (used by the Canvas). */
  sayAsAlice: (text: string, canvasRef?: CanvasPayload) => void;

  // Conversations sauvegardées
  conversationId: string | null;
  conversations: ConversationSummary[];
  /** L'offre dont parle la conversation affichée, s'il y en a une. */
  activeJob: { id: string; company: string; title: string } | null;
  newConversation: () => void;
  openConversation: (id: string) => Promise<void>;
  refreshConversations: () => Promise<void>;

  // Canvas
  canvas: CanvasPayload | null;
  isCanvasOpen: boolean;
  openCanvas: (payload: CanvasPayload) => void;
  closeCanvas: () => void;
}

const AliceContext = createContext<AliceContextValue | null>(null);

/** Tenu jusqu'à ce que le vrai briefing arrive — jamais affiché longtemps. */
const INITIAL_MESSAGES: ChatMessage[] = [
  {
    id: "seed-1",
    sender: "alice",
    timestamp: "",
    text: "Je reprends là où j'en étais.",
  },
];

function formatTime(date: Date): string {
  return `${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
}

/**
 * Le compte rendu d'ouverture.
 *
 * C'est le point où l'application cesse de ressembler à un chatbot : Alice ne
 * demande pas ce qu'on veut, elle dit ce qu'elle a fait pendant l'absence. Le
 * texte est construit à partir du journal de mission réel — jamais inventé,
 * sinon la promesse d'autonomie devient un décor.
 */
function briefingFrom(
  mission: Awaited<ReturnType<typeof fetchMission>>,
  pipeline: Pipeline | null,
): string {
  if (!mission) return "Je reprends là où j'en étais.";

  // Ce qui attend une décision passe avant le récit : c'est la seule chose
  // que l'utilisateur doit faire, et il doit l'apprendre en premier.
  const awaiting = pipeline?.counts.awaiting ?? 0;
  const followups = pipeline?.counts.followup_due ?? 0;
  const interviews = pipeline?.counts.interview ?? 0;
  const todo: string[] = [];
  if (awaiting > 0) {
    todo.push(
      `${awaiting} candidature${awaiting > 1 ? "s attendent" : " attend"} ton feu vert — tout est rédigé`,
    );
  }
  if (followups > 0) {
    todo.push(`${followups} relance${followups > 1 ? "s sont prêtes" : " est prête"} à partir`);
  }
  const agenda = todo.length ? ` ${todo.join(", et ")}. Tout est dans Candidatures.` : "";
  const congrats = interviews > 0
    ? ` Et ${interviews} entretien${interviews > 1 ? "s" : ""} en cours : je peux t'aider à le${interviews > 1 ? "s" : ""} préparer.`
    : "";

  if (mission.status === "paused") {
    return (
      "J'ai mis la recherche en pause, comme tu me l'as demandé. Dis-moi quand je reprends." +
      agenda
    );
  }

  const { scanned_last_run: scanned, shortlisted, applied } = mission.stats;

  if (!mission.last_run_at || scanned === 0) {
    if (pipeline?.items.length) {
      return `Je reprends là où j'en étais.${agenda}${congrats}`.trim();
    }
    return "Je n'ai pas encore lancé de veille sur ton mandat. Confie-moi une mission et je m'y mets.";
  }

  const parts: string[] = [`J'ai passé ${scanned} offres en revue`];

  if (shortlisted > 0) {
    parts.push(`j'en ai retenu ${shortlisted}`);
  } else {
    parts.push("aucune ne tient la route pour l'instant");
  }
  if (applied > 0) {
    parts.push(`et ${applied} candidature${applied > 1 ? "s sont parties" : " est partie"}`);
  }

  const report = parts.join(", ") + ".";

  if (agenda) return `${report}${agenda}${congrats}`;
  return shortlisted > 0
    ? `${report}${congrats} Je te les montre ?`
    : `${report}${congrats} Je continue de chercher.`;
}

/**
 * Le chip Canvas d'un message, reconstruit depuis ses blocs d'action. Sans
 * effet de bord : sert aussi à relire une conversation sauvegardée.
 */
function canvasRefFrom(blocks: UiBlock[]): CanvasPayload | undefined {
  let ref: CanvasPayload | undefined;
  for (const block of blocks) {
    if (block.type !== "action") continue;
    if (block.action === "open_cv_editor") {
      ref = { mode: "cv_editor", pane: block.data?.pane };
    } else if (block.action === "open_job" && block.data?.job) {
      ref = { mode: "job_detail", job: block.data.job };
    } else if (block.action === "open_cover_letter") {
      ref = {
        mode: "cover_letter",
        companyName: block.data?.companyName ?? block.data?.company_name,
        jobTitle: block.data?.jobTitle ?? block.data?.job_title,
        letter: block.data?.letter,
      };
    }
  }
  return ref;
}

function fromStored(m: StoredMessage): ChatMessage {
  const blocks = m.ui_blocks ?? [];
  const renderable = blocks.filter((b) => b.type !== "action");
  return {
    id: m.id,
    sender: m.sender,
    text: m.text,
    timestamp: formatTime(new Date(m.created_at)),
    uiBlocks: renderable.length ? renderable : undefined,
    canvasRef: canvasRefFrom(blocks),
  };
}

/** Au-delà, la dernière conversation n'est plus rouverte d'office. */
const RESUME_WITHIN_MS = 3 * 24 * 3600 * 1000;

export function AliceProvider({
  candidateId,
  onGoToConversation,
  children,
}: {
  candidateId: string | null;
  onGoToConversation: () => void;
  children: ReactNode;
}) {
  const [messages, setMessages] = useState<ChatMessage[]>(INITIAL_MESSAGES);
  const [isThinking, setIsThinking] = useState(false);
  const [emotion, setEmotion] = useState<AliceEmotion>("idle");
  const [canvas, setCanvas] = useState<CanvasPayload | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [briefing, setBriefing] = useState<ChatMessage | null>(null);
  const [pendingJob, setPendingJob] = useState<JobCardData | null>(null);

  const activeJob = useMemo(() => {
    const conv = conversations.find((c) => c.id === conversationId);
    if (conv?.job_id) {
      return { id: conv.job_id, company: conv.company_name ?? "", title: conv.job_title ?? conv.title };
    }
    return pendingJob ? { id: pendingJob.id, company: pendingJob.company_name, title: pendingJob.title } : null;
  }, [conversations, conversationId, pendingJob]);

  const hasConversation = messages.some((m) => m.sender === "user");

  const refreshConversations = useCallback(async () => {
    if (!candidateId) return;
    setConversations(await fetchConversations(candidateId));
  }, [candidateId]);

  // Compte rendu d'ouverture, tiré du journal de mission. Ne remplace la ligne
  // d'attente que si l'utilisateur n'a pas déjà commencé à parler.
  useEffect(() => {
    if (!candidateId) return;
    let alive = true;

    Promise.all([
      fetchMission(candidateId),
      fetchPipeline(candidateId),
      fetchConversations(candidateId),
    ]).then(async ([mission, pipeline, convs]) => {
      if (!alive) return;
      setConversations(convs);
      const greet: ChatMessage = {
        id: "briefing",
        sender: "alice",
        timestamp: formatTime(new Date()),
        text: briefingFrom(mission, pipeline),
      };
      setBriefing(greet);

      // La conversation récente reprend où elle s'était arrêtée — sur cet
      // appareil comme sur un autre. Le compte rendu du jour vient après.
      const latest = convs[0];
      let past: ChatMessage[] = [];
      if (latest && Date.now() - new Date(latest.updated_at).getTime() < RESUME_WITHIN_MS) {
        past = (await fetchConversationMessages(candidateId, latest.id)).map(fromStored);
        if (!alive) return;
        if (past.length) setConversationId(latest.id);
      }
      setMessages((prev) => (prev.some((m) => m.sender === "user") ? prev : [...past, greet]));
    });

    return () => {
      alive = false;
    };
  }, [candidateId]);

  const newConversation = useCallback(() => {
    setPendingJob(null);
    setConversationId(null);
    setMessages(briefing ? [briefing] : INITIAL_MESSAGES);
  }, [briefing]);

  const openConversation = useCallback(
    async (id: string) => {
      if (!candidateId) return;
      const stored = await fetchConversationMessages(candidateId, id);
      setPendingJob(null);
      setConversationId(id);
      setMessages(stored.length ? stored.map(fromStored) : briefing ? [briefing] : INITIAL_MESSAGES);
    },
    [candidateId, briefing],
  );

  const openCanvas = useCallback((payload: CanvasPayload) => setCanvas(payload), []);

  const closeCanvas = useCallback(() => setCanvas(null), []);

  const sayAsAlice = useCallback((text: string, canvasRef?: CanvasPayload) => {
    setMessages((prev) => [
      ...prev,
      {
        id: crypto.randomUUID(),
        sender: "alice",
        timestamp: formatTime(new Date()),
        text,
        canvasRef,
      },
    ]);
  }, []);

  const submitQuery = useCallback(
    async (userText: string, opts?: { job?: JobCardData }) => {
      const trimmed = userText.trim();
      if (!trimmed || isThinking) return;

      // Une question sur une offre part dans la conversation de CETTE offre :
      // son contexte reste séparé du fil général et des autres offres.
      let targetConv = conversationId;
      let jobId: string | null = null;
      let baseMessages = messages;
      if (opts?.job) {
        const existing = conversations.find((c) => c.job_id === opts.job!.id);
        jobId = opts.job.id;
        if (existing?.id !== conversationId || !existing) {
          targetConv = existing?.id ?? null;
          baseMessages =
            existing && candidateId
              ? (await fetchConversationMessages(candidateId, existing.id)).map(fromStored)
              : [];
          setPendingJob(existing ? null : opts.job);
          setConversationId(targetConv);
          setMessages(baseMessages);
        }
      } else if (pendingJob && !conversationId) {
        jobId = pendingJob.id;
      }

      setEmotion("thinking");
      setIsThinking(true);
      setMessages((prev) => [
        ...prev,
        { id: crypto.randomUUID(), sender: "user", text: trimmed },
      ]);

      if (!candidateId) {
        sayAsAlice("Je ne trouve pas ton profil. Essaie de te reconnecter.");
        setEmotion("idle");
        setIsThinking(false);
        return;
      }

      try {
        // On transmet les tours précédents — pas le message courant, que
        // l'API reçoit séparément.
        const response = await sendMessageToAlice(
          candidateId,
          trimmed,
          baseMessages
            .filter((m) => m.text.trim() && m.id !== "briefing")
            .map((m) => ({ sender: m.sender, text: m.text })),
          targetConv,
          jobId,
        );
        if (response.conversation_id && response.conversation_id !== targetConv) {
          setConversationId(response.conversation_id);
          setPendingJob(null);
          void refreshConversations();
        }

        // An action block means Alice produced an artifact: open it, and leave
        // a chip on her message so the thread keeps a handle on it.
        // Les effets d'interface (ouvrir un onglet, l'assistant de mission)
        // ne se jouent qu'en direct ; le chip Canvas, lui, reste dans le fil.
        for (const block of response.ui_blocks) {
          if (block.type !== "action") continue;
          if (block.action === "open_mission_launcher") {
            window.dispatchEvent(new CustomEvent("untaf:open-mission-launcher"));
          } else if (block.action === "select_tab" && block.data?.tab) {
            window.dispatchEvent(new CustomEvent("untaf:select-tab", { detail: block.data.tab }));
          }
        }
        let canvasRef = canvasRefFrom(response.ui_blocks);
        // « Postule » : l'offre s'ouvre directement sur la candidature.
        const applyBlock = response.ui_blocks.find(
          (b) => b.type === "action" && b.action === "open_job" && b.data?.autoApply,
        );
        if (applyBlock && canvasRef?.mode === "job_detail") {
          canvasRef = { ...canvasRef, autoApply: true };
        }
        if (canvasRef) openCanvas(canvasRef);

        const renderable = response.ui_blocks.filter((b) => b.type !== "action");

        setMessages((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            sender: "alice",
            timestamp: formatTime(new Date()),
            text: response.reply,
            uiBlocks: renderable.length > 0 ? renderable : undefined,
            canvasRef,
          },
        ]);
      } catch (err) {
        console.error("Alice error:", err);
        sayAsAlice("Désolée, j'ai rencontré un problème. Réessaie.");
      } finally {
        setEmotion("idle");
        setIsThinking(false);
      }
    },
    [
      candidateId, isThinking, messages, openCanvas, sayAsAlice, conversationId,
      refreshConversations, conversations, pendingJob,
    ],
  );

  const value = useMemo<AliceContextValue>(
    () => ({
      candidateId,
      goToConversation: onGoToConversation,
      messages,
      isThinking,
      emotion,
      hasConversation,
      submitQuery,
      sayAsAlice,
      conversationId,
      conversations,
      activeJob,
      newConversation,
      openConversation,
      refreshConversations,
      canvas,
      isCanvasOpen: canvas !== null,
      openCanvas,
      closeCanvas,
    }),
    [
      candidateId,
      onGoToConversation,
      messages,
      isThinking,
      emotion,
      hasConversation,
      submitQuery,
      sayAsAlice,
      conversationId,
      conversations,
      activeJob,
      newConversation,
      openConversation,
      refreshConversations,
      canvas,
      openCanvas,
      closeCanvas,
    ],
  );

  return <AliceContext.Provider value={value}>{children}</AliceContext.Provider>;
}

export function useAlice(): AliceContextValue {
  const ctx = useContext(AliceContext);
  if (!ctx) throw new Error("useAlice must be used inside <AliceProvider>");
  return ctx;
}
