/**
 * MascotController — behavior planner glue (§12): intent/context → directive
 * { body, face, gaze, head pose, intensity, speed, transition, env reaction }
 * + procedural composer + motion-memory record/reuse hooks.
 *
 * Data-driven: callers pass semantic labels (intent/emotion), never raw
 * sentences. Unknown inputs fall back safely (§30).
 */
import { estimateEmotion6, mapEmotionToChannels, NEUTRAL_EMOTION6, type Emotion6, type EmotionLabel } from "../../../services/mascotBehavior";
import { clipForEvent, sanitizeClipName, type MascotEventName } from "./MascotEventBridge";
import { composeRecipe, type MotionRecipe } from "./MascotMixer";

export type BehaviorIntent =
  | "greeting" | "listening" | "thinking" | "speaking" | "explaining"
  | "working" | "success" | "error" | "idle" | "celebrate" | "apologize"
  | "agree" | "disagree" | "curious" | "hero";

export type BehaviorDirective = {
  intent: BehaviorIntent;
  emotion: Emotion6;
  emotionLabel: EmotionLabel;
  body: string;
  face: Record<string, number>;
  gaze: "user" | "away" | "up_left" | "down";
  headTilt: number;
  headYaw: number;
  intensity: number;
  speed: number;
  recipe: MotionRecipe;
  ring: "cyan" | "gold" | "rose";
  ringPulse: number;
};

const INTENT_EVENT: Record<BehaviorIntent, MascotEventName> = {
  greeting: "system.ready",
  listening: "user.message.received",
  thinking: "assistant.thinking.started",
  speaking: "assistant.speaking.started",
  explaining: "assistant.speaking.started",
  working: "tool.started",
  success: "task.success",
  error: "tool.error",
  idle: "system.idle",
  celebrate: "task.success",
  apologize: "task.failed",
  agree: "assistant.speaking.started",
  disagree: "assistant.speaking.started",
  curious: "notification",
  hero: "system.ready",
};

const INTENT_BODY: Partial<Record<BehaviorIntent, string>> = {
  greeting: "greeting",
  listening: "listen",
  thinking: "think",
  speaking: "speak",
  explaining: "speak_emphasis",
  working: "executing",
  success: "success",
  error: "error_reaction",
  idle: "idle",
  celebrate: "celebrate",
  apologize: "apologize",
  agree: "nod",
  disagree: "shake_head",
  curious: "curious",
  hero: "hero",
};

const INTENT_GAZE: Record<BehaviorIntent, BehaviorDirective["gaze"]> = {
  greeting: "user", listening: "user", thinking: "up_left", speaking: "user",
  explaining: "user", working: "down", success: "user", error: "user",
  idle: "away", celebrate: "user", apologize: "user", agree: "user",
  disagree: "user", curious: "user", hero: "user",
};

/** Plan a full directive from a semantic intent (data-driven, no sentences). */
export function planDirective(
  intent: BehaviorIntent,
  prevEmotion: Emotion6 = NEUTRAL_EMOTION6,
  opts: { intensity?: number } = {},
): BehaviorDirective {
  const safeIntent: BehaviorIntent = INTENT_EVENT[intent] ? intent : "idle";
  const { label, emotion } = estimateEmotion6(INTENT_EVENT[safeIntent], prevEmotion);
  const channels = mapEmotionToChannels(emotion);
  const body = sanitizeClipName(INTENT_BODY[safeIntent] ?? clipForEvent(INTENT_EVENT[safeIntent]));
  const intensity = Math.max(0.15, Math.min(1, opts.intensity ?? 0.7 * channels.gestureAmplitude + 0.3));
  const headTilt = safeIntent === "thinking" ? -0.1 : safeIntent === "listening" ? 0.07 : safeIntent === "curious" ? 0.12 : 0;
  const headYaw = safeIntent === "thinking" ? -0.15 : 0;
  return {
    intent: safeIntent,
    emotion,
    emotionLabel: label,
    body,
    face: channels.face,
    gaze: INTENT_GAZE[safeIntent],
    headTilt,
    headYaw,
    intensity,
    speed: channels.speakRate,
    recipe: composeRecipe(body, { headTilt, headYaw, durationMs: 2000 }),
    ring: safeIntent === "success" || safeIntent === "celebrate" || safeIntent === "greeting" ? "gold" : safeIntent === "error" ? "rose" : "cyan",
    ringPulse: safeIntent === "success" || safeIntent === "celebrate" ? 1.0 : 0.5,
  };
}

/* ---------------- Motion-memory client (server + local fallback) -------- */

export type MotionOutcome = {
  context: string;
  emotion: string;
  gesture_name: string;
  score: number;
  use_count: number;
};

const MEMORY_WEIGHTS = { semantic: 0.4, history: 0.3, context: 0.15, freshness: 0.1, personality: 0.05 };

export function getMemoryWeights(): Record<string, number> {
  return { ...MEMORY_WEIGHTS };
}

/** Ask the gestures service for the best known motion; null = use planned. */
export async function recommendMotion(
  context: string,
  emotion: string,
  apiBase = "",
): Promise<MotionOutcome | null> {
  try {
    const r = await fetch(
      `${apiBase}/api/v1/motion/recommend?context=${encodeURIComponent(context)}&emotion=${encodeURIComponent(emotion)}`,
      { signal: AbortSignal.timeout(1500) },
    );
    if (!r.ok) return null;
    const j = await r.json();
    if (!j?.gesture_name) return null;
    return { context, emotion, gesture_name: sanitizeClipName(j.gesture_name), score: Number(j.score ?? 0.5), use_count: Number(j.use_count ?? 1) };
  } catch {
    return null;
  }
}

/** Record an outcome (fire-and-forget; metadata only, never raw text — §17). */
export function recordMotionOutcome(
  context: string,
  emotion: string,
  gestureName: string,
  signal: number,
  apiBase = "",
): void {
  const payload = JSON.stringify({
    context: context.slice(0, 64),
    emotion: emotion.slice(0, 32),
    gesture_name: sanitizeClipName(gestureName),
    signal: Math.max(0, Math.min(1, signal)),
  });
  try {
    void fetch(`${apiBase}/api/v1/motion/record`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: payload,
      signal: AbortSignal.timeout(1500),
    });
  } catch { /* offline-safe: memory is enhancement, never blocking */ }
}
