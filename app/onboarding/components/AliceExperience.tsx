"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { UploadCloud, Link as LinkIcon, Check, ArrowRight } from "lucide-react";
import { cvTemplates } from "../types";
import { cn } from "@/lib/utils";
import { AlicePresence, AliceEmotion } from "./AlicePresence";

// ─── Types ──────────────────────────────────────────────────────────────────

interface CandidateProfile {
  fullName: string;
  headline: string;
  email: string;
  phone: string;
  summary: string;
  skills: string[];
  experiences: any[];
  education: any[];
  languages: any[];
}

const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));

const TOTAL_PHASES = 7;

// ─── Main Component ─────────────────────────────────────────────────────────

export function AliceExperience() {
  const [phase, setPhase] = useState(0);
  const [aliceText, setAliceText] = useState<string[]>([]);
  const [emotion, setEmotion] = useState<AliceEmotion>("idle");
  const [showComponent, setShowComponent] = useState(false);

  // Candidate Profile State
  const [targetRole, setTargetRole] = useState("");
  const [cvFile, setCvFile] = useState<File | null>(null);
  const [linkedinUrl, setLinkedinUrl] = useState("");
  const [profile, setProfile] = useState<CandidateProfile>({
    fullName: "",
    headline: "",
    email: "",
    phone: "",
    summary: "",
    skills: [],
    experiences: [],
    education: [],
    languages: [],
  });
  const [detectedSkills, setDetectedSkills] = useState<string[]>([]);
  const [selectedTemplateIdx, setSelectedTemplateIdx] = useState(0);
  const [isEditingProfile, setIsEditingProfile] = useState(false);

  // Phase 6 Task Selection (Default all active)
  const [activeTasks, setActiveTasks] = useState<{ [key: string]: boolean }>({
    scan: true,
    adapt_cv: true,
    cover_letter: true,
    apply: true,
  });

  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto scroll smooth
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [aliceText, showComponent, detectedSkills]);

  const toggleTask = (id: string) => {
    setActiveTasks((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  // ─── Scenario API Helpers ────────────────────────────────────────────────

  const say = useCallback(async (text: string[], em: AliceEmotion = "listening", pauseMs = 600) => {
    setEmotion(em);
    setAliceText(text);
    await delay(pauseMs);
  }, []);

  const think = useCallback(async (text: string[], pauseMs = 800) => {
    setEmotion("thinking");
    setAliceText(text);
    await delay(pauseMs);
  }, []);

  const read = useCallback(async (text: string[], pauseMs = 700) => {
    setEmotion("reading");
    setAliceText(text);
    await delay(pauseMs);
  }, []);

  // ─── Initial Cinematic Intro ──────────────────────────────────────────────

  useEffect(() => {
    let active = true;
    const runIntro = async () => {
      await delay(400);
      if (!active) return;
      await say(["Salut."], "idle", 900);
      if (!active) return;
      await say(["Salut.", "Je suis Alice."], "listening", 950);
      if (!active) return;
      await say(["Salut.", "Je suis Alice.", "Je vais postuler pour toi."], "listening", 1100);
      if (!active) return;
      await think(["Qu'est-ce qu'on cherche ?"], 650);
      if (!active) return;
      setEmotion("listening");
      setShowComponent(true);
      setPhase(1);
    };
    runIntro();
    return () => {
      active = false;
    };
  }, [say, think]);

  // ─── Step Handlers ────────────────────────────────────────────────────────

  const handleRoleSelect = useCallback(async (role: string) => {
    setTargetRole(role);
    setShowComponent(false);
    await think([role + "."], 500);
    await say([role + ".", "Ton CV ?"], "listening", 400);
    setShowComponent(true);
    setPhase(2);
  }, [say, think]);

  const handleFileUpload = useCallback(async (file: File) => {
    setCvFile(file);
    setShowComponent(false);
    setPhase(3);
    setShowComponent(true);
    setDetectedSkills([]);

    await read(["Lecture du CV..."], 800);
    await read(["Extraction du parcours..."], 700);

    // Call parse-resume API
    let parsedData: any = null;
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch("http://localhost:8000/api/candidates/parse-resume", {
        method: "POST",
        body: formData,
      });
      if (res.ok) parsedData = await res.json();
    } catch (err) {
      console.error("CV parse error:", err);
    }

    await read(["Analyse des compétences..."], 600);

    // Reveal detected skills
    const skills = parsedData?.skills?.length > 0
      ? parsedData.skills.slice(0, 8)
      : ["React", "TypeScript", "Python", "Docker"];

    for (let i = 0; i < skills.length; i++) {
      await delay(200);
      setDetectedSkills((prev) => [...prev, skills[i]]);
    }

    if (parsedData) {
      setProfile((prev) => ({
        ...prev,
        fullName: parsedData.full_name || parsedData.name || prev.fullName,
        headline: parsedData.headline || parsedData.title || prev.headline,
        email: parsedData.email || prev.email,
        phone: parsedData.phone || prev.phone,
        summary: parsedData.summary || prev.summary,
        skills: parsedData.skills?.length > 0 ? parsedData.skills : prev.skills,
        experiences: parsedData.experiences || prev.experiences,
        education: parsedData.education || prev.education,
      }));
    }

    await delay(600);
    const firstName = (parsedData?.full_name || parsedData?.name || "").split(" ")[0] || "Candidat";
    await say([firstName + ", voici ton profil."], "happy", 400);
    setPhase(4);
  }, [read, say]);

  const handleLinkedinSubmit = useCallback(async () => {
    if (!linkedinUrl.trim()) return;
    setShowComponent(false);
    setDetectedSkills([]);
    setPhase(3);
    setShowComponent(true);

    await read(["Analyse du profil LinkedIn..."], 1000);
    await read(["Extraction du parcours..."], 800);
    await say(["Voici ton profil."], "happy", 400);
    setPhase(4);
  }, [linkedinUrl, read, say]);

  const handleKeepOriginalCv = useCallback(async () => {
    const firstName = profile.fullName.split(" ")[0] || "Candidat";
    setShowComponent(false);
    await think(["Entendu, " + firstName + "."], 950);
    await say(["Je garde ton CV original."], "listening", 1200);
    await say(["Je peux faire tout ça pour toi :"], "listening", 400);
    setShowComponent(true);
    setPhase(6);
  }, [profile.fullName, think, say]);

  const handleValidateProfile = useCallback(async () => {
    setShowComponent(false);
    await say(["J'ai préparé quelques styles."], "happy", 400);
    setShowComponent(true);
    setPhase(5);
  }, [say]);

  const handleTemplateSelect = useCallback(async (idx: number) => {
    setSelectedTemplateIdx(idx);
    const firstName = profile.fullName.split(" ")[0] || "Candidat";
    setShowComponent(false);
    await think(["Parfait, " + firstName + "."], 900);
    await say(["Style sélectionné."], "happy", 1100);
    await say(["Je peux faire tout ça pour toi :"], "listening", 400);
    setShowComponent(true);
    setPhase(6);
  }, [profile.fullName, think, say]);

  const handleBypassCv = useCallback(async () => {
    setShowComponent(false);
    await say(["Voici ton profil."], "listening", 300);
    setShowComponent(true);
    setPhase(4);
  }, [say]);

  const handleActivateAlice = useCallback(async () => {
    setShowComponent(false);
    setEmotion("happy");
    setAliceText(["C'est parti.", "Je travaille pour toi."]);
  }, []);

  // ─── Render Canvas ────────────────────────────────────────────────────────

  return (
    <main className="min-h-screen bg-[#FAFAF8] text-[#1A1918] flex flex-col items-center justify-center relative overflow-hidden">
      <div
        ref={scrollRef}
        className="w-full max-w-[520px] mx-auto px-6 py-10 md:py-14 flex flex-col items-center gap-6 overflow-y-auto"
        style={{ maxHeight: "100vh" }}
      >
        {/* ═══ Alice Presence (Always visible abstract eyes & gaze) ═══ */}
        <AlicePresence emotion={emotion} className="shrink-0" />

        {/* ═══ Alice Living Speech & Glowing Capsule Cursor ═══ */}
        <AnimatePresence mode="wait">
          {aliceText.length > 0 && (
            <motion.div
              key={aliceText.join("|")}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.35, ease: "easeOut" }}
              className="text-center space-y-1.5"
            >
              {aliceText.map((line, i) => {
                const isLastLine = i === aliceText.length - 1;
                const isPrompt =
                  line === "Qu'est-ce qu'on cherche ?" ||
                  line.startsWith("Je peux") ||
                  line.startsWith("Sélectionne");

                return (
                  <p
                    key={i}
                    className={cn(
                      "leading-snug tracking-tight",
                      i === 0 && !isPrompt && "text-2xl md:text-3xl font-normal text-[#1A1918]",
                      i === 1 && !isPrompt && "text-lg md:text-xl text-[#1A1918]/65",
                      i >= 2 && !isPrompt && "pt-1 text-xl md:text-2xl font-normal text-[#1A1918]",
                      isPrompt && "text-lg md:text-xl font-normal text-[#1A1918]/85 pt-1"
                    )}
                  >
                    <span>{line}</span>
                    {/* Alice's Presence = Glowing Capsule Cursor */}
                    {isLastLine && emotion !== "thinking" && (
                      <span className="alice-cursor-capsule" />
                    )}
                  </p>
                );
              })}
            </motion.div>
          )}
        </AnimatePresence>

        {/* ═══ Active Scenario Controls ═══ */}
        <AnimatePresence mode="wait">
          {showComponent && (
            <motion.div
              key={`component-${phase}`}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 8 }}
              transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
              className="w-full"
            >
              {/* ── Phase 1: Objective selector ── */}
              {phase === 1 && (
                <div className="space-y-3 pt-1">
                  <p className="text-sm font-medium text-[#1A1918]/40">Je cherche...</p>
                  {[
                    "une alternance",
                    "un stage",
                    "un CDI / CDD",
                    "je ne sais pas encore",
                  ].map((label, i) => (
                    <motion.button
                      key={label}
                      type="button"
                      onClick={() =>
                        handleRoleSelect(
                          label === "je ne sais pas encore"
                            ? "Poste ouvert"
                            : label.replace("un ", "").replace("une ", "")
                        )
                      }
                      initial={{ opacity: 0, x: -8 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ duration: 0.4, delay: i * 0.08 }}
                      className="group w-full min-h-14 text-left px-0 py-3.5 rounded-none bg-transparent transition-all text-lg font-medium text-[#1A1918]/82 hover:bg-[#F4F0E8] hover:text-[#006045] hover:pl-4 cursor-pointer flex items-center justify-between"
                    >
                      <span>{label}</span>
                      <ArrowRight className="h-4 w-4 mr-1 text-[#006045] opacity-0 -translate-x-2 transition-all duration-200 group-hover:opacity-100 group-hover:translate-x-0" />
                    </motion.button>
                  ))}
                </div>
              )}

              {/* ── Phase 2: CV drop / import ── */}
              {phase === 2 && (
                <div className="space-y-5 pt-2">
                  <div
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={(e) => {
                      e.preventDefault();
                      const file = e.dataTransfer.files[0];
                      if (file) handleFileUpload(file);
                    }}
                    className="relative border-2 border-dashed border-[#1A1918]/15 hover:border-[#006045]/50 bg-white/50 hover:bg-white rounded-2xl p-7 text-center transition-all cursor-pointer group shadow-sm"
                  >
                    <input
                      type="file"
                      accept=".pdf"
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file) handleFileUpload(file);
                      }}
                      className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                    />
                    <div className="flex flex-col items-center gap-3">
                      <div className="h-12 w-12 rounded-full bg-[#006045]/8 flex items-center justify-center text-[#006045] group-hover:scale-105 transition-transform">
                        <UploadCloud className="h-6 w-6" />
                      </div>
                      <div>
                        <p className="text-sm font-medium text-[#1A1918]">Glisse ton CV ici</p>
                        <p className="text-xs text-[#1A1918]/45 mt-0.5">ou clique pour parcourir (PDF)</p>
                      </div>
                    </div>
                  </div>

                  {/* LinkedIn fallback */}
                  <div className="relative">
                    <div className="absolute inset-y-0 left-3.5 flex items-center pointer-events-none text-[#1A1918]/35">
                      <LinkIcon className="h-4 w-4" />
                    </div>
                    <input
                      type="url"
                      placeholder="Ou colle ton lien LinkedIn..."
                      value={linkedinUrl}
                      onChange={(e) => setLinkedinUrl(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && handleLinkedinSubmit()}
                      className="w-full pl-10 pr-12 py-3 bg-white border border-[#EDECEA] rounded-xl text-sm placeholder:text-[#1A1918]/35 text-[#1A1918] focus:outline-none focus:border-[#006045] transition-all"
                    />
                    {linkedinUrl.trim() && (
                      <button
                        type="button"
                        onClick={handleLinkedinSubmit}
                        className="absolute right-2 top-2 px-3 py-1 bg-[#006045] text-white text-xs font-medium rounded-lg hover:bg-[#004d37] transition-colors"
                      >
                        OK
                      </button>
                    )}
                  </div>

                  <button
                    type="button"
                    onClick={handleBypassCv}
                    className="block mx-auto text-xs text-[#1A1918]/30 hover:text-[#006045] transition-colors cursor-pointer"
                  >
                    je n&apos;ai pas de CV
                  </button>
                </div>
              )}

              {/* ── Phase 3: Organic Skill Chips Stream ── */}
              {phase === 3 && (
                <div className="space-y-4">
                  {detectedSkills.length > 0 && (
                    <div className="flex flex-wrap gap-2 justify-center pt-2">
                      {detectedSkills.map((skill, i) => (
                        <motion.span
                          key={skill}
                          initial={{ opacity: 0, scale: 0.9 }}
                          animate={{ opacity: 1, scale: 1 }}
                          transition={{ duration: 0.35, delay: i * 0.05 }}
                          className="px-3 py-1.5 rounded-full text-xs font-normal bg-[#006045]/8 text-[#006045]"
                        >
                          {skill}
                        </motion.span>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* ── Phase 4: Profile Summary & Action Choices ── */}
              {phase === 4 && (
                <div className="space-y-6">
                  {!isEditingProfile ? (
                    <>
                      {profile.headline && (
                        <div className="space-y-1">
                          <div className="flex justify-between items-center">
                            <p className="text-xs text-[#1A1918]/35 uppercase tracking-wider font-medium">Titre professionnel</p>
                            <button
                              type="button"
                              onClick={() => setIsEditingProfile(true)}
                              className="text-xs text-[#006045] hover:underline font-medium cursor-pointer"
                            >
                              Ajuster
                            </button>
                          </div>
                          <p className="text-sm font-semibold text-[#1A1918]">{profile.headline}</p>
                        </div>
                      )}

                      {profile.summary && (
                        <div className="space-y-1">
                          <p className="text-xs text-[#1A1918]/35 uppercase tracking-wider font-medium">Accroche &amp; Synthèse</p>
                          <p className="text-xs text-[#1A1918]/70 leading-relaxed">{profile.summary}</p>
                        </div>
                      )}

                      {profile.skills.length > 0 && (
                        <div className="space-y-1.5">
                          <p className="text-xs text-[#1A1918]/35 uppercase tracking-wider font-medium">Compétences clés</p>
                          <div className="flex flex-wrap gap-1.5">
                            {profile.skills.map((s) => (
                              <span key={s} className="px-2.5 py-1 rounded-md text-xs font-medium bg-[#006045]/8 text-[#006045]">
                                {s}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Clean line actions */}
                      <div className="pt-4 space-y-2 border-t border-[#1A1918]/8">
                        <button
                          type="button"
                          onClick={handleKeepOriginalCv}
                          className="group w-full py-3.5 text-left text-sm text-[#1A1918] font-normal hover:text-[#006045] transition-colors cursor-pointer flex items-center justify-between"
                        >
                          <span>garder mon CV PDF original tel quel</span>
                          <ArrowRight className="h-4 w-4 text-[#006045] transition-transform group-hover:translate-x-1" />
                        </button>
                        <button
                          type="button"
                          onClick={handleValidateProfile}
                          className="group w-full py-3 text-left text-xs text-[#1A1918]/50 hover:text-[#006045] transition-colors cursor-pointer flex items-center justify-between"
                        >
                          <span>continuer avec un style recommandé par Alice</span>
                          <ArrowRight className="h-3.5 w-3.5 text-[#006045] transition-transform group-hover:translate-x-1" />
                        </button>
                      </div>
                    </>
                  ) : (
                    /* Inline Editor */
                    <div className="space-y-4 text-left">
                      <div>
                        <label className="text-xs font-medium text-[#1A1918]/50">Titre professionnel</label>
                        <input
                          type="text"
                          value={profile.headline}
                          onChange={(e) => setProfile((p) => ({ ...p, headline: e.target.value }))}
                          className="w-full mt-1 px-3 py-2 border border-[#EDECEA] rounded-lg text-sm"
                        />
                      </div>
                      <div>
                        <label className="text-xs font-medium text-[#1A1918]/50">Synthèse</label>
                        <textarea
                          rows={3}
                          value={profile.summary}
                          onChange={(e) => setProfile((p) => ({ ...p, summary: e.target.value }))}
                          className="w-full mt-1 px-3 py-2 border border-[#EDECEA] rounded-lg text-sm"
                        />
                      </div>
                      <button
                        type="button"
                        onClick={() => setIsEditingProfile(false)}
                        className="w-full py-2.5 bg-[#006045] text-white text-xs font-medium rounded-lg"
                      >
                        Enregistrer
                      </button>
                    </div>
                  )}
                </div>
              )}

              {/* ── Phase 5: Template Carousel ── */}
              {phase === 5 && (
                <div className="space-y-6">
                  <div className="flex items-center justify-between p-4 bg-white rounded-2xl border border-[#EDECEA] shadow-sm">
                    <button
                      type="button"
                      onClick={() => setSelectedTemplateIdx((i) => Math.max(0, i - 1))}
                      disabled={selectedTemplateIdx === 0}
                      className="p-2 text-[#1A1918]/40 hover:text-[#006045] disabled:opacity-20 cursor-pointer"
                    >
                      ←
                    </button>
                    <div className="text-center">
                      <p className="text-sm font-semibold text-[#1A1918]">{cvTemplates[selectedTemplateIdx].name}</p>
                      <p className="text-xs text-[#1A1918]/45 mt-0.5">{cvTemplates[selectedTemplateIdx].description}</p>
                    </div>
                    <button
                      type="button"
                      onClick={() => setSelectedTemplateIdx((i) => Math.min(cvTemplates.length - 1, i + 1))}
                      disabled={selectedTemplateIdx === cvTemplates.length - 1}
                      className="p-2 text-[#1A1918]/40 hover:text-[#006045] disabled:opacity-20 cursor-pointer"
                    >
                      →
                    </button>
                  </div>
                  <div className="flex justify-center">
                    <button
                      type="button"
                      onClick={() => handleTemplateSelect(selectedTemplateIdx)}
                      className="group inline-flex items-center justify-center gap-2 py-3.5 px-6 text-[#006045] hover:text-[#004d37] font-medium text-sm transition-all cursor-pointer bg-transparent"
                    >
                      <span>Sélectionner ce style</span>
                      <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
                    </button>
                  </div>
                </div>
              )}

              {/* ── Phase 6: Final Pact & Task Checklist (Cardless) ── */}
              {phase === 6 && (
                <div className="space-y-8 w-full">
                  <div className="w-full max-w-[440px] mx-auto text-left border-t border-b border-[#1A1918]/10 divide-y divide-[#1A1918]/8">
                    {[
                      { id: "scan", label: "Scanner 500+ offres par jour" },
                      { id: "adapt_cv", label: "Adapter ton CV à chaque poste" },
                      { id: "cover_letter", label: "Rédiger tes lettres de motivation" },
                      { id: "apply", label: "Postuler automatiquement pour toi" },
                    ].map((task) => {
                      const isChecked = activeTasks[task.id];
                      return (
                        <div
                          key={task.id}
                          onClick={() => toggleTask(task.id)}
                          className="flex items-center justify-between py-4 cursor-pointer group select-none transition-colors"
                        >
                          <div className="flex items-center gap-3">
                            <span
                              className={cn(
                                "text-sm font-medium transition-all w-4 text-center shrink-0",
                                isChecked ? "text-[#006045]" : "text-[#1A1918]/25"
                              )}
                            >
                              {isChecked ? "✓" : "—"}
                            </span>
                            <span
                              className={cn(
                                "text-sm md:text-base transition-all",
                                isChecked
                                  ? "text-[#1A1918] font-normal"
                                  : "text-[#1A1918]/30 line-through"
                              )}
                            >
                              {task.label}
                            </span>
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  <div className="flex justify-center pt-2">
                    <button
                      type="button"
                      onClick={handleActivateAlice}
                      className="group inline-flex items-center justify-center gap-2.5 py-4 px-8 text-[#006045] hover:text-[#004d37] font-medium text-base md:text-lg transition-all cursor-pointer bg-transparent"
                    >
                      <span>Oui, occupe-toi de tout</span>
                      <ArrowRight className="h-4.5 w-4.5 transition-transform group-hover:translate-x-1.5" />
                    </button>
                  </div>
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </main>
  );
}
