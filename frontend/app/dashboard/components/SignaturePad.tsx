"use client";

import { useEffect, useRef, useState } from "react";
import { Check, Eraser, Loader2 } from "lucide-react";

/**
 * Capture de signature manuscrite.
 *
 * Tracé à la souris ou au doigt, directement dans le Canvas. Une fois
 * enregistrée, la signature est réutilisée sur toutes les lettres suivantes
 * sans rien redemander — c'est ce qui rend une candidature automatique
 * réellement prête à partir.
 */
export function SignaturePad({
  onSave,
  onCancel,
}: {
  onSave: (dataUrl: string) => Promise<void> | void;
  onCancel?: () => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const drawing = useRef(false);
  const [hasInk, setHasInk] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  // Le canvas est dimensionné en pixels réels pour rester net sur écran HiDPI.
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ratio = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * ratio;
    canvas.height = rect.height * ratio;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.scale(ratio, ratio);
    ctx.lineWidth = 1.8;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.strokeStyle = "#1A1918";
  }, []);

  const pointFrom = (e: React.PointerEvent<HTMLCanvasElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    return { x: e.clientX - rect.left, y: e.clientY - rect.top };
  };

  const start = (e: React.PointerEvent<HTMLCanvasElement>) => {
    e.currentTarget.setPointerCapture(e.pointerId);
    const ctx = canvasRef.current?.getContext("2d");
    if (!ctx) return;
    const { x, y } = pointFrom(e);
    ctx.beginPath();
    ctx.moveTo(x, y);
    drawing.current = true;
    setHasInk(true);
  };

  const move = (e: React.PointerEvent<HTMLCanvasElement>) => {
    if (!drawing.current) return;
    const ctx = canvasRef.current?.getContext("2d");
    if (!ctx) return;
    const { x, y } = pointFrom(e);
    ctx.lineTo(x, y);
    ctx.stroke();
  };

  const end = () => {
    drawing.current = false;
  };

  const clear = () => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    setHasInk(false);
  };

  const save = async () => {
    const canvas = canvasRef.current;
    if (!canvas || !hasInk) return;
    setIsSaving(true);
    await onSave(canvas.toDataURL("image/png"));
    setIsSaving(false);
  };

  return (
    <div className="space-y-2.5">
      <p className="text-xs font-normal text-[#1A1918]/55 tracking-tight">
        Signe ici — je la réutiliserai sur toutes tes lettres.
      </p>

      <canvas
        ref={canvasRef}
        onPointerDown={start}
        onPointerMove={move}
        onPointerUp={end}
        onPointerLeave={end}
        className="w-full h-32 rounded-xl border border-dashed border-[#1A1918]/20 bg-white touch-none cursor-crosshair"
      />

      <div className="flex items-center justify-between gap-2">
        <button
          type="button"
          onClick={clear}
          disabled={!hasInk}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-[#1A1918]/12 text-xs font-normal text-[#1A1918]/60 tracking-tight hover:border-[#1A1918]/30 transition-colors cursor-pointer disabled:opacity-30"
        >
          <Eraser className="w-3.5 h-3.5 stroke-[1.5]" />
          Effacer
        </button>

        <div className="flex items-center gap-2">
          {onCancel && (
            <button
              type="button"
              onClick={onCancel}
              className="text-xs font-normal text-[#1A1918]/60 hover:text-[#1A1918] tracking-tight cursor-pointer"
            >
              Plus tard
            </button>
          )}
          <button
            type="button"
            onClick={save}
            disabled={!hasInk || isSaving}
            className="flex items-center gap-1.5 px-4 py-2 rounded-full bg-[#006045] text-white text-xs font-normal tracking-tight hover:bg-[#004d37] transition-colors cursor-pointer disabled:opacity-30"
          >
            {isSaving ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Check className="w-3.5 h-3.5 stroke-[2]" />
            )}
            Enregistrer
          </button>
        </div>
      </div>
    </div>
  );
}
