"""Doctor — PASS/WARN/FAIL/NOT_APPLICABLE health system (§12-13).

Distinguishes PROCESS ALIVE / SERVICE READY / APPLICATION HEALTHY /
DEPENDENCIES HEALTHY / SECURITY HEALTHY. Never a misleading green.

Tool detection is consumed from the single authoritative engine
(installer.preflight) — install, doctor and assistant share states.
"""
from installer.core.manifest import read_manifest
from installer.core.paths import DEFAULT_PORTS, layout
from installer.detectors import hardware
from installer.detectors import osinfo as platform
from installer.detectors.system import detect_network, detect_permissions, detect_ports
from installer import preflight as _preflight


def _check(name, status, detail=""):
    assert status in ("PASS", "WARN", "FAIL", "NOT_APPLICABLE")
    return {"name": name, "status": status, "detail": str(detail)[:300]}


def _http_probe(url, timeout=8):
    try:
        import urllib.request
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status, r.read(200)
    except Exception as e:
        return None, str(e)[:120]


def doctor(runner, prefix=None, deep=False):
    checks = []
    plat = platform.detect(runner)
    checks.append(_check("os", "PASS" if plat["supported"] else "FAIL",
                         f"{plat['distribution']} {plat['distro_version']} "
                         f"{plat['architecture']} init={plat['init']}"))
    hw = hardware.detect(runner)
    ram = hw["ram_total_mb"] or 0
    checks.append(_check("cpu", "PASS" if hw["cpu"] else "WARN", hw["cpu"] or "unknown"))
    checks.append(_check("ram", "PASS" if ram >= 4000 else ("WARN" if ram else "NOT_APPLICABLE"),
                         f"{ram} MB" if ram else "unknown"))
    disk_free = (hw["disk"] or {}).get("free_gb")
    checks.append(_check("disk", "PASS" if (disk_free or 0) >= 5 else "WARN",
                         f"free={disk_free}GB" if disk_free is not None else "unknown"))
    gpu = hw["gpu"]
    checks.append(_check("gpu", "PASS" if gpu["present"] else "NOT_APPLICABLE",
                         f"{gpu['vendor']} {gpu['memory_mb']}MB" if gpu["present"] else "no GPU"))
    sw = _preflight.preflight(runner)
    _statemap = {
        _preflight.AVAILABLE: "PASS",
        _preflight.MISSING: "FAIL",
        _preflight.BROKEN: "FAIL",
        _preflight.DAEMON_DOWN: "FAIL",
        _preflight.PERMISSION_DENIED: "FAIL",
        _preflight.VERSION_TOO_OLD: "WARN",
        _preflight.UNKNOWN: "WARN",
    }
    for name in ("python3", "git", "pip", "venv"):
        it = sw["items"].get(name, {"state": _preflight.UNKNOWN, "detail": "?"})
        checks.append(_check(f"tool:{name}", _statemap.get(it["state"], "WARN"),
                             it.get("detail", "")))
    dock = sw["items"].get("docker", {"state": _preflight.UNKNOWN, "detail": "?"})
    checks.append(_check("tool:docker", _statemap.get(dock["state"], "WARN"),
                         dock.get("detail", "")))
    import re as _re
    import shutil as _sh
    for name in ("node", "npm", "ffmpeg", "curl"):
        if _sh.which(name):
            r = runner.run([name, "--version"], timeout=15)
            m = _re.search(r"(\d+\.\d+(?:\.\d+)?)", (r.get("out") or "") + (r.get("err") or ""))
            checks.append(_check(f"tool:{name}", "PASS" if r["ok"] else "WARN",
                                 f"v={m.group(1)}" if m else "present"))
        else:
            checks.append(_check(f"tool:{name}", "NOT_APPLICABLE", "optional"))
    net = detect_network(runner)
    checks.append(_check("network", "PASS" if net["https"] else ("WARN" if net["dns"] else "FAIL"),
                         "offline" if net["offline"] else "online"))

    ports = dict(DEFAULT_PORTS)
    manifest = None
    if prefix:
        lay = layout(prefix)
        manifest = read_manifest(lay["manifest"])
        if manifest and manifest.get("ports"):
            ports.update(manifest["ports"])
        checks.append(_check("manifest", "PASS" if manifest else "FAIL",
                             f"id={manifest['installation_id'][:8]} health={manifest['health']}" if manifest else "none"))
        checks.append(_check("config", "PASS" if lay["env_file"].is_file() else "FAIL",
                             str(lay["env_file"]) if lay["env_file"].is_file() else "missing .env"))
        checks.append(_check("venv", "PASS" if (lay["venv"] / "bin" / "python").exists() else "FAIL",
                             str(lay["venv"])))
        checks.append(_check("data-dir", "PASS" if lay["data"].is_dir() else "WARN", str(lay["data"])))
        perms = detect_permissions(prefix)
        checks.append(_check("permissions", "PASS" if perms["prefix_writable"] else "FAIL",
                             f"user={perms['user']} root={perms['is_root']}"))
    portmap = detect_ports(runner, ports)
    for name, info in portmap.items():
        if info["free"]:
            checks.append(_check(f"port:{name}={info['port']}", "PASS", "free"))
        else:
            owner = info["owner"]
            checks.append(_check(f"port:{name}={info['port']}", "WARN",
                                 f"held by pid={owner.get('pid')} {owner.get('process')} "
                                 f"svc={owner.get('service')}"))
    # Service probes (read-only; a bound port is NOT health).
    if deep and prefix and manifest:
        api_port = ports.get("api", 8000)
        code, _ = _http_probe(f"http://127.0.0.1:{api_port}/health")
        checks.append(_check("api", "PASS" if code == 200 else "FAIL",
                             f"GET /health -> {code}"))
        code, _ = _http_probe(f"http://127.0.0.1:{ports.get('web', 8098)}/app")
        checks.append(_check("frontend", "PASS" if code == 200 else "WARN",
                             f"GET /app -> {code}"))
    fails = [c for c in checks if c["status"] == "FAIL"]
    return {"checks": checks, "fail": len(fails),
            "verdict": "HEALTHY" if not fails else "ATTENTION"}
