"use client";

import React, { useEffect, useId } from "react";
import { motion, useMotionValue, useSpring, useTransform } from "framer-motion";
import { AliceGlasses, AliceHead, HEAD_VIEWBOX } from "./AliceSilhouette";

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
 * Alice, présente : sa tête de face, en contre-jour, qui respire.
 *
 * Les états se lisent dans la lumière plus que dans le geste — nette quand
 * elle t'écoute, la tête qui s'incline quand elle lit ou écrit, le contour
 * qui se trouble et la lumière qui pulse derrière elle quand elle travaille.
 * Son regard suit très légèrement le pointeur : la tête se décale à peine,
 * la monture un peu plus, comme quand on tourne les yeux.
 */
export function AlicePresence({ emotion, className = "", size = "lg" }: AlicePresenceProps) {
  const uid = useId().replace(/[^a-zA-Z0-9]/g, "");
  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);
  const gx = useSpring(mouseX, { damping: 30, stiffness: 120 });
  const gy = useSpring(mouseY, { damping: 30, stiffness: 120 });

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      const cx = window.innerWidth / 2;
      const cy = window.innerHeight / 3;
      mouseX.set(Math.max(-1, Math.min(1, (e.clientX - cx) / cx)));
      mouseY.set(Math.max(-1, Math.min(1, (e.clientY - cy) / cy)));
    };
    window.addEventListener("mousemove", onMove);
    return () => window.removeEventListener("mousemove", onMove);
  }, [mouseX, mouseY]);

  const busy = emotion === "working" || emotion === "searching" || emotion === "thinking";
  const reading = emotion === "reading" || emotion === "writing";

  const headX = useTransform(gx, (g) => g * 0.7);
  const headY = useTransform(gy, (g) => g * 0.4 + (reading ? 1.2 : 0));
  const glassesX = useTransform(gx, (g) => g * 0.5);
  const glassesY = useTransform(gy, (g) => g * 0.35);
  const tilt = emotion === "thinking" ? -3 : reading ? 2.5 : 0;

  const sharp = emotion === "listening" || emotion === "happy" ? 0.5 : 0.75;
  const height = HEIGHT[size];
  const width = height;
  const id = (name: string) => `${name}-${uid}`;
  const pulse = { duration: 2.4, repeat: Infinity, ease: "easeInOut" } as const;

  return (
    <div className={`flex flex-col items-center justify-center select-none ${className}`}>
      <svg viewBox={HEAD_VIEWBOX} width={width} height={height} role="img" aria-label="Alice" className="overflow-visible">
        <defs>
          <filter id={id("soft")} x="-30%" y="-30%" width="160%" height="160%">
            <motion.feGaussianBlur
              initial={false}
              animate={{ stdDeviation: busy ? [sharp, sharp + 0.9, sharp] : sharp }}
              transition={busy ? pulse : { duration: 0.6 }}
            />
          </filter>
          <radialGradient id={id("glow")} cx="50%" cy="50%" r="50%">
            <stop offset="0" stopColor="#E5F0EC" />
            <stop offset="0.55" stopColor="#F3F8F6" stopOpacity="0.8" />
            <stop offset="1" stopColor="#fff" stopOpacity="0" />
          </radialGradient>
        </defs>

        {/* Le contre-jour : il s'intensifie quand elle travaille */}
        <motion.ellipse
          cx="50" cy="38" rx="34" ry="34"
          fill={`url(#${id("glow")})`}
          initial={false}
          animate={busy ? { opacity: [0.7, 1, 0.7], scale: [1, 1.06, 1] } : { opacity: emotion === "happy" ? 1 : 0.8, scale: 1 }}
          transition={busy ? pulse : { duration: 0.6 }}
          style={{ transformOrigin: "50px 38px" }}
        />

        {/* Elle respire */}
        <motion.g
          animate={{ scaleY: [1, 1.01, 1], y: emotion === "happy" ? -1.5 : 0 }}
          transition={{
            scaleY: { duration: 4.2, repeat: Infinity, ease: "easeInOut" },
            y: { type: "spring", stiffness: 200, damping: 14 },
          }}
          style={{ transformOrigin: "50px 62px" }}
        >
          <g filter={`url(#${id("soft")})`}>
            <motion.g
              style={{ x: headX, y: headY, transformOrigin: "50px 62px" }}
              animate={{ rotate: tilt }}
              transition={{ type: "spring", stiffness: 120, damping: 16 }}
            >
              <AliceHead />
              <motion.g style={{ x: glassesX, y: glassesY }}>
                <AliceGlasses />
              </motion.g>
            </motion.g>
          </g>
        </motion.g>
      </svg>
    </div>
  );
}
