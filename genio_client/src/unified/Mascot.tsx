import { useState } from "react";
import { imageForState } from "../presence/PresenceAvatar";
import type { EngineState } from "../presence/engine";
import type { GenioPresenceState } from "../presence/types";
import { effectiveMotion, loadPrefs } from "../presence/preferences";

/**
 * Mascot — canonical image character with interaction attention.
 * Interaction (hover/focus/tap) triggers an ATTENTION REACTION ONLY
 * (visual emphasis); it never changes system state.
 * CSS/SVG only: no 3D, no new deps. Reduced-motion honored.
 */
const ACTIVITY_LABEL: Record<EngineState, string> = {
  READY: "ready",
  LISTENING: "listening",
  THINKING: "thinking",
  TASK_RUNNING: "working",
  TOOL_ACTIVITY: "using a tool",
  COMPLETE: "done",
  ERROR: "something needs attention",
  OFFLINE: "offline",
  RECONNECTING: "reconnecting",
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
  const prefs = loadPrefs();
  const osReduced = typeof window !== "undefined" && !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  const motion = effectiveMotion(prefs, osReduced);
  // Single direction: canonical image from PRESENCE (who Genio is);
  // ring/motion from ENGINE phase (what Genio is doing). No second machine.
  const imgState = presence.semanticState;
  const dim = size ?? (prefs.mascotSize === "compact" ? 72 : prefs.mascotSize === "large" ? 160 : 112);
  const tone = engine === "ERROR" ? "#f43f5e" : engine === "COMPLETE" ? "#34d399"
    : engine === "OFFLINE" ? "#64748b" : "#22d3ee";
  return (
    <div
      role="img"
      aria-label={`Genio, ${presence.semanticState} (${ACTIVITY_LABEL[engine]})`}
      tabIndex={0}
      onMouseEnter={() => setAttending(true)}
      onMouseLeave={() => setAttending(false)}
      onFocus={() => setAttending(true)}
      onBlur={() => setAttending(false)}
      onClick={() => setAttending((v) => !v)}
      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setAttending((v) => !v); } }}
      className="g5-focusable relative inline-flex cursor-pointer items-center justify-center rounded-full"
      style={{ width: dim, height: dim }}
      title={`Genio is ${presence.semanticState}, ${ACTIVITY_LABEL[engine]} (visual attention only)`}
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
          className="rounded-full object-cover transition-transform"
          style={{ transform: attending ? "scale(1.04)" : undefined }}
        />
      )}
      <style>{`@keyframes g5-spin-slow { to { transform: rotate(360deg); } }
        .g5-spin-slow { animation: g5-spin-slow 6s linear infinite; transform-origin: center; }
        @media (prefers-reduced-motion: reduce) { .g5-spin-slow { animation: none; } }`}</style>
    </div>
  );
}
