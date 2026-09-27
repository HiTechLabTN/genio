import { describe, expect, it } from "vitest";
import { detectShell, validateOpenUrl, runDesktopCommand } from "./bridge";
import { lifecycleFromProbes } from "./lifecycle";

describe("desktop bridge", () => {
  it("detects web shell in test env (no fake tauri)", () => {
    expect(detectShell()).toBe("web");
  });
  it("rejects dangerous URL schemes", () => {
    expect(validateOpenUrl("javascript:alert(1)").ok).toBe(false);
    expect(validateOpenUrl("file:///etc/passwd").ok).toBe(false);
    expect(validateOpenUrl("myapp://x").ok).toBe(false);
    expect(validateOpenUrl("not a url").ok).toBe(false);
    expect(validateOpenUrl("https://github.com/HiTechLabTN/genio").ok).toBe(true);
  });
  it("native commands report NOT_AVAILABLE on web (never fake)", async () => {
    const r = await runDesktopCommand({ cmd: "desktop.getInfo" });
    expect(r.ok).toBe(false);
    expect(r.code).toBe("NOT_AVAILABLE");
    const n = await runDesktopCommand({ cmd: "desktop.notification", title: "t", body: "b" });
    expect(n.ok).toBe(false);
    expect(["NOT_AVAILABLE", "PERMISSION_REQUIRED", "NATIVE_ERROR"]).toContain(n.code);
  });
  it("notification validates input", async () => {
    const r = await runDesktopCommand({ cmd: "desktop.notification", title: " ", body: "x" });
    expect(r.ok).toBe(false);
  });
});

describe("lifecycle", () => {
  it("maps probes honestly", () => {
    expect(lifecycleFromProbes("web", true, true)).toBe("ready");
    expect(lifecycleFromProbes("web", true, false)).toBe("degraded");
    expect(lifecycleFromProbes("web", false, false)).toBe("failed");
  });
});
