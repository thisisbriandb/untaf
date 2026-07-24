"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  ArrowUpRight,
  BriefcaseBusiness,
  CheckCircle2,
  CircleAlert,
  DatabaseZap,
  Filter,
  Send,
  Sparkles,
  LogOut,
  Loader2,
  ExternalLink,
  MapPin,
  Clock,
  Briefcase,
  AlertCircle,
  Globe
} from "lucide-react";
import { cn } from "@/lib/utils";

interface Company {
  name: string;
  domain: string;
}

interface JobPosting {
  id: string;
  title: string;
  location: string | null;
  remote_policy: string;
  contract_type: string;
  experience_range: string | null;
  salary_range: string | null;
  tech_stack: string[] | null;
  source_url: string;
  apply_url: string | null;
  company_name: string | null;
  company_domain: string | null;
}

interface Application {
  id: string;
  candidate_id: string;
  job_posting_id: string;
  status: string;
  match_score: number;
  created_at: string;
  job_posting: JobPosting | null;
}

interface Candidate {
  id: string;
  full_name: string;
  email: string;
  skills: string[];
}

export default function DashboardPage() {
  const router = useRouter();
  
  // Loading & Data States
  const [candidateId, setCandidateId] = useState<string | null>(null);
  const [candidate, setCandidate] = useState<Candidate | null>(null);
  const [applications, setApplications] = useState<Application[]>([]);
  const [totalJobsCount, setTotalJobsCount] = useState(209); // Fallback static count
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState("");

  // Filters State
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [minScoreFilter, setMinScoreFilter] = useState<number>(60);
  const [updatingAppId, setUpdatingAppId] = useState<string | null>(null);

  // Authenticate / load candidate ID on mount
  useEffect(() => {
    const id = localStorage.getItem("candidate_id");
    if (!id) {
      router.push("/onboarding");
      return;
    }
    setCandidateId(id);
  }, [router]);

  // Fetch candidate profile, matches, and job stats
  useEffect(() => {
    if (!candidateId) return;

    const fetchData = async () => {
      setLoading(true);
      setErrorMsg("");
      try {
        // 1. Fetch Candidate Profile
        const candidateRes = await fetch(`http://localhost:8010/api/candidates/${candidateId}`);
        if (!candidateRes.ok) {
          throw new Error("Impossible de charger le profil candidat. Veuillez vous réinscrire.");
        }
        const candidateData = await candidateRes.json();
        setCandidate(candidateData);

        // 2. Fetch Matched Applications
        const appsRes = await fetch(`http://localhost:8010/api/applications/?candidate_id=${candidateId}`);
        if (appsRes.ok) {
          const appsData = await appsRes.json();
          setApplications(appsData);
        }

        // 3. Fetch Job Stats
        const statsRes = await fetch("http://localhost:8010/api/jobs/stats");
        if (statsRes.ok) {
          const statsData = await statsRes.json();
          setTotalJobsCount(statsData.total_active || 209);
        }
      } catch (e: any) {
        setErrorMsg(e.message || "Une erreur réseau est survenue lors de la récupération des données.");
        // Clear broken session
        localStorage.removeItem("candidate_id");
        setTimeout(() => router.push("/onboarding"), 2500);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [candidateId, router]);

  // Action: Logout / Reset Onboarding
  const handleLogout = () => {
    localStorage.removeItem("candidate_id");
    router.push("/");
  };

  // Action: Update Application Status
  const handleUpdateStatus = async (appId: string, currentStatus: string) => {
    setUpdatingAppId(appId);
    // Cycle status: matched/pending -> applied -> interview -> matched
    let nextStatus = "applied";
    if (currentStatus === "applied") {
      nextStatus = "interview";
    } else if (currentStatus === "interview") {
      nextStatus = "matched";
    }

    try {
      const response = await fetch(`http://localhost:8010/api/applications/${appId}/status`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ status: nextStatus })
      });

      if (response.ok) {
        const updated = await response.json();
        // Update local state
        setApplications((prev) =>
          prev.map((app) => (app.id === appId ? { ...app, status: updated.status } : app))
        );
      } else {
        alert("Impossible de modifier le statut de la candidature.");
      }
    } catch (e) {
      alert("Erreur réseau lors de la mise à jour.");
    } finally {
      setUpdatingAppId(null);
    }
  };

  // Stats derivation
  const activeMatchesCount = applications.filter(app => app.status === "matched" || app.status === "pending").length;
  const appliedCount = applications.filter(app => app.status === "applied" || app.status === "interview" || app.status === "offer").length;

  const stats = [
    {
      label: "Matchs recommandés",
      value: activeMatchesCount.toString(),
      detail: "En attente de votre validation",
      icon: Sparkles,
    },
    {
      label: "Candidatures actives",
      value: appliedCount.toString(),
      detail: "Suivi automatisé en cours",
      icon: Send,
    },
    {
      label: "Offres en base",
      value: totalJobsCount.toString(),
      detail: "Scrapées depuis Greenhouse/Lever",
      icon: DatabaseZap,
    },
  ];

  // Filtering list
  const filteredApps = applications.filter((app) => {
    // Score filter
    if (app.match_score < minScoreFilter) return false;
    
    // Status filter
    if (statusFilter === "all") return true;
    if (statusFilter === "matched") return app.status === "matched" || app.status === "pending";
    if (statusFilter === "applied") return app.status === "applied";
    if (statusFilter === "interview") return app.status === "interview" || app.status === "offer";
    return true;
  });

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-50 dark:bg-slate-950">
        <div className="flex flex-col items-center gap-4 text-center">
          <Loader2 className="h-10 w-10 animate-spin text-primary" />
          <h2 className="text-lg font-semibold">Analyse de vos opportunités...</h2>
          <p className="text-sm text-muted-foreground max-w-xs">
            Nous récupérons vos matchs en direct de la base de données.
          </p>
        </div>
      </main>
    );
  }

  if (errorMsg) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-50 dark:bg-slate-950 p-6">
        <div className="flex flex-col items-center gap-4 text-center max-w-md rounded-2xl border border-destructive/20 bg-card p-8 shadow-md">
          <AlertCircle className="h-12 w-12 text-destructive" />
          <h2 className="text-xl font-bold">Erreur de chargement</h2>
          <p className="text-sm text-muted-foreground">{errorMsg}</p>
          <p className="text-xs text-muted-foreground animate-pulse">
            Redirection vers l&apos;onboarding...
          </p>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-50">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-8 px-6 py-6 sm:px-8 lg:px-10">
        {/* Header section */}
        <header className="flex flex-col gap-4 border-b border-border pb-6 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="font-mono text-xs font-semibold uppercase text-primary">
              Tableau de bord personnel
            </p>
            <h1 className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl">
              Bonjour, {candidate?.full_name || "Candidat"}
            </h1>
            <p className="text-sm text-muted-foreground mt-1">
              Voici les offres du marché caché qualifiées pour votre profil.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => router.push("/onboarding")}
              className="inline-flex h-10 items-center gap-2 rounded-xl border border-border bg-card px-4 text-sm font-semibold transition hover:bg-muted"
            >
              <BriefcaseBusiness size={16} />
              Re-configurer
            </button>
            <button
              onClick={handleLogout}
              className="inline-flex h-10 items-center gap-2 rounded-xl bg-destructive/10 text-destructive px-4 text-sm font-semibold transition hover:bg-destructive/15"
            >
              <LogOut size={16} />
              Quitter
            </button>
          </div>
        </header>

        {/* Stats Grid */}
        <section className="grid gap-4 md:grid-cols-3">
          {stats.map((stat, index) => (
            <motion.article
              key={stat.label}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.08, duration: 0.35 }}
              className="rounded-2xl border border-border bg-card p-5 shadow-sm"
            >
              <div className="flex items-center justify-between gap-3">
                <span className="text-sm font-semibold text-muted-foreground">
                  {stat.label}
                </span>
                <stat.icon className="text-primary" size={18} />
              </div>
              <p className="mt-3 text-3xl font-bold tracking-tight">{stat.value}</p>
              <p className="mt-1 font-mono text-xs text-muted-foreground">
                {stat.detail}
              </p>
            </motion.article>
          ))}
        </section>

        {/* Filters Controls */}
        <section className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-border bg-card p-4 shadow-sm">
          <div className="flex flex-wrap items-center gap-3">
            <span className="inline-flex items-center gap-1.5 text-xs font-bold text-muted-foreground uppercase tracking-wider">
              <Filter size={13} />
              Filtrer par :
            </span>
            {/* Status pills */}
            <div className="flex gap-1">
              {[
                { label: "Tous", value: "all" },
                { label: "À valider", value: "matched" },
                { label: "Candidatés", value: "applied" },
                { label: "Entretiens", value: "interview" }
              ].map((pill) => (
                <button
                  key={pill.value}
                  onClick={() => setStatusFilter(pill.value)}
                  className={cn(
                    "rounded-lg px-3 py-1 text-xs font-semibold transition",
                    statusFilter === pill.value
                      ? "bg-primary/10 text-primary border border-primary/20"
                      : "text-muted-foreground hover:bg-muted"
                  )}
                >
                  {pill.label}
                </button>
              ))}
            </div>
          </div>

          {/* Min Score Range */}
          <div className="flex items-center gap-3">
            <span className="text-xs font-semibold text-muted-foreground">
              Score min : <strong className="text-foreground">{minScoreFilter}%</strong>
            </span>
            <input
              type="range"
              min="60"
              max="95"
              step="5"
              value={minScoreFilter}
              onChange={(e) => setMinScoreFilter(parseInt(e.target.value))}
              className="accent-primary h-1.5 w-32 bg-muted rounded-lg appearance-none cursor-pointer"
            />
          </div>
        </section>

        {/* Pipeline / Application List */}
        <section className="rounded-2xl border border-border bg-card text-card-foreground shadow-sm overflow-hidden">
          <div className="border-b border-border p-5">
            <h2 className="text-lg font-bold">Pipeline prioritaire de candidatures</h2>
            <p className="text-sm text-muted-foreground">
              Calculé à partir de vos compétences : <span className="font-mono text-xs font-semibold text-primary">{candidate?.skills.join(", ")}</span>
            </p>
          </div>

          <div className="divide-y divide-border">
            <AnimatePresence mode="popLayout">
              {filteredApps.length > 0 ? (
                filteredApps.map((app, index) => {
                  const job = app.job_posting;
                  if (!job) return null;
                  
                  return (
                    <motion.div
                      key={app.id}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, scale: 0.98 }}
                      transition={{ duration: 0.25 }}
                      className="p-5 hover:bg-muted/30 transition-colors"
                    >
                      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                        {/* Job Details */}
                        <div className="min-w-0 space-y-1.5">
                          <div className="flex flex-wrap items-center gap-2">
                            <h3 className="font-bold text-base truncate pr-2">{job.title}</h3>
                            <span
                              className={cn(
                                "inline-flex items-center gap-1.5 rounded-lg px-2.5 py-0.5 font-mono text-[10px] font-bold uppercase",
                                app.match_score >= 85
                                  ? "bg-success/10 text-success border border-success/20"
                                  : app.match_score >= 75
                                    ? "bg-primary/10 text-primary border border-primary/20"
                                    : "bg-warning/10 text-warning border border-warning/20"
                              )}
                            >
                              Match {app.match_score}%
                            </span>
                          </div>
                          
                          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
                            <span className="font-semibold text-foreground flex items-center gap-1">
                              {job.company_name || "Entreprise"}
                              {job.company_domain && (
                                <a
                                  href={`https://${job.company_domain}`}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-muted-foreground hover:text-primary transition"
                                >
                                  <ExternalLink size={12} />
                                </a>
                              )}
                            </span>
                            <span className="flex items-center gap-1">
                              <MapPin size={13} />
                              {job.location || "Non spécifié"}
                            </span>
                            <span className="flex items-center gap-1 capitalize">
                              <Globe size={13} />
                              {job.remote_policy}
                            </span>
                            <span className="flex items-center gap-1 uppercase">
                              <Briefcase size={13} />
                              {job.contract_type}
                            </span>
                          </div>

                          {/* Tech stack */}
                          {job.tech_stack && job.tech_stack.length > 0 && (
                            <div className="flex flex-wrap gap-1 mt-2">
                              {job.tech_stack.map((tech) => (
                                <span
                                  key={tech}
                                  className="rounded bg-muted px-2 py-0.5 font-mono text-[10px] text-muted-foreground"
                                >
                                  {tech}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>

                        {/* Actions & Status */}
                        <div className="flex shrink-0 items-center gap-3">
                          <span
                            className={cn(
                              "inline-flex h-8 items-center gap-1.5 rounded-lg px-2.5 font-mono text-xs font-bold capitalize",
                              app.status === "matched" && "bg-primary/10 text-primary border border-primary/20",
                              app.status === "pending" && "bg-warning/10 text-warning border border-warning/20",
                              app.status === "applied" && "bg-success/10 text-success border border-success/20",
                              app.status === "interview" && "bg-accent/15 text-accent-foreground border border-accent/20"
                            )}
                          >
                            {app.status === "applied" || app.status === "interview" ? (
                              <CheckCircle2 size={13} />
                            ) : (
                              <CircleAlert size={13} />
                            )}
                            {app.status === "matched" ? "À valider" : app.status === "pending" ? "Intéressant" : app.status === "applied" ? "Candidaté" : app.status}
                          </span>

                          {/* Action button */}
                          <div className="flex gap-2">
                            <button
                              onClick={() => handleUpdateStatus(app.id, app.status)}
                              disabled={updatingAppId === app.id}
                              className="inline-flex h-9 items-center justify-center gap-1.5 rounded-lg border border-border bg-card px-3 text-xs font-semibold text-foreground transition hover:bg-muted disabled:opacity-50"
                            >
                              {updatingAppId === app.id ? (
                                <Loader2 size={13} className="animate-spin" />
                              ) : app.status === "matched" || app.status === "pending" ? (
                                "Postuler"
                              ) : app.status === "applied" ? (
                                "En entretien"
                              ) : (
                                "Réinitialiser"
                              )}
                            </button>
                            <a
                              href={job.source_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-border bg-card text-muted-foreground hover:bg-muted hover:text-foreground"
                            >
                              <ArrowUpRight size={15} />
                            </a>
                          </div>
                        </div>
                      </div>
                    </motion.div>
                  );
                })
              ) : (
                <div className="flex flex-col items-center justify-center p-12 text-center text-muted-foreground">
                  <DatabaseZap className="h-10 w-10 text-muted-foreground opacity-50 mb-3" />
                  <p className="text-sm font-semibold">Aucune offre ne correspond à vos critères.</p>
                  <p className="text-xs">Essayez d&apos;ajuster vos filtres de score ou modifiez vos compétences dans le profil.</p>
                </div>
              )}
            </AnimatePresence>
          </div>
        </section>
      </div>
    </main>
  );
}
