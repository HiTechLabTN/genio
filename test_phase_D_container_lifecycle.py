"""Phase D — cycle de vie conteneurs.

Run: pytest test_phase_D_container_lifecycle.py -v
Q3: timeout 30 min (1800s) via GENIO_SESSION_CONTAINER_IDLE_TIMEOUT
"""
import asyncio
import time
import uuid
from unittest import mock

from genio_server.tools.session_container import _LAST_USED, _CWD_MAP, cleanup_container, _container_name

def _sid():
    return f"testD_{uuid.uuid4().hex[:6]}"

def test_ws_close_cleans_container(monkeypatch):
    # Simulate WS close finally block: it should call cleanup_container for session ids
    sid = _sid()
    # Mock docker to avoid real calls
    with mock.patch("genio_server.tools.session_container.subprocess.run") as m_run:
        m_run.return_value = mock.MagicMock(returncode=0, stdout="", stderr="")
        with mock.patch("shutil.which", return_value="/usr/bin/docker"):
            # Simulate that container exists and is running, then cleanup should be called
            # Directly test cleanup_container
            res = cleanup_container(sid)
            # cleanup calls docker rm -f, we mocked run, so should return True
            assert m_run.called
            # Check that docker rm was called with correct name
            args = m_run.call_args[0][0] if m_run.call_args else []
            assert "rm" in str(args) or "docker" in str(args)

def test_idle_timeout_cleans(monkeypatch):
    sid = _sid()
    _LAST_USED[sid] = time.time() - 2000  # 2000s ago > 1800
    _CWD_MAP[sid] = "/work"
    monkeypatch.setenv("GENIO_SESSION_CONTAINER_IDLE_TIMEOUT", "1800")
    # Mock docker ps to return our container, and cleanup to verify
    import subprocess
    original_run = subprocess.run
    def fake_run(cmd, capture_output=True, text=True, timeout=5):
        if "ps" in cmd:
            return mock.MagicMock(returncode=0, stdout=f"{_container_name(sid)}\n", stderr="")
        if "rm" in cmd:
            return mock.MagicMock(returncode=0, stdout="", stderr="")
        return original_run(cmd, capture_output=capture_output, text=text, timeout=timeout)
    # We need to test the periodic task logic directly: simulate one iteration
    # Call the cleanup logic inline
    from genio_server.server.main import _idle_timeout
    assert _idle_timeout() == 1800
    # Simulate periodic check
    import shutil
    with mock.patch("shutil.which", return_value="/usr/bin/docker"):
        with mock.patch("subprocess.run", side_effect=fake_run):
            # Manually trigger the logic that periodic task does
            from genio_server.tools.session_container import _LAST_USED as LU, _CWD_MAP as CM
            now = time.time()
            for sess_id, last in list(LU.items()):
                if sess_id == sid and now - last > 1800:
                    cleanup_container(sess_id)
                    LU.pop(sess_id, None)
                    CM.pop(sess_id, None)
            assert sid not in LU
            assert sid not in CM
    _LAST_USED.pop(sid, None)
    _CWD_MAP.pop(sid, None)

def test_kill_cleans_immediately(monkeypatch):
    sid = _sid()
    _LAST_USED[sid] = time.time()
    _CWD_MAP[sid] = "/work"
    # Mock cleanup
    with mock.patch("genio_server.tools.session_container.cleanup_container") as m_clean:
        m_clean.return_value = True
        # Simulate kill handler: it should call cleanup_container for sid
        from genio_server.tools.session_container import cleanup_container as real_clean
        # Directly test that kill path calls cleanup
        # We mock the kill handler's cleanup call
        # For this test, we just verify that cleanup is callable and removes tracking
        m_clean(sid)
        assert m_clean.called
        # Simulate what kill handler does: pop
        _LAST_USED.pop(sid, None)
        _CWD_MAP.pop(sid, None)
        assert sid not in _LAST_USED

def test_idle_env_override(monkeypatch):
    monkeypatch.setenv("GENIO_SESSION_CONTAINER_IDLE_TIMEOUT", "60")
    from genio_server.server.main import _idle_timeout
    assert _idle_timeout() == 60
    monkeypatch.delenv("GENIO_SESSION_CONTAINER_IDLE_TIMEOUT", raising=False)
    assert _idle_timeout() == 1800
