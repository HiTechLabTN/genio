"""Updater manifest schema + verification (G5-C task F).

Tauri-compatible latest.json shape with explicit signature status.
Production channel REQUIRES a minisign signature; development fixtures
may be unsigned ONLY with allow_unsigned=True (never in production).

No private keys here. No fake signatures. Ever.
"""
import hashlib


class UpdaterError(ValueError):
    pass


def make_manifest(product, version, platform, arch, url, size, sha256,
                  notes="", signature=None):
    manifest = {
        "product": product,
        "version": version,
        "platform": platform,
        "arch": arch,
        "url": url,
        "size": size,
        "sha256": sha256,
        "notes": notes,
        "signature": signature,
        "signature_status": "signed" if signature else "UNSIGNED-DEVELOPMENT",
    }
    return manifest


def to_tauri(manifest):
    """Tauri latest.json shape for one platform entry."""
    plat_key = {"linux": {"x86_64": "linux-x86_64", "aarch64": "linux-aarch64"},
                }.get(manifest["platform"], {}).get(manifest["arch"])
    if plat_key is None:
        raise UpdaterError(f"unsupported platform/arch: {manifest['platform']}/{manifest['arch']}")
    return {"version": manifest["version"], "notes": manifest.get("notes", ""),
            "pub_date": manifest.get("built_at", ""),
            "platforms": {plat_key: {"signature": manifest.get("signature") or "",
                                     "url": manifest["url"]}}}


def _version_key(v):
    import re
    return tuple(int(x) for x in re.findall(r"\d+", str(v))[:4])


def verify(manifest, current_version, platform, arch, data_bytes=None,
           allow_unsigned=False, allow_downgrade=False):
    """Returns manifest on success, raises UpdaterError otherwise."""
    for field in ("product", "version", "platform", "arch", "url", "size", "sha256"):
        if field not in manifest or manifest[field] in (None, ""):
            raise UpdaterError(f"malformed manifest: missing {field}")
    if manifest["platform"] != platform or manifest["arch"] != arch:
        raise UpdaterError("wrong platform/arch for this machine")
    if _version_key(manifest["version"]) < _version_key(current_version) and not allow_downgrade:
        raise UpdaterError("downgrade refused (use explicit override)")
    if not manifest.get("signature") and not allow_unsigned:
        raise UpdaterError("unsigned artifact refused on production channel")
    if data_bytes is not None:
        digest = hashlib.sha256(data_bytes).hexdigest()
        if digest != manifest["sha256"]:
            raise UpdaterError("SHA mismatch — artifact untrusted")
        if len(data_bytes) != manifest["size"]:
            raise UpdaterError("size mismatch — artifact untrusted")
    return manifest
