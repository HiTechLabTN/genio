/**
 * Installer event protocol mirror — must match installer/core/events.py.
 * Locked by tests/test_installer_events.py (python) and events.test.ts.
 * UI renders these deterministically; it never sends commands back.
 */
import type { InstallStateId, Severity } from "./installStates";

export const INSTALL_EVENTS = [
  "INSTALL_STARTED", "PREFLIGHT_STARTED", "PREFLIGHT_RESULT",
  "DOWNLOAD_STARTED", "DOWNLOAD_PROGRESS", "DOWNLOAD_COMPLETED",
  "VERIFICATION_STARTED", "VERIFICATION_RESULT", "INSTALL_PROGRESS",
  "CONFIGURATION_STARTED", "SECURITY_CHECK_STARTED",
  "HEALTH_CHECK_STARTED", "HEALTH_CHECK_RESULT",
  "INSTALL_COMPLETED", "INSTALL_FAILED",
  "ROLLBACK_STARTED", "ROLLBACK_COMPLETED", "USER_ACTION_REQUIRED",
] as const;

export type InstallEvent = (typeof INSTALL_EVENTS)[number];

export const EVENT_STATES: Record<InstallEvent, InstallStateId> = {
  INSTALL_STARTED: "detecting",
  PREFLIGHT_STARTED: "checking",
  PREFLIGHT_RESULT: "ready",
  DOWNLOAD_STARTED: "downloading",
  DOWNLOAD_PROGRESS: "downloading",
  DOWNLOAD_COMPLETED: "downloading",
  VERIFICATION_STARTED: "verifying",
  VERIFICATION_RESULT: "verifying",
  INSTALL_PROGRESS: "installing",
  CONFIGURATION_STARTED: "configuring",
  SECURITY_CHECK_STARTED: "securing",
  HEALTH_CHECK_STARTED: "health_check",
  HEALTH_CHECK_RESULT: "health_check",
  INSTALL_COMPLETED: "complete",
  INSTALL_FAILED: "failed",
  ROLLBACK_STARTED: "rolling_back",
  ROLLBACK_COMPLETED: "rolled_back",
  USER_ACTION_REQUIRED: "requires_user_action",
};

export interface InstallerErrorInfo {
  message: string;
  recovery: string | null;
  docs: string | null;
}

export const INSTALL_ERRORS: Record<string, InstallerErrorInfo> = {
  INSTALL_OK: { message: "Success.", recovery: null, docs: null },
  INSTALL_DISK_SPACE: { message: "Not enough free disk space.", recovery: "Free the required space, then retry.", docs: "/docs#troubleshooting" },
  INSTALL_PORT_TAKEN: { message: "A required port is already in use.", recovery: "Stop the conflicting service or use --api-port/--web-port.", docs: "/docs#installation" },
  INSTALL_DEPS_MISSING: { message: "Required system tools are missing.", recovery: "Install them with the host package manager, then retry.", docs: "/docs#installation" },
  INSTALL_DOWNLOAD: { message: "Artifact download failed.", recovery: "Check network, then retry (resumable where supported).", docs: "/docs#troubleshooting" },
  INSTALL_CHECKSUM: { message: "Checksum mismatch — artifact untrusted.", recovery: "Re-download from the official release. Never bypass.", docs: "/docs#installation" },
  INSTALL_VENV: { message: "Python environment creation failed.", recovery: "Install python3-venv (ensurepip) via package manager.", docs: "/docs#troubleshooting" },
  INSTALL_VERIFY: { message: "Post-install verification failed.", recovery: "Run doctor, then repair. See install log.", docs: "/docs#recovery" },
  INSTALL_PERMISSION: { message: "Insufficient permissions.", recovery: "Use a user-writable prefix or run the service step with sudo.", docs: "/docs#installation" },
  INSTALL_UNSUPPORTED: { message: "Unsupported platform.", recovery: "Use Docker or a supported Linux distribution.", docs: "/docs#installation" },
  INSTALL_AMBIGUOUS: { message: "Existing installation state is ambiguous.", recovery: "Use status/repair/update explicitly, or an isolated --prefix.", docs: "/docs#recovery" },
  INSTALL_CANCELLED: { message: "Cancelled by user.", recovery: "Re-run when ready; partial state is repairable.", docs: "/docs#recovery" },
  INSTALL_ROLLBACK_FAILED: { message: "Rollback did not restore the previous state.", recovery: "Restore the backup in .genio/backups/ manually and report.", docs: "/docs#recovery" },
};

export interface ParsedEvent {
  event: InstallEvent;
  state: InstallStateId;
  data: Record<string, unknown>;
  error: { code: string; message: string; recovery: string | null; docs: string | null } | null;
  raw: string;
  invalid?: string;
}

/** Parse --json-events lines deterministically. Invalid lines are flagged, never hidden. */
export function parseEventLog(text: string): ParsedEvent[] {
  return text
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean)
    .map((raw) => {
      let obj: Record<string, unknown>;
      try {
        obj = JSON.parse(raw) as Record<string, unknown>;
      } catch {
        return { event: "INSTALL_FAILED", state: "failed", data: {}, error: null, raw, invalid: "not JSON" } as ParsedEvent;
      }
      const event = obj.event as string;
      if (!(INSTALL_EVENTS as readonly string[]).includes(event)) {
        return { event: "INSTALL_FAILED", state: "failed", data: {}, error: null, raw, invalid: `unknown event ${event}` } as ParsedEvent;
      }
      const err = obj.error as ParsedEvent["error"];
      if (err && !(err.code in INSTALL_ERRORS)) {
        return { event: event as InstallEvent, state: EVENT_STATES[event as InstallEvent], data: {}, error: null, raw, invalid: `unknown error ${err.code}` };
      }
      return {
        event: event as InstallEvent,
        state: EVENT_STATES[event as InstallEvent],
        data: (obj.data ?? {}) as Record<string, unknown>,
        error: err ?? null,
        raw,
      };
    });
}

export function severityForState(state: InstallStateId): Severity {
  if (state === "complete" || state === "rolled_back") return "ok";
  if (state === "failed" || state === "blocked") return "error";
  if (state === "degraded" || state === "requires_user_action" || state === "rolling_back") return "warn";
  return "info";
}
