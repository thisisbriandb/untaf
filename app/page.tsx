"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { motion, useInView, AnimatePresence } from "framer-motion";
import {
  ArrowRight,
  Bot,
  BriefcaseBusiness,
  CheckCircle2,
  Clock,
  Eye,
  FileSearch,
  Ghost,
  Loader2,
  MousePointerClick,
  Rocket,
  ScanSearch,
  Send,
  Sparkles,
  Target,
  Timer,
  TrendingUp,
  Zap,
} from "lucide-react";
import { cn } from "@/lib/utils";

/* ───────────────── data ───────────────── */

const comparisonRows = [
  { label: "Temps moyen par candidature", classic: "45 min", agent: "< 2 min", icon: Clock },
  { label: "Offres du marché caché couvertes", classic: "~5%", agent: "85%+", icon: Ghost },
  { label: "Personnalisation CV & LM", classic: "Manuelle", agent: "IA contextuelle", icon: FileSearch },
  { label: "Suivi multi-plateforme", classic: "Tableur Excel", agent: "Temps réel", icon: Eye },
  { label: "Taux de réponse moyen", classic: "~8%", agent: "~24%", icon: TrendingUp },
];

const demoJobs = [
  { role: "Staff ML Engineer", company: "Mistral AI", score: 97, location: "Paris", remote: "Hybrid", stack: ["Python", "PyTorch", "K8s"] },
  { role: "Senior Backend", company: "Qonto", score: 94, location: "Paris", remote: "Remote", stack: ["Go", "PostgreSQL", "gRPC"] },
  { role: "Product Designer", company: "Doctolib", score: 91, location: "Paris", remote: "Hybrid", stack: ["Figma", "Design Systems"] },
  { role: "Frontend Lead", company: "Payfit", score: 88, location: "Paris", remote: "Remote", stack: ["React", "TypeScript", "Next.js"] },
  { role: "DevOps Engineer", company: "Alan", score: 85, location: "Paris", remote: "Remote", stack: ["Terraform", "AWS", "Docker"] },
];

const metrics = [
  { value: "2 847", label: "Offres qualifiées ce mois", icon: BriefcaseBusiness },
  { value: "128", label: "Sources ATS scrapées", icon: ScanSearch },
  { value: "94%", label: "Score de matching moyen", icon: Target },
  { value: "3×", label: "Plus de réponses vs classique", icon: TrendingUp },
];

const fadeUp = {
  hidden: { opacity: 0, y: 24 },
  visible: { opacity: 1, y: 0 },
};

/* ───────────────── components ───────────────── */

function SectionHeading({ badge, title, subtitle }: { badge: string; title: string; subtitle: string }) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: "-80px" });
  return (
    <motion.div
      ref={ref}
      initial="hidden"
      animate={inView ? "visible" : "hidden"}
      variants={fadeUp}
      transition={{ duration: 0.5 }}
      className="mx-auto max-w-2xl text-center"
    >
      <span className="inline-flex items-center gap-1.5 rounded-full border border-primary/20 bg-primary/5 px-3 py-1 font-mono text-xs font-semibold text-primary">
        {badge}
      </span>
      <h2 className="mt-4 text-3xl font-bold tracking-tight sm:text-4xl">
        {title}
      </h2>
      <p className="mt-3 text-base leading-relaxed text-muted-foreground">
        {subtitle}
      </p>
    </motion.div>
  );
}

function AnimatedCounter({ target }: { target: string }) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true });
  const [val, setVal] = useState("0");

  useEffect(() => {
    if (!inView) return;
    const num = parseInt(target.replace(/\s/g, ""));
    if (isNaN(num)) {
      setVal(target);
      return;
    }
    let cur = 0;
    const step = Math.max(1, Math.floor(num / 40));
    const id = setInterval(() => {
      cur = Math.min(cur + step, num);
      setVal(cur.toLocaleString("fr-FR"));
      if (cur >= num) clearInterval(id);
    }, 30);
    return () => clearInterval(id);
  }, [inView, target]);

  return <span ref={ref}>{val}</span>;
}

/* ───────── Simulator ───────── */

function Simulator() {
  const [skills, setSkills] = useState("Python, React, PostgreSQL");
  const [running, setRunning] = useState(false);
  const [results, setResults] = useState<typeof demoJobs | null>(null);

  const run = () => {
    setRunning(true);
    setResults(null);
    const tokens = skills.toLowerCase().split(",").map((s) => s.trim());
    setTimeout(() => {
      const scored = demoJobs
        .map((j) => {
          const overlap = j.stack.filter((t) =>
            tokens.some(
              (tk) =>
                t.toLowerCase().includes(tk) || tk.includes(t.toLowerCase()),
            ),
          );
          const bonus = overlap.length * 8;
          return {
            ...j,
            score: Math.min(99, j.score + bonus - (overlap.length === 0 ? 12 : 0)),
          };
        })
        .sort((a, b) => b.score - a.score);
      setResults(scored);
      setRunning(false);
    }, 1800);
  };

  return (
    <div className="mx-auto max-w-3xl">
      <div className="rounded-2xl border border-border bg-card p-6 shadow-sm">
        <div className="mb-4 flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10">
            <Bot className="h-4 w-4 text-primary" />
          </div>
          <p className="text-sm font-semibold">Agent de matching instantané</p>
        </div>
        <label className="mb-2 block text-sm font-medium text-muted-foreground">
          Vos compétences clés (séparées par des virgules)
        </label>
        <div className="flex gap-3">
          <input
            value={skills}
            onChange={(e) => setSkills(e.target.value)}
            placeholder="Ex: Python, React, AWS..."
            className="flex-1 rounded-lg border border-input bg-background px-4 py-2.5 text-sm transition focus:outline-none focus:ring-2 focus:ring-primary/40"
          />
          <button
            onClick={run}
            disabled={running || !skills.trim()}
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground transition hover:brightness-110 disabled:opacity-50"
          >
            {running ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Zap className="h-4 w-4" />
            )}
            {running ? "Analyse..." : "Matcher"}
          </button>
        </div>

        <AnimatePresence>
          {results && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.4 }}
              className="mt-5 divide-y divide-border overflow-hidden rounded-xl border border-border"
            >
              {results.slice(0, 4).map((job, i) => (
                <motion.div
                  key={job.company}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.1 }}
                  className="flex items-center justify-between gap-4 p-4 transition hover:bg-muted/50"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold">{job.role}</p>
                    <p className="text-xs text-muted-foreground">
                      {job.company} · {job.location} · {job.remote}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-3">
                    <div className="flex gap-1">
                      {job.stack.slice(0, 3).map((t) => (
                        <span
                          key={t}
                          className="rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground"
                        >
                          {t}
                        </span>
                      ))}
                    </div>
                    <span
                      className={cn(
                        "flex h-9 w-9 items-center justify-center rounded-lg font-mono text-xs font-bold text-white",
                        job.score >= 90
                          ? "bg-success"
                          : job.score >= 80
                            ? "bg-primary"
                            : "bg-warning",
                      )}
                    >
                      {job.score}
                    </span>
                  </div>
                </motion.div>
              ))}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

/* ───────────────── page ───────────────── */

export default function Home() {
  const router = useRouter();
  const [emailInput, setEmailInput] = useState("");

  const handleCtaSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (emailInput.trim()) {
      router.push(`/onboarding?email=${encodeURIComponent(emailInput.trim())}`);
    }
  };
  return (
    <main className="min-h-screen overflow-x-hidden">
      {/* ── Nav ── */}
      <nav className="sticky top-0 z-50 w-full border-b border-border/60 bg-background/80 backdrop-blur-lg">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary">
              <Sparkles className="h-4 w-4 text-primary-foreground" />
            </div>
            <span className="text-lg font-bold tracking-tight">UNTAF</span>
          </div>
          <div className="hidden items-center gap-8 text-sm font-medium text-muted-foreground md:flex">
            <a href="#comparatif" className="transition hover:text-foreground">Comparatif</a>
            <a href="#demo" className="transition hover:text-foreground">Démo</a>
            <a href="#metriques" className="transition hover:text-foreground">Résultats</a>
          </div>
          <a
            href="#cta"
            className="inline-flex h-10 items-center gap-2 rounded-lg bg-primary px-4 text-sm font-semibold text-primary-foreground transition hover:brightness-110"
          >
            Accès anticipé
            <ArrowRight className="h-4 w-4" />
          </a>
        </div>
      </nav>

      {/* ── 1. Hero — Outcome : on candidate à votre place ── */}
      <section className="relative overflow-hidden border-b border-border">
        <div className="mx-auto max-w-7xl px-6 pb-24 pt-24 text-center sm:pt-32">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
          >
            <span className="mb-6 inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/5 px-4 py-1.5 font-mono text-xs font-semibold text-primary">
              <Rocket className="h-3.5 w-3.5" />
              Beta privée — Places limitées
            </span>

            <h1 className="mx-auto max-w-4xl text-4xl font-extrabold leading-[1.1] tracking-tight sm:text-5xl lg:text-6xl">
              On candidate à votre place.
              <br />
              <span className="text-primary">Vous, vous passez des entretiens.</span>
            </h1>

            <p className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-muted-foreground">
              UNTAF découvre les offres invisibles, qualifie chaque poste par IA,
              génère un CV et une lettre sur-mesure, puis postule automatiquement.{" "}
              <strong className="text-foreground">
                Zéro effort manuel. 3× plus de réponses.
              </strong>
            </p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3, duration: 0.5 }}
            className="mt-10 flex flex-col items-center gap-4 sm:flex-row sm:justify-center"
          >
            <a
              href="#cta"
              className="inline-flex h-12 items-center gap-2 rounded-xl bg-primary px-8 text-sm font-bold text-primary-foreground shadow-md shadow-primary/15 transition hover:brightness-110"
            >
              <Send className="h-4 w-4" />
              Rejoindre la beta
            </a>
            <a
              href="#demo"
              className="inline-flex h-12 items-center gap-2 rounded-xl border border-border bg-card px-6 text-sm font-semibold transition hover:bg-muted"
            >
              <MousePointerClick className="h-4 w-4 text-primary" />
              Tester le matching
            </a>
          </motion.div>

          {/* Mini floating demo preview */}
          <motion.div
            initial={{ opacity: 0, y: 40 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.6, duration: 0.7 }}
            className="mx-auto mt-16 max-w-2xl"
          >
            <div className="rounded-2xl border border-border bg-card p-5 shadow-lg">
              <div className="mb-3 flex items-center gap-2">
                <span className="h-3 w-3 rounded-full bg-destructive/60" />
                <span className="h-3 w-3 rounded-full bg-warning/60" />
                <span className="h-3 w-3 rounded-full bg-success/60" />
                <span className="ml-2 font-mono text-[11px] text-muted-foreground">
                  agent-matching.untaf.io
                </span>
              </div>
              <div className="space-y-2.5">
                {demoJobs.slice(0, 3).map((j) => (
                  <div
                    key={j.company}
                    className="flex items-center justify-between rounded-lg bg-muted/50 px-4 py-3"
                  >
                    <div>
                      <p className="text-sm font-semibold">{j.role}</p>
                      <p className="text-xs text-muted-foreground">
                        {j.company} · {j.remote}
                      </p>
                    </div>
                    <span
                      className={cn(
                        "rounded-lg px-2.5 py-1 font-mono text-xs font-bold text-white",
                        j.score >= 95
                          ? "bg-success"
                          : j.score >= 90
                            ? "bg-primary"
                            : "bg-accent",
                      )}
                    >
                      {j.score}%
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* ── 2. Comparatif — Marché caché + couverture ── */}
      <section id="comparatif" className="bg-muted/30 py-20 sm:py-28">
        <div className="mx-auto max-w-7xl px-6">
          <SectionHeading
            badge="Comparatif"
            title="Pourquoi les candidatures classiques échouent"
            subtitle="85% des offres tech ne sont jamais publiées sur les grands agrégateurs. Nos agents scrapent directement les pages carrières et ATS des entreprises."
          />

          <div className="mx-auto mt-14 max-w-3xl">
            <div className="grid grid-cols-[1fr_auto_auto] items-center gap-x-6 gap-y-0 text-sm">
              <div />
              <span className="pb-3 text-center font-mono text-xs font-semibold text-muted-foreground">
                CLASSIQUE
              </span>
              <span className="pb-3 text-center font-mono text-xs font-semibold text-primary">
                UNTAF
              </span>

              {comparisonRows.map((row, i) => {
                const ref = useRef(null);
                const inView = useInView(ref, { once: true, margin: "-40px" });
                return (
                  <motion.div
                    ref={ref}
                    key={row.label}
                    className="col-span-3 grid grid-cols-subgrid items-center border-t border-border py-4"
                    initial={{ opacity: 0, x: -20 }}
                    animate={inView ? { opacity: 1, x: 0 } : {}}
                    transition={{ delay: i * 0.08, duration: 0.4 }}
                  >
                    <div className="flex items-center gap-3">
                      <row.icon className="h-4 w-4 shrink-0 text-muted-foreground" />
                      <span className="font-medium">{row.label}</span>
                    </div>
                    <span className="text-center text-muted-foreground line-through decoration-destructive/60">
                      {row.classic}
                    </span>
                    <span className="text-center font-semibold text-primary">
                      {row.agent}
                    </span>
                  </motion.div>
                );
              })}
            </div>
          </div>
        </div>
      </section>

      {/* ── 3. Simulateur — Matching CV chirurgical ── */}
      <section id="demo" className="border-t border-border py-20 sm:py-28">
        <div className="mx-auto max-w-7xl px-6">
          <SectionHeading
            badge="Démo Live"
            title="Ce n'est pas du spam. C'est chirurgical."
            subtitle="Entrez vos compétences et voyez instantanément les offres que nos agents sélectionneraient pour vous."
          />
          <div className="mt-14">
            <Simulator />
          </div>
        </div>
      </section>

      {/* ── 4. Métriques & Preuve Sociale ── */}
      <section id="metriques" className="border-t border-border bg-muted/30 py-20 sm:py-28">
        <div className="mx-auto max-w-7xl px-6">
          <SectionHeading
            badge="Résultats"
            title="Des chiffres, pas des promesses"
            subtitle="Voici ce que notre pipeline multi-agents produit chaque mois sur le marché tech français."
          />

          <div className="mx-auto mt-14 grid max-w-4xl gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {metrics.map((m, i) => {
              const ref = useRef(null);
              const inView = useInView(ref, { once: true, margin: "-60px" });
              return (
                <motion.div
                  ref={ref}
                  key={m.label}
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={inView ? { opacity: 1, scale: 1 } : {}}
                  transition={{ delay: i * 0.1, duration: 0.4 }}
                  className="flex flex-col items-center rounded-xl border border-border bg-card p-6 text-center shadow-sm"
                >
                  <m.icon className="mb-3 h-6 w-6 text-primary" />
                  <p className="text-3xl font-bold tracking-tight">
                    <AnimatedCounter target={m.value} />
                  </p>
                  <p className="mt-1 text-xs font-medium text-muted-foreground">
                    {m.label}
                  </p>
                </motion.div>
              );
            })}
          </div>

          {/* Testimonials */}
          <div className="mx-auto mt-16 max-w-3xl">
            <div className="flex flex-col gap-4 sm:flex-row">
              {[
                {
                  quote:
                    "J'ai reçu 3 entretiens en une semaine sans lever le petit doigt.",
                  name: "Marie L.",
                  role: "Data Engineer",
                },
                {
                  quote:
                    "Les offres du marché caché que je n'aurais jamais trouvées seul.",
                  name: "Thomas R.",
                  role: "Product Manager",
                },
              ].map((t) => (
                <div
                  key={t.name}
                  className="flex-1 rounded-xl border border-border bg-card p-5"
                >
                  <p className="text-sm italic leading-relaxed text-muted-foreground">
                    &ldquo;{t.quote}&rdquo;
                  </p>
                  <div className="mt-3 flex items-center gap-2">
                    <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
                      {t.name[0]}
                    </div>
                    <div>
                      <p className="text-sm font-semibold">{t.name}</p>
                      <p className="text-xs text-muted-foreground">{t.role}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ── 5. CTA Final ── */}
      <section id="cta" className="border-t border-border py-20 sm:py-28">
        <div className="mx-auto max-w-7xl px-6 text-center">
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            variants={fadeUp}
            transition={{ duration: 0.5 }}
          >
            <span className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/5 px-4 py-1.5 font-mono text-xs font-semibold text-primary">
              <Timer className="h-3.5 w-3.5" />
              Accès limité — Beta Q3 2026
            </span>
            <h2 className="mt-6 text-3xl font-bold tracking-tight sm:text-4xl lg:text-5xl">
              Arrêtez de chercher.
              <br />
              <span className="text-primary">Laissez vos agents trouver.</span>
            </h2>
            <p className="mx-auto mt-4 max-w-xl text-muted-foreground">
              Inscrivez-vous pour un accès anticipé. Pas de carte bancaire, pas
              d&apos;engagement — juste votre email.
            </p>

            <form
              onSubmit={handleCtaSubmit}
              className="mx-auto mt-8 flex max-w-md gap-3"
            >
              <input
                type="email"
                placeholder="votre@email.com"
                required
                value={emailInput}
                onChange={(e) => setEmailInput(e.target.value)}
                className="flex-1 rounded-xl border border-input bg-background px-4 py-3 text-sm transition focus:outline-none focus:ring-2 focus:ring-primary/40"
              />
              <button
                type="submit"
                className="inline-flex items-center gap-2 rounded-xl bg-primary px-6 py-3 text-sm font-bold text-primary-foreground shadow-md shadow-primary/15 transition hover:brightness-110"
              >
                <Send className="h-4 w-4" />
                Rejoindre
              </button>
            </form>

            <p className="mt-4 text-xs text-muted-foreground">
              Rejoint par{" "}
              <strong className="text-foreground">324 candidats</strong> cette
              semaine. Aucun spam.
            </p>
          </motion.div>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="border-t border-border bg-muted/30 py-10">
        <div className="mx-auto flex max-w-7xl flex-col items-center gap-4 px-6 text-center sm:flex-row sm:justify-between sm:text-left">
          <div className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary">
              <Sparkles className="h-3.5 w-3.5 text-primary-foreground" />
            </div>
            <span className="font-bold">UNTAF</span>
          </div>
          <p className="text-xs text-muted-foreground">
            © 2026 UNTAF · Pipeline multi-agents de recherche d&apos;emploi
          </p>
        </div>
      </footer>
    </main>
  );
}
