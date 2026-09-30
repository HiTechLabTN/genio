import { describe, expect, it, beforeEach } from "vitest";
import { composeGesture, PRIMITIVES, STATE_COMBOS } from "./primitives";
import { resolvePresence, layoutModeFor } from "./resolve";
import { loadPrefs, savePrefs, effectiveMotion, DEFAULT_PREFS } from "./preferences";
import { renderToStaticMarkup } from "react-dom/server";
import PresenceAvatar from "./PresenceAvatar";

describe("state → representation", () => {
  it("every semantic state composes a valid gesture", () => {
    for (const state of Object.keys(STATE_COMBOS)) {
      const g = composeGesture(state as keyof typeof STATE_COMBOS);
      expect(g.valid).toBe(true);
      expect(g.totalDuration).toBeLessThanOrEqual(12);
      for (const p of g.primitives) {
        expect(PRIMITIVES[p.id]).toBeTruthy();
        expect(p.amplitude).toBeLessThanOrEqual(0.8);
      }
    }
  });
  it("unknown state falls back to known-good", () => {
    const g = composeGesture("nope" as never);
    expect(g.valid).toBe(true);
    expect(g.fallback).toBe(true);
  });
  it("intensity caps amplitude (calm default)", () => {
    const low = composeGesture("greeting", 0, "low");
    expect(Math.max(...low.primitives.map((p) => p.amplitude))).toBeLessThanOrEqual(0.3);
  });
});

describe("state → layout", () => {
  it("maps thinking/executing/result/conversation", () => {
    const thinking = resolvePresence({ socket: "connected", agent: "thinking", streaming: false, typing: false, taskActive: false, needsInput: false, sessionAgeMin: 5 });
    expect(thinking.semanticState).toBe("thinking");
    expect(layoutModeFor(thinking, false)).toBe("thinking");
    const exec = resolvePresence({ socket: "connected", agent: "idle", streaming: false, typing: false, taskActive: true, needsInput: false, sessionAgeMin: 5 });
    expect(layoutModeFor(exec, false)).toBe("execution");
    expect(layoutModeFor(exec, true)).toBe("developer");
  });
  it("error and disconnect win honestly", () => {
    const err = resolvePresence({ socket: "connected", agent: "idle", streaming: false, typing: false, taskActive: false, needsInput: false, error: "boom", sessionAgeMin: 5 });
    expect(err.semanticState).toBe("error");
    const dc = resolvePresence({ socket: "disconnected", agent: "idle", streaming: false, typing: false, taskActive: false, needsInput: false, sessionAgeMin: 5 });
    expect(dc.semanticState).toBe("disconnected");
  });
  it("listening only while typing, success brief", () => {
    const l = resolvePresence({ socket: "connected", agent: "idle", streaming: false, typing: true, taskActive: false, needsInput: false, sessionAgeMin: 5 });
    expect(l.semanticState).toBe("listening");
    expect(l.attentionTarget).toBe("user");
  });
});

describe("reduced motion changes behavior", () => {
  it("os setting and explicit prefs", () => {
    expect(effectiveMotion({ ...DEFAULT_PREFS, animation: "on" }, true)).toBe("reduced");
    expect(effectiveMotion({ ...DEFAULT_PREFS, animation: "off" }, false)).toBe("off");
    expect(effectiveMotion(DEFAULT_PREFS, false)).toBe("on");
  });
});

describe("preferences persist safely", () => {
  beforeEach(() => {
    // No jsdom here: minimal in-memory Storage shim (no new deps).
    const store = new Map<string, string>();
    (globalThis as Record<string, unknown>).localStorage = {
      getItem: (k: string) => (store.has(k) ? store.get(k)! : null),
      setItem: (k: string, v: string) => { store.set(k, String(v)); },
      removeItem: (k: string) => { store.delete(k); },
      clear: () => store.clear(),
    };
  });
  it("round-trips valid prefs, rejects garbage", () => {
    savePrefs({ ...DEFAULT_PREFS, density: "advanced" });
    expect(loadPrefs().density).toBe("advanced");
    localStorage.setItem("genio-experience-prefs-v1", "{bad");
    expect(loadPrefs()).toEqual(DEFAULT_PREFS);
    localStorage.setItem("genio-experience-prefs-v1", JSON.stringify({ animation: "hyper" }));
    expect(loadPrefs()).toEqual(DEFAULT_PREFS);
  });
});

describe("3D failure never breaks UI", () => {
  it("PresenceAvatar renders without 3D, labelled with real state", () => {
    const html = renderToStaticMarkup(
      <PresenceAvatar presence={{ semanticState: "thinking", attentionTarget: "task", intensity: "low" }} compact />
    );
    expect(html).toContain('aria-label="Genio state: thinking');
    expect(html).not.toContain("canvas");
    expect(html).not.toContain("three");
  });
});

describe("canonical image mapping", () => {
  it("maps key states to canonical reference images", async () => {
    const { imageForState } = await import("./PresenceAvatar");
    expect(imageForState("greeting")).toMatch(/genio-wave/);
    expect(imageForState("listening")).toMatch(/genio-listen/);
    expect(imageForState("success")).toMatch(/genio-wink/);
    expect(imageForState("celebrating")).toMatch(/genio-wink/);
    expect(imageForState("thinking")).toMatch(/genio-think/);
    expect(imageForState("executing")).toMatch(/genio-think/);
    expect(imageForState("explaining")).toMatch(/genio-speak/);
    expect(imageForState("understanding")).toMatch(/genio-think/);
    expect(imageForState("idle")).toMatch(/genio-hero/);
    expect(imageForState("error")).toMatch(/genio-hero/);
    expect(imageForState("disconnected")).toMatch(/genio-hero/);
  });
  it("greeting avatar renders the wave image, thinking the think image", async () => {
    const { renderToStaticMarkup: render } = await import("react-dom/server");
    const React = await import("react");
    const { default: PresenceAvatar } = await import("./PresenceAvatar");
    const wave = render(React.createElement(PresenceAvatar, { presence: { semanticState: "greeting", intensity: "low" } }));
    expect(wave).toContain("genio-wave");
    const think = render(React.createElement(PresenceAvatar, { presence: { semanticState: "thinking", intensity: "low" } }));
    expect(think).toContain("genio-think");
    expect(think).not.toContain("genio-wave");
  });
});
