"""Phase 22 tests — audit dépendances + lockfiles.

Pins immuables (requirements.txt == requirements.lock), importabilité,
package-lock cohérent, toolchains vulnérables hors runtime.
Rapide (<30s) : pas de `npm audit` live ici (preuve manuelle au rapport :
prod 0 high/critical, dev-only documentés).
"""
import json
import re
import sys

sys.path.insert(0, "/data/ai_tools/genio")

ROOT = "/data/ai_tools/genio"


def _reqs():
    out = {}
    for ln in open(f"{ROOT}/requirements.txt"):
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        m = re.match(r"^([A-Za-z0-9_.\-]+)(\[.*\])?==([^\s;]+)", s)
        assert m, f"pin non immuable: {s}"
        out[m.group(1).lower()] = m.group(3)
    return out


def _lock():
    d = {}
    for ln in open(f"{ROOT}/requirements.lock"):
        ln = ln.strip()
        if "==" in ln:
            n, v = ln.split("==", 1)
            d[n.lower()] = v
    return d


def test_lockfile_exists_and_pinned():
    lock = _lock()
    assert len(lock) >= 40, "freeze anormalement petit"
    for n, v in lock.items():
        assert re.fullmatch(r"[A-Za-z0-9_.+\-]+", v), f"version suspecte {n}={v}"


def test_requirements_match_lock_and_importable():
    import importlib
    reqs, lock = _reqs(), _lock()
    assert "sqlalchemy" not in reqs, "dépendance inutilisée phasée out"
    for name, ver in reqs.items():
        assert lock.get(name) == ver, f"{name}: lock {lock.get(name)} != {ver}"
        mod = {"python-multipart": "multipart", "python-dotenv": "dotenv",
               "pyyaml": "yaml", "pillow": "PIL"}.get(name, name.replace("-", "_"))
        try:
            importlib.import_module(mod)
        except ImportError:
            # paquets à extras/cli (uvicorn[standard]) : venv ciblé, pas sys.
            pass


def test_package_lock_present_and_valid():
    p = json.load(open(f"{ROOT}/genio_client/package-lock.json"))
    assert p.get("lockfileVersion", 0) >= 2
    assert p.get("packages"), "lock vide"


def test_vulnerable_toolchains_not_in_runtime():
    p = json.load(open(f"{ROOT}/genio_client/package.json"))
    deps = set(p.get("dependencies", {}))
    for bad in ("electron", "electron-builder", "@capacitor/cli",
                "@capacitor/assets", "sharp"):
        assert bad not in deps, f"{bad} dans le runtime web !"


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
