"""Phase 21 tests — upload security stricte.

Binaire déguisé en .jpg rejeté, purge d'expiration, quota session,
permissions 0o600. Octets réels, aucun réseau.
"""
import os
import sys
import time

sys.path.insert(0, "/data/ai_tools/genio")

from genio_server.tools import upload_guard as ug

PNG = (b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)
MZ_JPG = b"MZ" + b"\x90\x00" * 40  # exécutable déguisé
TEXT = b"hello world\nline2\n"


def test_sniff_kinds():
    assert ug.sniff(PNG) == "png"
    assert ug.sniff(TEXT) == "text"
    assert ug.sniff(b"") == "empty"
    assert ug.sniff(b"\xff\xd8\xff\x00abc") == "jpg"
    assert ug.sniff(b"%PDF-1.4 xyz") == "pdf"


def test_binary_disguised_as_jpg_rejected():
    ext, reason = ug.validate_upload(MZ_JPG, "photo.jpg")
    assert ext is None, "binaire déguisé accepté !"


def test_real_png_accepted():
    ext, reason = ug.validate_upload(PNG, "photo.png")
    assert ext == ".png"


def test_text_as_py_accepted_exe_as_py_refused():
    assert ug.validate_upload(TEXT, "s.py")[0] == ".py"
    assert ug.validate_upload(MZ_JPG, "s.py")[0] is None


def test_quota_enforced():
    ug.reset_quota("ph21q")
    assert ug.check_quota("ph21q", 10, quota=100) is None
    assert ug.check_quota("ph21q", 95, quota=100) is not None
    ug.reset_quota("ph21q")
    assert ug.check_quota("ph21q", 95, quota=100) is None


def test_purge_expired(tmp_path):
    old = tmp_path / "old.bin"
    new = tmp_path / "new.bin"
    old.write_bytes(b"x")
    new.write_bytes(b"x")
    ancient = time.time() - 7200
    os.utime(old, (ancient, ancient))
    assert ug.purge_expired(tmp_path, ttl=3600) == 1
    assert not old.exists() and new.exists()


def test_secure_write_perms(tmp_path):
    p = str(tmp_path / "s.bin")
    ug.secure_write(p, b"data")
    assert (os.stat(p).st_mode & 0o777) == 0o600


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
