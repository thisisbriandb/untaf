"use client";

import React, { useEffect } from "react";
import { motion, useMotionValue, useSpring, useTransform } from "framer-motion";

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

export function AlicePresence({ emotion, className = "", size = "lg" }: AlicePresenceProps) {
  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);

  const springConfig = { damping: 25, stiffness: 200 };
  const gazeX = useSpring(mouseX, springConfig);
  const gazeY = useSpring(mouseY, springConfig);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      const cx = window.innerWidth / 2;
      const cy = window.innerHeight / 3;
      const dx = Math.max(-1, Math.min(1, (e.clientX - cx) / cx));
      const dy = Math.max(-1, Math.min(1, (e.clientY - cy) / cy));
      mouseX.set(dx * 3);
      mouseY.set(dy * 3);
    };

    window.addEventListener("mousemove", handleMouseMove);
    return () => window.removeEventListener("mousemove", handleMouseMove);
  }, [mouseX, mouseY]);

  const emotionOffsetY = useTransform(gazeY, (y) => {
    if (emotion === "reading") return y + 3;
    if (emotion === "thinking" || emotion === "working") return y - 2.5;
    return y;
  });

  const eyeSize = {
    sm: "w-3 h-3 border-[2px]",
    md: "w-4 h-4 border-[2px]",
    lg: "w-5 h-5 border-[2.5px]",
  }[size];

  const gap = {
    sm: "gap-4",
    md: "gap-5",
    lg: "gap-6",
  }[size];

  const isWorking = emotion === "working" || emotion === "searching" || emotion === "thinking";

  return (
    <div className={`flex flex-col items-center justify-center gap-3 select-none ${className}`}>
      {/* ═══ Living Morphing Eyes Signature (○   ○) ═══ */}
      <motion.div className={`flex items-center justify-center ${gap}`}>
        {/* Left Eye */}
        <motion.div
          style={{ x: gazeX, y: emotionOffsetY }}
          animate={
            emotion === "working"
              ? { scale: [1, 1.15, 1], opacity: [0.8, 1, 0.8] }
              : emotion === "thinking"
              ? { rotate: [0, 180, 360], scale: [1, 1.1, 1] }
              : { scale: [1, 1.08, 1], opacity: [0.85, 1, 0.85] }
          }
          transition={{
            duration: emotion === "thinking" ? 2.5 : isWorking ? 1.4 : 3.2,
            repeat: Infinity,
            ease: "easeInOut",
          }}
          className={`${eyeSize} rounded-full border-[#006045] bg-transparent shadow-[0_0_14px_rgba(0,96,69,0.4)] flex items-center justify-center relative`}
        >
          {/* Internal Iris / Dot depending on state */}
          {isWorking && (
            <motion.span
              animate={{ scale: [0.6, 1, 0.6] }}
              transition={{ duration: 1.2, repeat: Infinity }}
              className="w-1.5 h-1.5 rounded-full bg-[#006045]"
            />
          )}
        </motion.div>

        {/* Center Live Node Pulse when working (○ • ○) */}
        {isWorking && (
          <motion.span
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: [0.8, 1.2, 0.8], opacity: [0.4, 1, 0.4] }}
            exit={{ scale: 0, opacity: 0 }}
            transition={{ duration: 1, repeat: Infinity }}
            className="w-1.5 h-1.5 rounded-full bg-[#006045]"
          />
        )}

        {/* Right Eye */}
        <motion.div
          style={{ x: gazeX, y: emotionOffsetY }}
          animate={
            emotion === "working"
              ? { scale: [1, 1.15, 1], opacity: [0.8, 1, 0.8] }
              : emotion === "thinking"
              ? { rotate: [0, -180, -360], scale: [1, 1.1, 1] }
              : { scale: [1, 1.08, 1], opacity: [0.85, 1, 0.85] }
          }
          transition={{
            duration: emotion === "thinking" ? 2.5 : isWorking ? 1.4 : 3.2,
            repeat: Infinity,
            ease: "easeInOut",
          }}
          className={`${eyeSize} rounded-full border-[#006045] bg-transparent shadow-[0_0_14px_rgba(0,96,69,0.4)] flex items-center justify-center relative`}
        >
          {/* Internal Iris / Dot depending on state */}
          {isWorking && (
            <motion.span
              animate={{ scale: [0.6, 1, 0.6] }}
              transition={{ duration: 1.2, repeat: Infinity, delay: 0.1 }}
              className="w-1.5 h-1.5 rounded-full bg-[#006045]"
            />
          )}
        </motion.div>
      </motion.div>
    </div>
  );
}
