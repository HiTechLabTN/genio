"""Public-truth consistency — README/landing/portal vs authoritative sources.

Fails on stale claims (deleted tags, old test counts) and on drift
between product-data.json and its sources.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

STALE = [
    "v2.0.0-sovereign-rc1",
    "v2.0.0--sovereign--rc1",
    "269%20Passed",
    "269 Passed",
    "sovereign-rc1",
]


def _read(rel):
    return (ROOT / rel).read_text()


def test_no_stale_release_claims():
    hits = []
    for rel in ("README.md", "genio_client/src/product-data.json",
                "docs/product/GENIO_PUBLIC_PRODUCT_TRUTH.md"):
        try:
            text = _read(rel)
        except FileNotFoundError:
            continue
        for s in STALE:
            if s in text:
                hits.append(f"{rel}: {s}")
    assert not hits, f"stale claims: {hits}"


def test_readme_points_to_public_release():
    text = _read("README.md")
    assert "releases/tag/v5.0.0" in text or "v5.0.0" in text


def test_public_release_file_valid():
    rel = json.loads(_read("docs/releases/PUBLIC_RELEASE.json"))
    assert rel["tag"] == "v5.0.0"
    for key in ("tarball", "sha256", "manifest", "sbom", "notes"):
        url = rel[key]
        assert url.startswith("https://"), f"{key} not https: {url}"
    assert rel["docker"].startswith("ghcr.io/hitechlabtn/genio:")


def test_product_data_matches_sources():
    pd = json.loads(_read("genio_client/src/product-data.json"))
    assert pd["version"] == (ROOT / "VERSION").read_text().strip()
    assert pd["public_release"]["tag"] == "v5.0.0"
    assert pd["public_release"]["tarball"].endswith("genio-5.0.0.tar.gz")


def test_download_center_uses_truth_not_hardcoded_old_release():
    text = _read("genio_client/src/portal/pages/DownloadCenter.tsx")
    assert "v4.1.0" not in text or "product-data" in text.lower() or "pd." in text, \
        "hardcoded old release in DownloadCenter"
