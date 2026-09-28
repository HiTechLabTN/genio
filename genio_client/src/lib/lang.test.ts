import { describe, expect, it, beforeEach } from "vitest";
import { getLang, setLang, t, type Lang } from "./lang";

function shimStorage() {
  const store = new Map<string, string>();
  (globalThis as Record<string, unknown>).localStorage = {
    getItem: (k: string) => (store.has(k) ? store.get(k)! : null),
    setItem: (k: string, v: string) => { store.set(k, String(v)); },
    removeItem: (k: string) => { store.delete(k); },
    clear: () => store.clear(),
  };
}

describe("language alternatives", () => {
  beforeEach(shimStorage);
  it("defaults to Tunisian", () => {
    expect(getLang()).toBe("tu");
  });
  it("persists fr/en explicitly (never default)", () => {
    setLang("fr");
    expect(getLang()).toBe("fr");
    setLang("en");
    expect(getLang()).toBe("en");
  });
  it("rejects garbage to Tunisian", () => {
    (globalThis as Record<string, unknown>).localStorage = {
      getItem: () => "xx", setItem: () => undefined,
      removeItem: () => undefined, clear: () => undefined,
    };
    expect(getLang()).toBe("tu");
  });
  it("every key exists in all three languages (no missing-label fallback gaps)", () => {
    const keys = ["nav_install", "install_title", "try", "offline", "error", "retry", "task", "evidence", "settings", "assistant", "start", "tools_activity"];
    for (const k of keys) {
      for (const l of ["tu", "fr", "en"] as Lang[]) {
        expect(t(l, k), `${l}.${k}`).toBeTruthy();
        expect(t(l, k)).not.toBe(k);
      }
    }
  });
  it("Tunisian is actually Tunisian (not MSA-generic, not English)", () => {
    expect(t("tu", "nav_install")).toMatch(/ركّب/);
    expect(t("tu", "offline")).toMatch(/ما فماش/);
    expect(t("fr", "offline")).toMatch(/Pas de connexion/);
  });
});
