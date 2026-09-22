"""Phase 5 — per-session container sandboxing.

Run: pytest test_phase5_sandbox.py -v
"""
import os

from genio_server.tools.bash_tool import run_command
from genio_server.tools.session_container import _container_name, exec_in_container


def test_local_mode_still_works(monkeypatch):
    monkeypatch.setenv("GENIO_SANDBOX_MODE", "")
    res = run_command("echo hello", session_id="test123")
    assert res["returncode"] == 0
    assert "hello" in res["stdout"]


def test_container_mode_fallback_when_no_docker(monkeypatch):
    monkeypatch.setenv("GENIO_SANDBOX_MODE", "container")
    # Even in container mode, without docker it should fallback and still execute
    res = run_command("echo sandbox-test", session_id="sessABC123")
    # Should succeed either via container or fallback
    assert res["returncode"] == 0
    assert "sandbox-test" in res["stdout"]


def test_container_name_sanitized():
    assert _container_name("abc-123_!@#") == "genio-session-abc123"
    assert _container_name("short") == "genio-session-short"


def test_dangerous_still_blocked_in_container(monkeypatch):
    monkeypatch.setenv("GENIO_SANDBOX_MODE", "container")
    res = run_command("rm -rf /", session_id="sess1")
    assert res["returncode"] == 126
    assert "refused" in res["stderr"]
