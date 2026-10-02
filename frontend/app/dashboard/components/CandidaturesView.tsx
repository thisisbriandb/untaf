"use client";

import { motion } from "framer-motion";
import { FolderDown } from "lucide-react";
import { packUrl } from "@/lib/tailor-client";

interface JobPosting {
  id: string;
  title: string;
  location: string | null;
  company_name: string | null;
}

interface Application {
  id: string;
  job_posting_id: string;
  status: string;
  match_score: number;
  job_posting: JobPosting | null;
}

interface CandidaturesViewProps {
  candidateId: string | null;
  applications: Application[];
  updatingAppId: string | null;
  onUpdateStatus: (appId: string, currentStatus: string) => void;
}

export function CandidaturesView({
  candidateId,
  applications,
  updatingAppId,
  onUpdateStatus,
}: CandidaturesViewProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.35 }}
      className="w-full max-w-2xl text-left space-y-6 py-4"
    >
      <div>
        <h2 className="text-xl font-normal text-[#1A1918]">Candidatures &amp; Matchs</h2>
        <p className="text-xs text-[#1A1918]/50 mt-0.5">
          Opportunités détectées et postulées par Alice pour toi.
        </p>
      </div>

      {applications.length === 0 ? (
        <div className="text-left py-10 space-y-2">
          <p className="text-sm text-[#1A1918]/60">Aucune candidature enregistrée pour le moment.</p>
          <p className="text-xs text-[#1A1918]/40">Alice cherche de nouvelles offres en continu.</p>
        </div>
      ) : (
        <div className="divide-y divide-[#1A1918]/8 border-t border-b border-[#1A1918]/10">
          {applications.map((app) => {
            const job = app.job_posting;
            const statusLabel =
              app.status === "matched"
                ? "Match détecté"
                : app.status === "applied"
                ? "Postulé"
                : app.status === "interview"
                ? "Entretien"
                : app.status;

            return (
              <div key={app.id} className="py-4 flex flex-col gap-2">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h3 className="text-base font-medium text-[#1A1918]">
                      {job?.title || "Offre développeur"}
                    </h3>
                    <p className="text-xs text-[#1A1918]/60 mt-0.5">
                      {job?.company_name || "Entreprise confidentielle"} • {job?.location || "Paris"}
                    </p>
                  </div>
                  <span className="font-mono text-xs font-semibold px-2 py-1 rounded-md bg-[#006045]/10 text-[#006045]">
                    {app.match_score || 88}% match
                  </span>
                </div>

                <div className="flex items-center justify-between pt-1">
                  <span className="text-xs font-medium text-[#1A1918]/50">
                    Statut : <strong className="text-[#006045]">{statusLabel}</strong>
                  </span>
                  <div className="flex items-center gap-4">
                    {candidateId && (
                      <a
                        href={packUrl(candidateId, app.job_posting_id)}
                        className="flex items-center gap-1 text-xs text-[#006045] hover:underline font-medium"
                      >
                        <FolderDown className="w-3.5 h-3.5 stroke-[1.6]" />
                        Pack
                      </a>
                    )}
                    <button
                      type="button"
                      onClick={() => onUpdateStatus(app.id, app.status)}
                      disabled={updatingAppId === app.id}
                      className="text-xs text-[#006045] hover:underline font-medium cursor-pointer"
                    >
                      Changer statut
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </motion.div>
  );
}
