"""Distribution tests — release archive, integrity, no-git update (§8)."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from installer.core.runner import Runner  # noqa: E402
from installer.dist.make_release import (  # noqa: E402
    make_release, sha256_file, verify_archive,
)


def _git(path, *argv):
    env = dict(os.environ, GIT_CONFIG_NOSYSTEM="1", GIT_AUTHOR_NAME="t",
               GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
               GIT_COMMITTER_EMAIL="t@t")
    subprocess.run(["git", *argv], cwd=str(path), env=env, check=True,
                   capture_output=True, timeout=60)


def _mini_repo(tmp_path):
    src = tmp_path / "mini"
    src.mkdir()
    (src / "config.py").write_text("def get_config():\n    return object()\n")
    (src / "requirements.txt").write_text("")
    (src / "genio_server").mkdir()
    (src / "genio_server" / "__init__.py").write_text("")
    _git(src, "init")
    _git(src, "add", "-A")
    _git(src, "commit", "-qm", "v1")
    return src


def test_make_release_and_verify(tmp_path):
    src = _mini_repo(tmp_path)
    out = tmp_path / "rel"
    archive = make_release(src, "9.9.9-test", out)
    assert archive.is_file()
    sha = out / f"{archive.name}.sha256"
    assert sha.is_file()
    assert verify_archive(archive, checksum_file=sha) == sha256_file(archive)
    manifest = json.loads((out / "genio-9.9.9-test.release.json").read_text())
    assert manifest["version"] == "9.9.9-test" and manifest["sha256"]


def test_tampered_archive_fails_closed(tmp_path):
    src = _mini_repo(tmp_path)
    out = tmp_path / "rel"
    archive = make_release(src, "1.0-t", out)
    with open(archive, "r+b") as fh:
        fh.seek(-10, 2)
        fh.write(b"XX")
    with pytest.raises(SystemExit):
        verify_archive(archive, checksum_file=out / f"{archive.name}.sha256")


def test_install_from_archive_no_git(tmp_path):
    src = _mini_repo(tmp_path)
    out = tmp_path / "rel"
    archive = make_release(src, "2.0-t", out)
    from installer.installers.standalone import _copy_source
    dest = tmp_path / "prefix" / "repo"
    dest.parent.mkdir(parents=True)
    mode, commit = _copy_source(Runner(), str(archive), dest,
                                checksum=str(out / f"{archive.name}.sha256"))
    assert mode.startswith("archive:")
    assert (dest / "config.py").is_file()
    assert not (dest / ".git").exists()


def test_update_from_archive_with_rollback(tmp_path):
    from installer.core.manifest import new_manifest, write_manifest
    from installer.core.paths import layout
    from installer.repair.fix import update
    lay = layout(tmp_path / "prefix")
    for d in ("meta", "repo", "config", "data"):
        lay[d].mkdir(parents=True, exist_ok=True)
    (lay["repo"] / "app.txt").write_text("v1\n")
    (lay["repo"] / "config.py").write_text(
        "def get_config():\n    return object()\n")
    (lay["env_file"]).write_text("GENIO_ENV=dev\n")
    man = new_manifest(lay["prefix"], "1.0", "nongit", "standalone-archive")
    write_manifest(lay["manifest"], man)
    src = _mini_repo(tmp_path)
    (src / "app.txt").write_text("v2\n")
    _git(src, "add", "-A")
    _git(src, "commit", "-qm", "v2")
    out = tmp_path / "rel"
    archive = make_release(src, "2.0", out)
    # venv factice avec python qui valide l'import (chemin stub)
    (lay["venv"] / "bin").mkdir(parents=True)
    import shutil
    shutil.copy(sys.executable, lay["venv"] / "bin" / "python")
    res = update(Runner(), lay["prefix"], archive=str(archive),
                 checksum=str(out / f"{archive.name}.sha256"))
    assert (lay["repo"] / "app.txt").read_text() == "v2\n"
    assert res["backup"] and res["new"]
    # downgrade refusé sans flag (archive 1.5 < version installée 2.0)
    older = make_release(src, "1.5", out)
    with pytest.raises(Exception):
        update(Runner(), lay["prefix"], archive=str(older),
               checksum=str(out / f"{older.name}.sha256"))
