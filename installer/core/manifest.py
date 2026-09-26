"""Installation manifest — durable machine-readable identity (§2)."""

import json
import platform
import socket
import uuid
from datetime import datetime, timezone

from installer import INSTALLER_VERSION, PRODUCT


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_manifest(prefix, version, commit, mode):
    return {
        "product": PRODUCT,
        "installation_id": str(uuid.uuid4()),
        "version": version,
        "commit": commit or "unknown",
        "install_root": str(prefix),
        "install_mode": mode,
        "installer_version": INSTALLER_VERSION,
        "installed_at": now_iso(),
        "updated_at": now_iso(),
        "platform": platform.system().lower(),
        "architecture": platform.machine(),
        "hostname": socket.gethostname(),
        "health": "unknown",
        "ports": {},
        "history": [],
    }


def read_manifest(path):
    try:
        with open(path) as fh:
            data = json.load(fh)
        if not isinstance(data, dict) or data.get("product") != PRODUCT:
            return None
        return data
    except (OSError, ValueError):
        return None


def write_manifest(path, data):
    data = dict(data)
    data["updated_at"] = now_iso()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)
        fh.write("\n")
    tmp.replace(path)
    return data


def record_event(manifest, kind, detail=""):
    manifest.setdefault("history", []).append(
        {"ts": now_iso(), "kind": kind, "detail": str(detail)[:500]})
    manifest["history"] = manifest["history"][-50:]
    return manifest
