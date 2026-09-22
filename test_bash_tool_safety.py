"""Security baseline tests for the bash tool's danger-detection logic.

Phase 0 — covers the obfuscations found in the security audit plus a set of
legitimate commands that MUST keep working.

Run:  pytest test_bash_tool_safety.py -v
"""
from __future__ import annotations

import pytest

from genio_server.tools.bash_tool import is_dangerous, run_command


# --------------------------------------------------------------------------- #
# Dangerous commands that MUST be refused
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "cmd",
    [
        "sudo rm -rf /",
        "sudo rm -rf /*",
        "rm -rf /",
        "rm -rf /*",
        "rm -rf ~",
        "rm -rf ~/",
        "bash -c \"rm -rf /\"",
        "cd / && rm -rf .",
        "rm -rf .",
        "rm -r /",
        "sudo dd if=/dev/sda of=/dev/sdb",
        "dd of=/dev/sda",
        "mkfs.ext4 /dev/sda",
        "mkfs.xfs /dev/sdb",
        "> /dev/sda",
        "chmod -R 777 /",
        ":(){ :|:& };:",
    ],
)
def test_dangerous_blocked(cmd: str):
    assert is_dangerous(cmd) is not None, f"expected refusal for: {cmd!r}"


# --------------------------------------------------------------------------- #
# Legitimate commands that MUST pass
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "cmd",
    [
        "git status",
        "ls -la",
        "rm -rf ./build",
        "rm -rf build",
        "rm -f tmp/old.log",
        "python3 -m pip install requests",
        "npm install",
        "mkdir -p /work/repo/src",
        "echo hello && pwd",
        "cd /work/repo && npm test",
        "cat ./README.md",
        "grep -r foo ./src",  # -r here is not rm -r; should pass
        "make build",
    ],
)
def test_safe_passes(cmd: str):
    assert is_dangerous(cmd) is None, f"unexpected refusal for: {cmd!r}"


def test_empty_command_is_safe():
    assert is_dangerous("") is None
    assert is_dangerous("   ") is None


def test_sudo_configurable():
    import os
    try:
        os.environ["GENIO_ALLOW_SUDO"] = "1"
        assert is_dangerous("sudo apt-get update") is None
    finally:
        os.environ.pop("GENIO_ALLOW_SUDO", None)
    assert is_dangerous("sudo apt-get update") is not None


def test_refused_run_command_returns_126():
    result = run_command("rm -rf /")
    assert result["returncode"] == 126
    assert "refused" in result["stderr"]

    ok = run_command("ls -la")
    assert ok["returncode"] == 0


# --------------------------------------------------------------------------- #
# Phase 0 — ambient hardening (GENIO_ENV guard + CORS allow-list)
# --------------------------------------------------------------------------- #
def _sub_import(env: dict) -> "subprocess.CompletedProcess":
    import subprocess, sys, os
    code = "import genio_server.server.main  # triggers module-level init"
    full_env = dict(os.environ)
    full_env.update(env)
    return subprocess.run(
        [sys.executable, "-c", code], cwd=".", env=full_env,
        capture_output=True, text=True,
    )


def test_prod_requires_api_key():
    proc = _sub_import({"GENIO_ENV": "prod", "GENIO_API_KEY": ""})
    assert proc.returncode != 0, "server must refuse to start in prod without a key"
    assert "requires GENIO_API_KEY" in proc.stderr


def test_prod_with_key_starts():
    proc = _sub_import({"GENIO_ENV": "prod", "GENIO_API_KEY": "sekret"})
    # Import alone must not raise; a hard failure appears as non-zero.
    assert "requires GENIO_API_KEY" not in proc.stderr


def test_cors_default_localhost():
    proc = _sub_import({"GENIO_CORS_ORIGINS": ""})
    from genio_server.server import main as m
    assert any("1420" in o for o in m.CORS_ORIGINS)


def test_cors_from_env():
    proc = _sub_import({"GENIO_CORS_ORIGINS": "http://localhost:1420,https://lab.hitech.tn"})
    # Confirm the env reached the module by echoing CORS in a subprocess too.
    import subprocess, sys, os
    env = dict(os.environ)
    env["GENIO_CORS_ORIGINS"] = "http://localhost:1420,https://lab.hitech.tn"
    out = subprocess.run(
        [sys.executable, "-c",
         "from genio_server.server import main as m; print(m.CORS_ORIGINS)"],
        cwd=".", env=env, capture_output=True, text=True,
    ).stdout
    assert "lab.hitech.tn" in out
