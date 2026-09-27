"""Updater manifest tests — accept/reject matrix, no fake signatures."""
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from installer.dist.updater_manifest import (  # noqa: E402
    UpdaterError, make_manifest, to_tauri, verify,
)


def _good(**kw):
    base = make_manifest(
        product="genio", version="4.2.0", platform="linux", arch="x86_64",
        url="https://example.invalid/genio.tar.gz", size=4,
        sha256="9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
        notes="test")
    base.update(kw)
    return base


def test_accept_signed_with_matching_bytes():
    data = b"test"
    m = _good(signature="minisign-sig-placeholder")
    assert verify(m, "4.1.0", "linux", "x86_64", data_bytes=data)["version"] == "4.2.0"


def test_reject_tampered_bytes():
    m = _good(signature="sig")
    with pytest.raises(UpdaterError):
        verify(m, "4.1.0", "linux", "x86_64", data_bytes=b"tampered")


def test_reject_wrong_platform_arch():
    with pytest.raises(UpdaterError):
        verify(_good(signature="s"), "4.1.0", "windows", "x86_64")
    with pytest.raises(UpdaterError):
        verify(_good(signature="s"), "4.1.0", "linux", "arm64")


def test_reject_downgrade_without_override():
    m = _good(version="4.0.0", signature="s")
    with pytest.raises(UpdaterError):
        verify(m, "4.1.0", "linux", "x86_64")
    assert verify(m, "4.1.0", "linux", "x86_64", allow_downgrade=True)


def test_unsigned_refused_on_prod_allowed_in_dev():
    m = _good()
    assert m["signature_status"] == "UNSIGNED-DEVELOPMENT"
    with pytest.raises(UpdaterError):
        verify(m, "4.1.0", "linux", "x86_64")
    assert verify(m, "4.1.0", "linux", "x86_64", allow_unsigned=True)


def test_reject_malformed_and_size_mismatch():
    bad = _good()
    del bad["sha256"]
    with pytest.raises(UpdaterError):
        verify(bad, "4.1.0", "linux", "x86_64", allow_unsigned=True)
    m = _good(size=999, signature="s")
    with pytest.raises(UpdaterError):
        verify(m, "4.1.0", "linux", "x86_64", data_bytes=b"test")


def test_tauri_shape_and_unsupported():
    t = to_tauri(_good(signature="s"))
    assert t["platforms"]["linux-x86_64"]["url"].startswith("https://")
    with pytest.raises(UpdaterError):
        to_tauri(_good(platform="windows"))
