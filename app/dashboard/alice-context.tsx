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
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { sendMessageToAlice, type JobCardData, type UiBlock } from "@/lib/alice-client";
import type { AliceEmotion } from "../onboarding/components/AlicePresence";

export type CanvasMode = "cv_editor" | "cover_letter" | "job_detail";

/** What the Canvas is currently showing — mode plus everything it needs. */
export type CanvasPayload =
  | { mode: "cv_editor" }
  | { mode: "cover_letter"; companyName?: string; jobTitle?: string; content?: string }
  | { mode: "job_detail"; job: JobCardData };

export function canvasLabel(payload: CanvasPayload): string {
  switch (payload.mode) {
    case "cv_editor":
      return "Éditeur de CV";
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
  submitQuery: (text: string) => Promise<void>;
  /** Post a line as Alice without a round-trip (used by the Canvas). */
  sayAsAlice: (text: string, canvasRef?: CanvasPayload) => void;

  // Canvas
  canvas: CanvasPayload | null;
  isCanvasOpen: boolean;
  openCanvas: (payload: CanvasPayload) => void;
  closeCanvas: () => void;
}

const AliceContext = createContext<AliceContextValue | null>(null);

const INITIAL_MESSAGES: ChatMessage[] = [
  {
    id: "seed-1",
    sender: "alice",
    timestamp: "09:41",
    text: "J'ai terminé ma veille de ce matin. Demande-moi ce que tu veux savoir.",
  },
];

function formatTime(date: Date): string {
  return `${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
}

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

  const hasConversation = messages.some((m) => m.sender === "user");

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
    async (userText: string) => {
      const trimmed = userText.trim();
      if (!trimmed || isThinking) return;

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
        const response = await sendMessageToAlice(candidateId, trimmed);

        // An action block means Alice produced an artifact: open it, and leave
        // a chip on her message so the thread keeps a handle on it.
        let canvasRef: CanvasPayload | undefined;
        for (const block of response.ui_blocks) {
          if (block.type !== "action") continue;
          if (block.action === "open_cv_editor") {
            canvasRef = { mode: "cv_editor" };
          } else if (block.action === "open_cover_letter") {
            canvasRef = {
              mode: "cover_letter",
              companyName: block.data?.companyName ?? block.data?.company_name,
              jobTitle: block.data?.jobTitle ?? block.data?.job_title,
              content: block.data?.content,
            };
          }
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
    [candidateId, isThinking, openCanvas, sayAsAlice],
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
