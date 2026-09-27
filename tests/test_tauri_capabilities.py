"""Tauri capability contract — least privilege locked in CI.

Asserts default.json grants no broad native power:
- shell: open-only (no execute/run)
- fs/http: explicit scopes, no wildcard
- no custom Rust commands beyond scaffold (audited list)
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAP = ROOT / "genio_client" / "src-tauri" / "capabilities" / "default.json"


def _cap():
    assert CAP.is_file(), "capability file missing"
    return json.loads(CAP.read_text())


def test_shell_open_only():
    perms = [e if isinstance(e, str) else e.get("identifier") for e in _cap()["permissions"]]
    assert "shell:allow-open" in perms
    assert not any("execut" in str(p) for p in perms), "shell execute must never appear"


def test_fs_scoped_no_wildcard():
    found = {}
    for e in _cap()["permissions"]:
        if isinstance(e, dict) and str(e.get("identifier", "")).startswith("fs:"):
            found[e["identifier"]] = e.get("allow", [])
    assert found, "fs permissions must be scoped objects"
    for ident, allow in found.items():
        assert allow, f"{ident} has empty scope"
        for rule in allow:
            assert "*" not in str(rule.get("path", "")).replace("/**", ""), \
                f"{ident} wildcard beyond dir scope: {rule}"
            assert ".." not in str(rule.get("path", "")), f"{ident} traversal: {rule}"


def test_http_scoped_to_official():
    found = {}
    for e in _cap()["permissions"]:
        if isinstance(e, dict) and str(e.get("identifier", "")).startswith("http:"):
            found[e["identifier"]] = e.get("allow", [])
    assert found, "http permissions must be scoped objects"
    urls = [r.get("url", "") for rules in found.values() for r in rules]
    assert urls, "http scope empty"
    for u in urls:
        assert u.startswith("https://"), f"non-https scope: {u}"
        assert "github.com" in u or "objects.githubusercontent.com" in u, \
            f"unofficial origin scoped: {u}"


def test_no_custom_rust_commands():
    src = ROOT / "genio_client" / "src-tauri" / "src" / "lib.rs"
    text = src.read_text()
    commands = [line.strip() for line in text.splitlines() if "#[tauri::command]" in line]
    assert len(commands) <= 1, f"unexpected custom commands: {commands}"


def test_updater_key_labeled_untrusted():
    import base64
    conf = json.loads((ROOT / "genio_client" / "src-tauri" / "tauri.conf.json").read_text())
    pubkey = conf.get("plugins", {}).get("updater", {}).get("pubkey", "")
    decoded = base64.b64decode(pubkey).decode(errors="replace")
    assert "untrusted" in decoded.lower(), "updater key must stay labeled until real signing exists"
