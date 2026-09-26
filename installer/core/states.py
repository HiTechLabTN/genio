"""Shared UX/installation state machine (§13 charter, G1-E).

Single source of truth for semantic states consumed by the CLI
installer, the download center and the application UI. Every state
carries: identifier, human label, explanation, severity, allowed
transitions, recovery action. The TypeScript mirror
(genio_client/src/lib/installStates.ts) MUST stay in sync
(locked by test_states_mirror.py).
"""
from __future__ import annotations

STATES = {
    "idle": {
        "label": "Idle",
        "explanation": "No operation started.",
        "severity": "info",
        "transitions": ["detecting"],
        "recovery": None,
    },
    "detecting": {
        "label": "Detecting system",
        "explanation": "Probing OS, hardware, tools, ports and existing installations.",
        "severity": "info",
        "transitions": ["checking", "blocked", "cancelled", "failed"],
        "recovery": "Retry detection.",
    },
    "checking": {
        "label": "Preflight checks",
        "explanation": "Validating requirements before any change.",
        "severity": "info",
        "transitions": ["ready", "blocked", "requires_user_action", "cancelled", "failed"],
        "recovery": "Resolve reported items, then retry.",
    },
    "ready": {
        "label": "Ready",
        "explanation": "System ready; awaiting user confirmation.",
        "severity": "ok",
        "transitions": ["downloading", "installing", "cancelled"],
        "recovery": None,
    },
    "downloading": {
        "label": "Downloading",
        "explanation": "Fetching the release artifact. Real bytes only.",
        "severity": "info",
        "transitions": ["verifying", "cancelled", "failed"],
        "recovery": "Retry download (resumable where supported).",
    },
    "verifying": {
        "label": "Verifying integrity",
        "explanation": "SHA-256 (and signature when available) checked. Mismatch aborts.",
        "severity": "info",
        "transitions": ["installing", "failed", "cancelled"],
        "recovery": "Re-download from the official release.",
    },
    "installing": {
        "label": "Installing",
        "explanation": "Extracting, creating venv, installing pinned dependencies.",
        "severity": "info",
        "transitions": ["configuring", "failed", "cancelled", "rolling_back"],
        "recovery": "Repair the prefix or reinstall with --force.",
    },
    "configuring": {
        "label": "Configuring",
        "explanation": "Writing config, ports and environment (never secrets in logs).",
        "severity": "info",
        "transitions": ["securing", "failed", "cancelled", "rolling_back"],
        "recovery": "Repair regenerates safe defaults.",
    },
    "securing": {
        "label": "Applying security",
        "explanation": "File permissions, boot-guard check, cloud default closed.",
        "severity": "info",
        "transitions": ["health_check", "failed", "cancelled", "rolling_back"],
        "recovery": "See doctor output; fix permissions/keys.",
    },
    "health_check": {
        "label": "Health check",
        "explanation": "Import verify, API probe, sandbox probe. Process alive is not enough.",
        "severity": "info",
        "transitions": ["complete", "degraded", "failed", "rolling_back"],
        "recovery": "Inspect failing check, repair, re-run doctor.",
    },
    "complete": {
        "label": "Ready",
        "explanation": "Installation verified healthy.",
        "severity": "ok",
        "transitions": [],
        "recovery": None,
    },
    "degraded": {
        "label": "Degraded",
        "explanation": "Usable with explicitly listed unavailable parts.",
        "severity": "warn",
        "transitions": ["health_check", "rolling_back"],
        "recovery": "Resolve listed items or roll back.",
    },
    "failed": {
        "label": "Failed",
        "explanation": "Operation failed with an exact reported cause.",
        "severity": "error",
        "transitions": ["rolling_back", "requires_user_action"],
        "recovery": "Follow the reported recovery action.",
    },
    "blocked": {
        "label": "Blocked",
        "explanation": "Cannot proceed safely (permissions, platform, missing external).",
        "severity": "error",
        "transitions": ["requires_user_action", "cancelled"],
        "recovery": "Satisfy the blocker, then restart.",
    },
    "requires_user_action": {
        "label": "Action required",
        "explanation": "Explicit user decision needed (ports, purge, reconcile).",
        "severity": "warn",
        "transitions": ["checking", "cancelled"],
        "recovery": None,
    },
    "rolling_back": {
        "label": "Rolling back",
        "explanation": "Restoring the previous known-good state.",
        "severity": "warn",
        "transitions": ["rolled_back", "failed"],
        "recovery": None,
    },
    "rolled_back": {
        "label": "Rolled back",
        "explanation": "Previous state restored; user data preserved.",
        "severity": "ok",
        "transitions": [],
        "recovery": None,
    },
    "cancelled": {
        "label": "Cancelled",
        "explanation": "Stopped by user before irreversible steps.",
        "severity": "info",
        "transitions": [],
        "recovery": None,
    },
}

SEVERITIES = {"info", "ok", "warn", "error"}


def validate_graph():
    """The machine itself is tested: closed transitions + known severities."""
    errors = []
    for sid, spec in STATES.items():
        if spec["severity"] not in SEVERITIES:
            errors.append(f"{sid}: bad severity")
        for dst in spec["transitions"]:
            if dst not in STATES:
                errors.append(f"{sid} -> unknown {dst}")
        for key in ("label", "explanation", "transitions", "recovery"):
            if key not in spec:
                errors.append(f"{sid}: missing {key}")
    return errors
