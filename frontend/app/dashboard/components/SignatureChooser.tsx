"use client";

/**
 * Trois façons de signer, parce qu'à la souris la signature sort tremblée :
 *   - sur son téléphone (ordinateur seulement) : un QR code, on signe au
 *     doigt, l'écran se met à jour tout seul ;
 *   - en tapant son nom, rendu dans une écriture manuscrite au choix ;
 *   - en traçant dans le cadre (souris, pavé, ou doigt sur mobile).
 */

import { useCallback, useEffect, useState, useSyncExternalStore } from "react";
import { Caveat, Dancing_Script, Homemade_Apple } from "next/font/google";
import QRCode from "qrcode";
import { Loader2, PenLine, RefreshCw, Smartphone, Type } from "lucide-react";
import { cn } from "@/lib/utils";
import { everyWhileVisible } from "@/lib/visible-interval";
import { openSignatureSession, readSignatureSession } from "@/lib/signature-session";
import { SignaturePad } from "./SignaturePad";

const caveat = Caveat({ subsets: ["latin"], weight: "600", display: "swap" });
const dancing = Dancing_Script({ subsets: ["latin"], weight: "600", display: "swap" });
const homemade = Homemade_Apple({ subsets: ["latin"], weight: "400", display: "swap" });
const FONTS = [caveat, dancing, homemade];

type Mode = "phone" | "typed" | "draw";

const noSubscription = () => () => {};

function isDesktop() {
  return typeof window !== "undefined" && window.matchMedia("(min-width: 768px) and (pointer: fine)").matches;
}

/** Le nom, dans l'écriture choisie, en PNG transparent (comme une signature tracée). */
async function renderTyped(name: string, fontFamily: string): Promise<string> {
  // Seule la police elle-même compte (la liste contient aussi un secours local
  // dont le chargement peut échouer) ; une police absente ne bloque rien.
  const primary = fontFamily.split(",")[0].trim();
  try {
    await document.fonts.load(`64px ${primary}`);
  } catch {
    /* on dessine avec ce qui est disponible */
  }
  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d")!;
  ctx.font = `64px ${fontFamily}`;
  const width = Math.ceil(ctx.measureText(name).width) + 40;
  canvas.width = Math.max(width, 200);
  canvas.height = 120;
  ctx.font = `64px ${fontFamily}`;
  ctx.fillStyle = "#1A1918";
  ctx.textBaseline = "middle";
  ctx.fillText(name, 20, 62);
  return canvas.toDataURL("image/png");
}

function PhoneSignature({ onSave }: { onSave: (dataUrl: string) => void }) {
  const [qr, setQr] = useState<string | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [state, setState] = useState<"loading" | "waiting" | "expired" | "error" | "done">("loading");

  const start = useCallback(
    () =>
      openSignatureSession().then(async (session) => {
        if (!session) return setState("error");
        const url = `${window.location.origin}/signer?t=${encodeURIComponent(session.token)}`;
        setQr(await QRCode.toDataURL(url, { margin: 1, width: 220, color: { dark: "#1A1918", light: "#ffffff" } }));
        setToken(session.token);
        setState("waiting");
      }),
    [],
  );

  useEffect(() => {
    void start();
  }, [start]);

  // L'ordinateur attend la signature du téléphone.
  useEffect(() => {
    if (!token || state !== "waiting") return;
    return everyWhileVisible(async () => {
      const s = await readSignatureSession(token);
      if (s?.status === "signed" && s.image) {
        setState("done");
        onSave(s.image);
      }
      else if (s?.status === "expired" || s?.status === "gone") setState("expired");
    }, 2000);
  }, [token, state, onSave]);

  if (state === "loading" || state === "done") {
    return <div className="h-[220px] flex items-center justify-center"><Loader2 className="h-5 w-5 animate-spin text-[#006045]" /></div>;
  }
  if (state === "error" || state === "expired") {
    return (
      <div className="h-[220px] flex flex-col items-center justify-center gap-3 text-center">
        <p className="text-xs text-[#1A1918]/60">
          {state === "expired" ? "Le QR code a expiré." : "Je n'arrive pas à préparer le QR code."}
        </p>
        <button
          type="button"
          onClick={() => { setState("loading"); void start(); }}
          className="inline-flex items-center gap-1.5 rounded-full border border-[#1A1918]/12 px-3 py-1.5 text-xs text-[#1A1918]/70 hover:text-[#006045] cursor-pointer"
        >
          <RefreshCw className="h-3.5 w-3.5" /> Nouveau QR code
        </button>
      </div>
    );
  }
  return (
    <div className="flex flex-col sm:flex-row items-center gap-4">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      {qr && <img src={qr} alt="QR code pour signer sur ton téléphone" width={180} height={180} className="rounded-lg border border-[#1A1918]/8" />}
      <div className="space-y-2 text-left">
        <p className="text-sm text-[#1A1918] tracking-tight">Scanne avec l&apos;appareil photo de ton téléphone</p>
        <p className="text-xs text-[#1A1918]/60 leading-relaxed">
          Signe au doigt, puis valide : ta signature arrive ici toute seule.
        </p>
        <p className="inline-flex items-center gap-1.5 text-[11px] text-[#006045]">
          <Loader2 className="h-3 w-3 animate-spin" /> En attente de ta signature…
        </p>
      </div>
    </div>
  );
}

function TypedSignature({ defaultName, onSave }: { defaultName: string; onSave: (dataUrl: string) => void }) {
  const [name, setName] = useState(defaultName);
  const [font, setFont] = useState(0);
  const [busy, setBusy] = useState(false);

  return (
    <div className="space-y-3">
      <input
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="Prénom Nom"
        maxLength={60}
        className="w-full rounded-xl border border-[#1A1918]/12 bg-white px-3 py-2 text-sm text-[#1A1918] focus:outline-none focus:border-[#006045]"
      />
      <div className="grid gap-2">
        {FONTS.map((f, i) => (
          <button
            key={i}
            type="button"
            onClick={() => setFont(i)}
            className={cn(
              "rounded-xl border bg-white px-4 py-2 text-left text-3xl text-[#1A1918] truncate cursor-pointer",
              f.className,
              font === i ? "border-[#006045] ring-1 ring-[#006045]/40" : "border-[#1A1918]/10 hover:border-[#1A1918]/25",
            )}
          >
            {name || "Prénom Nom"}
          </button>
        ))}
      </div>
      <button
        type="button"
        disabled={!name.trim() || busy}
        onClick={async () => {
          setBusy(true);
          onSave(await renderTyped(name.trim(), FONTS[font].style.fontFamily));
          setBusy(false);
        }}
        className="w-full rounded-full bg-[#006045] px-4 py-2 text-sm text-white hover:bg-[#004d37] cursor-pointer disabled:opacity-40"
      >
        Utiliser cette signature
      </button>
    </div>
  );
}

export function SignatureChooser({
  fullName,
  onSave,
  onCancel,
}: {
  fullName: string;
  onSave: (dataUrl: string) => Promise<void> | void;
  onCancel?: () => void;
}) {
  // Sur ordinateur, le téléphone d'abord ; sur mobile, le doigt directement.
  // Lu après le rendu serveur (qui ne connaît pas l'écran) : pas de décalage.
  const desktop = useSyncExternalStore(noSubscription, isDesktop, () => false);
  const [chosen, setMode] = useState<Mode | null>(null);
  const mode: Mode = chosen ?? (desktop ? "phone" : "draw");

  const save = useCallback((dataUrl: string) => void onSave(dataUrl), [onSave]);
  const tabs: { id: Mode; label: string; icon: typeof Smartphone }[] = [
    ...(desktop ? [{ id: "phone" as Mode, label: "Sur mon téléphone", icon: Smartphone }] : []),
    { id: "typed", label: "Taper mon nom", icon: Type },
    { id: "draw", label: desktop ? "À la souris" : "Au doigt", icon: PenLine },
  ];

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-1.5">
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setMode(t.id)}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs tracking-tight cursor-pointer",
              mode === t.id ? "border-[#006045] bg-[#006045]/8 text-[#006045]" : "border-[#1A1918]/10 text-[#1A1918]/65",
            )}
          >
            <t.icon className="h-3.5 w-3.5" /> {t.label}
          </button>
        ))}
      </div>

      {mode === "phone" && <PhoneSignature onSave={save} />}
      {mode === "typed" && <TypedSignature defaultName={fullName} onSave={save} />}
      {mode === "draw" && <SignaturePad onSave={onSave} onCancel={onCancel} />}

      {onCancel && mode !== "draw" && (
        <button
          type="button"
          onClick={onCancel}
          className="text-xs text-[#1A1918]/55 hover:text-[#1A1918] cursor-pointer"
        >
          Plus tard
        </button>
      )}
    </div>
  );
}
