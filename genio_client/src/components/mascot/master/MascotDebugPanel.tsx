/**
 * MascotDebugPanel — developer-only diagnostics + manual triggers (§25).
 * Rendered only when explicitly enabled (never in production by default).
 */
import { memo } from "react";
import type { MascotDebugInfo } from "./MascotScene";

const TRIGGERS = ["wave", "listen", "think", "speak", "hero", "smile", "nod", "idle"] as const;

const MascotDebugPanel = memo(function MascotDebugPanel({
  info,
  ready,
  onTrigger,
  onReset,
}: {
  info: MascotDebugInfo | null;
  ready: { clips: number; morphs: number } | null;
  onTrigger: (clip: string) => void;
  onReset: () => void;
}) {
  return (
    <div
      data-testid="mascot-debug"
      className="absolute left-2 top-2 z-[80] w-60 rounded-lg border border-cyan-400/30 bg-black/70 p-2 font-mono text-[10px] text-cyan-100 backdrop-blur"
    >
      <div className="mb-1 flex items-center justify-between">
        <span className="font-bold tracking-widest">MASCOT DEBUG</span>
        <button onClick={onReset} className="rounded border border-white/20 px-1.5 py-0.5 hover:bg-white/10">
          reset
        </button>
      </div>
      <div className="space-y-0.5">
        <div>State: {info?.state ?? "—"}</div>
        <div>Animation: {info?.clip ?? "—"}</div>
        <div>Emotion: {info?.emotionLabel ?? "—"}</div>
        <div>Viseme: {info?.viseme ?? "—"}</div>
        <div>Gaze: {info?.gaze ?? "—"}</div>
        <div>Source: {info?.motionSource ?? "—"}</div>
        <div>FPS: {info?.fps ?? "—"}</div>
        <div>Draws: {info?.drawCalls ?? "—"} / Tris: {info?.triangles ?? "—"}</div>
        <div>GLB: {info?.glbSize ?? "—"}</div>
        <div>Clips: {ready?.clips ?? "—"} / Morphs: {ready?.morphs ?? "—"}</div>
      </div>
      <div className="mt-1.5 flex flex-wrap gap-1">
        {TRIGGERS.map((t) => (
          <button
            key={t}
            onClick={() => onTrigger(t)}
            className="rounded border border-white/20 px-1.5 py-0.5 uppercase hover:bg-white/10"
          >
            {t}
          </button>
        ))}
      </div>
    </div>
  );
});

export default MascotDebugPanel;
