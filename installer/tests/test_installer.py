"""Installer tests — deterministic, tmp_path only, no network, no sudo."""
import os
import socket
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from installer.core import manifest as M  # noqa: E402
from installer.core.paths import layout  # noqa: E402
from installer.core.runner import Runner, scrub  # noqa: E402
from installer.detectors.system import detect_ports  # noqa: E402
from installer.discovery import find as discovery  # noqa: E402
from installer.health import doctor as doc  # noqa: E402


def _runner(tmp_path):
    return Runner(log_path=tmp_path / "t.log")


def _fake_prefix(tmp_path, with_manifest=True, with_repo=True, with_venv=True):
    lay = layout(tmp_path / "prefix")
    for d in ("meta", "repo", "config", "data"):
        lay[d].mkdir(parents=True, exist_ok=True)
    if with_repo:
        (lay["repo"] / "config.py").write_text("x = 1\n")
        (lay["repo"] / ".git").mkdir(exist_ok=True)
    if with_venv:
        (lay["venv"] / "bin").mkdir(parents=True, exist_ok=True)
        (lay["venv"] / "bin" / "python").write_text("#!/bin/sh\n")
    (lay["config"] / ".env").write_text("GENIO_ENV=dev\n")
    man = None
    if with_manifest:
        man = M.new_manifest(lay["prefix"], "9.9-test", "abc123", "standalone")
        M.write_manifest(lay["manifest"], man)
        man = M.read_manifest(lay["manifest"])
    return lay, man


def test_manifest_roundtrip(tmp_path):
    lay = layout(tmp_path / "p")
    man = M.new_manifest(lay["prefix"], "1.0", "deadbee", "standalone")
    M.write_manifest(lay["manifest"], man)
    back = M.read_manifest(lay["manifest"])
    assert back["installation_id"] == man["installation_id"]
    assert back["product"] == "genio"
    assert M.read_manifest(lay["prefix"] / "nope.json") is None


def test_discovery_not_found(tmp_path):
    rec = discovery.inspect_prefix(tmp_path / "empty", _runner(tmp_path))
    assert rec["state"] == "NOT_FOUND"
    plan = discovery.summarize([])
    assert plan["action"] == "install"


def test_discovery_healthy_no_duplicate(tmp_path):
    lay, _ = _fake_prefix(tmp_path)
    rec = discovery.inspect_prefix(lay["prefix"], _runner(tmp_path))
    assert rec["state"] == "HEALTHY"
    plan = discovery.summarize([rec])
    assert plan["action"] == "already-installed"
    assert "no second installation" in plan["message"].lower()


def test_discovery_partial_and_reconcile(tmp_path):
    lay, _ = _fake_prefix(tmp_path, with_repo=False, with_venv=False)
    rec = discovery.inspect_prefix(lay["prefix"], _runner(tmp_path))
    assert rec["state"] in ("PARTIAL", "DEGRADED")
    other = dict(rec)
    other["location"] = "/elsewhere"
    plan = discovery.summarize([rec, other])
    assert plan["action"] == "reconcile"
    assert "no automatic choice" in plan["message"].lower()


def test_doctor_status_vocabulary(tmp_path):
    res = doc.doctor(_runner(tmp_path))
    allowed = {"PASS", "WARN", "FAIL", "NOT_APPLICABLE"}
    assert res["checks"], "doctor must not return an empty suite"
    for c in res["checks"]:
        assert c["status"] in allowed, c
    assert res["verdict"] in ("HEALTHY", "ATTENTION")


def _free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def test_ports_free_and_held(tmp_path):
    held = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    held.bind(("127.0.0.1", 0))
    held.listen(1)  # ss only lists LISTEN sockets for owner lookup
    port = held.getsockname()[1]
    try:
        res = detect_ports(_runner(tmp_path), {"held": port, "free": _free_port()})
        assert res["held"]["free"] is False
        assert res["held"]["owner"]["pid"] == os.getpid()
        assert res["free"]["free"] is True
    finally:
        held.close()


def test_runner_scrubs_secrets(tmp_path):
    assert "sk-abc" not in scrub("key sk-abcdef1234567890 here")
    assert "***REDACTED***" in scrub("GENIO_API_KEY=supersecretvalue123")
    r = _runner(tmp_path)
    r.run(["echo", "hello"])
    assert (tmp_path / "t.log").is_file()


def _git_repo(path):
    env = dict(os.environ, GIT_CONFIG_NOSYSTEM="1",
               GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
    for argv in (["git", "init"], ["git", "add", "-A"], ["git", "commit", "-qm", "v1"]):
        subprocess.run(argv, cwd=str(path), env=env, check=True,
                       capture_output=True, timeout=60)


def test_backup_update_rollback_cycle(tmp_path):
    lay, _ = _fake_prefix(tmp_path)
    _git_repo(lay["repo"])
    (lay["repo"] / "app.txt").write_text("v1\n")
    subprocess.run(["git", "-C", str(lay["repo"]), "add", "-A"], check=True,
                   capture_output=True, timeout=60)
    env = dict(os.environ, GIT_CONFIG_NOSYSTEM="1", GIT_AUTHOR_NAME="t",
               GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
    subprocess.run(["git", "-C", str(lay["repo"]), "commit", "-qm", "v1"],
                   env=env, check=True, capture_output=True, timeout=60)
    (lay["env_file"]).write_text("GENIO_ENV=dev\n")
    from installer.core.state import create_backup, list_backups, restore_backup
    r = _runner(tmp_path)
    b = create_backup(r, lay["prefix"])
    assert (b / "backup.json").is_file()
    # v2 commit then update to it
    (lay["repo"] / "app.txt").write_text("v2\n")
    subprocess.run(["git", "-C", str(lay["repo"]), "commit", "-qam", "v2"],
                   env=env, check=True, capture_output=True, timeout=60)
    (lay["repo"] / "app.txt").write_text("v1\n")  # dirty tree, update must handle
    subprocess.run(["git", "-C", str(lay["repo"]), "checkout", "--", "app.txt"],
                   check=True, capture_output=True, timeout=60)
    assert len(list_backups(lay["prefix"])) >= 1
    man = restore_backup(r, lay["prefix"], b)
    assert man is not None
    assert (lay["env_file"]).read_text() == "GENIO_ENV=dev\n"


def test_repair_regenerates_env_preserves_data(tmp_path):
    lay, _ = _fake_prefix(tmp_path)
    (lay["data"] / "precious.txt").write_text("keep me\n")
    from installer.repair.fix import repair
    res = repair(_runner(tmp_path), lay["prefix"])
    assert lay["env_file"].is_file()
    assert (lay["data"] / "precious.txt").read_text() == "keep me\n"
    assert "backup" in res


def test_cli_exit_codes(tmp_path):
    cli = REPO / "installer" / "genio"
    assert cli.is_file()
    r = subprocess.run([sys.executable, str(cli), "version"],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0 and "genio installer" in r.stdout
    r = subprocess.run([sys.executable, str(cli), "status",
                        "--prefix", str(tmp_path / "noprefix")],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0
