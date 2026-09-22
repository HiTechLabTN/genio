/**
 * MascotLife — eyes/micro-movements (§8) + secondary-motion springs (§11).
 *
 * Idle is stochastic but constrained: seeded RNG for deterministic tests,
 * asymmetric blinks, saccades, breathing, head/shoulder micro-motion.
 * Secondary motion: deterministic spring/damper per bone with damping,
 * max displacement/velocity, teleport reset, pause/resume, reduced-motion.
 */
import * as THREE from "three";

/** Seeded RNG (mulberry32) — deterministic when a seed is given. */
export function seededRng(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export type LifeOptions = {
  seed?: number;
  reducedMotion?: boolean;
  gazeEnergy?: number;
};

export class IdleLife {
  private rng: () => number;
  private nextBlinkAt = 2.5;
  private blinkT = -1;
  private nextSaccadeAt = 1.5;
  private gazeX = 0;
  private gazeY = 0;
  private t = 0;
  private head: THREE.Bone | null = null;
  private eyeL: THREE.Bone | null = null;
  private eyeR: THREE.Bone | null = null;
  private reduced = false;
  private gazeEnergy = 1;

  constructor(root: THREE.Object3D, opts: LifeOptions = {}) {
    this.rng = seededRng(opts.seed ?? ((Math.random() * 1e9) | 0));
    this.reduced = !!opts.reducedMotion;
    this.gazeEnergy = opts.gazeEnergy ?? 1;
    root.traverse((o) => {
      const b = o as THREE.Bone;
      if (!b.isBone) return;
      const n = b.name.toLowerCase();
      if ((n === "head") && !this.head) this.head = b;
      if ((n === "eye.l") && !this.eyeL) this.eyeL = b;
      if ((n === "eye.r") && !this.eyeR) this.eyeR = b;
    });
  }

  setReducedMotion(v: boolean): void {
    this.reduced = v;
  }

  /** Returns blink 0..1 for morphs (asymmetric: L/R offset). */
  update(dt: number): { blinkL: number; blinkR: number; breath: number } {
    this.t += dt;
    const amp = this.reduced ? 0.25 : 1;
    if (this.t >= this.nextBlinkAt) {
      this.blinkT = 0;
      this.nextBlinkAt = this.t + 2.8 + this.rng() * 2.4;
    }
    let blinkL = 0;
    let blinkR = 0;
    if (this.blinkT >= 0) {
      this.blinkT += dt;
      const d = 0.14;
      const p = this.blinkT / d;
      if (p >= 1) {
        this.blinkT = -1;
      } else {
        const s = Math.sin(p * Math.PI);
        blinkL = s;
        blinkR = Math.sin(Math.min(1, p * 1.12) * Math.PI) * 0.96;
      }
    }
    if (this.t >= this.nextSaccadeAt) {
      this.nextSaccadeAt = this.t + 0.9 + this.rng() * 2.2;
      this.gazeX = (this.rng() - 0.5) * 0.5 * this.gazeEnergy * amp;
      this.gazeY = (this.rng() - 0.5) * 0.3 * this.gazeEnergy * amp;
    }
    const breath = Math.sin(this.t * 1.4) * 0.5 + 0.5;
    if (this.head && !this.reduced) {
      this.head.rotation.y += (this.gazeX * 0.4 - this.head.rotation.y) * 0.06;
      this.head.rotation.x += (Math.sin(this.t * 0.6) * 0.02 - this.head.rotation.x) * 0.05;
    }
    if (this.eyeL) {
      this.eyeL.rotation.y = this.gazeX * 0.6;
      this.eyeL.rotation.x = this.gazeY * 0.5;
    }
    if (this.eyeR) {
      this.eyeR.rotation.y = this.gazeX * 0.6;
      this.eyeR.rotation.x = this.gazeY * 0.5;
    }
    return { blinkL, blinkR, breath };
  }
}

/* ---------------- Secondary-motion springs ---------------- */

export type SpringConfig = {
  damping: number;
  stiffness: number;
  maxDisplacement: number;
  maxVelocity: number;
};

const DEFAULT_SPRING: SpringConfig = {
  damping: 6.5,
  stiffness: 42,
  maxDisplacement: 0.35,
  maxVelocity: 2.5,
};

type SpringState = { x: number; v: number };

/**
 * SpringBone chain driver for secondary bones (Beard, Hair, Chachia_Tassel,
 * Jebba...). Semi-implicit Euler, clamped, teleport-safe.
 */
export class SecondaryMotion {
  private bones: THREE.Bone[] = [];
  private states: SpringState[] = [];
  private cfg: SpringConfig;
  private paused = false;
  private reduced = false;

  constructor(root: THREE.Object3D, cfg: Partial<SpringConfig> = {}) {
    this.cfg = { ...DEFAULT_SPRING, ...cfg };
    const names = ["beard", "hair", "chachia_tassel", "chachia", "jebba", "jebba.l", "jebba.r"];
    root.traverse((o) => {
      const b = o as THREE.Bone;
      if (b.isBone && names.includes(b.name.toLowerCase())) this.bones.push(b);
    });
    this.states = this.bones.map(() => ({ x: 0, v: 0 }));
  }

  get boneCount(): number {
    return this.bones.length;
  }

  setPaused(v: boolean): void {
    this.paused = v;
  }

  setReducedMotion(v: boolean): void {
    this.reduced = v;
  }

  /** Teleport/reset: zero all spring energy (call on clip cuts, seeks). */
  reset(): void {
    for (const s of this.states) {
      s.x = 0;
      s.v = 0;
    }
  }

  /** Drive with parent angular velocity proxy (head/chest sway energy 0..1). */
  update(dt: number, energy: number): void {
    if (this.paused || this.reduced || dt <= 0) return;
    const c = Math.min(dt, 1 / 30);
    for (let i = 0; i < this.bones.length; i++) {
      const s = this.states[i];
      const target = Math.sin(performance.now() / 1000 + i * 1.7) * 0.12 * energy;
      const F = (target - s.x) * this.cfg.stiffness - s.v * this.cfg.damping;
      s.v = THREE.MathUtils.clamp(s.v + F * c, -this.cfg.maxVelocity, this.cfg.maxVelocity);
      s.x = THREE.MathUtils.clamp(s.x + s.v * c, -this.cfg.maxDisplacement, this.cfg.maxDisplacement);
      this.bones[i].rotation.x = s.x;
      this.bones[i].rotation.z = s.x * 0.6;
    }
  }
}
