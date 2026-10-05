"use client";

import React, { useEffect, useId } from "react";
import { motion, useMotionValue, useSpring, useTransform } from "framer-motion";
import { ALICE_INK, BUN, GLASSES_PATH, SILHOUETTE_PATH } from "./AliceSilhouette";

export type AliceEmotion =
  | "idle"
  | "listening"
  | "thinking"
  | "reading"
  | "writing"
  | "searching"
  | "happy"
  | "working";

interface AlicePresenceProps {
  emotion: AliceEmotion;
  className?: string;
  size?: "sm" | "md" | "lg";
}

const HEIGHT = { sm: 34, md: 64, lg: 104 } as const;

/**
 * Alice, présente : sa silhouette en contre-jour, qui respire.
 *
 * Les états se lisent dans la lumière plus que dans le geste — nette et
 * tournée vers toi quand elle écoute, la tête qui s'incline quand elle lit ou
 * écrit, le contour qui se trouble et le halo qui pulse quand elle travaille.
 * Elle suit très légèrement le pointeur, sans jamais quitter son profil.
 */
export function AlicePresence({ emotion, className = "", size = "lg" }: AlicePresenceProps) {
  const uid = useId().replace(/[^a-zA-Z0-9]/g, "");
  const mouseX = useMotionValue(0);
  const gaze = useSpring(mouseX, { damping: 30, stiffness: 120 });

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      const cx = window.innerWidth / 2;
      mouseX.set(Math.max(-1, Math.min(1, (e.clientX - cx) / cx)));
    };
    window.addEventListener("mousemove", onMove);
    return () => window.removeEventListener("mousemove", onMove);
  }, [mouseX]);

  const busy = emotion === "working" || emotion === "searching" || emotion === "thinking";
  const tilt =
    emotion === "reading" || emotion === "writing" ? 2.2 : emotion === "thinking" ? -1.4 : 0;
  // Le regard suit le pointeur, à peine : ±1,2° autour de l'inclinaison de l'état.
  const rotate = useTransform(gaze, (g) => tilt + g * 1.2);

  const sharp = emotion === "listening" || emotion === "happy" ? 0.55 : 0.85;
  const height = HEIGHT[size];
  const width = Math.round((height * 100) / 120);
  const id = (name: string) => `${name}-${uid}`;

  return (
    <div className={`flex flex-col items-center justify-center select-none ${className}`}>
      <svg
        viewBox="0 0 100 120"
        width={width}
        height={height}
        role="img"
        aria-label="Alice"
        className="overflow-visible"
      >
        <defs>
          <filter id={id("soft")} x="-30%" y="-30%" width="160%" height="160%">
            <motion.feGaussianBlur
              initial={false}
              animate={{ stdDeviation: busy ? [sharp, sharp + 1.1, sharp] : sharp }}
              transition={busy ? { duration: 2.4, repeat: Infinity, ease: "easeInOut" } : { duration: 0.6 }}
            />
          </filter>
          <filter id={id("haze")} x="-40%" y="-40%" width="180%" height="180%">
            <motion.feGaussianBlur
              initial={false}
              animate={{ stdDeviation: busy ? [3.4, 4.8, 3.4] : 3.6 }}
              transition={busy ? { duration: 2.4, repeat: Infinity, ease: "easeInOut" } : { duration: 0.6 }}
            />
          </filter>
          <radialGradient id={id("glow")} cx="50%" cy="50%" r="50%">
            <stop offset="0" stopColor="#fff" />
            <stop offset="1" stopColor="#fff" stopOpacity="0" />
          </radialGradient>
          <linearGradient id={id("top")} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0.62" stopColor="#fff" />
            <stop offset="0.86" stopColor="#fff" stopOpacity="0" />
          </linearGradient>
          <linearGradient id={id("bottom")} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0.48" stopColor="#fff" stopOpacity="0" />
            <stop offset="0.68" stopColor="#fff" />
            <stop offset="0.86" stopColor="#fff" stopOpacity="0.7" />
            <stop offset="1" stopColor="#fff" stopOpacity="0" />
          </linearGradient>
          <mask id={id("mt")} maskContentUnits="userSpaceOnUse">
            <rect width="100" height="120" fill={`url(#${id("top")})`} />
          </mask>
          <mask id={id("mb")} maskContentUnits="userSpaceOnUse">
            <rect width="100" height="120" fill={`url(#${id("bottom")})`} />
          </mask>
        </defs>

        {/* Le contre-jour : il s'intensifie quand elle travaille */}
        <motion.ellipse
          cx="54" cy="46" rx="46" ry="50"
          fill={`url(#${id("glow")})`}
          initial={false}
          animate={
            busy
              ? { opacity: [0.7, 1, 0.7], scale: [1, 1.06, 1] }
              : { opacity: emotion === "happy" ? 1 : 0.8, scale: 1 }
          }
          transition={busy ? { duration: 2.4, repeat: Infinity, ease: "easeInOut" } : { duration: 0.6 }}
          style={{ transformOrigin: "54px 46px" }}
        />

        {/* Elle respire */}
        <motion.g
          animate={{ scaleY: [1, 1.012, 1], y: emotion === "happy" ? -1.5 : 0 }}
          transition={{
            scaleY: { duration: 4.2, repeat: Infinity, ease: "easeInOut" },
            y: { type: "spring", stiffness: 200, damping: 14 },
          }}
          style={{ transformOrigin: "50px 120px" }}
        >
          <motion.g style={{ rotate, transformOrigin: "50px 118px" }} fill={ALICE_INK}>
            <g mask={`url(#${id("mt")})`} filter={`url(#${id("soft")})`}>
              <circle {...BUN} />
              <path d={SILHOUETTE_PATH} />
              <path d={GLASSES_PATH} fill="none" stroke={ALICE_INK} strokeWidth="1.05" />
            </g>
            <g mask={`url(#${id("mb")})`} filter={`url(#${id("haze")})`}>
              <path d={SILHOUETTE_PATH} />
            </g>
          </motion.g>
        </motion.g>
      </svg>
    </div>
  );
}
