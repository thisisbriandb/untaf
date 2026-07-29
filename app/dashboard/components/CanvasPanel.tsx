"use client";

import { motion, AnimatePresence } from "framer-motion";
import { X } from "lucide-react";
import { CoverLetterEditor } from "./CoverLetterEditor";
import { Step2CvEditor } from "@/app/onboarding/components/Step2CvEditor";
import { useState } from "react";

export type CanvasMode = "cv_editor" | "cover_letter" | null;

interface CanvasPanelProps {
  isOpen: boolean;
  onClose: () => void;
  mode: CanvasMode;
  coverLetterData?: {
    companyName?: string;
    content?: string;
  };
}

export function CanvasPanel({
  isOpen,
  onClose,
  mode,
  coverLetterData,
}: CanvasPanelProps) {
  // CV Dummy state for full interactive preview in Canvas mode
  const [fullName, setFullName] = useState("Briand");
  const [email, setEmail] = useState("briand@example.com");
  const [phone, setPhone] = useState("06 12 34 56 78");
  const [linkedinUrl, setLinkedinUrl] = useState("linkedin.com/in/briand");
  const [headline, setHeadline] = useState("Développeur Full Stack React & Python");
  const [summary, setSummary] = useState("Développeur passionné par les interfaces ultra-minimalistes et le web moderne.");
  const [experiences, setExperiences] = useState<any[]>([]);
  const [education, setEducation] = useState<any[]>([]);
  const [skills, setSkills] = useState<string[]>(["React", "TypeScript", "FastAPI", "Tailwind CSS"]);
  const [languages, setLanguages] = useState<any[]>([{ language: "Français", level: "Natif" }]);
  const [showPhotoOnCv, setShowPhotoOnCv] = useState(false);

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Overlay backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-[#1A1918]/20 backdrop-blur-xs z-40 lg:hidden cursor-pointer"
          />

          {/* Slide-over Panel */}
          <motion.aside
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", damping: 25, stiffness: 220 }}
            className="fixed top-0 right-0 h-full w-full lg:w-1/2 bg-white border-l border-[#EDECEA] shadow-2xl z-50 flex flex-col overflow-hidden font-light tracking-tight text-[#1A1918]"
          >
            {/* Top Close Bar */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-[#1A1918]/8 shrink-0 bg-[#FAFAF8]">
              <span className="text-xs font-mono text-[#006045] uppercase tracking-wider">
                Canvas — {mode === "cv_editor" ? "Éditeur de CV" : "Lettre de Motivation"}
              </span>
              <button
                type="button"
                onClick={onClose}
                aria-label="Fermer le Canvas"
                className="p-1.5 rounded-full text-[#1A1918]/45 hover:text-[#1A1918] hover:bg-[#1A1918]/5 transition-colors cursor-pointer"
              >
                <X className="w-4 h-4 stroke-[1.4]" />
              </button>
            </div>

            {/* Canvas Body */}
            <div className="flex-1 overflow-y-auto p-6">
              {mode === "cover_letter" && (
                <CoverLetterEditor
                  companyName={coverLetterData?.companyName}
                  initialContent={coverLetterData?.content}
                  onClose={onClose}
                />
              )}

              {mode === "cv_editor" && (
                <Step2CvEditor
                  fullName={fullName}
                  setFullName={setFullName}
                  email={email}
                  setEmail={setEmail}
                  phone={phone}
                  setPhone={setPhone}
                  linkedinUrl={linkedinUrl}
                  setLinkedinUrl={setLinkedinUrl}
                  headline={headline}
                  setHeadline={setHeadline}
                  summary={summary}
                  setSummary={setSummary}
                  userPhotoUrl={null}
                  handlePhotoUpload={() => {}}
                  showPhotoOnCv={showPhotoOnCv}
                  setShowPhotoOnCv={setShowPhotoOnCv}
                  experiences={experiences}
                  setExperiences={setExperiences}
                  education={education}
                  setEducation={setEducation}
                  skills={skills}
                  setSkills={setSkills}
                  languages={languages}
                  setLanguages={setLanguages}
                  atsAudit={null}
                  experienceYears={3}
                  selectedTemplate="modern"
                  activeColorSwatch={{ id: "emerald", name: "Émeraude", bg: "bg-emerald-50", border: "border-emerald-600", text: "text-emerald-700", hex: "#006045" }}
                />
              )}
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
