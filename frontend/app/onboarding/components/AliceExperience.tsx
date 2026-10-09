"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { UploadCloud, Link as LinkIcon, ArrowRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { API_BASE_URL } from "@/lib/config";
import { AlicePresence, AliceEmotion } from "./AlicePresence";
import {
  CriteriaStep,
  DEFAULT_CRITERIA,
  ZONE_COUNTRIES,
  type CriteriaDraft,
} from "./CriteriaStep";
import { ApiUnreachableError, apiFetch, describeApiError } from "@/lib/api";
import { startRun } from "@/lib/mission-run-client";
import { accessToken, authEnabled } from "@/lib/auth";
import { destinationAfterSignIn } from "@/lib/session";
import { EmailSignIn } from "../../auth/EmailSignIn";
import { SignaturePad } from "@/app/dashboard/components/SignaturePad";
import { saveCvDesign, uploadPhoto } from "@/lib/cv-profile";
import { CvLookStep, DEFAULT_LOOK, type CvLook } from "./CvLookStep";
import Link from "next/link";

// ─── Types ──────────────────────────────────────────────────────────────────

interface CandidateProfile {
  firstName: string;
  lastName: string;
  headline: string;
  email: string;
  phone: string;
  summary: string;
  skills: string[];
  experienceYears: number | null;
  experiences: any[];
  education: any[];
  languages: any[];
}

const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** « Camille Martin Durand » → prénom « Camille », nom « Martin Durand ». */
function splitName(full: string | null | undefined): { first: string; last: string } {
  const parts = (full || "").trim().split(/\s+/).filter(Boolean);
  return { first: parts[0] ?? "", last: parts.slice(1).join(" ") };
}

/** Le serveur ne lit que le PDF : on le dit avant l'envoi, pas après. */
const isPdf = (file: File) =>
  file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");

/** Une question appelle une réponse : elle s'affiche plus discrètement. */
const isPrompt = (line: string) => line.trim().endsWith("?");

/** L'objectif choisi en phase 1 est déjà un filtre dur sur le contrat. */
const ROLE_TO_CONTRACTS: Record<string, string[]> = {
  alternance: ["alternance"],
  stage: ["stage"],
  "CDI / CDD": ["cdi", "cdd"],
  "Poste ouvert": [],
};

// ─── Main Component ─────────────────────────────────────────────────────────

export function AliceExperience() {
  const router = useRouter();
  const [phase, setPhase] = useState(0);
  const [aliceLine, setAliceLine] = useState("");
  const [emotion, setEmotion] = useState<AliceEmotion>("idle");
  const [showComponent, setShowComponent] = useState(false);

  // Candidate Profile State
  const [targetRole, setTargetRole] = useState("");
  const [cvFile, setCvFile] = useState<File | null>(null);
  const [linkedinUrl, setLinkedinUrl] = useState("");
  const [profile, setProfile] = useState<CandidateProfile>({
    firstName: "",
    lastName: "",
    headline: "",
    email: "",
    phone: "",
    summary: "",
    skills: [],
    experienceYears: null,
    experiences: [],
    education: [],
    languages: [],
  });

  // Mandat de recherche — dernière étape du parcours (phase 5)
  const [criteria, setCriteria] = useState<CriteriaDraft>(DEFAULT_CRITERIA);
  // Allure des CV (phase 6) et signature des lettres (phase 7), enregistrées
  // au profil à l'activation : tous les dossiers les suivent.
  const [look, setLook] = useState<CvLook>(DEFAULT_LOOK);
  const [lookChosen, setLookChosen] = useState(false);
  const [signature, setSignature] = useState<string | null>(null);
  const [cityInput, setCityInput] = useState("");
  const [emailInput, setEmailInput] = useState("");
  const [isActivating, setIsActivating] = useState(false);
  const [activationError, setActivationError] = useState<string | null>(null);
  /** Adresse en attente de confirmation : l'activation reprend à la connexion. */
  const [pendingAuthEmail, setPendingAuthEmail] = useState<string | null>(null);
  const [isSignedIn, setIsSignedIn] = useState(false);

  const [detectedSkills, setDetectedSkills] = useState<string[]>([]);
  const [isEditingProfile, setIsEditingProfile] = useState(false);
  /** Prénom ou nom inconnus à l'arrivée sur le profil : on les demande. */
  const [askName, setAskName] = useState(false);
  const [nameError, setNameError] = useState<string | null>(null);

  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto scroll smooth
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [aliceLine, showComponent, detectedSkills]);

  // ─── Scenario API Helpers ────────────────────────────────────────────────

  // Alice ne dit qu'une phrase à la fois : la suivante remplace la précédente
  // en fondu, au lieu de s'empiler. Une seule ligne à l'écran, toujours.
  const say = useCallback(async (line: string, em: AliceEmotion = "listening", pauseMs = 600) => {
    setEmotion(em);
    setAliceLine(line);
    await delay(pauseMs);
  }, []);

  const think = useCallback(async (line: string, pauseMs = 800) => {
    setEmotion("thinking");
    setAliceLine(line);
    await delay(pauseMs);
  }, []);

  const read = useCallback(async (line: string, pauseMs = 700) => {
    setEmotion("reading");
    setAliceLine(line);
    await delay(pauseMs);
  }, []);

  // ─── Initial Cinematic Intro ──────────────────────────────────────────────

  useEffect(() => {
    let active = true;
    const runIntro = async () => {
      await delay(400);
      if (!active) return;
      await say("Salut.", "idle", 1000);
      if (!active) return;
      await say("Je suis Alice.", "listening", 1050);
      if (!active) return;
      await say("Je vais postuler pour toi.", "listening", 1250);
      if (!active) return;
      await think("Qu'est-ce qu'on cherche ?", 700);
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

  /** Remplissage du profil, partagé par l'import CV et l'import LinkedIn. */
  const applyParsedProfile = useCallback((parsed: any) => {
    const name = splitName(parsed.full_name || parsed.name);
    setProfile((prev) => ({
      ...prev,
      firstName: name.first || prev.firstName,
      lastName: name.last || prev.lastName,
      headline: parsed.headline || parsed.title || prev.headline,
      email: parsed.email || prev.email,
      phone: parsed.phone || prev.phone,
      summary: parsed.summary || prev.summary,
      skills: parsed.skills?.length > 0 ? parsed.skills : prev.skills,
      experienceYears: parsed.experience_years ?? prev.experienceYears,
      experiences: parsed.experiences || prev.experiences,
      education: parsed.education || prev.education,
      languages: parsed.languages?.length ? parsed.languages : prev.languages,
    }));

    // Les localisations extraites pré-remplissent le mandat sans l'imposer.
    if (parsed.preferred_locations?.length) {
      setCriteria((prev) => ({
        ...prev,
        locations: prev.locations.length ? prev.locations : parsed.preferred_locations,
      }));
    }
  }, []);

  const handleRoleSelect = useCallback(async (role: string) => {
    setTargetRole(role);
    setShowComponent(false);
    await think(role + ".", 700);
    await say("Ton CV ?", "listening", 350);
    setShowComponent(true);
    setPhase(2);
  }, [say, think]);

  const handleFileUpload = useCallback(async (file: File) => {
    if (!isPdf(file)) {
      await say("Je ne lis que les CV en PDF.", "thinking", 900);
      await say("Enregistre-le en PDF, puis dépose-le ici.", "listening", 400);
      return;
    }
    setCvFile(file);
    setShowComponent(false);
    setPhase(3);
    setShowComponent(true);
    setDetectedSkills([]);

    await read("Je lis ton CV...", 850);
    await read("Je découvre ton parcours...", 750);

    // Call parse-resume API
    let parsedData: any = null;
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await apiFetch(`${API_BASE_URL}/api/candidates/parse-resume`, {
        method: "POST",
        body: formData,
      });
      if (res.ok) parsedData = await res.json();
    } catch (err) {
      console.error("CV parse error:", err);
      if (err instanceof ApiUnreachableError) {
        // Ne pas faire comme si la lecture avait marché : le dire, et
        // laisser recommencer quand le serveur répondra.
        await say("Je n'arrive pas à joindre mon serveur pour lire ton CV.", "thinking", 600);
        await say("Réessaie dans un moment — rien n'est perdu.", "listening", 400);
        setPhase(2); // retour au dépôt du CV
        return;
      }
    }

    if (!parsedData) {
      // Lecture refusée ou échouée : ne rien montrer d'inventé.
      setCvFile(null);
      await say("Je n'ai pas réussi à lire ce fichier.", "thinking", 900);
      await say("Essaie un autre PDF, ou continue sans CV.", "listening", 400);
      setPhase(2);
      return;
    }

    const name = splitName(parsedData.full_name || parsedData.name);
    setAskName(!name.first || !name.last);

    if (parsedData.text_detected === false) {
      // CV scanné : aucun texte à lire. Le dire, et demander l'essentiel.
      await say("Ton CV ressemble à un scan : je n'y trouve aucun texte à lire.", "thinking", 1300);
      await say("Remplis l'essentiel ici, ou dépose un PDF avec du texte.", "listening", 500);
      setIsEditingProfile(true);
      setPhase(4);
      return;
    }

    await read("Je rassemble ce qui compte...", 650);

    // Seules les compétences réellement lues s'affichent.
    const skills: string[] = (parsedData.skills || []).slice(0, 8);
    for (let i = 0; i < skills.length; i++) {
      await delay(200);
      setDetectedSkills((prev) => [...prev, skills[i]]);
    }

    applyParsedProfile(parsedData);

    await delay(600);
    await say(name.first ? `${name.first}, voici ton profil.` : "Voici ton profil.", "happy", 400);
    setPhase(4);
  }, [read, say, applyParsedProfile]);

  const handleLinkedinSubmit = useCallback(async () => {
    if (!linkedinUrl.trim()) return;
    setShowComponent(false);
    setDetectedSkills([]);
    setPhase(3);
    setShowComponent(true);

    await read("Je regarde ton profil LinkedIn...", 900);

    let parsedData: any = null;
    try {
      const res = await apiFetch(
        `${API_BASE_URL}/api/candidates/parse-linkedin?linkedin_url=${encodeURIComponent(linkedinUrl.trim())}`,
        { method: "POST" }
      );
      if (res.ok) parsedData = await res.json();
    } catch (err) {
      console.error("LinkedIn parse error:", err);
    }

    await read("Je rassemble ce qui compte...", 650);

    // LinkedIn bloque les lectures anonymes : on ne récupère au mieux qu'un nom
    // deviné depuis l'URL. Tout dire plutôt que de mimer une extraction réussie.
    const isUsable = Boolean(parsedData?.headline || parsedData?.skills?.length);

    if (parsedData) applyParsedProfile(parsedData);
    const name = splitName(parsedData?.full_name);
    setAskName(!name.first || !name.last);

    if (isUsable) {
      const skills = (parsedData.skills || []).slice(0, 8);
      for (const skill of skills) {
        await delay(180);
        setDetectedSkills((prev) => [...prev, skill]);
      }
      await delay(500);
      const firstName = (parsedData.full_name || "").split(" ")[0];
      await say(firstName ? `${firstName}, voici ton profil.` : "Voici ton profil.", "happy", 400);
    } else {
      await say("LinkedIn ne me laisse pas lire ton profil.", "idle", 1100);
      await say("Complète-le ici, ou reviens avec ton CV.", "listening", 700);
    }

    setPhase(4);
  }, [linkedinUrl, read, say, applyParsedProfile]);

  /**
   * Sortie unique de la phase profil.
   *
   * Le choix d'un modèle de CV ne fait pas partie de l'onboarding : il se fera
   * plus tard, avec Alice, dans le Canvas. Annoncer ici « j'ai préparé quelques
   * styles » promettait une étape qui n'existe pas à ce moment du parcours.
   */
  const handleProfileValidated = useCallback(async () => {
    if (!profile.firstName.trim() || !profile.lastName.trim()) {
      setNameError("Ton prénom et ton nom signent tes candidatures : j'en ai besoin.");
      return;
    }
    setNameError(null);
    setShowComponent(false);
    await say("Ton CV est prêt.", "happy", 950);
    await say("Choisis son allure : chaque dossier que je prépare la suivra.", "listening", 1100);
    setEmotion("listening");
    setShowComponent(true);
    setPhase(6);
  }, [profile.firstName, profile.lastName, say]);

  const handleLookChosen = useCallback(async () => {
    setLookChosen(true);
    setShowComponent(false);
    await say("Noté.", "happy", 700);
    await say("Une lettre signée fait plus sérieux. Signe une fois, je la mettrai sur chacune.", "listening", 1300);
    setEmotion("listening");
    setShowComponent(true);
    setPhase(7);
  }, [say]);

  const handleSignatureDone = useCallback(async (dataUrl: string | null) => {
    setSignature(dataUrl);
    setShowComponent(false);
    await say(
      dataUrl ? "Parfait, tes lettres partiront signées." : "D'accord, je te la redemanderai avant le premier envoi.",
      "happy", 1000,
    );
    await think("Où, et à quelles conditions ?", 700);
    setEmotion("listening");
    setShowComponent(true);
    setPhase(5);
  }, [say, think]);

  const handleBypassCv = useCallback(async () => {
    setShowComponent(false);
    await say("Pas de souci, on part de zéro.", "listening", 800);
    await say("Comment tu t'appelles ?", "listening", 300);
    setAskName(true);
    setShowComponent(true);
    setPhase(4);
  }, [say]);

  /**
   * Dernière étape du parcours : le mandat renseigné crée (ou retrouve) le
   * profil, puis bascule sur le dashboard — sans écran intermédiaire.
   *
   * Idempotent : relancer l'onboarding avec le même email reprend le profil
   * existant au lieu de buter sur le conflit d'unicité.
   */
  const handleActivateAlice = useCallback(async () => {
    const email = (profile.email || emailInput).trim();
    const fullName = `${profile.firstName.trim()} ${profile.lastName.trim()}`.trim();
    if (!profile.firstName.trim() || !profile.lastName.trim()) {
      setActivationError("Il me manque ton prénom et ton nom : reviens à ton profil pour les ajouter.");
      return;
    }
    if (!email) {
      setActivationError("J'ai besoin de ton email pour te suivre.");
      return;
    }

    setActivationError(null);

    // Le profil appartient à un compte : sans session, on fait confirmer
    // l'adresse d'abord. Tout ce qui a été saisi reste en mémoire, et
    // l'activation reprend d'elle-même une fois la connexion faite.
    if ((await authEnabled()) && !(await accessToken())) {
      setPendingAuthEmail(email);
      return;
    }

    setIsActivating(true);

    const matchingCriteria = {
      languages: criteria.languages,
      countries: ZONE_COUNTRIES[criteria.zone],
      remote_policies: criteria.remotePolicies,
      contract_types: ROLE_TO_CONTRACTS[targetRole] ?? [],
      locations: criteria.locations,
      ...(criteria.jobFamilies.length ? { job_families: criteria.jobFamilies } : {}),
    };

    const payload = {
      full_name: fullName,
      email,
      phone: profile.phone || null,
      linkedin_url: linkedinUrl || null,
      headline: profile.headline || null,
      skills: profile.skills,
      experience_years: profile.experienceYears,
      preferred_locations: criteria.locations,
      preferred_remote_policies: criteria.remotePolicies,
      preferred_contract_types: ROLE_TO_CONTRACTS[targetRole] ?? [],
      resume_raw: profile.summary || null,
      matching_criteria: matchingCriteria,
    };

    try {
      let res = await apiFetch(`${API_BASE_URL}/api/candidates/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      let candidate: { id: string; full_name: string; email: string } | null = null;

      if (res.ok) {
        candidate = await res.json();
      } else if (res.status === 409) {
        // Profil déjà connu : on le récupère et on réécrit tout — profil *et*
        // mandat. Ne mettre à jour que le mandat laisserait un CV périmé
        // derrière, et c'est le profil qui sert à déduire ce que le mandat ne
        // dit pas. Le PUT relance le matching côté serveur.
        const lookup = await apiFetch(
          `${API_BASE_URL}/api/candidates/?email=${encodeURIComponent(email)}`
        );
        const found = lookup.ok ? await lookup.json() : [];
        const existing = found[0] ?? null;

        if (existing) {
          const updated = await apiFetch(`${API_BASE_URL}/api/candidates/${existing.id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
          });
          candidate = updated.ok ? await updated.json() : existing;
        }
      }

      if (!candidate) {
        if (res.status === 409 && (await authEnabled())) {
          setActivationError("Cette adresse est déjà liée à un autre compte. Connecte-toi avec elle.");
          setIsActivating(false);
          return;
        }
        throw new Error(`Création impossible (${res.status})`);
      }

      // Le parcours détaillé part au serveur dès l'activation : c'est avec lui
      // qu'Alice compose le CV adapté et argumente les lettres. Sans ça, le
      // CV adapté sortait avec un nom et des compétences, rien d'autre.
      try {
        await apiFetch(`${API_BASE_URL}/api/candidates/${candidate.id}/cv-content`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            summary: profile.summary || "",
            experiences: profile.experiences,
            education: profile.education,
            languages: profile.languages,
          }),
        });
      } catch (err) {
        console.error("CV content save failed:", err);
      }

      // L'allure des CV et la signature, choisies pendant l'inscription :
      // enregistrées avant la première mission, pour que ses dossiers les
      // portent déjà. Un échec ne bloque pas l'entrée dans l'application.
      try {
        if (look.photo) await uploadPhoto(candidate.id, look.photo);
        if (lookChosen) {
          await saveCvDesign(candidate.id, {
            mode: "template",
            template_id: look.templateId,
            color_hex: look.colorHex,
            show_photo: look.showPhoto && Boolean(look.photo),
          });
        }
        if (signature) {
          await apiFetch(`${API_BASE_URL}/api/candidates/${candidate.id}/signature`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ image: signature }),
          });
        }
      } catch (err) {
        console.error("CV look / signature save failed:", err);
      }

      localStorage.setItem("candidate_id", candidate.id);
      localStorage.setItem("candidate_email", candidate.email);
      localStorage.setItem("candidate_name", candidate.full_name);

      // Le CV d'origine est conservé tel quel : c'est lui qui s'ouvrira dans le
      // Canvas tant que le candidat n'aura pas demandé un modèle. Un échec ici
      // ne doit pas bloquer l'entrée dans l'application.
      if (cvFile) {
        try {
          const form = new FormData();
          form.append("file", cvFile);
          await apiFetch(`${API_BASE_URL}/api/candidates/${candidate.id}/resume`, {
            method: "POST",
            body: form,
          });
        } catch (err) {
          console.error("Resume upload failed:", err);
        }
      }

      // Première valeur, tout de suite : une mission sur 3 offres démarre
      // dès l'arrivée — l'utilisateur ouvre son espace sur des dossiers qui
      // se rédigent, pas sur un tableau vide. Rien ne part sans son accord.
      const firstRun = await startRun(candidate.id, {
        title: "Tes premiers dossiers",
        objective: "apply",
        count: 3,
        allowed_actions: { send: false },
      }).catch(() => null);

      setShowComponent(false);
      await say("C'est parti.", "happy", 1000);
      await say(
        firstRun
          ? "Je cherche tes offres et je prépare tes trois premiers dossiers."
          : "Je travaille pour toi.",
        "happy",
        1400,
      );
      router.push("/dashboard");
    } catch (err) {
      console.error("Activation error:", err);
      setActivationError(
        describeApiError(err, "Je n'ai pas réussi à ouvrir ton espace. Réessaie dans un moment.")
      );
      setIsActivating(false);
    }
  }, [profile, emailInput, criteria, targetRole, linkedinUrl, cvFile, router, say, look, lookChosen, signature]);

  const activateRef = useRef(handleActivateAlice);
  useEffect(() => {
    activateRef.current = handleActivateAlice;
  }, [handleActivateAlice]);

  const handleAuthConfirmed = useCallback(() => {
    setPendingAuthEmail(null);
    void activateRef.current();
  }, []);

  // Déjà connecté avec un profil : rien à refaire ici, direction l'espace.
  // Un rechargement ne doit jamais renvoyer quelqu'un qui a déjà un espace
  // au début de l'onboarding : avec une session, direction son espace ; sans
  // session mais avec un profil connu sur ce navigateur, la connexion.
  const [authOn, setAuthOn] = useState(false);
  useEffect(() => {
    let alive = true;
    (async () => {
      const on = await authEnabled();
      if (!alive) return;
      setAuthOn(on);
      if (!on) {
        if (localStorage.getItem("candidate_id")) router.replace("/dashboard");
        return;
      }
      const token = await accessToken();
      if (!alive) return;
      if (!token) {
        if (localStorage.getItem("candidate_id")) router.replace("/login");
        return;
      }
      setIsSignedIn(true);
      const destination = await destinationAfterSignIn();
      if (alive && destination !== "/") router.replace(destination);
    })();
    return () => {
      alive = false;
    };
  }, [router]);

  // ─── Render Canvas ────────────────────────────────────────────────────────

  return (
    <main className="min-h-screen bg-[#FAFAF8] text-[#1A1918] flex flex-col items-center justify-center relative overflow-hidden">
      {authOn && !isSignedIn && (
        <Link
          href="/login"
          className="absolute top-5 right-6 z-10 text-xs font-normal text-[#1A1918]/60 hover:text-[#006045] tracking-tight"
        >
          Déjà un compte ? Se connecter
        </Link>
      )}
      <div
        ref={scrollRef}
        className="w-full max-w-[520px] mx-auto px-6 py-10 md:py-14 flex flex-col items-center gap-6 overflow-y-auto"
        style={{ maxHeight: "100vh" }}
      >
        {/* ═══ Alice Presence (Always visible abstract eyes & gaze) ═══ */}
        <AlicePresence emotion={emotion} className="shrink-0" />

        {/* ═══ Parole d'Alice — une seule phrase, remplacée en fondu ═══ */}
        <div className="min-h-[3.5rem] flex items-center justify-center">
          <AnimatePresence mode="wait">
            {aliceLine && (
              <motion.p
                key={aliceLine}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.32, ease: [0.16, 1, 0.3, 1] }}
                className={cn(
                  "text-center leading-snug tracking-tight",
                  isPrompt(aliceLine)
                    ? "text-lg md:text-xl font-normal text-[#1A1918]/85"
                    : "text-2xl md:text-3xl font-normal text-[#1A1918]"
                )}
              >
                <span>{aliceLine}</span>
                {emotion !== "thinking" && <span className="alice-cursor-capsule" />}
              </motion.p>
            )}
          </AnimatePresence>
        </div>

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
                  <p className="text-sm font-medium text-[#1A1918]/55">Je cherche...</p>
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
                      accept=".pdf,application/pdf"
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
                        <p className="text-xs text-[#1A1918]/60 mt-0.5">ou clique pour parcourir (PDF)</p>
                      </div>
                    </div>
                  </div>

                  {/* LinkedIn fallback */}
                  <div className="relative">
                    <div className="absolute inset-y-0 left-3.5 flex items-center pointer-events-none text-[#1A1918]/50">
                      <LinkIcon className="h-4 w-4" />
                    </div>
                    <input
                      type="url"
                      placeholder="Ou colle ton lien LinkedIn..."
                      value={linkedinUrl}
                      onChange={(e) => setLinkedinUrl(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && handleLinkedinSubmit()}
                      className="w-full pl-10 pr-12 py-3 bg-white border border-[#EDECEA] rounded-xl text-sm placeholder:text-[#1A1918]/50 text-[#1A1918] focus:outline-none focus:border-[#006045] transition-all"
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
                    className="block mx-auto text-xs text-[#1A1918]/45 hover:text-[#006045] transition-colors cursor-pointer"
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
                      {/* « Ajuster » reste accessible même sans titre ni nom lus. */}
                      <div className="flex justify-between items-center">
                        <p className="text-xs text-[#1A1918]/50 uppercase tracking-wider font-medium">Ton profil</p>
                        <button
                          type="button"
                          onClick={() => setIsEditingProfile(true)}
                          className="text-xs text-[#006045] hover:underline font-medium cursor-pointer"
                        >
                          Ajuster
                        </button>
                      </div>

                      {askName ? (
                        <div className="space-y-2">
                          <p className="text-xs text-[#1A1918]/50">
                            Ton prénom et ton nom : ils signent tes candidatures.
                          </p>
                          <div className="grid grid-cols-2 gap-2">
                            <input
                              type="text"
                              autoComplete="given-name"
                              placeholder="Prénom"
                              aria-label="Prénom"
                              value={profile.firstName}
                              onChange={(e) => setProfile((p) => ({ ...p, firstName: e.target.value }))}
                              className="w-full px-3 py-2.5 bg-white border border-[#EDECEA] rounded-xl text-sm placeholder:text-[#1A1918]/50 focus:outline-none focus:border-[#006045]"
                            />
                            <input
                              type="text"
                              autoComplete="family-name"
                              placeholder="Nom"
                              aria-label="Nom"
                              value={profile.lastName}
                              onChange={(e) => setProfile((p) => ({ ...p, lastName: e.target.value }))}
                              className="w-full px-3 py-2.5 bg-white border border-[#EDECEA] rounded-xl text-sm placeholder:text-[#1A1918]/50 focus:outline-none focus:border-[#006045]"
                            />
                          </div>
                        </div>
                      ) : (
                        <p className="text-sm font-semibold text-[#1A1918]">
                          {profile.firstName} {profile.lastName}
                        </p>
                      )}

                      {profile.headline && (
                        <div className="space-y-1">
                          <p className="text-xs text-[#1A1918]/50 uppercase tracking-wider font-medium">Titre professionnel</p>
                          <p className="text-sm font-semibold text-[#1A1918]">{profile.headline}</p>
                        </div>
                      )}

                      {profile.summary && (
                        <div className="space-y-1">
                          <p className="text-xs text-[#1A1918]/50 uppercase tracking-wider font-medium">Accroche &amp; Synthèse</p>
                          <p className="text-xs text-[#1A1918]/70 leading-relaxed">{profile.summary}</p>
                        </div>
                      )}

                      {profile.skills.length > 0 && (
                        <div className="space-y-1.5">
                          <p className="text-xs text-[#1A1918]/50 uppercase tracking-wider font-medium">Compétences clés</p>
                          <div className="flex flex-wrap gap-1.5">
                            {profile.skills.map((s) => (
                              <span key={s} className="px-2.5 py-1 rounded-md text-xs font-medium bg-[#006045]/8 text-[#006045]">
                                {s}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      {nameError && <p className="text-center text-xs text-red-600/80">{nameError}</p>}

                      {/* Sortie unique : le style du CV se choisira plus tard,
                          avec Alice, dans le Canvas. */}
                      <div className="pt-4 border-t border-[#1A1918]/8">
                        <button
                          type="button"
                          onClick={handleProfileValidated}
                          className="group w-full py-3.5 text-left text-sm text-[#1A1918] font-normal hover:text-[#006045] transition-colors cursor-pointer flex items-center justify-between"
                        >
                          <span>c&apos;est bien moi, on continue</span>
                          <ArrowRight className="h-4 w-4 text-[#006045] transition-transform group-hover:translate-x-1" />
                        </button>
                      </div>
                    </>
                  ) : (
                    /* Inline Editor */
                    <div className="space-y-4 text-left">
                      <div className="grid grid-cols-2 gap-2">
                        <div>
                          <label className="text-xs font-medium text-[#1A1918]/50">Prénom</label>
                          <input
                            type="text"
                            autoComplete="given-name"
                            value={profile.firstName}
                            onChange={(e) => setProfile((p) => ({ ...p, firstName: e.target.value }))}
                            className="w-full mt-1 px-3 py-2 border border-[#EDECEA] rounded-lg text-sm"
                          />
                        </div>
                        <div>
                          <label className="text-xs font-medium text-[#1A1918]/50">Nom</label>
                          <input
                            type="text"
                            autoComplete="family-name"
                            value={profile.lastName}
                            onChange={(e) => setProfile((p) => ({ ...p, lastName: e.target.value }))}
                            className="w-full mt-1 px-3 py-2 border border-[#EDECEA] rounded-lg text-sm"
                          />
                        </div>
                      </div>
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
                        onClick={() => {
                          // Nom encore incomplet : les champs restent affichés.
                          setAskName(!profile.firstName.trim() || !profile.lastName.trim());
                          setIsEditingProfile(false);
                        }}
                        className="w-full py-2.5 bg-[#006045] hover:bg-[#004d37] text-white text-xs font-medium rounded-lg"
                      >
                        Enregistrer
                      </button>
                    </div>
                  )}

                  <button
                    type="button"
                    onClick={() => {
                      setCvFile(null);
                      setIsEditingProfile(false);
                      setPhase(2);
                    }}
                    className="block mx-auto text-xs text-[#1A1918]/45 hover:text-[#006045] transition-colors cursor-pointer"
                  >
                    déposer un autre CV
                  </button>
                </div>
              )}

              {/* ── Phase 6: L'allure des CV ── */}
              {phase === 6 && (
                <CvLookStep profile={profile} value={look} onChange={setLook} onContinue={handleLookChosen} />
              )}

              {/* ── Phase 7: Signature des lettres ── */}
              {phase === 7 && (
                <div className="w-full max-w-md mx-auto space-y-2 text-left">
                  <SignaturePad
                    onSave={(dataUrl) => void handleSignatureDone(dataUrl)}
                    onCancel={() => void handleSignatureDone(null)}
                  />
                  <p className="text-[11px] text-[#1A1918]/50 tracking-tight">
                    Trace ta signature au doigt ou à la souris. Elle ne sert qu&apos;au bas de tes lettres.
                  </p>
                </div>
              )}

              {/* ── Confirmation de l'adresse, avant d'ouvrir l'espace ── */}
              {phase === 5 && pendingAuthEmail && (
                <EmailSignIn
                  initialEmail={pendingAuthEmail}
                  autoSend
                  title="Confirme ton adresse : c'est elle qui protège ton espace."
                  onSignedIn={handleAuthConfirmed}
                />
              )}

              {/* ── Phase 5: Mandat de recherche — dernière étape ── */}
              {phase === 5 && !pendingAuthEmail && (
                <CriteriaStep
                  value={criteria}
                  onChange={setCriteria}
                  onSubmit={handleActivateAlice}
                  cityInput={cityInput}
                  setCityInput={setCityInput}
                  needsEmail={!profile.email}
                  emailInput={emailInput}
                  setEmailInput={setEmailInput}
                  isSubmitting={isActivating}
                  error={activationError}
                />
              )}

            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </main>
  );
}
