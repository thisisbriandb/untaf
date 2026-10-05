"use client";

import { useEffect, useState } from "react";

/**
 * Raconte une attente longue, étape par étape, au lieu d'un sablier muet.
 * Les étapes décrivent le travail en cours (dans l'ordre où il se fait) ;
 * la dernière reste affichée tant que le résultat n'est pas arrivé.
 */
export function useNarration(active: boolean, steps: string[], everyMs = 4000): string {
  const [index, setIndex] = useState(0);
  useEffect(() => {
    if (!active) return;
    const id = setInterval(() => setIndex((i) => Math.min(i + 1, steps.length - 1)), everyMs);
    return () => {
      clearInterval(id);
      setIndex(0);
    };
  }, [active, steps.length, everyMs]);
  return steps[active ? index : 0];
}
