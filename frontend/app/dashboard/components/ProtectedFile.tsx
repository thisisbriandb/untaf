"use client";

/**
 * Fichiers protégés — CV, lettres, packs.
 *
 * Un lien ou un `<object data>` n'envoie pas le jeton de session : ces
 * documents sont donc récupérés par `apiFetch`, puis servis au navigateur
 * sous forme d'URL locale.
 */

import { useEffect, useState, type ReactNode } from "react";
import { Loader2 } from "lucide-react";
import { apiFetch, downloadFile } from "@/lib/api";
import { useToast } from "./Toaster";

export function DownloadLink({
  url,
  filename,
  className,
  children,
}: {
  url: string;
  filename: string;
  className?: string;
  children: ReactNode;
}) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);

  return (
    <button
      type="button"
      disabled={busy}
      onClick={async () => {
        setBusy(true);
        const ok = await downloadFile(url, filename);
        setBusy(false);
        if (!ok) toast("Téléchargement impossible pour l'instant.", "warning");
      }}
      className={`${className ?? ""} cursor-pointer disabled:opacity-60`}
    >
      {busy && <Loader2 className="w-3 h-3 animate-spin" />}
      {children}
    </button>
  );
}

/** URL locale d'un fichier protégé, pour un aperçu intégré. */
export function useProtectedBlobUrl(url: string | null): string | null {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!url) return;
    let alive = true;
    let created: string | null = null;
    apiFetch(url)
      .then((res) => (res.ok ? res.blob() : null))
      .then((blob) => {
        if (!alive || !blob) return;
        created = URL.createObjectURL(blob);
        setBlobUrl(created);
      })
      .catch(() => {});
    return () => {
      alive = false;
      if (created) URL.revokeObjectURL(created);
    };
  }, [url]);

  return url ? blobUrl : null;
}
