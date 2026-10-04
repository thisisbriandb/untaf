"use client";

import { useCallback, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { AlicePresence } from "../onboarding/components/AlicePresence";
import { EmailSignIn } from "../auth/EmailSignIn";
import { authEnabled } from "@/lib/auth";
import { destinationAfterSignIn } from "@/lib/session";

export default function LoginPage() {
  const router = useRouter();

  // Sans authentification configurée (développement), rien à faire ici.
  useEffect(() => {
    authEnabled().then((on) => {
      if (!on) router.replace("/dashboard");
    });
  }, [router]);

  const handleSignedIn = useCallback(async () => {
    const next = new URLSearchParams(window.location.search).get("next");
    router.replace(await destinationAfterSignIn(next));
  }, [router]);

  return (
    <main className="min-h-[100dvh] bg-[#FAFAF8] flex flex-col items-center justify-center gap-8 px-6">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
        className="w-full flex flex-col items-center gap-7"
      >
        <AlicePresence emotion="listening" />
        <EmailSignIn onSignedIn={handleSignedIn} />
      </motion.div>
      <Link href="/" className="text-xs font-light text-[#1A1918]/40 hover:text-[#006045] tracking-tight">
        Pas encore de compte ? Je te présente Alice →
      </Link>
    </main>
  );
}
