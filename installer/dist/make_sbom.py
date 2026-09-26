"""SBOM generator — CycloneDX-lite from lockfiles (no invented data).

Python: requirements.lock pins (source: pypi). JS: package-lock.json
(name@version + resolved URL). Run: python3 make_sbom.py <repo> <out>.
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


def _py(lock):
    comps = []
    for line in Path(lock).read_text().splitlines():
        m = re.match(r"^([A-Za-z0-9_.\-]+)(\[.*\])?==([^\s;]+)", line.strip())
        if m:
            name = m.group(1)
            comps.append({"type": "library", "name": name, "version": m.group(3),
                          "purl": f"pkg:pypi/{name}@{m.group(3)}"})
    return comps


def _npm(lockfile):
    comps = []
    try:
        data = json.loads(Path(lockfile).read_text())
    except (OSError, ValueError):
        return comps
    for path, meta in (data.get("packages") or {}).items():
        if not path or not isinstance(meta, dict) or "version" not in meta:
            continue
        name = path.split("node_modules/")[-1]
        comps.append({"type": "library", "name": f"npm:{name}",
                      "version": meta["version"],
                      "purl": f"pkg:npm/{name}@{meta['version']}"})
    return comps


def make_sbom(repo, out):
    repo = Path(repo)
    components = _py(repo / "requirements.lock")
    components += _npm(repo / "genio_client" / "package-lock.json")
    sbom = {"bomFormat": "CycloneDX", "specVersion": "1.5", "version": 1,
            "metadata": {"timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                         "component": {"type": "application", "name": "genio"}},
            "components": sorted(components, key=lambda c: c["name"].lower())}
    Path(out).write_text(json.dumps(sbom, indent=1))
    print(f"sbom: {len(components)} components -> {out}")
    return out


if __name__ == "__main__":
    make_sbom(sys.argv[1], sys.argv[2])
