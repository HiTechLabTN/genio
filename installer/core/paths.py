"""Filesystem layout — no developer paths, XDG-aware, prefix-relative."""

import os
from pathlib import Path

INSTALLER_DIR = Path(__file__).resolve().parents[1]

# Known Genio network services (authoritative defaults).
DEFAULT_PORTS = {
    "api": 8000,
    "web": 8098,
    "voder": 5050,
    "gestures": 8001,
    "ollama": 11434,
}

# Unit names that signal a system-service installation.
KNOWN_UNITS = (
    "genio.service",
    "genio-web.service",
    "voder-5050.service",
    "genio-gestures.service",
)

# Markers that signal a development checkout.
DEV_MARKERS = (
    "genio_server",
    "core",
    "genio_client",
    "requirements.lock",
    ".git",
)


def default_prefix():
    """System prefix if writable with sudo available, else user prefix."""
    if os.geteuid() == 0:
        return Path("/opt/genio")
    return Path.home() / ".local" / "share" / "genio"


def layout(prefix):
    """Prefix layout separating code / config / data / runtime (§11)."""
    p = Path(prefix)
    return {
        "prefix": p,
        "meta": p / ".genio",
        "manifest": p / ".genio" / "manifest.json",
        "backups": p / ".genio" / "backups",
        "log": p / ".genio" / "install.log",
        "repo": p / "repo",
        "venv": p / "venv",
        "config": p / "config",
        "env_file": p / "config" / ".env",
        "ports_file": p / "config" / "ports.json",
        "data": p / "data",
        "cache": p / "cache",
        "logs": p / "logs",
        "tmp": p / "tmp",
    }
