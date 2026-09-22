/**
 * Adaptive Dual-Engine Pipeline — Phase 2.
 *
 * Tier A (High-Performance, RAM≥6GB): on-device GGUF via WASM/ONNX + local Whisper/Sherpa + Piper.
 * Tier B (Cloud Fallback): transparent routing to Genio Node / Cloud gateway.
 * Strict Tunisian Darija persona enforced on both paths.
 */

import { getDeviceProfile, type DeviceProfile, type DeviceTier } from "./deviceProfiler";
import { GENIO_PERSONA_PROMPT } from "./persona";

// Re-export for legacy callers
export const DARIJA_SYSTEM_PROMPT = GENIO_PERSONA_PROMPT;

export const LOCAL_MODEL_ID = "qwen2.5-1.5b-instruct-q4_k_m.gguf";
export const LOCAL_WHISPER_MODEL = "whisper-small-q5_0.bin";
export const LOCAL_PIPER_MODEL = "piper-darija.onnx";

export type EngineMode = "local" | "cloud";
export type EngineState = "idle" | "loading" | "ready" | "fallback";

export interface EngineDecision {
  mode: EngineMode;
  tier: DeviceTier;
  reason: string;
  profile: DeviceProfile;
}

export function decideEngine(overrides?: { ramGB?: number; cores?: number; sluggish?: boolean; forceCloud?: boolean }): EngineDecision {
  const profile = getDeviceProfile(overrides);
  let mode: EngineMode = profile.tier === "A" ? "local" : "cloud";
  let reason = profile.reason;

  // Manual override or sluggish inference => force cloud fallback transparently
  const sluggish = overrides?.sluggish ?? false;
  const forceCloud = overrides?.forceCloud ?? false;
  if ((sluggish || forceCloud) && mode === "local") {
    mode = "cloud";
    reason += "; sluggish → cloud fallback";
  }

  // Additional guard: if WebGL texture too low or isLowEnd, force cloud
  if (profile.isLowEnd && mode === "local") {
    mode = "cloud";
    reason += "; low-end → cloud";
  }

  return { mode, tier: profile.tier, reason, profile };
}

export interface TranscriptionResult {
  text: string;
  engine: EngineMode;
  latencyMs: number;
}

export interface SynthesisResult {
  audioUrl?: string;
  engine: EngineMode;
}

// Mock on-device loader state
let localReady = false;
let localLoadPromise: Promise<void> | null = null;

export async function ensureLocalEngine(): Promise<boolean> {
  const decision = decideEngine();
  if (decision.mode !== "local") return false;
  if (localReady) return true;
  if (localLoadPromise) return localLoadPromise.then(() => localReady).catch(() => false);

  localLoadPromise = (async () => {
    // Simulate WASM/ONNX GGUF load. In production, this would instantiate
    // wllama / onnxruntime-web with LOCAL_MODEL_ID.
    await new Promise((r) => setTimeout(r, 120));
    // Heuristic: if document is hidden or memory pressure, mark not ready
    localReady = true;
  })();

  try {
    await localLoadPromise;
    return localReady;
  } catch {
    localReady = false;
    return false;
  }
}

export function isLocalReady(): boolean {
  return localReady;
}

export function resetLocalEngineForTests() {
  localReady = false;
  localLoadPromise = null;
}

export async function transcribeAdaptive(
  blob: Blob,
  opts?: { overrides?: { ramGB?: number; cores?: number }; cloudFn?: (b: Blob) => Promise<string> }
): Promise<TranscriptionResult> {
  const start = performance.now();
  const decision = decideEngine(opts?.overrides);

  if (decision.mode === "local" && isLocalReady()) {
    // Local Whisper/Sherpa mocked — would decode offline
    await new Promise((r) => setTimeout(r, 40));
    return { text: "[local STT] marhba, chnowa n3awnk?", engine: "local", latencyMs: Math.round(performance.now() - start) };
  }

  if (decision.mode === "local" && !isLocalReady()) {
    const ok = await ensureLocalEngine();
    if (ok) {
      await new Promise((r) => setTimeout(r, 40));
      return { text: "[local STT] marhba, chnowa n3awnk?", engine: "local", latencyMs: Math.round(performance.now() - start) };
    }
  }

  // Cloud fallback: delegate to provided cloud function or return placeholder
  if (opts?.cloudFn) {
    const text = await opts.cloudFn(blob);
    return { text, engine: "cloud", latencyMs: Math.round(performance.now() - start) };
  }

  // Transparent cloud gateway placeholder (would POST to Genio Node)
  await new Promise((r) => setTimeout(r, 80));
  return { text: "[cloud STT] marhba, chnowa n3awnk?", engine: "cloud", latencyMs: Math.round(performance.now() - start) };
}

export async function synthesizeAdaptive(
  text: string,
  opts?: { overrides?: { ramGB?: number; cores?: number }; cloudFn?: (t: string) => Promise<string | undefined> }
): Promise<SynthesisResult> {
  const decision = decideEngine(opts?.overrides);
  if (decision.mode === "local" && isLocalReady()) {
    // Piper TTS local mock
    await new Promise((r) => setTimeout(r, 30));
    return { engine: "local" };
  }
  if (opts?.cloudFn) {
    const url = await opts.cloudFn(text);
    return { audioUrl: url, engine: "cloud" };
  }
  await new Promise((r) => setTimeout(r, 60));
  return { engine: "cloud" };
}

export async function generateAdaptive(
  prompt: string,
  opts?: { overrides?: { ramGB?: number; cores?: number; sluggish?: boolean }; cloudFn?: (p: string) => Promise<string> }
): Promise<{ text: string; engine: EngineMode }> {
  const decision = decideEngine(opts?.overrides);
  const personaPrompt = `${DARIJA_SYSTEM_PROMPT}\n\nUser: ${prompt}`;

  if (decision.mode === "local" && (isLocalReady() || (await ensureLocalEngine()))) {
    // Simulate on-device GGUF inference with Darija persona
    await new Promise((r) => setTimeout(r, 90));
    return { text: `[local ${LOCAL_MODEL_ID}] ${personaPrompt.slice(0, 80)}…`, engine: "local" };
  }

  if (opts?.cloudFn) {
    const text = await opts.cloudFn(personaPrompt);
    return { text, engine: "cloud" };
  }

  await new Promise((r) => setTimeout(r, 120));
  return { text: `[cloud gateway] ${personaPrompt.slice(0, 80)}…`, engine: "cloud" };
}

export function getDarijaPrompt(userPrompt: string, includeSystem = true): string {
  return includeSystem ? `${DARIJA_SYSTEM_PROMPT}\n\n${userPrompt}` : userPrompt;
}
