"use client";

import { motion } from "framer-motion";
import type { JobCardData } from "@/lib/alice-client";

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
  const contract = CONTRACT_LABELS[job.contract_type] || "";
  const remote = REMOTE_LABELS[job.remote_policy] || "";
  const tags = [contract, remote].filter(Boolean).join(" · ");

  return (
    <motion.a
      href={job.source_url}
      target="_blank"
      rel="noopener noreferrer"
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      className="block p-4 rounded-xl border border-[#1A1918]/8 hover:border-[#006045]/30 bg-white transition-colors group cursor-pointer"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-0.5 min-w-0">
          <p className="text-sm font-normal text-[#1A1918] tracking-tight truncate">
            {job.title}
          </p>
          <p className="text-xs font-light text-[#1A1918]/55 tracking-tight truncate">
            {job.company_name} · {job.location}
          </p>
          {tags && (
            <p className="text-[11px] font-light text-[#1A1918]/45 tracking-tight">
              {tags}
            </p>
          )}
        </div>
        <span className="shrink-0 text-xs font-medium text-[#006045] tabular-nums">
          {job.match_score}%
        </span>
      </div>
    </motion.a>
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
