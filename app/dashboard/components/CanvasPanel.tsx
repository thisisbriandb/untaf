"use client";

import { motion, AnimatePresence } from "framer-motion";
import { X } from "lucide-react";
import { CoverLetterEditor } from "./CoverLetterEditor";
import { CanvasCvEditor } from "./CanvasCvEditor";
import { JobDetailCanvas } from "./JobDetailCanvas";
import { AlicePresence } from "@/app/onboarding/components/AlicePresence";
import { canvasLabel, useAlice } from "../alice-context";

/**
 * Canvas — the artifact surface next to the conversation.
 *
 * Below `lg` it is a sheet over the thread (there is no room for two columns);
 * from `lg` up it joins the flex row so the chat keeps its own share of the
 * screen and stays readable while the user edits.
 */
export function CanvasPanel({ candidateId }: { candidateId: string | null }) {
  const { canvas, closeCanvas, emotion } = useAlice();

  return (
    <AnimatePresence>
      {canvas && (
        <>
          {/* Backdrop — sheet mode only */}
          <motion.div
            key="canvas-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={closeCanvas}
            className="fixed inset-0 bg-[#1A1918]/20 backdrop-blur-xs z-40 lg:hidden cursor-pointer"
          />

          <motion.aside
            key="canvas-panel"
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", damping: 26, stiffness: 230 }}
            className="fixed inset-y-0 right-0 z-50 w-full sm:w-[26rem]
                       lg:relative lg:inset-auto lg:z-auto lg:h-full lg:w-[44%] lg:min-w-[24rem] lg:max-w-[52rem] lg:shrink-0
                       bg-white border-l border-[#EDECEA] shadow-2xl lg:shadow-none
                       flex flex-col overflow-hidden font-light tracking-tight text-[#1A1918]"
            aria-label={`Canvas — ${canvasLabel(canvas)}`}
          >
            {/* En-tête : Alice reste présente dans le canvas */}
            <div className="flex items-center justify-between gap-3 px-5 py-3 border-b border-[#1A1918]/8 shrink-0 bg-[#FAFAF8]">
              <div className="flex items-center gap-2.5 min-w-0">
                <AlicePresence emotion={emotion} size="sm" />
                <div className="min-w-0">
                  <p className="text-xs font-normal text-[#1A1918] tracking-tight truncate">
                    {canvasLabel(canvas)}
                  </p>
                  <p className="text-[11px] font-light text-[#1A1918]/45 tracking-tight truncate">
                    {canvas.mode === "job_detail"
                      ? "Alice a le contexte de cette offre"
                      : "Alice suit tes modifications"}
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={closeCanvas}
                aria-label="Fermer le Canvas"
                className="p-1.5 rounded-full text-[#1A1918]/45 hover:text-[#1A1918] hover:bg-[#1A1918]/5 transition-colors cursor-pointer shrink-0"
              >
                <X className="w-4 h-4 stroke-[1.4]" />
              </button>
            </div>

            {/* Corps */}
            <div className="flex-1 min-h-0">
              {canvas.mode === "cv_editor" && <CanvasCvEditor candidateId={candidateId} />}

              {canvas.mode === "job_detail" && <JobDetailCanvas job={canvas.job} />}

              {canvas.mode === "cover_letter" && (
                <CoverLetterEditor
                  companyName={canvas.companyName}
                  jobTitle={canvas.jobTitle}
                  initialContent={canvas.content}
                />
              )}
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
