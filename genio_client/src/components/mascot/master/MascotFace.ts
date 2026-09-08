/**
 * MascotFace — expression controller + phoneme/viseme lip-sync (§6, §7).
 *
 * FACE layer combines morph weights (smile 0.7 + browUp 0.2 + squint 0.15).
 * LIPS layer maps viseme groups to mouth morphs + Jaw bone, consuming an
 * optional timing provider (Genio TTS timing API) or falling back to the
 * live audio level (adapter interface below).
 */
import * as THREE from "three";

/** Viseme groups required by the master spec (§7). */
export const VISEME_GROUPS = [
  "AA", "AE", "AH", "AO", "EH", "ER", "IH", "IY", "OH", "OU", "UH",
  "BMP", "FV", "L", "TH", "TD", "KG", "SZ", "SH", "CH", "R", "WQ",
] as const;

export type Viseme = (typeof VISEME_GROUPS)[number] | "REST";

/** Viseme → mouth morph weights (combined, never mutually exclusive). */
const VISEME_MAP: Record<Viseme, { MouthOpen: number; JawOpen: number; LipPucker: number; LipPress: number; MouthSmile: number }> = {
  REST: { MouthOpen: 0, JawOpen: 0, LipPucker: 0, LipPress: 0, MouthSmile: 0 },
  AA: { MouthOpen: 0.9, JawOpen: 0.85, LipPucker: 0, LipPress: 0, MouthSmile: 0.1 },
  AE: { MouthOpen: 0.7, JawOpen: 0.6, LipPucker: 0, LipPress: 0, MouthSmile: 0.25 },
  AH: { MouthOpen: 0.6, JawOpen: 0.55, LipPucker: 0, LipPress: 0, MouthSmile: 0.1 },
  AO: { MouthOpen: 0.75, JawOpen: 0.6, LipPucker: 0.3, LipPress: 0, MouthSmile: 0 },
  EH: { MouthOpen: 0.5, JawOpen: 0.4, LipPucker: 0, LipPress: 0, MouthSmile: 0.2 },
  ER: { MouthOpen: 0.45, JawOpen: 0.35, LipPucker: 0.25, LipPress: 0, MouthSmile: 0 },
  IH: { MouthOpen: 0.35, JawOpen: 0.25, LipPucker: 0, LipPress: 0, MouthSmile: 0.3 },
  IY: { MouthOpen: 0.3, JawOpen: 0.2, LipPucker: 0, LipPress: 0, MouthSmile: 0.4 },
  OH: { MouthOpen: 0.6, JawOpen: 0.45, LipPucker: 0.55, LipPress: 0, MouthSmile: 0 },
  OU: { MouthOpen: 0.4, JawOpen: 0.3, LipPucker: 0.7, LipPress: 0, MouthSmile: 0 },
  UH: { MouthOpen: 0.45, JawOpen: 0.35, LipPucker: 0.4, LipPress: 0, MouthSmile: 0 },
  BMP: { MouthOpen: 0.05, JawOpen: 0.02, LipPucker: 0, LipPress: 0.9, MouthSmile: 0 },
  FV: { MouthOpen: 0.15, JawOpen: 0.08, LipPucker: 0, LipPress: 0.6, MouthSmile: 0 },
  L: { MouthOpen: 0.3, JawOpen: 0.2, LipPucker: 0, LipPress: 0.2, MouthSmile: 0.1 },
  TH: { MouthOpen: 0.25, JawOpen: 0.15, LipPucker: 0, LipPress: 0.3, MouthSmile: 0 },
  TD: { MouthOpen: 0.2, JawOpen: 0.12, LipPucker: 0, LipPress: 0.4, MouthSmile: 0 },
  KG: { MouthOpen: 0.35, JawOpen: 0.3, LipPucker: 0, LipPress: 0, MouthSmile: 0 },
  SZ: { MouthOpen: 0.2, JawOpen: 0.1, LipPucker: 0, LipPress: 0.35, MouthSmile: 0.15 },
  SH: { MouthOpen: 0.3, JawOpen: 0.15, LipPucker: 0.5, LipPress: 0, MouthSmile: 0 },
  CH: { MouthOpen: 0.35, JawOpen: 0.2, LipPucker: 0.45, LipPress: 0, MouthSmile: 0 },
  R: { MouthOpen: 0.35, JawOpen: 0.25, LipPucker: 0.5, LipPress: 0, MouthSmile: 0 },
  WQ: { MouthOpen: 0.35, JawOpen: 0.25, LipPucker: 0.65, LipPress: 0, MouthSmile: 0 },
};

/** Timing provider adapter — plug Genio TTS timing here when available. */
export interface LipSyncTimingProvider {
  /** Current viseme + progress 0..1, or null when no timing info. */
  currentViseme(now: number): { viseme: Viseme; weight: number } | null;
}

function findMorphMeshes(root: THREE.Object3D): THREE.SkinnedMesh[] {
  const out: THREE.SkinnedMesh[] = [];
  root.traverse((o) => {
    const m = o as THREE.SkinnedMesh;
    if (m.isSkinnedMesh && m.morphTargetDictionary && m.morphTargetInfluences) out.push(m);
  });
  return out;
}

export class ExpressionController {
  private meshes: THREE.SkinnedMesh[];
  private current: Record<string, number> = {};
  private target: Record<string, number> = {};

  constructor(root: THREE.Object3D) {
    this.meshes = findMorphMeshes(root);
  }

  get meshCount(): number {
    return this.meshes.length;
  }

  /** Set a combined expression (weights 0..1 each, clamped to morph bounds). */
  setExpression(expr: Record<string, number>): void {
    for (const [k, v] of Object.entries(expr)) {
      this.target[k] = Math.max(0, Math.min(1, v));
    }
  }

  /** Clear expression keys back toward 0. */
  relax(keys?: string[]): void {
    const ks = keys ?? Object.keys(this.target);
    for (const k of ks) this.target[k] = 0;
  }

  /** Smoothly approach targets (call each frame). */
  update(rate = 0.18): void {
    for (const m of this.meshes) {
      const dict = m.morphTargetDictionary as Record<string, number>;
      const infl = m.morphTargetInfluences as number[];
      for (const [k, t] of Object.entries(this.target)) {
        const idx = dict[k];
        if (idx === undefined) continue;
        const cur = this.current[k] ?? 0;
        const next = cur + (t - cur) * rate;
        this.current[k] = next;
        infl[idx] = next;
      }
    }
  }
}

export class LipSyncDriver {
  private expr: ExpressionController;
  private jaw: THREE.Bone | null = null;
  private provider: LipSyncTimingProvider | null = null;
  private t = 0;

  constructor(root: THREE.Object3D, expr: ExpressionController) {
    this.expr = expr;
    root.traverse((o) => {
      const b = o as THREE.Bone;
      if (b.isBone && (b.name === "Jaw" || b.name === "jaw") && !this.jaw) this.jaw = b;
    });
  }

  setTimingProvider(p: LipSyncTimingProvider | null): void {
    this.provider = p;
  }

  /** Drive lips from timing provider or estimated audio level (0..1). */
  update(dt: number, audioLevel: number, speaking: boolean): void {
    this.t += dt;
    if (!speaking) {
      this.expr.relax(["MouthOpen", "JawOpen", "LipPucker", "LipPress"]);
      if (this.jaw) this.jaw.rotation.x *= 0.85;
      return;
    }
    const timed = this.provider?.currentViseme(performance.now()) ?? null;
    if (timed) {
      const w = VISEME_MAP[timed.viseme] ?? VISEME_MAP.REST;
      const scaled: Record<string, number> = {};
      for (const [k, v] of Object.entries(w)) scaled[k] = v * timed.weight;
      this.expr.setExpression(scaled);
      if (this.jaw) this.jaw.rotation.x = (w.JawOpen * timed.weight) * 0.35;
      return;
    }
    // Fallback: audio-level estimation cycling open visemes (never frozen).
    const cyc: Viseme[] = ["AA", "EH", "OH", "AE", "OU"];
    const v = cyc[Math.floor(this.t * 7) % cyc.length];
    const w = VISEME_MAP[v];
    const amp = Math.min(1, 0.3 + audioLevel * 1.4);
    this.expr.setExpression({
      MouthOpen: w.MouthOpen * amp,
      JawOpen: w.JawOpen * amp,
      LipPucker: w.LipPucker * amp,
    });
    if (this.jaw) this.jaw.rotation.x = w.JawOpen * amp * 0.35;
  }
}
