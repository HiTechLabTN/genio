import { useState } from "react";
import { imageForState } from "../presence/PresenceAvatar";
import type { EngineState } from "../presence/engine";
import type { GenioPresenceState } from "../presence/types";
import { effectiveMotion, loadPrefs } from "../presence/preferences";
import { t, useLang } from "../lib/lang";

/**
 * Mascot — canonical image character with interaction attention.
 * Interaction (hover/focus/tap) triggers an ATTENTION REACTION ONLY
 * (visual emphasis); it never changes system state.
 * CSS/SVG only: no 3D, no new deps. Reduced-motion honored.
 */
/** Engine phase → existing localized shell status (single visible voice). */
const ACTIVITY_KEY: Record<EngineState, string> = {
  READY: "shell.ready",
  LISTENING: "shell.listening",
  THINKING: "shell.thinking",
  TASK_RUNNING: "shell.executing",
  TOOL_ACTIVITY: "shell.executing",
  COMPLETE: "shell.success",
  ERROR: "shell.error",
  OFFLINE: "shell.disconnected",
  RECONNECTING: "shell.recovering",
};

export default function Mascot({ presence, engine, size }: {
  /** Canonical presence (who Genio is / where attention goes). */
  presence: GenioPresenceState;
  /** Task-lifecycle phase (what Genio is doing). Same facts, other axis. */
  engine: EngineState;
  size?: number;
}) {
  const [attending, setAttending] = useState(false);
  const [failed, setFailed] = useState(false);
  const [lang] = useLang();
  const prefs = loadPrefs();
  const osReduced = typeof window !== "undefined" && !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  const motion = effectiveMotion(prefs, osReduced);
  // Single direction: canonical image from PRESENCE (who Genio is);
  // ring/motion from ENGINE phase (what Genio is doing). No second machine.
  // Per-state motion: idle breathes, thinking pulses, reconnecting spins.
  const imgState = presence.semanticState;
  const dim = size ?? (prefs.mascotSize === "compact" ? 72 : prefs.mascotSize === "large" ? 176 : 140);
  const tone = engine === "ERROR" ? "#f43f5e" : engine === "COMPLETE" ? "#34d399"
    : engine === "OFFLINE" ? "#64748b" : "#22d3ee";
  const stateLabel = t(lang, ACTIVITY_KEY[engine]);
  const motionClass =
    motion === "on" && engine === "RECONNECTING" ? "g5-spin-slow"
    : motion === "on" && engine === "THINKING" ? "g5-think-pulse"
    : motion === "on" && engine === "LISTENING" ? "g5-listen-lean"
    : motion === "on" && engine === "COMPLETE" ? "g5-complete-bounce"
    : motion === "on" ? "g5-breathe-soft"
    : undefined;
  return (
    <div
      role="img"
      aria-label={stateLabel}
      tabIndex={0}
      onMouseEnter={() => setAttending(true)}
      onMouseLeave={() => setAttending(false)}
      onFocus={() => setAttending(true)}
      onBlur={() => setAttending(false)}
      onClick={() => setAttending((v) => !v)}
      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setAttending((v) => !v); } }}
      className="g5-focusable relative inline-flex cursor-pointer items-center justify-center rounded-full"
      style={{ width: dim, height: dim }}
      title={stateLabel}
    >
      <svg aria-hidden="true" className="absolute inset-0 h-full w-full" viewBox="0 0 100 100">
        <circle
          cx="50" cy="50" r="46" fill="none" stroke={tone} strokeOpacity="0.5" strokeWidth="2"
          strokeDasharray={engine === "RECONNECTING" || engine === "THINKING" ? "8 6" : "none"}
          className={motion === "on" && (engine === "RECONNECTING" || engine === "THINKING") ? "g5-spin-slow" : undefined}
        />
      </svg>
      {failed ? (
        <span aria-hidden="true" className="text-2xl font-bold text-cyan-300">G</span>
      ) : (
        <img
          src={imageForState(imgState as never)}
          alt=""
          width={dim}
          height={dim}
          loading="lazy"
          onError={() => setFailed(true)}
          className={`rounded-full object-cover transition-transform ${motionClass ?? ""}`}
          style={{ transform: attending ? "scale(1.04)" : undefined }}
        />
      )}
      <style>{`@keyframes g5-spin-slow { to { transform: rotate(360deg); } }
        .g5-spin-slow { animation: g5-spin-slow 6s linear infinite; transform-origin: center; }
        @keyframes g5-think-pulse { 0%,100% { transform: scale(1); } 50% { transform: scale(1.05); } }
        .g5-think-pulse { animation: g5-think-pulse 2.2s ease-in-out infinite; }
        @keyframes g5-listen-lean { 0%,100% { transform: scale(1) rotate(0deg); } 50% { transform: scale(1.03) rotate(1.5deg); } }
        .g5-listen-lean { animation: g5-listen-lean 3s ease-in-out infinite; }
        @keyframes g5-complete-bounce { 0%,100% { transform: scale(1); } 30% { transform: scale(1.07); } 60% { transform: scale(0.99); } }
        .g5-complete-bounce { animation: g5-complete-bounce 1.6s ease-in-out 2; }
        @keyframes g5-breathe-soft { 0%,100% { transform: scale(1); } 50% { transform: scale(1.025); } }
        .g5-breathe-soft { animation: g5-breathe-soft 4.5s ease-in-out infinite; }
        @media (prefers-reduced-motion: reduce) { .g5-spin-slow, .g5-think-pulse, .g5-listen-lean, .g5-complete-bounce, .g5-breathe-soft { animation: none; } }`}</style>
    </div>
  );
}
