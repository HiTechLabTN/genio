"""Software detection with REQUIRED/OPTIONAL classification (§5)."""
import shutil
import sys

# name -> (kind, min_version|None). kind: required|recommended|optional.
REQUIREMENTS = {
    "python3": ("required", (3, 10)),
    "git": ("required", None),
    "pip": ("required", None),
    "venv": ("required", None),
    "docker": ("recommended", None),
    "node": ("optional", (18, 0)),
    "npm": ("optional", None),
    "ffmpeg": ("optional", None),
    "curl": ("recommended", None),
}


def _version_tuple(out):
    import re
    m = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", out or "")
    if not m:
        return None
    return tuple(int(g) for g in m.groups() if g is not None)


def check_one(runner, name):
    kind, minimum = REQUIREMENTS[name]
    if name == "pip":
        found = shutil.which("pip3") or shutil.which("pip")
        ver = _version_tuple(runner.run([sys.executable, "-m", "pip", "--version"], timeout=30)["out"]) if found else None
        return {"name": name, "kind": kind, "present": bool(found), "version": ver, "ok": bool(found)}
    if name == "venv":
        import tempfile
        from pathlib import Path
        try:
            with tempfile.TemporaryDirectory(prefix="genio-venv-probe-") as tmp:
                # Honest check: real venv creation (help alone lies when
                # ensurepip is absent). Full create first, fallback probe.
                r = runner.run([sys.executable, "-m", "venv", str(Path(tmp) / "v")],
                               timeout=120)
                if r["ok"]:
                    return {"name": name, "kind": kind, "present": True,
                            "version": None, "ok": True}
                r2 = runner.run([sys.executable, "-m", "venv", "--without-pip",
                                 str(Path(tmp) / "v2")], timeout=120)
                if r2["ok"]:
                    return {"name": name, "kind": kind, "present": True,
                            "version": None, "ok": False,
                            "note": "venv works only --without-pip (ensurepip absent)"}
        except Exception:
            pass
        return {"name": name, "kind": kind, "present": False, "version": None, "ok": False}
    path = shutil.which(name if name != "python3" else sys.executable)
    if name == "python3":
        ver = sys.version_info[:3]
        ok = ver >= minimum
        return {"name": name, "kind": kind, "present": True, "version": ver, "ok": ok}
    if not path:
        return {"name": name, "kind": kind, "present": False, "version": None,
                "ok": kind != "required"}
    flag = "--version"
    r = runner.run([path, flag], timeout=30)
    ver = _version_tuple(r["out"] + r["err"])
    ok = True
    if minimum and ver and ver < minimum:
        ok = kind != "required"
    return {"name": name, "kind": kind, "present": True, "version": ver, "ok": ok}


def detect(runner):
    results = {name: check_one(runner, name) for name in REQUIREMENTS}
    missing_required = [n for n, r in results.items()
                        if r["kind"] == "required" and not r["ok"]]
    return {"tools": results, "missing_required": missing_required,
            "ok": not missing_required}
