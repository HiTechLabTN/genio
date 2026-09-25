"""Phase 8 tests — filesystem boundary + canonicalisation.

Autorisation TOUJOURS après realpath : symlink escape, /etc/shadow,
traversées, /root/.ssh, docker.sock, devices. Écritures légitimes OK.
"""
import os
import sys

sys.path.insert(0, "/data/ai_tools/genio")

from genio_server.tools.fs_guard import (
    authorize,
    canonicalize,
    sanitize_ext,
    stage_path,
)

WS = "/tmp/ph8_ws"


def setup_function(_):
    os.makedirs(WS, exist_ok=True)


def test_canonical_resolves_symlink():
    link = os.path.join(WS, "evil")
    try:
        os.symlink("/etc/shadow", link)
    except FileExistsError:
        pass
    assert canonicalize(link) == "/etc/shadow"
    assert authorize(link, workspace=WS) is not None


def test_absolute_sensitive_denied():
    for p in ("/etc/shadow", "/etc/passwd", "/root/.ssh/id_rsa",
              "/var/run/docker.sock", "/proc/self/environ", "/dev/sda"):
        assert authorize(p, workspace=WS) is not None, p


def test_traversal_denied():
    assert authorize(os.path.join(WS, "..", "escape"), workspace=WS) is not None
    assert authorize("/tmp/../etc/shadow", workspace=WS) is not None


def test_credential_filenames_denied():
    assert authorize(os.path.join(WS, "id_rsa"), workspace=WS) is not None
    assert authorize(os.path.join(WS, "app.env"), workspace=WS) is not None


def test_legit_workspace_write_allowed():
    assert authorize(os.path.join(WS, "sub", "f.txt"), workspace=WS) is None


def test_read_only_scope():
    assert authorize("/etc/hostname", scope="read_only_system",
                     for_write=False) is None
    assert authorize("/etc/hostname", scope="read_only_system",
                     for_write=True) is not None
    assert authorize("/x", scope="none") is not None


def test_sanitize_ext():
    assert sanitize_ext("../../evil.py") == ".py"
    assert sanitize_ext("a." + "x" * 40) == ".bin"
    assert sanitize_ext("noext") == ".bin"
    assert sanitize_ext("doc.PDF") == ".pdf"


def test_stage_path_inside_workspace():
    p = stage_path(WS, "file", ".txt", "tok1")
    assert p.startswith(os.path.realpath(WS) + os.sep)
    assert p.endswith("file_tok1.txt")


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
