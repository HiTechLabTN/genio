import { useState } from "react";
import { imageForState } from "../../presence/PresenceAvatar";
import type { PresenceStateId } from "../../presence/types";

/**
 * LivingMascot — canonical 2D character anchor (mascot-revamp).
 *
 * Canonical portrait image per REAL presence state + lightweight CSS motion.
 * Pure DOM/CSS: no Canvas, no WebGL, no new deps — it can never crash the app
 * the way the 3D path can. Asset failure degrades hero → "G" letter → nothing
 * breaks around it. Reduced-motion always honored (static portrait stays).
 *
 * States map 1:1 onto presence semantic states; error/offline reuse the base
 * portrait with an honest CSS treatment (tone ring + dim), never fake assets.
 */
export type LivingVisual =
  | "idle" | "listening" | "thinking" | "working"
  | "speaking" | "success" | "error" | "offline" | "reconnecting";

const VISUAL_TO_SEMANTIC: Record<LivingVisual, PresenceStateId> = {
  idle: "idle",
  listening: "listening",
  thinking: "thinking",
  working: "executing",
  speaking: "explaining",
  success: "success",
  error: "error",
  offline: "disconnected",
  reconnecting: "waiting",
};

const TONE: Record<LivingVisual, string> = {
  idle: "#22d3ee",
  listening: "#67e8f9",
  thinking: "#a78bfa",
  working: "#22d3ee",
  speaking: "#34d399",
  success: "#34d399",
  error: "#f43f5e",
  offline: "#64748b",
  reconnecting: "#f59e0b",
};

const MOTION: Record<LivingVisual, string> = {
  idle: "lm-breathe",
  listening: "lm-lean",
  thinking: "lm-sway",
  working: "lm-work",
  speaking: "lm-speak",
  success: "lm-celebrate",
  error: "lm-still",
  offline: "lm-still",
  reconnecting: "lm-spin-slow",
};

export default function LivingMascot({ visual, statusText, size = 220, compact = false }: {
  /** Real presence-derived visual state — never a timer, never faked. */
  visual: LivingVisual;
  /** Localized human status line rendered under the portrait. */
  statusText: string;
  /** Portrait width in px (height auto, aspect preserved). */
  size?: number;
  /** Compact variant for small screens. */
  compact?: boolean;
}) {
  const [stage, setStage] = useState(0); // 0 state img → 1 hero → 2 letter
  const semantic = VISUAL_TO_SEMANTIC[visual];
  const src = stage === 0 ? imageForState(semantic) : stage === 1 ? imageForState("idle") : null;
  const tone = TONE[visual];
  const dimmed = visual === "offline" || visual === "error";
  const osReduced = typeof window !== "undefined" && !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  const motion = !osReduced && !compact ? MOTION[visual] : "lm-still";
  const w = compact ? Math.min(size, 140) : size;
  return (
    <div className="pointer-events-none flex select-none flex-col items-center" aria-hidden="false">
      <div
        role="img"
        aria-label={statusText}
        className="relative"
        style={{ width: w }}
      >
        <div
          aria-hidden="true"
          className="absolute -inset-3 rounded-[2rem]"
          style={{
            background: `radial-gradient(ellipse at center, ${tone}26 0%, transparent 70%)`,
            filter: "blur(6px)",
          }}
        />
        {src ? (
          <img
            src={src}
            alt=""
            width={w}
            draggable={false}
            onError={() => setStage((s) => Math.min(s + 1, 2))}
            className={`relative h-auto w-full rounded-[1.5rem] border object-cover ${motion}`}
            style={{
              borderColor: `${tone}55`,
              boxShadow: `0 0 28px ${tone}44, 0 8px 32px rgba(0,0,0,0.5)`,
              filter: dimmed ? "saturate(0.35) brightness(0.75)" : undefined,
              maskImage: "linear-gradient(to bottom, black 82%, transparent 100%)",
              WebkitMaskImage: "linear-gradient(to bottom, black 82%, transparent 100%)",
            }}
          />
        ) : (
          <div
            className="relative flex items-center justify-center rounded-[1.5rem] border bg-[#020B1E]"
            style={{ width: w, height: w * 1.1, borderColor: `${tone}55` }}
          >
            <span aria-hidden="true" className="text-5xl font-black text-cyan-300">G</span>
          </div>
        )}
        <span
          aria-hidden="true"
          className="absolute left-1/2 top-2 h-2.5 w-2.5 -translate-x-1/2 rounded-full"
          style={{ background: tone, boxShadow: `0 0 10px ${tone}` }}
        />
      </div>
      <p className="mt-2 max-w-[240px] truncate text-center font-mono text-[12px] font-bold text-white/90">{statusText}</p>
      <style>{`@keyframes lm-breathe { 0%,100% { transform: translateY(0) scale(1); } 50% { transform: translateY(-6px) scale(1.015); } }
        .lm-breathe { animation: lm-breathe 4.5s ease-in-out infinite; }
        @keyframes lm-lean { 0%,100% { transform: rotate(0deg) scale(1); } 50% { transform: rotate(1.2deg) scale(1.02); } }
        .lm-lean { animation: lm-lean 3s ease-in-out infinite; }
        @keyframes lm-sway { 0%,100% { transform: translateX(0); } 50% { transform: translateX(7px); } }
        .lm-sway { animation: lm-sway 2.4s ease-in-out infinite; }
        @keyframes lm-work { 0%,100% { transform: scale(1); filter: brightness(1); } 50% { transform: scale(1.03); filter: brightness(1.12); } }
        .lm-work { animation: lm-work 1.8s ease-in-out infinite; }
        @keyframes lm-speak { 0%,100% { transform: scale(1); } 30% { transform: scale(1.04); } 60% { transform: scale(1.01); } }
        .lm-speak { animation: lm-speak 1.1s ease-in-out infinite; }
        @keyframes lm-celebrate { 0%,100% { transform: translateY(0); } 40% { transform: translateY(-10px); } }
        .lm-celebrate { animation: lm-celebrate 1.4s ease-in-out 3; }
        @keyframes lm-spin-slow { to { transform: rotate(360deg); } }
        .lm-spin-slow { animation: lm-spin-slow 7s linear infinite; }
        .lm-still { animation: none; }
        @media (prefers-reduced-motion: reduce) { .lm-breathe, .lm-lean, .lm-sway, .lm-work, .lm-speak, .lm-celebrate, .lm-spin-slow { animation: none; } }`}</style>
    </div>
  );
}
