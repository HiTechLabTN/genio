/**
 * mascotBehavior — Emotion Engine + high-level Behavior Planner (2.5D, no GLB).
 *
 * Normalized emotion state drives the 2.5D layered mascot (mascot_cutout.png):
 * valence [-1..1] (negative→positive), arousal [0..1] (calm→excited),
 * confidence [0..1], energy [0..1].
 *
 * The planner maps system events to mascot states consumed by
 * StateLoopAvatar / RiggedMascot / MascotStage. Pure logic, no React,
 * no WebGL — testable in isolation.
 */

export type EmotionState = {
  valence: number;
  arousal: number;
  confidence: number;
  energy: number;
};

export type MascotVisualState =
  | "idle"
  | "thinking"
  | "speaking"
  | "listening"
  | "executing"
  | "success"
  | "error"
  | "greeting";

export type SystemEvent =
  | "assistant.thinking"
  | "assistant.speaking"
  | "assistant.listening"
  | "assistant.greeting"
  | "assistant.idle"
  | "tool.executing"
  | "system.success"
  | "system.error";

export type BehaviorDirective = {
  /** Visual state to render (maps to StateLoopAvatar status / RiggedMascot clip). */
  state: MascotVisualState;
  /** Subtle head tilt in radians (thinking gaze). */
  headTilt: number;
  /** Ring color theme. */
  ring: "cyan" | "gold" | "rose";
  /** Ring pulse intensity 0..1 (ambient cyan pulse, golden flare on success). */
  ringPulse: number;
  /** Lips pulse 0..1 (speaking reactivity). */
  lipsPulse: number;
  /** Audio reactivity gain 0..1. */
  audioGain: number;
  /** Posture hint for the physics driver. */
  posture: "relaxed" | "focused" | "warm" | "reset";
  /** Emotion snapshot after applying this event. */
  emotion: EmotionState;
};

const NEUTRAL: EmotionState = { valence: 0.1, arousal: 0.3, confidence: 0.6, energy: 0.5 };

function clampEmotion(e: EmotionState): EmotionState {
  const c = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v));
  return {
    valence: c(e.valence, -1, 1),
    arousal: c(e.arousal, 0, 1),
    confidence: c(e.confidence, 0, 1),
    energy: c(e.energy, 0, 1),
  };
}

/**
 * Map a system event to a full behavior directive, blending from `prev`
 * emotion toward the event target (smoothing factor 0.55 keeps transitions
 * gentle — no jitter, no snapping).
 */
export function planBehavior(event: SystemEvent, prev: EmotionState = NEUTRAL): BehaviorDirective {
  let target: EmotionState;
  let partial: Omit<BehaviorDirective, "emotion" | "state"> & { state: MascotVisualState };

  switch (event) {
    case "assistant.thinking":
      target = { valence: 0.05, arousal: 0.45, confidence: 0.55, energy: 0.4 };
      partial = {
        state: "thinking",
        headTilt: -0.09,
        ring: "cyan",
        ringPulse: 0.45,
        lipsPulse: 0.08,
        audioGain: 0.1,
        posture: "relaxed",
      };
      break;
    case "assistant.speaking":
      target = { valence: 0.35, arousal: 0.7, confidence: 0.8, energy: 0.7 };
      partial = {
        state: "speaking",
        headTilt: 0.03,
        ring: "cyan",
        ringPulse: 0.6,
        lipsPulse: 1.0,
        audioGain: 1.0,
        posture: "relaxed",
      };
      break;
    case "assistant.listening":
      target = { valence: 0.2, arousal: 0.6, confidence: 0.7, energy: 0.55 };
      partial = {
        state: "listening",
        headTilt: 0.07,
        ring: "cyan",
        ringPulse: 0.55,
        lipsPulse: 0.0,
        audioGain: 0.35,
        posture: "relaxed",
      };
      break;
    case "assistant.greeting":
      target = { valence: 0.6, arousal: 0.75, confidence: 0.85, energy: 0.8 };
      partial = {
        state: "greeting",
        headTilt: 0.05,
        ring: "gold",
        ringPulse: 0.7,
        lipsPulse: 0.4,
        audioGain: 0.5,
        posture: "warm",
      };
      break;
    case "tool.executing":
      target = { valence: 0.0, arousal: 0.55, confidence: 0.75, energy: 0.6 };
      partial = {
        state: "executing",
        headTilt: -0.03,
        ring: "cyan",
        ringPulse: 0.5,
        lipsPulse: 0.05,
        audioGain: 0.15,
        posture: "focused",
      };
      break;
    case "system.success":
      target = { valence: 0.85, arousal: 0.65, confidence: 0.95, energy: 0.75 };
      partial = {
        state: "success",
        headTilt: 0.08,
        ring: "gold",
        ringPulse: 1.0,
        lipsPulse: 0.45,
        audioGain: 0.4,
        posture: "warm",
      };
      break;
    case "system.error":
      target = { valence: -0.45, arousal: 0.5, confidence: 0.35, energy: 0.3 };
      partial = {
        state: "error",
        headTilt: -0.06,
        ring: "rose",
        ringPulse: 0.4,
        lipsPulse: 0.1,
        audioGain: 0.1,
        posture: "reset",
      };
      break;
    case "assistant.idle":
    default:
      target = { valence: 0.1, arousal: 0.3, confidence: 0.6, energy: 0.5 };
      partial = {
        state: "idle",
        headTilt: 0.0,
        ring: "cyan",
        ringPulse: 0.3,
        lipsPulse: 0.0,
        audioGain: 0.0,
        posture: "relaxed",
      };
      break;
  }

  const k = 0.55;
  const emotion = clampEmotion({
    valence: prev.valence + (target.valence - prev.valence) * k,
    arousal: prev.arousal + (target.arousal - prev.arousal) * k,
    confidence: prev.confidence + (target.confidence - prev.confidence) * k,
    energy: prev.energy + (target.energy - prev.energy) * k,
  });

  return { ...partial, emotion };
}

/** Initial neutral directive (app boot). */
export function initialBehavior(): BehaviorDirective {
  return planBehavior("assistant.idle", NEUTRAL);
}

export const NEUTRAL_EMOTION: EmotionState = { ...NEUTRAL };

/* ------------------------------------------------------------------ */
/* Master v2 — 6-dimension emotion estimator (valence, arousal,         */
/* confidence, attention, energy, urgency). The 4-dim planner above is  */
/* kept for backward compatibility; the 6-dim estimator below feeds    */
/* the master runtime (face/gaze/posture/voice mapping).               */
/* ------------------------------------------------------------------ */

export type Emotion6 = {
  valence: number; // [-1, 1]
  arousal: number; // [0, 1]
  confidence: number; // [0, 1]
  attention: number; // [0, 1]
  energy: number; // [0, 1]
  urgency: number; // [0, 1]
};

export const NEUTRAL_EMOTION6: Emotion6 = {
  valence: 0.1,
  arousal: 0.3,
  confidence: 0.6,
  attention: 0.55,
  energy: 0.5,
  urgency: 0.2,
};

export type EmotionLabel =
  | "happy"
  | "sad"
  | "angry"
  | "confused"
  | "curious"
  | "neutral"
  | "focused"
  | "surprised";

/** Estimate a 6-dim emotion from a system event + previous state (smoothed).
 *  Accepts any event name string; unknown events map to neutral. */
export function estimateEmotion6(
  event: string,
  prev: Emotion6 = NEUTRAL_EMOTION6,
): { label: EmotionLabel; emotion: Emotion6 } {
  let target: Emotion6;
  let label: EmotionLabel;
  switch (event) {
    case "assistant.speaking":
      target = { valence: 0.4, arousal: 0.7, confidence: 0.8, attention: 0.8, energy: 0.7, urgency: 0.3 };
      label = "happy";
      break;
    case "assistant.thinking":
      target = { valence: 0.0, arousal: 0.45, confidence: 0.55, attention: 0.85, energy: 0.4, urgency: 0.4 };
      label = "focused";
      break;
    case "assistant.listening":
    case "user.message.received":
      target = { valence: 0.2, arousal: 0.6, confidence: 0.7, attention: 0.95, energy: 0.55, urgency: 0.25 };
      label = "curious";
      break;
    case "tool.executing":
      target = { valence: 0.0, arousal: 0.55, confidence: 0.75, attention: 0.9, energy: 0.6, urgency: 0.55 };
      label = "focused";
      break;
    case "system.success":
    case "tool.success":
      target = { valence: 0.85, arousal: 0.65, confidence: 0.95, attention: 0.7, energy: 0.75, urgency: 0.15 };
      label = "happy";
      break;
    case "system.error":
    case "tool.error":
      target = { valence: -0.45, arousal: 0.5, confidence: 0.35, attention: 0.7, energy: 0.3, urgency: 0.6 };
      label = event === "system.error" || event === "tool.error" ? "confused" : "sad";
      break;
    case "assistant.greeting":
      target = { valence: 0.65, arousal: 0.75, confidence: 0.85, attention: 0.9, energy: 0.8, urgency: 0.2 };
      label = "happy";
      break;
    default:
      target = { ...NEUTRAL_EMOTION6 };
      label = "neutral";
      break;
  }
  const k = 0.55;
  const c = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v));
  const emotion: Emotion6 = {
    valence: c(prev.valence + (target.valence - prev.valence) * k, -1, 1),
    arousal: c(prev.arousal + (target.arousal - prev.arousal) * k, 0, 1),
    confidence: c(prev.confidence + (target.confidence - prev.confidence) * k, 0, 1),
    attention: c(prev.attention + (target.attention - prev.attention) * k, 0, 1),
    energy: c(prev.energy + (target.energy - prev.energy) * k, 0, 1),
    urgency: c(prev.urgency + (target.urgency - prev.urgency) * k, 0, 1),
  };
  return { label, emotion };
}

/** Map 6-dim emotion → face/gaze/posture/voice weights (master runtime). */
export function mapEmotionToChannels(e: Emotion6): {
  face: Record<string, number>;
  gazeEnergy: number;
  gestureAmplitude: number;
  speakRate: number;
  posture: "relaxed" | "focused" | "warm" | "reset";
  lightWarmth: number;
} {
  const pos = Math.max(0, e.valence);
  const neg = Math.max(0, -e.valence);
  const face: Record<string, number> = {
    Smile: +(pos * 0.9).toFixed(3),
    MouthSmile: +(pos * 0.7).toFixed(3),
    CheekRaise_L: +(pos * 0.4).toFixed(3),
    CheekRaise_R: +(pos * 0.4).toFixed(3),
    Frown: +(neg * 0.7).toFixed(3),
    MouthFrown: +(neg * 0.6).toFixed(3),
    BrowDown_L: +(neg * 0.5).toFixed(3),
    BrowDown_R: +(neg * 0.5).toFixed(3),
    BrowUp_L: +((1 - neg) * e.attention * 0.4).toFixed(3),
    BrowUp_R: +((1 - neg) * e.attention * 0.4).toFixed(3),
    EyeWide_L: +(e.arousal * e.attention * 0.35).toFixed(3),
    EyeWide_R: +(e.arousal * e.attention * 0.35).toFixed(3),
  };
  return {
    face,
    gazeEnergy: +(0.3 + e.attention * 0.7).toFixed(3),
    gestureAmplitude: +(0.35 + e.energy * 0.65).toFixed(3),
    speakRate: +(0.9 + e.energy * 0.25 - neg * 0.15).toFixed(3),
    posture: neg > 0.35 ? "reset" : pos > 0.5 ? "warm" : e.attention > 0.75 ? "focused" : "relaxed",
    lightWarmth: +pos.toFixed(3),
  };
}
