"""Version source-of-truth lock (G5-A §9, G5-B §8).

- Product release version: VERSION file (e.g. 4.1.0).
- Client component: package.json == tauri.conf.json (bundle version).
- Installer component: installer/__init__.py INSTALLER_VERSION.
- IPC contract: PROTOCOL_VERSION. API app: FastAPI version.
- Cargo.toml crate version is scaffold debt (0.1.0), NOT a product
  version — asserted as documentation, not enforced equal.
- No stale product version may linger (the 2.0.0 incident).
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _read(p):
    return (ROOT / p).read_text()


def test_product_version_single_truth():
    v = (ROOT / "VERSION").read_text().strip()
    assert re.fullmatch(r"\d+\.\d+\.\d+", v), f"VERSION malformed: {v!r}"


def test_client_versions_aligned():
    pkg = json.loads(_read("genio_client/package.json"))["version"]
    tauri = json.loads(_read("genio_client/src-tauri/tauri.conf.json"))["version"]
    assert pkg == tauri, f"package.json {pkg} != tauri.conf {tauri}"
    assert pkg != "0.1.0"


def test_component_versions_sane():
    init = _read("installer/__init__.py")
    m = re.search(r'INSTALLER_VERSION\s*=\s*"([^"]+)"', init)
    assert m and re.fullmatch(r"\d+\.\d+\.\d+", m.group(1))
    proto = _read("genio/integrations/hitechos/__init__.py")
    assert 'PROTOCOL_VERSION = "1.0"' in proto


def test_no_stale_product_version():
    for rel in ("docs/install/INSTALLATION.md", "docs/release/RELEASE_NOTES_4.1.0.md",
                "genio_client/src/product-data.json"):
        text = _read(rel)
        assert "2.0.0-sovereign" not in text, f"stale version in {rel}"
        assert "v2.0.0" not in text, f"stale version in {rel}"


def test_desktop_mobile_ids_stable():
    tauri = json.loads(_read("genio_client/src-tauri/tauri.conf.json"))
    assert tauri["identifier"] == "tn.hitechlab.genio"
    cap = json.loads(_read("genio_client/capacitor.config.json"))
    assert cap["appId"] == "com.hitechlab.genio"
