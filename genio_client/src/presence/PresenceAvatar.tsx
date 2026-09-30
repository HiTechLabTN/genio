import { useEffect, useState } from "react";
import type { GenioPresenceState, PresenceStateId } from "./types";
import { composeGesture } from "./primitives";
import { effectiveMotion, loadPrefs } from "./preferences";
import heroBase from "../assets/mascot/genio-hero.webp";
import heroWave from "../assets/character/genio-wave.webp";
import heroWink from "../assets/character/genio-wink.webp";
import stateListen from "../assets/mascot/genio-listen.webp";
import stateThink from "../assets/mascot/genio-think.webp";
import stateSpeak from "../assets/mascot/genio-speak.webp";

/**
 * CharacterView (canonical image character layer, G4.2 + mascot-revamp).
 * Presence state → canonical reference image, never a reinterpretation:
 *   greeting/listening-wave... — see table. The bearded jebba identity
 *   (hero/listen/think/speak) covers focused states; wave/wink cover
 *   greeting/success. error/offline/disconnected reuse base with a
 *   CSS treatment applied by the component (dim + tone ring) — no fake
 *   assets, the artwork itself is never altered.
 */
const STATE_IMAGE: Partial<Record<PresenceStateId, string>> = {
  greeting: heroWave,
  asking_user: heroWave,
  attention: heroWave,
  listening: stateListen,
  understanding: stateThink,
  thinking: stateThink,
  planning: stateThink,
  executing: stateThink,
  explaining: stateSpeak,
  success: heroWink,
  celebrating: heroWink,
};

export function imageForState(state: PresenceStateId): string {
  return STATE_IMAGE[state] ?? heroBase;
}

/**
 * PresenceAvatar — Phase-2 lightweight presence (no 3D cost).
 * Existing mascot_cutout.webp identity + state-driven CSS only:
 * breathing scale, attention tilt, status glow. Reduced-motion and
 * animation-off honored. Image failure → neutral initial fallback.
 * Never blocks, never fakes: label always names the real state.
 */
export default function PresenceAvatar({ presence, compact }: { presence: GenioPresenceState; compact?: boolean }) {
  const [failed, setFailed] = useState(false);
  const [prefs, setPrefs] = useState(loadPrefs);
  useEffect(() => {
    const onStorage = () => setPrefs(loadPrefs());
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);
  const osReduced = typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  const motion = effectiveMotion(prefs, !!osReduced);
  const gesture = composeGesture(
    presence.semanticState,
    0,
    motion === "off" ? "low" : presence.intensity
  );
  const size = compact ? 56 : prefs.mascotSize === "compact" ? 72 : prefs.mascotSize === "large" ? 160 : 112;
  const animate = motion === "on";
  const dot: Record<string, string> = {
    error: "#f43f5e", success: "#34d399", executing: "#22d3ee", thinking: "#a78bfa",
    listening: "#67e8f9", disconnected: "#64748b",
  };
  const color = dot[presence.semanticState] ?? "#22d3ee";
  return (
    <div
      role="img"
      aria-label={`Genio state: ${presence.semanticState}, attention: ${presence.attentionTarget ?? "user"}`}
      className="relative inline-flex items-center justify-center"
      style={{ width: size, height: size }}
      title={`state=${presence.semanticState} gesture=${gesture.primitives.map((p) => p.id).join("+")}`}
    >
      <span
        aria-hidden="true"
        className={animate ? "g5-animated absolute inset-0 rounded-full" : "absolute inset-0 rounded-full"}
        style={{
          boxShadow: prefs.ambient ? `0 0 ${motion === "off" ? 8 : 24}px ${color}55` : "none",
          border: `2px solid ${color}66`,
          animation: animate ? "g5-breathe 4s ease-in-out infinite" : undefined,
        }}
      />
      {failed ? (
        <span aria-hidden="true" className="text-2xl font-bold text-cyan-300">G</span>
      ) : (
        <img
          src={imageForState(presence.semanticState)}
          alt=""
          width={size}
          height={size}
          onError={() => setFailed(true)}
          className="rounded-full object-cover"
          style={{ transform: presence.attentionTarget === "task" ? "scale(0.96)" : undefined }}
        />
      )}
      <span
        aria-hidden="true"
        className="absolute bottom-1 right-1 h-3 w-3 rounded-full border border-black/50"
        style={{ background: color }}
      />
      <style>{`@keyframes g5-breathe { 0%,100% { transform: scale(1); } 50% { transform: scale(1.03); } }
        @media (prefers-reduced-motion: reduce) { @keyframes g5-breathe { to { transform: none; } } }`}</style>
    </div>
  );
}
