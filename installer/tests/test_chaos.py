"""Chaos / recovery tests — controlled failures, no data loss (§27).

kill mid-update, corrupt config/cache/venv, interrupted install.
Deterministic, tmp_path only.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from installer.core.errors import InstallerError  # noqa: E402
from installer.core.manifest import new_manifest, write_manifest  # noqa: E402
from installer.core.paths import layout  # noqa: E402
from installer.core.runner import Runner  # noqa: E402


def _git(path, *argv):
    env = dict(os.environ, GIT_CONFIG_NOSYSTEM="1", GIT_AUTHOR_NAME="t",
               GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
               GIT_COMMITTER_EMAIL="t@t")
    subprocess.run(["git", *argv], cwd=str(path), env=env, check=True,
                   capture_output=True, timeout=60)


def _prefix_with_git(tmp_path):
    lay = layout(tmp_path / "prefix")
    for d in ("meta", "repo", "config", "data"):
        lay[d].mkdir(parents=True, exist_ok=True)
    (lay["repo"] / "app.txt").write_text("v1\n")
    (lay["repo"] / "config.py").write_text("def get_config():\n    return object()\n")
    (lay["env_file"]).write_text("GENIO_ENV=dev\n")
    (lay["data"] / "keep.txt").write_text("user-data\n")
    _git(lay["repo"], "init")
    _git(lay["repo"], "add", "-A")
    _git(lay["repo"], "commit", "-qm", "v1")
    man = new_manifest(lay["prefix"], "1.0", "v1", "standalone")
    write_manifest(lay["manifest"], man)
    (lay["venv"] / "bin").mkdir(parents=True)
    import shutil
    shutil.copy(sys.executable, lay["venv"] / "bin" / "python")
    return lay


def test_killed_update_restores_known_good(tmp_path):
    """checkout vers ref inexistante == update tué : rollback, data intacte."""
    from installer.repair.fix import update
    lay = _prefix_with_git(tmp_path)
    with pytest.raises(InstallerError):
        update(Runner(), lay["prefix"], ref="no-such-ref-xyz")
    assert (lay["repo"] / "app.txt").read_text() == "v1\n"
    assert (lay["data"] / "keep.txt").read_text() == "user-data\n"


def test_corrupt_config_repaired_not_deleted(tmp_path):
    from installer.repair.fix import repair
    lay = _prefix_with_git(tmp_path)
    (lay["env_file"]).write_text("GARBAGE LINE WITHOUT EQUALS\nVALID=1\n")
    res = repair(Runner(), lay["prefix"])
    assert any("regenerated" in f for f in res["fixed"])
    assert (lay["data"] / "keep.txt").read_text() == "user-data\n"


def test_broken_venv_recreated(tmp_path):
    from installer.repair.fix import repair
    lay = _prefix_with_git(tmp_path)
    import shutil
    shutil.rmtree(lay["venv"])
    (lay["repo"] / "requirements.txt").write_text("")
    res = repair(Runner(), lay["prefix"])
    assert (lay["venv"] / "bin" / "python").exists()
    assert any("venv" in f for f in res["fixed"])


def test_interrupted_install_is_partial_not_healthy(tmp_path):
    from installer.discovery.find import inspect_prefix
    lay = layout(tmp_path / "prefix")
    (lay["repo"]).mkdir(parents=True)
    (lay["repo"] / "config.py").write_text("x=1\n")
    rec = inspect_prefix(lay["prefix"], Runner())
    assert rec["state"] == "PARTIAL"


def test_force_reinstall_preserves_data_moves_code(tmp_path):
    from installer.installers.standalone import install
    lay = layout(tmp_path / "prefix")
    for d in ("meta", "repo", "config", "data"):
        lay[d].mkdir(parents=True, exist_ok=True)
    (lay["repo"] / "old.txt").write_text("old\n")
    (lay["data"] / "keep.txt").write_text("user-data\n")
    src = tmp_path / "src"
    src.mkdir()
    (src / "requirements.txt").write_text("")
    (src / "config.py").write_text(
        "class _O:\n    primary_model = 'test'\n"
        "class _C:\n    ollama = _O()\n"
        "def get_config():\n    return _C()\n")
    man = install(Runner(), lay["prefix"], str(src), "t",
                  {"ports": {}, "api_key": "", "force": True, "npm_ok": False})
    assert (lay["repo"] / "config.py").is_file()
    assert not (lay["repo"] / "old.txt").exists()
    assert (lay["data"] / "keep.txt").read_text() == "user-data\n"
    assert man["health"] == "healthy"
