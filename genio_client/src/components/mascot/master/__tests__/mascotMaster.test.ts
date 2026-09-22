/** Master mascot unit tests (§29): emotion, behavior, scoring, transitions, visemes. */
import { describe, it, expect } from "vitest";
import {
  planBehavior,
  estimateEmotion6,
  mapEmotionToChannels,
  NEUTRAL_EMOTION6,
} from "../../../../services/mascotBehavior";
import {
  clipForEvent,
  sanitizeClipName,
  deriveEvents,
} from "../MascotEventBridge";
import {
  ruleFor,
  layerFor,
  composeRecipe,
  DEFAULT_JOINT_LIMITS,
} from "../MascotMixer";
import { VISEME_GROUPS } from "../MascotFace";
import { seededRng } from "../MascotLife";
import { planDirective, getMemoryWeights } from "../MascotController";
import { isRenderableEvent, cleanAnswerText } from "../../../../lib/chatSanitize";

describe("emotion mapping", () => {
  it("thinking lowers energy vs speaking", () => {
    const t = estimateEmotion6("assistant.thinking");
    const s = estimateEmotion6("assistant.speaking");
    expect(t.emotion.energy).toBeLessThan(s.emotion.energy);
    expect(s.label).toBe("happy");
  });
  it("unknown events map to neutral without throwing", () => {
    const r = estimateEmotion6("nonsense.event.xyz");
    expect(r.label).toBe("neutral");
    expect(r.emotion.valence).toBeCloseTo(NEUTRAL_EMOTION6.valence, 1);
  });
  it("channels stay in bounds", () => {
    const c = mapEmotionToChannels({ valence: -0.8, arousal: 0.9, confidence: 0.2, attention: 0.9, energy: 0.7, urgency: 0.8 });
    expect(c.face.Frown).toBeGreaterThan(0.3);
    expect(c.posture).toBe("reset");
    expect(c.gestureAmplitude).toBeGreaterThanOrEqual(0.35);
    expect(c.gestureAmplitude).toBeLessThanOrEqual(1);
  });
  it("legacy 4-dim planner still works", () => {
    const d = planBehavior("assistant.speaking");
    expect(d.state).toBe("speaking");
    expect(d.lipsPulse).toBe(1.0);
  });
});

describe("behavior selection", () => {
  it("greeting directive uses greeting clip + gold ring", () => {
    const d = planDirective("greeting");
    expect(d.body).toBe("greeting");
    expect(d.ring).toBe("gold");
    expect(d.gaze).toBe("user");
  });
  it("unknown intent falls back to idle safely", () => {
    const d = planDirective("nonexistent" as never);
    expect(d.body).toBe("idle");
  });
  it("memory weights sum to 1", () => {
    const w = getMemoryWeights();
    expect(Object.values(w).reduce((a, b) => a + b, 0)).toBeCloseTo(1, 5);
  });
});

describe("event bridge", () => {
  it("maps thinking status to think event", () => {
    const evs = deriveEvents({ kind: "thinking" }, { kind: "idle" }, 0, 0, false, false);
    expect(evs.map((e) => e.name)).toContain("assistant.thinking.started");
    expect(clipForEvent("assistant.thinking.started")).toBe("think");
  });
  it("rejects arbitrary animation names (security)", () => {
    expect(sanitizeClipName("../../etc/passwd")).toBe("idle");
    expect(sanitizeClipName("wave; rm -rf")).toBe("idle");
    expect(sanitizeClipName("wave")).toBe("wave");
    expect(sanitizeClipName(123)).toBe("idle");
  });
});

describe("transition rules + layers", () => {
  it("greeting outranks idle and is not interruptible", () => {
    expect(ruleFor("greeting").priority).toBeGreaterThan(ruleFor("idle").priority);
    expect(ruleFor("greeting").interruptible).toBe(false);
  });
  it("idle owns BASE, nod owns HEAD, wave owns SPECIAL", () => {
    expect(layerFor("idle")).toBe("BASE");
    expect(layerFor("nod")).toBe("HEAD");
    expect(layerFor("wave")).toBe("SPECIAL");
    expect(layerFor("point")).toBe("UPPER_BODY");
  });
  it("procedural composer clamps joint limits", () => {
    const r = composeRecipe("nod", { headTilt: 99, headYaw: -99, durationMs: 99999 });
    expect(r.headTilt).toBeLessThanOrEqual(DEFAULT_JOINT_LIMITS.Head.max);
    expect(r.headYaw).toBeGreaterThanOrEqual(DEFAULT_JOINT_LIMITS.Head.min);
    expect(r.durationMs).toBeLessThanOrEqual(9000);
    expect(r.base).toBe("nod");
  });
});

describe("visemes", () => {
  it("covers all 22 required groups + REST", () => {
    expect(VISEME_GROUPS).toHaveLength(22);
    for (const v of ["AA", "BMP", "WQ", "SZ", "TH"]) {
      expect(VISEME_GROUPS).toContain(v);
    }
  });
});

describe("seeded idle", () => {
  it("same seed gives same sequence (deterministic tests)", () => {
    const a = seededRng(42);
    const b = seededRng(42);
    expect([a(), a(), a()]).toEqual([b(), b(), b()]);
  });
});

describe("chat sanitization", () => {
  it("drops pong/stats/thought, keeps user/answer", () => {
    expect(isRenderableEvent({ type: "pong" })).toBe(false);
    expect(isRenderableEvent({ type: "stats" })).toBe(false);
    expect(isRenderableEvent({ type: "thought" })).toBe(false);
    expect(isRenderableEvent({ type: "user", text: "salut" })).toBe(true);
    expect(isRenderableEvent({ type: "answer", text: "عسلامة" })).toBe(true);
    expect(isRenderableEvent({ type: "tool_call" })).toBe(false);
  });
  it("strips thought blocks from answers", () => {
    expect(cleanAnswerText("hello <thought>secret</thought> world")).toBe("hello  world");
  });
});
