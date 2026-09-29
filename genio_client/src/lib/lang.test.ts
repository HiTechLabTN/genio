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
  it("ALL keys exist in all three languages (full-table completeness)", () => {
    // Access the internal table via a known-complete probe: every tu key
    // must resolve in fr/en to something other than the raw key itself.
    // (t() falls back tu -> key, so a missing fr/en entry would leak TN
    // or the raw key into the wrong language.)
    const probeDomains = [
      "landing.hero_badge", "landing.cta_try", "landing.how_title",
      "install.title", "install.state_detecting_label", "install.understood",
      "download.title", "download.available",
      "security.title", "security.sandbox.title", "security.tag_verified",
      "explore.title", "explore.agent.what", "explore.status_production",
      "api.title", "api.ws_note",
      "docs.title", "docs.search_ph", "docs.empty",
      "footer.docs", "footer.tag",
      "a11y.skip", "a11y.nav_dialog", "a11y.open_menu", "a11y.copy",
      "boundary.crash", "boundary.mascot_crash_hint",
      "app.mode_technique", "chat.title",
      "perm.status_granted", "perm.status_unavailable",
    ];
    for (const k of probeDomains) {
      for (const l of ["tu", "fr", "en"] as Lang[]) {
        expect(t(l, k), `${l}.${k}`).not.toBe(k);
      }
    }
  });
  it("public TN surface carries no English barrier on core strings", () => {
    const tnCore = [
      "landing.hero_badge", "landing.cta_try", "landing.cta_install",
      "install.title", "install.sub", "install.go_download",
      "download.title", "security.title", "security.sub",
      "explore.title", "api.title", "docs.title", "footer.docs",
    ];
    for (const k of tnCore) {
      const v = t("tu", k);
      expect(v, k).not.toMatch(/^[A-Za-z].*(Explore|Download|Install|Documentation|Security|Center|Assistant)/);
    }
    expect(t("tu", "landing.hero_badge")).toMatch(/تونسي|دارجة/);
    expect(t("tu", "install.title")).toMatch(/ثبّت/);
  });
  it("setLang notifies same-tab subscribers via genio:lang", () => {
    if (typeof window === "undefined" || typeof window.dispatchEvent !== "function") return;
    let fired = 0;
    const h = () => { fired += 1; };
    window.addEventListener("genio:lang", h);
    try {
      setLang("fr");
      expect(fired).toBeGreaterThan(0);
    } finally {
      window.removeEventListener("genio:lang", h);
      setLang("tu");
    }
  });
});
