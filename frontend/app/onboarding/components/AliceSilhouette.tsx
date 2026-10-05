"use client";

/**
 * L'identité d'Alice : un profil en contre-jour — chignon, lunettes, le
 * visage tourné vers ce qui vient. Monochrome, net sur le visage, de plus en
 * plus flou vers les épaules, comme une silhouette derrière un verre dépoli.
 *
 * Dessinée en vecteur (et non une photo) : elle reste nette à toutes les
 * tailles, s'anime, et ne dépend d'aucun droit d'image.
 */

export const ALICE_INK = "#161615";

/** Tête, cou et épaules, d'un seul tenant (viewBox 0 0 100 120). */
export const SILHOUETTE_PATH =
  "M40 62 C34 56 31 45 33.6 35 C36 25.5 46 20.5 55.5 22 C63 23.5 67.2 30.5 67.6 37.5 " +
  "L68 42 C68 43.2 67.5 44 67.5 44.6 C69 47.2 71.4 50.4 73 52.6 C73.4 53.5 72.4 54.2 69.8 54.5 " +
  "C69.3 55.1 69.2 55.8 69.3 56.3 C70 56.9 70.6 57.6 70.2 58.3 C69.7 58.8 68.8 59 68.8 59.3 " +
  "C69.5 59.8 69.8 60.5 69.4 61.2 C68.8 61.8 67.8 62 67.6 62.4 C67.8 62.8 68.2 63.8 68 64.8 " +
  "C67.4 67 64.4 68.5 60.4 68.7 C58.6 68.9 57.4 69.6 57.2 71.4 C57 75 57.4 79.5 58.6 83.5 " +
  "C61 90 68 98 74 106 C77 110.5 79 115 80 120 L16 120 C17 111 21 103 27 97 " +
  "C33 91 38.5 87 41.6 81 C43 77 42 69 40 62 Z";

/** Le chignon. */
export const BUN = { cx: 37.5, cy: 21, r: 7.6 };

/** La monture : seule la lumière qui la traverse la révèle. */
export const GLASSES_PATH = "M64.2 43.2 L71 42.9 L71.3 47.9 C69.3 48.8 66.3 48.8 64.4 48 Z";

/** Vignette ronde (barre latérale, onglet) : la tête seule, nette. */
export function AliceAvatar({ size = 32, className = "" }: { size?: number; className?: string }) {
  return (
    <span
      className={`inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full bg-white ring-1 ring-[#1A1918]/[0.08] ${className}`}
      style={{ width: size, height: size }}
      aria-hidden
    >
      <svg viewBox="21 9 62 62" width={size} height={size}>
        <g fill={ALICE_INK}>
          <circle {...BUN} />
          <path d={SILHOUETTE_PATH} />
        </g>
        <path d={GLASSES_PATH} fill="none" stroke={ALICE_INK} strokeWidth="1.2" />
      </svg>
    </span>
  );
}
