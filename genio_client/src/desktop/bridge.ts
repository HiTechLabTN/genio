/**
 * Desktop bridge — detects Tauri vs Web, exposes ONLY the typed command
 * registry (no generic shell). In pure web builds every native command
 * reports NOT_AVAILABLE honestly; nothing is simulated.
 */

export type ShellKind = "web" | "tauri";

export function detectShell(): ShellKind {
  try {
    if (typeof window !== "undefined" && "__TAURI_INTERNALS__" in window) return "tauri";
  } catch { /* ignore */ }
  return "web";
}

/** Approved URL schemes for openUrl. Everything else is rejected. */
const ALLOWED_URL_SCHEMES = ["https:", "intent:"];

export function validateOpenUrl(url: string): { ok: boolean; reason?: string } {
  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch {
    return { ok: false, reason: "malformed URL" };
  }
  if (!ALLOWED_URL_SCHEMES.includes(parsed.protocol)) {
    return { ok: false, reason: `scheme not allowed: ${parsed.protocol}` };
  }
  if (parsed.protocol === "https:" && !parsed.hostname) {
    return { ok: false, reason: "https URL without host" };
  }
  return { ok: true };
}

/** Defense in depth: bodies must never carry secrets even if a caller
 * passes them (pipeline only sends fixed status strings). Pure, tested. */
export function sanitizeNotificationText(s: string): string {
  return s
    .replace(/sk-[A-Za-z0-9]{8,}/g, "[redacted]")
    .replace(/ghp_[A-Za-z0-9]{8,}/g, "[redacted]")
    .replace(/Bearer\s+[A-Za-z0-9._~+/-]{8,}/gi, "Bearer [redacted]")
    .replace(/(api[_-]?key|token|password|secret)\s*[:=]\s*\S+/gi, "$1=[redacted]");
}
export type DesktopCommand =
  | { cmd: "desktop.getInfo" }
  | { cmd: "desktop.openUrl"; url: string }
  | { cmd: "desktop.getDiagnostics" }
  | { cmd: "desktop.notification"; title: string; body: string };

export interface CommandResult {
  ok: boolean;
  code: string;
  data?: unknown;
  error?: string;
}

export async function runDesktopCommand(c: DesktopCommand): Promise<CommandResult> {
  if (detectShell() !== "tauri") {
    return { ok: false, code: "NOT_AVAILABLE", error: "native shell absent (web build)" };
  }
  try {
    if (c.cmd === "desktop.getInfo") {
      const [{ platform, arch }, { version }] = await Promise.all([
        import("@tauri-apps/plugin-os").then((m) => ({ platform: m.platform(), arch: m.arch() })),
        import("@tauri-apps/api/app").then((m) => m.getVersion().then((version: string) => ({ version }))),
      ]);
      return { ok: true, code: "OK", data: { platform, arch, appVersion: version } };
    }
    if (c.cmd === "desktop.openUrl") {
      const v = validateOpenUrl(c.url);
      if (!v.ok) return { ok: false, code: "URL_REJECTED", error: v.reason };
      const { openUrl } = await import("@tauri-apps/plugin-opener");
      await openUrl(c.url);
      return { ok: true, code: "OK" };
    }
    if (c.cmd === "desktop.getDiagnostics") {
      const info = await runDesktopCommand({ cmd: "desktop.getInfo" });
      if (!info.ok) return info;
      return {
        ok: true, code: "OK",
        data: {
          ...(info.data as Record<string, unknown>),
          // Safe fields only: versions, OS/arch, NO env dumps, NO tokens, NO paths.
          installer: "external CLI (protocol v1)",
          backend: "not probed here (use doctor)",
        },
      };
    }
    if (c.cmd === "desktop.notification") {
      if (!c.title.trim() || !c.body.trim()) {
        return { ok: false, code: "INVALID_INPUT", error: "title/body required" };
      }
      // Defense in depth: bodies must never carry secrets even if a caller
      // passes them (pipeline only sends fixed status strings).
      const title = sanitizeNotificationText(c.title).slice(0, 120);
      const body = sanitizeNotificationText(c.body).slice(0, 300);
      if ("Notification" in window && Notification.permission === "granted") {
        new Notification(title, { body });
        return { ok: true, code: "OK", data: { via: "web" } };
      }
      return { ok: false, code: "PERMISSION_REQUIRED", error: "notification permission not granted" };
    }
    const _exhaustive: never = c;
    return { ok: false, code: "UNKNOWN_COMMAND", error: String((_exhaustive as { cmd: string }).cmd) };
  } catch (e) {
    return { ok: false, code: "NATIVE_ERROR", error: String(e).slice(0, 200) };
  }
}
