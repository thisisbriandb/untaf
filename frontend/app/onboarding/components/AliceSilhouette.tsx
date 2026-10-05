"use client";

/**
 * Vignette d'Alice : ses deux yeux, comme sa présence animée, en petit.
 * Utilisée là où l'animation complète prendrait trop de place (barre
 * latérale, fil de conversation).
 */
export function AliceAvatar({ size = 32, className = "" }: { size?: number; className?: string }) {
  const eye = Math.max(5, Math.round(size * 0.2));
  return (
    <span
      className={`inline-flex shrink-0 items-center justify-center gap-[3px] rounded-full bg-[#ECF4F0] ring-1 ring-[#006045]/15 ${className}`}
      style={{ width: size, height: size, gap: Math.round(size * 0.12) }}
      aria-hidden
    >
      {[0, 1].map((i) => (
        <span
          key={i}
          className="rounded-full border-[1.5px] border-[#006045] shadow-[0_0_6px_rgba(0,96,69,0.35)]"
          style={{ width: eye, height: eye }}
        />
      ))}
    </span>
  );
}
