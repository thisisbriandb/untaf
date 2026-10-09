"use client";

/**
 * La page ouverte en scannant le QR code : on signe au doigt, la signature
 * part vers l'ordinateur qui l'attend. Pas de connexion demandée : le jeton du
 * lien suffit, il ne sert qu'une fois et expire au bout de dix minutes.
 */

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { CheckCircle2 } from "lucide-react";
import { SignaturePad } from "@/app/dashboard/components/SignaturePad";
import { dropSignature } from "@/lib/signature-session";

function Signer() {
  const token = useSearchParams().get("t") ?? "";
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!token) {
    return <p className="text-sm text-[#1A1918]/70">Ce lien est incomplet : scanne à nouveau le QR code.</p>;
  }
  if (done) {
    return (
      <div className="space-y-3 text-center">
        <CheckCircle2 className="h-10 w-10 text-[#006045] mx-auto" />
        <p className="text-lg text-[#1A1918]">Signature envoyée.</p>
        <p className="text-sm text-[#1A1918]/60">Tu peux revenir sur ton ordinateur : elle y est déjà.</p>
      </div>
    );
  }
  return (
    <div className="space-y-4">
      <div className="space-y-1">
        <h1 className="text-xl text-[#1A1918] tracking-tight">Ta signature</h1>
        <p className="text-sm text-[#1A1918]/60">
          Signe au doigt dans le cadre. Elle figurera au bas de tes lettres de motivation.
        </p>
      </div>
      <SignaturePad
        onSave={async (dataUrl) => {
          const reason = await dropSignature(token, dataUrl);
          if (reason) setError(reason);
          else setDone(true);
        }}
      />
      {error && <p className="text-sm text-red-600">{error}</p>}
    </div>
  );
}

export default function SignerPage() {
  return (
    <main className="min-h-[100dvh] bg-[#FAFAF8] px-5 py-10 flex justify-center">
      <div className="w-full max-w-md">
        <p className="text-[12px] font-medium text-[#006045] tracking-tight pb-6">Alice</p>
        <Suspense fallback={null}>
          <Signer />
        </Suspense>
      </div>
    </main>
  );
}
