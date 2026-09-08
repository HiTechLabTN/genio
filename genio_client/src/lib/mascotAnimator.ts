import { recordGesture, pickWeighted } from "./mascotMemory";
import type { AgentStatus } from "./types";

export type MascotContext =
  | "idle"
  | "greeting"
  | "listening"
  | "thinking"
  | "executing"
  | "success"
  | "error"
  | "speaking";

export interface PoseTarget {
  /** Root position offset within the free-roam bounds (physics impulse target, meters) */
  moveTo?: { x: number; z: number };
  /** Head look-at / tilt, radians */
  headTilt: number;
  headYaw: number;
  /** 0..1 mouth openness (also driven live by TTS amplitude on top of this) */
  mouthOpen: number;
  /** 0..1 eyebrow/eye expressiveness (bigger glow / gaze intensity) */
  alertness: number;
  /** Arm gesture: none | wave | point | shrug | thumbsUp */
  arm: "none" | "wave" | "point" | "shrug" | "thumbsUp";
  /** Overall animation duration for this pose, ms */
  durationMs: number;
  contextKey: MascotContext;
  variantId: string;
}

function contextFromAgentStatus(status: AgentStatus, listening: boolean, speaking: boolean): MascotContext {
  if (speaking) return "speaking";
  if (listening) return "listening";
  if (status.kind === "thinking") return "thinking";
  if (status.kind === "executing") return "executing";
  if (status.kind === "completed") return "success";
  return "idle";
}

const ARM_OPTIONS: PoseTarget["arm"][] = ["none", "wave", "point", "shrug", "thumbsUp"];

/** Generates a brand-new procedural variation for a context (never seen before). */
function generateVariant(context: MascotContext): PoseTarget {
  const rand = (min: number, max: number) => min + Math.random() * (max - min);
  const base: Record<MascotContext, Partial<PoseTarget>> = {
    idle: { headTilt: rand(-0.08, 0.08), headYaw: rand(-0.3, 0.3), mouthOpen: 0, alertness: rand(0.2, 0.4), durationMs: rand(2600, 4200) },
    greeting: { headTilt: rand(-0.1, 0.15), headYaw: rand(-0.2, 0.2), mouthOpen: 0.3, alertness: 0.8, arm: "wave", durationMs: 1400 },
    listening: { headTilt: rand(0.02, 0.12), headYaw: rand(-0.15, 0.15), mouthOpen: 0, alertness: rand(0.6, 0.9), durationMs: rand(1800, 3000) },
    thinking: { headTilt: rand(-0.15, -0.02), headYaw: rand(-0.35, 0.35), mouthOpen: 0.08, alertness: rand(0.5, 0.75), durationMs: rand(1200, 2200) },
    executing: { headTilt: rand(-0.05, 0.05), headYaw: rand(-0.1, 0.1), mouthOpen: 0.05, alertness: 0.9, arm: Math.random() > 0.6 ? "point" : "none", durationMs: rand(900, 1600) },
    success: { headTilt: rand(0.05, 0.12), headYaw: 0, mouthOpen: 0.5, alertness: 1, arm: "thumbsUp", durationMs: 1100 },
    error: { headTilt: rand(-0.1, -0.03), headYaw: rand(-0.1, 0.1), mouthOpen: 0.15, alertness: 0.5, arm: "shrug", durationMs: 1300 },
    speaking: { headTilt: rand(-0.06, 0.1), headYaw: rand(-0.25, 0.25), mouthOpen: 0.4, alertness: 0.85, durationMs: rand(600, 1200) },
  };
  const b = base[context];
  const moveTo = context === "idle" || context === "listening"
    ? { x: rand(-1.4, 1.4), z: rand(-0.6, 0.6) }
    : undefined;
  const variant: PoseTarget = {
    headTilt: b.headTilt ?? 0,
    headYaw: b.headYaw ?? 0,
    mouthOpen: b.mouthOpen ?? 0,
    alertness: b.alertness ?? 0.5,
    arm: b.arm ?? (Math.random() > 0.85 ? ARM_OPTIONS[Math.floor(Math.random() * ARM_OPTIONS.length)] : "none"),
    durationMs: b.durationMs ?? 2000,
    moveTo,
    contextKey: context,
    variantId: `${context}-${Math.random().toString(36).slice(2, 9)}`,
  };
  return variant;
}

/**
 * Main entry point: given the live agent/interaction state, returns the next
 * pose the mascot should move toward. Mostly reuses gestures that have
 * worked before for this context (weighted pick from mascotMemory), but
 * regularly synthesizes a brand-new variation and records it — this is what
 * makes the mascot keep "growing" its repertoire instead of looping the same
 * few animations, per user, saved locally for smoother reuse next time.
 */
export function nextPose(status: AgentStatus, opts: { listening: boolean; speaking: boolean }): PoseTarget {
  const context = contextFromAgentStatus(status, opts.listening, opts.speaking);
  const remembered = pickWeighted(context);
  const pose = remembered
    ? { ...generateVariant(context), ...remembered.params, contextKey: context, variantId: remembered.variantId }
    : generateVariant(context);
  recordGesture(context, pose.variantId, {
    headTilt: pose.headTilt,
    headYaw: pose.headYaw,
    mouthOpen: pose.mouthOpen,
    alertness: pose.alertness,
    durationMs: pose.durationMs,
    moveX: pose.moveTo?.x ?? 0,
    moveZ: pose.moveTo?.z ?? 0,
  });
  return pose;
}
