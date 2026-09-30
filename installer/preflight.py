"""Full machine preflight — structured understanding before any change.

Every prerequisite resolves to a clear state; NOTHING here raises just
because an executable is missing (Runner maps that to rc=127).

States: AVAILABLE | MISSING | BROKEN | DAEMON_DOWN | PERMISSION_DENIED
        | VERSION_TOO_OLD | UNKNOWN
"""
import shutil

from installer.detectors import hardware, osinfo, software
from installer.detectors import system as sysdet

AVAILABLE = "AVAILABLE"
MISSING = "MISSING"
BROKEN = "BROKEN"
DAEMON_DOWN = "DAEMON_DOWN"
PERMISSION_DENIED = "PERMISSION_DENIED"
VERSION_TOO_OLD = "VERSION_TOO_OLD"
UNKNOWN = "UNKNOWN"


def _docker_state(runner):
    """Distinguish CLI missing / daemon stopped / permission / working."""
    if not shutil.which("docker"):
        return {"state": MISSING, "detail": "no docker executable"}
    r = runner.run(["docker", "info", "--format", "{{.ServerVersion}}"], timeout=20)
    if r["ok"]:
        return {"state": AVAILABLE, "detail": f"daemon ok ({r['out'].strip()[:20]})"}
    blob = ((r.get("err") or "") + (r.get("out") or "")).lower()
    if "permission denied" in blob or "permissiondenied" in blob or "got permission denied" in blob:
        return {"state": PERMISSION_DENIED, "detail": "user cannot talk to the daemon"}
    if "cannot connect" in blob or "is the docker daemon running" in blob or "no such file" in blob:
        return {"state": DAEMON_DOWN, "detail": "daemon not running"}
    if r.get("rc") == 127:
        return {"state": MISSING, "detail": "docker vanished mid-check"}
    return {"state": BROKEN, "detail": (r.get("err") or "unknown docker error")[:160]}


def _tool_state(check):
    """Map a software.check_one() result onto a preflight state."""
    if check.get("ok"):
        return AVAILABLE, check.get("version") or "present"
    if not check.get("present"):
        return MISSING, "absent"
    if check.get("note"):
        return BROKEN, check["note"]
    return VERSION_TOO_OLD, f"v={check.get('version')}"


def preflight(runner, prefix=None):
    """Return a full machine report. Never raises for missing tools."""
    report = {"items": {}, "all_ready": True, "needs_repair": []}
    try:
        plat = osinfo.detect(runner)
    except Exception:
        plat = {"distribution": "unknown", "distro_id": "unknown",
                "distro_version": "unknown", "architecture": "unknown",
                "package_manager": None, "supported": False}
    report["os"] = plat
    try:
        hw = hardware.detect(runner)
    except Exception:
        hw = {"cpu": "", "ram_total_mb": 0, "disk": {}, "gpu": {"present": False}}
    report["hardware"] = hw
    try:
        sw = software.detect(runner)
    except Exception:
        sw = {"tools": {}, "missing_required": [], "ok": False}
    for name in ("python3", "git", "pip", "venv"):
        c = sw.get("tools", {}).get(name) or {"ok": False, "present": False}
        st, detail = _tool_state(c)
        report["items"][name] = {"state": st, "detail": str(detail)[:160]}
        if st != AVAILABLE:
            report["needs_repair"].append(name)
    dock = _docker_state(runner)
    report["items"]["docker"] = dock
    if dock["state"] != AVAILABLE:
        report["needs_repair"].append("docker")
    try:
        net = sysdet.detect_network(runner)
    except Exception:
        net = {"dns": False, "https": False, "offline": True}
    report["network"] = net
    if prefix is not None:
        try:
            perms = sysdet.detect_permissions(prefix)
        except Exception:
            perms = {"user": "?", "is_root": False, "sudo": False,
                     "prefix_writable": False}
        report["permissions"] = perms
    else:
        report["permissions"] = {}
    report["all_ready"] = not report["needs_repair"] and not net.get("offline")
    return report
