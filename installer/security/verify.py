"""Install-time security verification (§16 — survivors, not new policy)."""
import os


def verify(runner, prefix):
    """Returns list of {name, status, detail} using PASS/WARN/FAIL."""
    from installer.core.manifest import read_manifest
    from installer.core.paths import layout
    out = []
    lay = layout(prefix)
    if read_manifest(lay["manifest"]) is None:
        out.append({"name": "manifest", "status": "WARN",
                    "detail": "no installation manifest at prefix"})
    env = {}
    if lay["env_file"].is_file():
        for line in lay["env_file"].read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
        mode = oct(os.stat(lay["env_file"]).st_mode & 0o777)
        out.append({"name": "env-perms", "status": "PASS" if mode == "0o600" else "WARN",
                    "detail": f"{lay['env_file']} mode={mode}"})
    else:
        out.append({"name": "env-present", "status": "FAIL", "detail": "config/.env missing"})
        return out
    strict = env.get("GENIO_SECURITY_MODE", "") == "strict" or env.get("GENIO_ENV") == "prod"
    keyed = bool(env.get("GENIO_API_KEY"))
    if strict and not keyed:
        out.append({"name": "boot-guard", "status": "FAIL",
                    "detail": "strict/prod without GENIO_API_KEY would refuse boot"})
    else:
        out.append({"name": "boot-guard", "status": "PASS",
                    "detail": f"mode={'strict' if strict else 'development'} keyed={keyed}"})
    cloud = env.get("GENIO_ALLOW_CLOUD", "")
    out.append({"name": "cloud-default", "status": "PASS" if not cloud else "WARN",
                "detail": "closed by default" if not cloud else f"enabled ({cloud})"})
    # Repo must not contain live secrets in tracked files (spot check).
    repo = lay["repo"]
    hits = []
    if repo.is_dir():
        import re
        pat = re.compile(r"sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|xox[bap]-[A-Za-z0-9-]{10,}")
        for name in ("config.py", "genio_server/server/main.py"):
            p = repo / name
            if p.is_file():
                try:
                    if pat.search(p.read_text()):
                        hits.append(name)
                except OSError:
                    pass
    out.append({"name": "tracked-secrets", "status": "FAIL" if hits else "PASS",
                "detail": f"suspicious: {hits}" if hits else "no token patterns in key files"})
    return out
