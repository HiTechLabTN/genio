"""Typed installer↔UI event protocol (§5) + stable error catalog (§9).

Events are emitted by the CLI with --json-events (JSON lines, stdout),
scrubbed of secrets. Any UI renders them deterministically; the UI
never sends commands back. Schema locked by tests on both sides.
"""
from __future__ import annotations

import json
import sys
from typing import Any, Dict

from installer import INSTALLER_VERSION
from installer.core.runner import scrub

EVENTS = (
    "INSTALL_STARTED",
    "PREFLIGHT_STARTED",
    "PREFLIGHT_RESULT",
    "DOWNLOAD_STARTED",
    "DOWNLOAD_PROGRESS",
    "DOWNLOAD_COMPLETED",
    "VERIFICATION_STARTED",
    "VERIFICATION_RESULT",
    "INSTALL_PROGRESS",
    "CONFIGURATION_STARTED",
    "SECURITY_CHECK_STARTED",
    "HEALTH_CHECK_STARTED",
    "HEALTH_CHECK_RESULT",
    "INSTALL_COMPLETED",
    "INSTALL_FAILED",
    "ROLLBACK_STARTED",
    "ROLLBACK_COMPLETED",
    "USER_ACTION_REQUIRED",
)

# state = G1 shared state id for deterministic UI rendering.
EVENT_STATES = {
    "INSTALL_STARTED": "detecting",
    "PREFLIGHT_STARTED": "checking",
    "PREFLIGHT_RESULT": "ready",
    "DOWNLOAD_STARTED": "downloading",
    "DOWNLOAD_PROGRESS": "downloading",
    "DOWNLOAD_COMPLETED": "downloading",
    "VERIFICATION_STARTED": "verifying",
    "VERIFICATION_RESULT": "verifying",
    "INSTALL_PROGRESS": "installing",
    "CONFIGURATION_STARTED": "configuring",
    "SECURITY_CHECK_STARTED": "securing",
    "HEALTH_CHECK_STARTED": "health_check",
    "HEALTH_CHECK_RESULT": "health_check",
    "INSTALL_COMPLETED": "complete",
    "INSTALL_FAILED": "failed",
    "ROLLBACK_STARTED": "rolling_back",
    "ROLLBACK_COMPLETED": "rolled_back",
    "USER_ACTION_REQUIRED": "requires_user_action",
}

# Stable error catalog (§9): code -> message + recovery + docs.
ERRORS = {
    "INSTALL_OK": {"message": "Success.", "recovery": None, "docs": None},
    "INSTALL_DISK_SPACE": {
        "message": "Not enough free disk space.",
        "recovery": "Free the required space, then retry.",
        "docs": "/docs/troubleshooting"},
    "INSTALL_PORT_TAKEN": {
        "message": "A required port is already in use.",
        "recovery": "Stop the conflicting service or use --api-port/--web-port.",
        "docs": "/docs/installation"},
    "INSTALL_DEPS_MISSING": {
        "message": "Required system tools are missing.",
        "recovery": "Install them with the host package manager, then retry.",
        "docs": "/docs/installation"},
    "INSTALL_DOWNLOAD": {
        "message": "Artifact download failed.",
        "recovery": "Check network, then retry (resumable where supported).",
        "docs": "/docs/troubleshooting"},
    "INSTALL_CHECKSUM": {
        "message": "Checksum mismatch — artifact untrusted.",
        "recovery": "Re-download from the official release. Never bypass.",
        "docs": "/docs/installation"},
    "INSTALL_VENV": {
        "message": "Python environment creation failed.",
        "recovery": "Install python3-venv (ensurepip) via package manager.",
        "docs": "/docs/troubleshooting"},
    "INSTALL_VERIFY": {
        "message": "Post-install verification failed.",
        "recovery": "Run doctor, then repair. See install log.",
        "docs": "/docs/recovery"},
    "INSTALL_PERMISSION": {
        "message": "Insufficient permissions.",
        "recovery": "Use a user-writable prefix or run the service step with sudo.",
        "docs": "/docs/installation"},
    "INSTALL_UNSUPPORTED": {
        "message": "Unsupported platform.",
        "recovery": "Use Docker or a supported Linux distribution.",
        "docs": "/docs/installation"},
    "INSTALL_AMBIGUOUS": {
        "message": "Existing installation state is ambiguous.",
        "recovery": "Use status/repair/update explicitly, or an isolated --prefix.",
        "docs": "/docs/recovery"},
    "INSTALL_CANCELLED": {
        "message": "Cancelled by user.",
        "recovery": "Re-run when ready; partial state is repairable.",
        "docs": "/docs/recovery"},
    "INSTALL_ROLLBACK_FAILED": {
        "message": "Rollback did not restore the previous state.",
        "recovery": "Restore the backup in .genio/backups/ manually and report.",
        "docs": "/docs/recovery"},
}


class Emitter:
    """Writes scrubbed JSON lines to stdout when enabled (--json-events)."""

    def __init__(self, enabled=False, installation_id=None):
        self.enabled = enabled
        self.installation_id = installation_id

    def emit(self, event, data=None, error=None):
        assert event in EVENTS, f"unknown event {event!r}"
        if error is not None:
            assert error in ERRORS, f"unknown error {error!r}"
        payload = {
            "protocol": "genio-installer-events/1",
            "installer_version": INSTALLER_VERSION,
            "event": event,
            "state": EVENT_STATES[event],
            "installation_id": self.installation_id,
            "data": self._scrub_data(data or {}),
            "error": None,
        }
        if error is not None:
            info = ERRORS[error]
            payload["error"] = {"code": error, "message": info["message"],
                                "recovery": info["recovery"], "docs": info["docs"]}
        line = json.dumps(payload, sort_keys=True)
        if self.enabled:
            sys.stdout.write(line + "\n")
            sys.stdout.flush()
        return payload

    def _scrub_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return {k: (scrub(v) if isinstance(v, str) else v) for k, v in data.items()}
