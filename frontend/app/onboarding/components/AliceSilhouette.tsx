"use client";

/**
 * L'identité d'Alice : une silhouette de face, en contre-jour — chignon,
 * lunettes, blazer. Elle te regarde : c'est une présence attentive, pas une
 * figure qui regarde ailleurs. Visage à peine éclairé, monture plus sombre
 * que la peau, épaules qui se fondent dans la lumière.
 *
 * Dessinée en vecteur (et non une photo) : nette à toutes les tailles,
 * animable, sans droit d'image. Repère : viewBox 0 0 100 120.
 */

export const TONES = {
  hair: "#0b0b0a",
  face: "#252422",
  ears: "#1c1b19",
  neck: "#1f1e1c",
  blazer: "#0c0c0b",
  shirt: "#1d1c1a",
  frame: "#050505",
} as const;

export const BLAZER_PATH =
  "M50 69.5 C45 69.5 42.5 68.5 40.5 69.6 C33 72.5 23 74 18 79 C13.5 85 11.5 102 10.5 120 " +
  "L89.5 120 C88.5 102 86.5 85 82 79 C77 74 67 72.5 59.5 69.6 C57.5 68.5 55 69.5 50 69.5 Z";
export const SHIRT_PATH =
  "M44 70 L50 92 L56 70 C54 70.6 52 70.8 50 70.8 C48 70.8 46 70.6 44 70 Z";
export const NECK_PATH =
  "M43.4 56 L43 67.5 C43.6 70 46.6 71 50 71 C53.4 71 56.4 70 57 67.5 L56.6 56 Z";
export const FACE_PATH =
  "M37.4 37 C37.6 31 42.6 28 50 28 C57.4 28 62.4 31 62.6 37 C62.8 44 62.2 49.6 59.8 54.6 " +
  "C57.4 59.4 54 61.8 50 62 C46 61.8 42.6 59.4 40.2 54.6 C37.8 49.6 37.2 44 37.4 37 Z";

/** Tête : chignon, chevelure, oreilles, visage. */
export function AliceHead() {
  return (
    <>
      <circle cx="50" cy="16.4" r="6.6" fill={TONES.hair} />
      <ellipse cx="50" cy="38" rx="15.2" ry="17.4" fill={TONES.hair} />
      <ellipse cx="35.6" cy="45.6" rx="2.4" ry="4.4" fill={TONES.ears} />
      <ellipse cx="64.4" cy="45.6" rx="2.4" ry="4.4" fill={TONES.ears} />
      <path d={FACE_PATH} fill={TONES.face} />
    </>
  );
}

/** La monture : plus sombre que le visage, c'est elle qui donne le regard. */
export function AliceGlasses() {
  return (
    <>
      <g fill="rgba(5,5,5,0.45)" stroke={TONES.frame} strokeWidth="1.7" strokeLinejoin="round">
        <rect x="37.8" y="41.4" width="10.4" height="7.2" rx="2" />
        <rect x="51.8" y="41.4" width="10.4" height="7.2" rx="2" />
      </g>
      <path
        d="M48.2 43.6 Q50 42.7 51.8 43.6 M37.8 42.6 L35.4 42.9 M62.2 42.6 L64.6 42.9"
        stroke={TONES.frame}
        strokeWidth="1.4"
        fill="none"
      />
    </>
  );
}

/** Vignette ronde (barre latérale) : visage et épaules, nets. */
export function AliceAvatar({ size = 32, className = "" }: { size?: number; className?: string }) {
  return (
    <span
      className={`inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full bg-white ring-1 ring-[#1A1918]/[0.08] ${className}`}
      style={{ width: size, height: size }}
      aria-hidden
    >
      <svg viewBox="22 4 56 56" width={size} height={size}>
        <path d={BLAZER_PATH} fill={TONES.blazer} />
        <path d={SHIRT_PATH} fill={TONES.shirt} />
        <path d={NECK_PATH} fill={TONES.neck} />
        <AliceHead />
        <AliceGlasses />
      </svg>
    </span>
  );
}
