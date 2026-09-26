"""Existing-installation discovery — the no-duplicate rule (§1).

States: NOT_FOUND HEALTHY DEGRADED BROKEN OUTDATED PARTIAL UNKNOWN
        DEVELOPMENT_CHECKOUT DOCKER_INSTALLATION SYSTEM_SERVICE_INSTALLATION
Signals: manifest, .genio metadata, version, git checkout, units,
         CLI, containers, images, config/data/runtime dirs, processes.
"""
import subprocess
from pathlib import Path

from installer.core.manifest import read_manifest
from installer.core.paths import DEV_MARKERS, KNOWN_UNITS


def _read_version(repo):
    for name in ("VERSION", "version.txt", "package.json"):
        p = Path(repo) / name
        if p.is_file():
            try:
                return p.read_text().strip()[:40]
            except OSError:
                pass
    return None


def _git_commit(repo):
    try:
        out = subprocess.run(["git", "-C", str(repo), "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=20)
        return out.stdout.strip()[:12] if out.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def _unit_active(runner, unit):
    r = runner.run(["systemctl", "is-active", unit], timeout=15)
    return r["out"].strip() == "active"


def inspect_prefix(prefix, runner):
    """Inspect one candidate prefix; returns an installation record."""
    from installer.core.paths import layout
    lay = layout(prefix)
    rec = {"location": str(lay["prefix"]), "kind": "prefix", "state": "UNKNOWN",
           "version": None, "commit": None, "manifest": None, "signals": []}
    man = read_manifest(lay["manifest"]) if lay["manifest"].is_file() else None
    if man:
        rec["manifest"] = man
        rec["version"] = man.get("version")
        rec["commit"] = man.get("commit")
        rec["signals"].append("manifest")
    repo = lay["repo"]
    if repo.is_dir():
        markers = [m for m in DEV_MARKERS if (repo / m).exists()]
        if markers:
            rec["signals"].append("checkout:" + ",".join(sorted(markers)))
            if ".git" in markers:
                rec["commit"] = rec["commit"] or _git_commit(repo)
                rec["version"] = rec["version"] or _read_version(repo)
    has_code = (repo / "genio_server").is_dir() or (repo / "config.py").is_file()
    has_venv = (lay["venv"] / "bin" / "python").exists()
    has_config = (lay["config"] / ".env").is_file()
    if man and has_code and has_venv and has_config:
        rec["state"] = "HEALTHY"
    elif man and has_code and (has_venv or has_config):
        rec["state"] = "DEGRADED"
    elif man or has_code or has_venv:
        rec["state"] = "PARTIAL"
    if rec["state"] == "UNKNOWN" and not rec["signals"]:
        rec["state"] = "NOT_FOUND"
    return rec


def inspect_development_checkout(path, runner):
    """A raw git checkout (like the dev machine) is NOT an installation."""
    p = Path(path)
    rec = {"location": str(p), "kind": "development-checkout",
           "state": "NOT_FOUND", "signals": []}
    if not p.is_dir():
        return rec
    markers = [m for m in DEV_MARKERS if (p / m).exists()]
    if markers:
        rec["state"] = "DEVELOPMENT_CHECKOUT"
        rec["signals"].append("checkout:" + ",".join(sorted(markers)))
        rec["commit"] = _git_commit(p)
        rec["version"] = _read_version(p)
    return rec


def inspect_system_services(runner):
    found = []
    for unit in KNOWN_UNITS:
        r = runner.run(["systemctl", "show", unit, "-p", "LoadState,ActiveState,ExecStart,WorkingDirectory"],
                       timeout=15)
        if "LoadState=loaded" in r["out"]:
            active = "ActiveState=active" in r["out"]
            wd = None
            for line in r["out"].splitlines():
                if line.startswith("WorkingDirectory="):
                    wd = line.split("=", 1)[1] or None
            found.append({"location": wd or unit, "kind": "system-service",
                          "unit": unit,
                          "state": "HEALTHY" if active else "DEGRADED",
                          "signals": ["unit:" + unit]})
    return found


def inspect_docker(runner):
    found = []
    r = runner.run(["docker", "images", "--format", "{{.Repository}}:{{.Tag}}"], timeout=30)
    if not r["ok"]:
        return found
    for line in r["out"].splitlines():
        if line.startswith("genio"):
            found.append({"location": line, "kind": "docker-image",
                          "state": "UNKNOWN", "signals": ["image:" + line]})
    r = runner.run(["docker", "ps", "-a", "--format", "{{.Names}} {{.Image}} {{.Status}}"], timeout=30)
    if r["ok"]:
        for line in r["out"].splitlines():
            if "genio" in line.lower():
                found.append({"location": line, "kind": "docker-container",
                              "state": "HEALTHY" if "Up " in line else "DEGRADED",
                              "signals": ["container:" + line]})
    return found


def discover(runner, prefix, extra_checkout=None):
    """Full discovery: prefix + optional dev checkout + services + docker."""
    installs = []
    rec = inspect_prefix(prefix, runner)
    if rec["state"] != "NOT_FOUND":
        installs.append(rec)
    if extra_checkout:
        dev = inspect_development_checkout(extra_checkout, runner)
        if dev["state"] != "NOT_FOUND":
            installs.append(dev)
    installs.extend(inspect_system_services(runner))
    installs.extend(inspect_docker(runner))
    # OUTDATED: manifest commit/version older than repo HEAD is decided by
    # update flow (needs source); mark here only when manifest exists.
    return installs


def summarize(installs):
    """Human-readable reconciliation plan (never deletes, never picks)."""
    if not installs:
        return {"action": "install", "message": "No Genio installation detected."}
    prefixes = [i for i in installs if i["kind"] == "prefix"]
    if len(prefixes) == 1 and len(installs) == 1:
        st = prefixes[0]["state"]
        if st == "HEALTHY":
            return {"action": "already-installed",
                    "message": f"Already installed ({st}) at {prefixes[0]['location']}. "
                               "Use verify, update or repair — no second installation created."}
        return {"action": "repair-or-update",
                "message": f"Existing installation is {st} at {prefixes[0]['location']}. "
                           "Repair or update it instead of reinstalling."}
    lines = ["Multiple Genio traces detected — no automatic choice made:"]
    for i in installs:
        lines.append(f"  - [{i['kind']}] {i['location']} state={i['state']}")
    lines.append("Provide --prefix for an isolated install, or repair/update one explicitly.")
    return {"action": "reconcile", "message": "\n".join(lines)}
