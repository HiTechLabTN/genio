import { describe, expect, it } from "vitest";
import { arabicSpeakable, hasArabicScript } from "./arabicVoice";

describe("arabicVoice routing", () => {
  it("detects Arabic script (Tunisian answers route to the sidecar)", () => {
    expect(hasArabicScript("عسلامة، شنوّة تحب؟")).toBe(true);
    expect(hasArabicScript("Bonjour, ça va ?")).toBe(false);
    expect(hasArabicScript("")).toBe(false);
  });

  it("rejects empty / over-long / non-Arabic locally (mirrors 400/422)", () => {
    expect(arabicSpeakable("   ").ok).toBe(false);
    expect(arabicSpeakable("x".repeat(2001)).ok).toBe(false);
    expect(arabicSpeakable("hello only").ok).toBe(false);
    expect(arabicSpeakable("مرحبا 123!").ok).toBe(true);
  });

  it("French/English answers stay out of the Arabic path", () => {
    // The App effect routes on hasArabicScript: Latin-only text keeps the
    // existing browser-synthesis path untouched.
    expect(hasArabicScript("Mise à jour terminée.")).toBe(false);
    expect(hasArabicScript("Update complete: 10 packages.")).toBe(false);
  });
});
