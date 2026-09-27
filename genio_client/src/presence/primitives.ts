/**
 * Animation grammar — validated primitive catalog (§5) + procedural
 * composition (§6). Primitives are declarative descriptors (no code gen,
 * no downloads). compose() validates bounds and falls back to known-good.
 */
import type { Intensity, PresenceStateId } from "./types";

export interface Primitive {
  id: string;
  family: "body" | "head" | "face" | "arms" | "hands" | "eyes" | "ambient";
  /** seconds, validated 0.2..8 */
  duration: number;
  /** 0..1 movement amplitude */
  amplitude: number;
}

export const PRIMITIVES: Record<string, Primitive> = {
  "body.breathe": { id: "body.breathe", family: "body", duration: 4.0, amplitude: 0.15 },
  "body.weight-shift": { id: "body.weight-shift", family: "body", duration: 3.0, amplitude: 0.25 },
  "body.lean-calm": { id: "body.lean-calm", family: "body", duration: 2.5, amplitude: 0.2 },
  "head.look-user": { id: "head.look-user", family: "head", duration: 1.2, amplitude: 0.3 },
  "head.look-away": { id: "head.look-away", family: "head", duration: 1.5, amplitude: 0.3 },
  "head.tilt": { id: "head.tilt", family: "head", duration: 1.8, amplitude: 0.25 },
  "head.nod": { id: "head.nod", family: "head", duration: 1.0, amplitude: 0.35 },
  "head.gaze-down": { id: "head.gaze-down", family: "head", duration: 2.0, amplitude: 0.3 },
  "face.blink": { id: "face.blink", family: "face", duration: 0.3, amplitude: 0.5 },
  "face.smile-soft": { id: "face.smile-soft", family: "face", duration: 2.0, amplitude: 0.3 },
  "face.focus": { id: "face.focus", family: "face", duration: 2.5, amplitude: 0.25 },
  "arms.open": { id: "arms.open", family: "arms", duration: 1.6, amplitude: 0.5 },
  "arms.explain": { id: "arms.explain", family: "arms", duration: 2.2, amplitude: 0.4 },
  "arms.thinking-pose": { id: "arms.thinking-pose", family: "arms", duration: 3.0, amplitude: 0.2 },
  "hands.wave": { id: "hands.wave", family: "hands", duration: 1.4, amplitude: 0.6 },
  "hands.palm-up": { id: "hands.palm-up", family: "hands", duration: 1.2, amplitude: 0.4 },
  "hands.chin-rest": { id: "hands.chin-rest", family: "hands", duration: 2.5, amplitude: 0.15 },
  "eyes.to-user": { id: "eyes.to-user", family: "eyes", duration: 1.0, amplitude: 0.3 },
  "eyes.to-task": { id: "eyes.to-task", family: "eyes", duration: 1.0, amplitude: 0.3 },
  "eyes.thinking-gaze": { id: "eyes.thinking-gaze", family: "eyes", duration: 2.0, amplitude: 0.2 },
  "ambient.glow-soft": { id: "ambient.glow-soft", family: "ambient", duration: 4.0, amplitude: 0.2 },
  "ambient.pulse-slow": { id: "ambient.pulse-slow", family: "ambient", duration: 5.0, amplitude: 0.15 },
};

/** Validated state → primitive combinations (one row each, all bounds-checked). */
export const STATE_COMBOS: Record<PresenceStateId, string[][]> = {
  idle: [["body.breathe", "face.blink", "ambient.glow-soft"]],
  greeting: [["hands.wave", "face.smile-soft", "head.look-user"], ["arms.open", "face.smile-soft"]],
  listening: [["head.look-user", "eyes.to-user", "body.breathe"]],
  understanding: [["head.tilt", "eyes.to-task", "body.breathe"]],
  thinking: [["head.look-away", "head.tilt", "body.breathe"], ["head.gaze-down", "hands.chin-rest", "eyes.thinking-gaze"]],
  planning: [["face.focus", "eyes.to-task", "arms.thinking-pose"]],
  explaining: [["arms.explain", "hands.palm-up", "head.look-user"]],
  executing: [["eyes.to-task", "face.focus", "body.lean-calm"]],
  waiting: [["body.weight-shift", "eyes.to-user", "ambient.pulse-slow"]],
  asking_user: [["arms.open", "hands.palm-up", "eyes.to-user"]],
  success: [["head.nod", "face.smile-soft"]],
  warning: [["head.tilt", "face.focus"]],
  error: [["head.look-user", "face.focus", "body.lean-calm"]],
  recovering: [["body.breathe", "eyes.to-task", "ambient.pulse-slow"]],
  celebrating: [["hands.wave", "face.smile-soft", "arms.open"]],
  sleeping: [["body.breathe", "ambient.glow-soft"]],
  disconnected: [["body.breathe"]],
  attention: [["eyes.to-user", "head.look-user", "hands.palm-up"]],
};

const FALLBACK = ["body.breathe", "face.blink"];
const MAX_TOTAL_S = 12;
const MAX_AMPLITUDE = 0.8;

export interface ComposedGesture {
  primitives: Primitive[];
  totalDuration: number;
  valid: boolean;
  fallback: boolean;
}

/** Compose a validated gesture for a state. Invalid → known-good fallback. */
export function composeGesture(state: PresenceStateId, variant = 0, intensity: Intensity = "low"): ComposedGesture {
  const combos = STATE_COMBOS[state];
  if (!combos || combos.length === 0) return fallback();
  const ids = combos[variant % combos.length];
  const prims: Primitive[] = [];
  for (const id of ids) {
    const p = PRIMITIVES[id];
    if (!p) return fallback();
    prims.push(p);
  }
  const cap = intensity === "high" ? MAX_AMPLITUDE : intensity === "medium" ? 0.5 : 0.3;
  const scaled = prims.map((p) => ({ ...p, amplitude: Math.min(p.amplitude, cap) }));
  const total = scaled.reduce((s, p) => s + p.duration, 0);
  if (total > MAX_TOTAL_S) return fallback();
  if (scaled.some((p) => p.duration < 0.2 || p.duration > 8)) return fallback();
  return { primitives: scaled, totalDuration: total, valid: true, fallback: false };
}

function fallback(): ComposedGesture {
  const prims = FALLBACK.map((id) => PRIMITIVES[id]);
  return { primitives: prims, totalDuration: 4.3, valid: true, fallback: true };
}
