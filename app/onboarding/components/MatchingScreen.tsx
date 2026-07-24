"use client";

import { motion } from "framer-motion";
import { Loader2 } from "lucide-react";

interface MatchingScreenProps {
  matchingProgress: number;
  matchingStatus: string;
}

export function MatchingScreen({
  matchingProgress,
  matchingStatus,
}: MatchingScreenProps) {
  return (
    <motion.div
      key="matching"
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className="flex flex-col items-center justify-center py-20 text-center"
    >
      <div className="relative flex h-24 w-24 items-center justify-center">
        <Loader2 className="h-20 w-20 animate-spin text-primary opacity-20" />
        <span className="absolute font-mono text-xl font-bold text-primary">
          {matchingProgress}%
        </span>
      </div>
      <h3 className="mt-6 text-lg font-semibold text-foreground">
        Génération du CV et recherche d&apos;opportunités
      </h3>
      <p className="mt-2 font-mono text-xs text-muted-foreground min-h-[16px]">
        {matchingStatus}
      </p>
    </motion.div>
  );
}
