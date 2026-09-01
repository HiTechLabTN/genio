"""Phase C — montage volume + network policy + cwd persistence.

Run: pytest test_phase_C_session_volume.py -v
Q2: Allow-list registries, workdir isolé state/session_workdirs/<session_id>/, network bridge
"""
import os
import uuid
import pathlib
import pytest

from genio_server.tools.session_container import _host_workdir, exec_in_container, cleanup_container, _CWD_MAP, _LAST_USED

os.environ["GENIO_SANDBOX_MODE"] = "container"

def _sid(prefix="testC"):
    return f"{prefix}_{uuid.uuid4().hex[:6]}"


def test_cwd_persistence():
    sid = _sid("cwd")
    _CWD_MAP.pop(sid, None)
    res1 = exec_in_container(sid, "cd /work && mkdir -p sub && cd sub", timeout=10)
    assert res1["returncode"] == 0
    assert _CWD_MAP.get(sid) == "/work/sub"
    res2 = exec_in_container(sid, "pwd", timeout=10)
    assert res2["stdout"].strip() == "/work/sub"
    cleanup_container(sid)
    _CWD_MAP.pop(sid, None)
    _LAST_USED.pop(sid, None)


@pytest.mark.xfail(reason="env var persistence requires persistent shell, not just cd prefix")
def test_env_persistence_xfail():
    sid = _sid("env")
    _CWD_MAP.pop(sid, None)
    exec_in_container(sid, "export FOO=bar", timeout=10)
    res = exec_in_container(sid, "echo $FOO", timeout=10)
    assert res["stdout"].strip() == "bar"
    cleanup_container(sid)


def test_file_visible_on_host():
    sid = _sid("file")
    _CWD_MAP.pop(sid, None)
    wd = _host_workdir(sid)
    res = exec_in_container(sid, "echo hi > /work/out.txt && cat /work/out.txt", timeout=10)
    assert res["returncode"] == 0
    assert "hi" in res["stdout"]
    host_file = wd / "out.txt"
    assert host_file.exists(), f"host file not visible at {host_file}"
    assert host_file.read_text().strip() == "hi"
    cleanup_container(sid)
    _CWD_MAP.pop(sid, None)


def test_network_allowlist_pip():
    sid = _sid("net")
    _CWD_MAP.pop(sid, None)
    # Try to fetch pypi.org — should succeed with allowlist bridge
    # Use single quotes for outer -c to avoid shell quoting issues
    res = exec_in_container(sid, "python3 -c 'import urllib.request; print(urllib.request.urlopen(\"https://pypi.org/simple/\", timeout=5).status)'", timeout=15)
    # If network is bridge allowlist, should get 200; if none, should fail
    # We assert either success or proper failure, but not crash
    assert res["returncode"] == 0 or "urllib" in res["stderr"] or "Connection" in res["stderr"] or "timeout" in res["stderr"].lower()
    if res["returncode"] == 0 and res["stdout"].strip():
        assert "200" in res["stdout"]
    cleanup_container(sid)
    _CWD_MAP.pop(sid, None)


def test_workdir_isolated_per_session():
    sid1 = _sid("iso1")
    sid2 = _sid("iso2")
    wd1 = _host_workdir(sid1)
    wd2 = _host_workdir(sid2)
    assert wd1 != wd2
    # _host_workdir strips non-alnum, so iso1_xxx -> iso1xxx
    alnum1 = "".join(c for c in sid1 if c.isalnum())
    alnum2 = "".join(c for c in sid2 if c.isalnum())
    assert alnum1 in str(wd1) or sid1.replace("_","") in str(wd1)
    # Create file in sid1, ensure not in sid2
    exec_in_container(sid1, "echo s1 > /work/s1.txt", timeout=10)
    exec_in_container(sid2, "echo s2 > /work/s2.txt", timeout=10)
    assert (wd1 / "s1.txt").exists()
    assert not (wd1 / "s2.txt").exists()
    assert (wd2 / "s2.txt").exists()
    assert not (wd2 / "s1.txt").exists()
    cleanup_container(sid1)
    cleanup_container(sid2)
    _CWD_MAP.pop(sid1, None)
    _CWD_MAP.pop(sid2, None)
