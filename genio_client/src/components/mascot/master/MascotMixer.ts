/**
 * MascotMixer — layered animation architecture over THREE.AnimationMixer (§14)
 * + motion graph / state machine (§21) + constrained procedural composer (§20).
 *
 * Layers: BASE / UPPER_BODY / HEAD / SPECIAL. FACE + LIPS + SECONDARY are
 * driven at runtime (morphs / bones), not by baked clips.
 * Uses the official three.js AnimationMixer API (fadeIn/fadeOut, weights).
 */
import * as THREE from "three";
import { sanitizeClipName } from "./MascotEventBridge";

export type MixerLayer = "BASE" | "UPPER_BODY" | "HEAD" | "SPECIAL";

export type TransitionRule = {
  priority: number;
  interruptible: boolean;
  blendDuration: number;
  cooldownMs: number;
  minDurationMs: number;
};

const DEFAULT_RULE: TransitionRule = {
  priority: 1,
  interruptible: true,
  blendDuration: 0.35,
  cooldownMs: 400,
  minDurationMs: 600,
};

const RULES: Record<string, Partial<TransitionRule>> = {
  idle: { priority: 0, blendDuration: 0.5, cooldownMs: 0, minDurationMs: 0 },
  greeting: { priority: 5, interruptible: false, minDurationMs: 1400 },
  wave: { priority: 5, interruptible: false, minDurationMs: 1200 },
  hero: { priority: 6, interruptible: false, minDurationMs: 1500 },
  error_reaction: { priority: 7, minDurationMs: 900 },
  warning: { priority: 7, minDurationMs: 800 },
  success: { priority: 6, minDurationMs: 1000 },
  celebrate: { priority: 6, minDurationMs: 1200 },
  speak: { priority: 3, minDurationMs: 500 },
  think: { priority: 2, minDurationMs: 800 },
  listen: { priority: 2, minDurationMs: 800 },
};

export function ruleFor(clip: string): TransitionRule {
  return { ...DEFAULT_RULE, ...(RULES[clip] ?? {}) };
}

/** Layer assignment: full-body clips own BASE; gestures overlay UPPER/HEAD. */
export function layerFor(clip: string): MixerLayer {
  if (["idle", "idle_variant_01", "idle_variant_02", "idle_thinking", "walk", "run", "sit", "stand", "sleep", "wake", "step_forward", "step_backward", "turn_left", "turn_right"].includes(clip)) return "BASE";
  if (["hero", "celebrate", "success", "greeting", "wave", "excited", "happy", "sad", "angry"].includes(clip)) return "SPECIAL";
  if (["nod", "shake_head", "look_left", "look_right", "look_up", "look_down", "agree", "disagree", "think", "listen", "listen_attentive", "curious", "confused", "surprised", "wait"].includes(clip)) return "HEAD";
  return "UPPER_BODY";
}

export class LayeredMixer {
  private mixer: THREE.AnimationMixer;
  private clips: Map<string, THREE.AnimationClip>;
  private active: Partial<Record<MixerLayer, { action: THREE.AnimationAction; clip: string; startedAt: number }>> = {};
  private lastSwitchAt: Partial<Record<MixerLayer, number>> = {};
  weights: Partial<Record<MixerLayer, number>> = {};

  constructor(root: THREE.Object3D, clips: THREE.AnimationClip[]) {
    this.mixer = new THREE.AnimationMixer(root);
    this.clips = new Map(clips.map((c) => [c.name, c]));
  }

  get threeMixer(): THREE.AnimationMixer {
    return this.mixer;
  }

  clipNames(): string[] {
    return [...this.clips.keys()];
  }

  /** Play a clip on its layer with crossfade; returns false if rejected by rules. */
  play(rawClip: string, now = performance.now(), opts?: { force?: boolean; timeScale?: number }): boolean {
    const clip = sanitizeClipName(rawClip);
    const layer = layerFor(clip);
    const rule = ruleFor(clip);
    const cur = this.active[layer];
    if (cur && !opts?.force) {
      const elapsed = now - cur.startedAt;
      if (elapsed < ruleFor(cur.clip).minDurationMs && !ruleFor(cur.clip).interruptible) return false;
      if (elapsed < rule.minDurationMs * 0 && false) return false;
      const last = this.lastSwitchAt[layer] ?? 0;
      if (now - last < rule.cooldownMs && cur.clip !== clip) return false;
      if (rule.priority < ruleFor(cur.clip).priority) return false;
    }
    const threeClip = this.clips.get(clip) ?? this.clips.get("idle");
    if (!threeClip) return false;
    const action = this.mixer.clipAction(threeClip);
    action.enabled = true;
    if (opts?.timeScale) action.timeScale = opts.timeScale;
    action.reset().fadeIn(rule.blendDuration).play();
    if (cur && cur.clip !== threeClip.name) {
      try {
        cur.action.fadeOut(rule.blendDuration);
      } catch { /* ignore */ }
    }
    this.active[layer] = { action, clip: threeClip.name, startedAt: now };
    this.lastSwitchAt[layer] = now;
    this.weights[layer] = 1;
    return true;
  }

  /** Stop a layer gracefully. */
  stopLayer(layer: MixerLayer, fade = 0.3): void {
    const cur = this.active[layer];
    if (!cur) return;
    try {
      cur.action.fadeOut(fade);
    } catch { /* ignore */ }
    delete this.active[layer];
  }

  currentClip(layer?: MixerLayer): string | null {
    if (layer) return this.active[layer]?.clip ?? null;
    return this.active["SPECIAL"]?.clip ?? this.active["UPPER_BODY"]?.clip ?? this.active["HEAD"]?.clip ?? this.active["BASE"]?.clip ?? null;
  }

  update(dt: number): void {
    this.mixer.update(dt);
  }

  dispose(): void {
    this.mixer.stopAllAction();
  }
}

/* ---------------- Procedural composer (§20) ---------------- */

export type JointLimits = Record<string, { min: number; max: number }>;

export const DEFAULT_JOINT_LIMITS: JointLimits = {
  Head: { min: -0.5, max: 0.5 },
  Neck: { min: -0.35, max: 0.35 },
  UpperArm: { min: -2.6, max: 2.6 },
  Jaw: { min: 0, max: 0.35 },
  Spine: { min: -0.3, max: 0.3 },
};

export type MotionRecipe = {
  base: string;
  headTilt?: number;
  headYaw?: number;
  browRaise?: number;
  audioGain?: number;
  durationMs: number;
};

/**
 * Compose a safe variation of an existing clip (never invents poses outside
 * joint limits; foot grounding preserved because Root translation is untouched).
 */
export function composeRecipe(
  base: string,
  opts: { headTilt?: number; headYaw?: number; browRaise?: number; audioGain?: number; durationMs?: number } = {},
): MotionRecipe {
  const lim = DEFAULT_JOINT_LIMITS;
  const clamp = (v: number, b: { min: number; max: number }) => Math.max(b.min, Math.min(b.max, v));
  return {
    base: sanitizeClipName(base),
    headTilt: opts.headTilt !== undefined ? clamp(opts.headTilt, lim.Head) : 0,
    headYaw: opts.headYaw !== undefined ? clamp(opts.headYaw, lim.Head) : 0,
    browRaise: opts.browRaise !== undefined ? Math.max(0, Math.min(1, opts.browRaise)) : 0,
    audioGain: opts.audioGain !== undefined ? Math.max(0, Math.min(1, opts.audioGain)) : 0,
    durationMs: Math.max(400, Math.min(9000, opts.durationMs ?? 2000)),
  };
}
