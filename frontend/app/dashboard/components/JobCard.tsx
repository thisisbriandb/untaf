"use client";

import { motion } from "framer-motion";
import { APPLY_MODE_LABELS, type JobCardData } from "@/lib/alice-client";
import { useAlice } from "../alice-context";
import { companyOf } from "@/lib/company";

const CONTRACT_LABELS: Record<string, string> = {
  cdi: "CDI",
  cdd: "CDD",
  freelance: "Freelance",
  stage: "Stage",
  alternance: "Alternance",
  unknown: "",
};

const REMOTE_LABELS: Record<string, string> = {
  remote: "Remote",
  hybrid: "Hybride",
  onsite: "Présentiel",
  unknown: "",
};

export function JobCard({ job }: { job: JobCardData }) {
  const { openCanvas, canvas } = useAlice();
  const contract = CONTRACT_LABELS[job.contract_type] || "";
  const remote = REMOTE_LABELS[job.remote_policy] || "";
  const tags = [contract, remote].filter(Boolean).join(" · ");
  const isOpen = canvas?.mode === "job_detail" && canvas.job.id === job.id;

  return (
    <motion.button
      type="button"
      onClick={() => openCanvas({ mode: "job_detail", job })}
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      aria-label={`Ouvrir le détail de l'offre ${job.title}`}
      className={`block w-full text-left p-4 rounded-xl border bg-white transition-colors cursor-pointer ${
        isOpen
          ? "border-[#006045]/45 bg-[#006045]/4"
          : "border-[#1A1918]/8 hover:border-[#006045]/30"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-0.5 min-w-0">
          <p className="text-sm font-normal text-[#1A1918] tracking-tight truncate">
            {job.title}
          </p>
          <p className="text-xs font-normal text-[#1A1918]/55 tracking-tight truncate">
            {[companyOf(job.company_name) ?? "Employeur non communiqué", job.location].filter(Boolean).join(" · ")}
          </p>
          {(tags || job.apply_mode) && (
            <p className="text-[11px] font-normal text-[#1A1918]/60 tracking-tight">
              {tags}
              {job.apply_mode && (
                <span className={job.apply_mode === "auto" ? "text-[#006045]" : ""}>
                  {tags ? " · " : ""}
                  {APPLY_MODE_LABELS[job.apply_mode]}
                </span>
              )}
            </p>
          )}
        </div>
        <span className="shrink-0 text-xs font-medium text-[#006045] tabular-nums">
          {job.match_score}%
        </span>
      </div>
    </motion.button>
  );
}

export function JobCardList({ jobs }: { jobs: JobCardData[] }) {
  if (!jobs.length) {
    return (
      <p className="text-sm font-light text-[#1A1918]/50 tracking-tight py-2">
        Aucune offre trouvée pour l&apos;instant.
      </p>
    );
  }

  return (
    <div className="space-y-2 w-full py-1">
      {jobs.map((job) => (
        <JobCard key={job.id} job={job} />
      ))}
    </div>
  );
}
