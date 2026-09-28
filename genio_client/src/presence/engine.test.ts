import { describe, expect, it } from "vitest";
import { resolveEngine } from "./engine";
import type { AppFacts } from "./engine";

const base: AppFacts = {
  online: true, socket: "connected", agent: "idle", streaming: false,
  typing: false, taskActive: false, toolActive: false, needsInput: false,
  sessionAgeMin: 99,
};

describe("presence engine (real facts only)", () => {
  it("READY when idle and connected", () => {
    expect(resolveEngine(base).engine).toBe("READY");
  });
  it("LISTENING while typing, never from timers", () => {
    expect(resolveEngine({ ...base, typing: true }).engine).toBe("LISTENING");
  });
  it("THINKING from agent state", () => {
    expect(resolveEngine({ ...base, agent: "thinking" }).engine).toBe("THINKING");
  });
  it("TASK_RUNNING beats streaming (no premature COMPLETE)", () => {
    const r = resolveEngine({ ...base, taskActive: true, streaming: true });
    expect(r.engine).toBe("TASK_RUNNING");
  });
  it("TOOL_ACTIVITY when a tool is active", () => {
    expect(resolveEngine({ ...base, taskActive: true, toolActive: true }).engine).toBe("TOOL_ACTIVITY");
  });
  it("COMPLETE only on real outcome", () => {
    expect(resolveEngine({ ...base, lastOutcome: "success" }).engine).toBe("COMPLETE");
  });
  it("ERROR on error, OFFLINE when disconnected", () => {
    expect(resolveEngine({ ...base, error: "x" }).engine).toBe("ERROR");
    expect(resolveEngine({ ...base, socket: "disconnected" }).engine).toBe("OFFLINE");
    expect(resolveEngine({ ...base, online: false }).engine).toBe("OFFLINE");
  });
  it("RECONNECTING while connecting", () => {
    expect(resolveEngine({ ...base, socket: "connecting" }).engine).toBe("RECONNECTING");
  });
  it("every visual config uses known motion/attention vocabulary", () => {
    const v = resolveEngine({ ...base }).visual;
    expect(["none", "breathe", "pulse", "signal"]).toContain(v.motion);
    expect(["low", "medium", "high"]).toContain(v.attention);
    expect(["ok", "info", "warn", "error"]).toContain(v.statusTone);
  });
  it("presence object stays contract-compatible", () => {
    const r = resolveEngine({ ...base, taskActive: true });
    expect(r.presence.semanticState).toBe("executing");
    expect(r.presence.intensity).toBe("low");
  });
});
