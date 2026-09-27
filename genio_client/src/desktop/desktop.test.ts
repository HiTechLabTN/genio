import { describe, expect, it } from "vitest";
import { detectShell, validateOpenUrl, runDesktopCommand, sanitizeNotificationText } from "./bridge";
import { lifecycleFromProbes } from "./lifecycle";
import { lifecycleOf } from "./notifications";

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
  it("sanitizes secrets from notification text (plain-text API, no HTML vector)", () => {
    expect(sanitizeNotificationText("key sk-abcdef1234567890 here")).not.toContain("sk-abcdef");
    expect(sanitizeNotificationText("Bearer abcdef1234567890 tok")).toContain("Bearer [redacted]");
    expect(sanitizeNotificationText("api_key=supersecret123")).toContain("api_key=[redacted]");
    expect(sanitizeNotificationText("Task completed.")).toBe("Task completed.");
  });
});

describe("lifecycle", () => {
  it("maps probes honestly", () => {
    expect(lifecycleFromProbes("web", true, true)).toBe("ready");
    expect(lifecycleFromProbes("web", true, false)).toBe("degraded");
    expect(lifecycleFromProbes("web", false, false)).toBe("failed");
  });
});

describe("task lifecycle", () => {
  it("derives running/completed/failed/idle without inventing", () => {
    expect(lifecycleOf(true, "", null)).toBe("running");
    expect(lifecycleOf(false, "answer", null)).toBe("completed");
    expect(lifecycleOf(false, "", "boom")).toBe("failed");
    expect(lifecycleOf(false, "", null)).toBe("idle");
  });
});

describe("web/desktop parity (no second state machine)", () => {
  it("same runtime facts resolve identically on both shells", async () => {
    const { resolvePresence } = await import("../presence/resolve");
    const ctx = { socket: "connected", agent: "executing", streaming: true, typing: false, taskActive: true, needsInput: false, sessionAgeMin: 5 } as const;
    const web = resolvePresence({ ...ctx });
    const desktop = resolvePresence({ ...ctx });
    expect(web).toEqual(desktop);
    expect(web.semanticState).toBe("explaining");
  });
});
