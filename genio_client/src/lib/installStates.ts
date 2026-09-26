/**
 * Shared UX/installation states — TypeScript mirror of installer/core/states.py.
 * DO NOT EDIT BY HAND: run `node scripts/gen-product-data.mjs --check-states`
 * or keep in sync; locked by tests/test_states_mirror.py + states.test.ts.
 */
export type InstallStateId =
  | "idle" | "detecting" | "checking" | "ready" | "downloading"
  | "verifying" | "installing" | "configuring" | "securing"
  | "health_check" | "complete" | "degraded" | "failed" | "blocked"
  | "requires_user_action" | "rolling_back" | "rolled_back" | "cancelled";

export type Severity = "info" | "ok" | "warn" | "error";

export interface InstallState {
  id: InstallStateId;
  label: string;
  explanation: string;
  severity: Severity;
  transitions: InstallStateId[];
  recovery: string | null;
}

export const INSTALL_STATES: Record<InstallStateId, Omit<InstallState, "id">> = {
  idle: { label: "Idle", explanation: "No operation started.", severity: "info", transitions: ["detecting"], recovery: null },
  detecting: { label: "Detecting system", explanation: "Probing OS, hardware, tools, ports and existing installations.", severity: "info", transitions: ["checking", "blocked", "cancelled", "failed"], recovery: "Retry detection." },
  checking: { label: "Preflight checks", explanation: "Validating requirements before any change.", severity: "info", transitions: ["ready", "blocked", "requires_user_action", "cancelled", "failed"], recovery: "Resolve reported items, then retry." },
  ready: { label: "Ready", explanation: "System ready; awaiting user confirmation.", severity: "ok", transitions: ["downloading", "installing", "cancelled"], recovery: null },
  downloading: { label: "Downloading", explanation: "Fetching the release artifact. Real bytes only.", severity: "info", transitions: ["verifying", "cancelled", "failed"], recovery: "Retry download (resumable where supported)." },
  verifying: { label: "Verifying integrity", explanation: "SHA-256 (and signature when available) checked. Mismatch aborts.", severity: "info", transitions: ["installing", "failed", "cancelled"], recovery: "Re-download from the official release." },
  installing: { label: "Installing", explanation: "Extracting, creating venv, installing pinned dependencies.", severity: "info", transitions: ["configuring", "failed", "cancelled", "rolling_back"], recovery: "Repair the prefix or reinstall with --force." },
  configuring: { label: "Configuring", explanation: "Writing config, ports and environment (never secrets in logs).", severity: "info", transitions: ["securing", "failed", "cancelled", "rolling_back"], recovery: "Repair regenerates safe defaults." },
  securing: { label: "Securing", explanation: "File permissions, boot-guard check, cloud default closed.", severity: "info", transitions: ["health_check", "failed", "cancelled", "rolling_back"], recovery: "See doctor output; fix permissions/keys." },
  health_check: { label: "Health check", explanation: "Import verify, API probe, sandbox probe. Process alive is not enough.", severity: "info", transitions: ["complete", "degraded", "failed", "rolling_back"], recovery: "Inspect failing check, repair, re-run doctor." },
  complete: { label: "Ready", explanation: "Installation verified healthy.", severity: "ok", transitions: [], recovery: null },
  degraded: { label: "Degraded", explanation: "Usable with explicitly listed unavailable parts.", severity: "warn", transitions: ["health_check", "rolling_back"], recovery: "Resolve listed items or roll back." },
  failed: { label: "Failed", explanation: "Operation failed with an exact reported cause.", severity: "error", transitions: ["rolling_back", "requires_user_action"], recovery: "Follow the reported recovery action." },
  blocked: { label: "Blocked", explanation: "Cannot proceed safely (permissions, platform, missing external).", severity: "error", transitions: ["requires_user_action", "cancelled"], recovery: "Satisfy the blocker, then restart." },
  requires_user_action: { label: "Action required", explanation: "Explicit user decision needed (ports, purge, reconcile).", severity: "warn", transitions: ["checking", "cancelled"], recovery: null },
  rolling_back: { label: "Rolling back", explanation: "Restoring the previous known-good state.", severity: "warn", transitions: ["rolled_back", "failed"], recovery: null },
  rolled_back: { label: "Rolled back", explanation: "Previous state restored; user data preserved.", severity: "ok", transitions: [], recovery: null },
  cancelled: { label: "Cancelled", explanation: "Stopped by user before irreversible steps.", severity: "info", transitions: [], recovery: null },
};

export function canTransition(from: InstallStateId, to: InstallStateId): boolean {
  return INSTALL_STATES[from].transitions.includes(to);
}
