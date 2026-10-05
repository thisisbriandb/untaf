"use client";

/**
 * L'identité d'Alice : une tête de face, en contre-jour — chignon,
 * lunettes aux verres clairs. Elle te regarde : une présence attentive,
 * pas une figure qui regarde ailleurs. Visage à peine éclairé, monture plus sombre
 * que la peau, verres qui laissent passer la lumière.
 *
 * Dessinée en vecteur (et non une photo) : nette à toutes les tailles,
 * animable, sans droit d'image. Repère : viewBox 0 0 100 120.
 */

export const TONES = {
  hair: "#0b0b0a",
  face: "#2c2b28",
  ears: "#1c1b19",
  frame: "#050505",
} as const;

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

/**
 * La monture, nette, et des verres clairs qui accrochent la lumière : c'est
 * ce qui donne le regard à une silhouette sans traits.
 */
export function AliceGlasses() {
  return (
    <>
      <g fill="#D9D8D3" fillOpacity="0.28" stroke={TONES.frame} strokeWidth="1.5" strokeLinejoin="round">
        <rect x="37.8" y="41.4" width="10.4" height="7.2" rx="2" />
        <rect x="51.8" y="41.4" width="10.4" height="7.2" rx="2" />
      </g>
      {/* Reflets */}
      <path
        d="M40 47 L44.2 42.6 M54 47 L58.2 42.6"
        stroke="#fff"
        strokeOpacity="0.45"
        strokeWidth="0.9"
        strokeLinecap="round"
      />
      <path
        d="M48.2 43.6 Q50 42.7 51.8 43.6 M37.8 42.6 L35.4 42.9 M62.2 42.6 L64.6 42.9"
        stroke={TONES.frame}
        strokeWidth="1.4"
        fill="none"
      />
    </>
  );
}

/** Cadrage sur la tête seule (chignon compris). */
export const HEAD_VIEWBOX = "18 5 64 64";

/** Vignette ronde (barre latérale) : la tête seule, nette. */
export function AliceAvatar({ size = 32, className = "" }: { size?: number; className?: string }) {
  return (
    <span
      className={`inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full bg-[#ECF4F0] ring-1 ring-[#006045]/15 ${className}`}
      style={{ width: size, height: size }}
      aria-hidden
    >
      <svg viewBox="20 7 60 60" width={size} height={size}>
        <AliceHead />
        <AliceGlasses />
      </svg>
    </span>
  );
}
