import { describe, expect, it } from "vitest";
import { renderToStaticMarkup as render } from "react-dom/server";
import React from "react";
import LivingMascot from "./LivingMascot";

describe("LivingMascot state mapping (real presence → canonical image)", () => {
  it("idle shows the hero portrait", () => {
    const html = render(React.createElement(LivingMascot, { visual: "idle", statusText: "Genio حاضر" }));
    expect(html).toContain("genio-hero");
    expect(html).toContain("Genio حاضر");
  });
  it("thinking shows the think portrait, speaking the speak portrait", () => {
    const think = render(React.createElement(LivingMascot, { visual: "thinking", statusText: "Genio يخمّم" }));
    expect(think).toContain("genio-think");
    const speak = render(React.createElement(LivingMascot, { visual: "speaking", statusText: "Genio يحكيلك" }));
    expect(speak).toContain("genio-speak");
  });
  it("listening shows the listen portrait, success the wink", () => {
    const listen = render(React.createElement(LivingMascot, { visual: "listening", statusText: "Genio يسمع فيك" }));
    expect(listen).toContain("genio-listen");
    const ok = render(React.createElement(LivingMascot, { visual: "success", statusText: "كمّلنا المهمة" }));
    expect(ok).toContain("genio-wink");
  });
  it("working reuses the think portrait (no fake assets)", () => {
    const html = render(React.createElement(LivingMascot, { visual: "working", statusText: "Genio يخدم" }));
    expect(html).toContain("genio-think");
  });
  it("error/offline reuse base with honest treatment (no invented character)", () => {
    const err = render(React.createElement(LivingMascot, { visual: "error", statusText: "صارت مشكلة" }));
    expect(err).toContain("genio-hero");
    const off = render(React.createElement(LivingMascot, { visual: "offline", statusText: "موش متصل" }));
    expect(off).toContain("genio-hero");
    expect(off).toContain("saturate(0.35)");
  });
  it("exposes the real status as its accessible name, animation is decorative", () => {
    const html = render(React.createElement(LivingMascot, { visual: "thinking", statusText: "Genio يخمّم..." }));
    expect(html).toContain('aria-label="Genio يخمّم..."');
    expect(html).toContain('aria-hidden="true"');
  });
  it("never renders canvas/three (crash isolation by construction)", () => {
    const html = render(React.createElement(LivingMascot, { visual: "idle", statusText: "x" }));
    expect(html).not.toContain("canvas");
    expect(html).not.toContain("three");
    expect(html).not.toContain("webgl");
  });
  it("every animation has a prefers-reduced-motion kill-switch", () => {
    const html = render(React.createElement(LivingMascot, { visual: "speaking", statusText: "x" }));
    expect(html).toContain("@media (prefers-reduced-motion: reduce)");
    expect(html).toContain("animation: none");
    for (const cls of ["lm-breathe", "lm-lean", "lm-sway", "lm-work", "lm-speak", "lm-celebrate", "lm-spin-slow"]) {
      expect(html).toContain(cls);
    }
  });
});
