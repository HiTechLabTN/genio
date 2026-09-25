"""Phase 6 tests — sandbox fail-closed (P0) + quotas d'isolation.

- strict sans conteneur/docker → SANDBOX_UNAVAILABLE, JAMAIS d'hôte (canari).
- quotas live (docker réel) : RAM 512m, pids 256, CPU, FS lecture seule.
- dev : fallback hôte préservé (documenté, explicite).
"""
import json
import os
import subprocess
import sys
import uuid

sys.path.insert(0, "/data/ai_tools/genio")

from genio_server.tools import session_container as sc


def _env_strict_container():
    os.environ["GENIO_SECURITY_MODE"] = "strict"
    os.environ["GENIO_SANDBOX_MODE"] = "container"


def _env_dev():
    os.environ.pop("GENIO_SECURITY_MODE", None)
    os.environ.pop("GENIO_SANDBOX_MODE", None)


def _sid():
    return f"ph6_{uuid.uuid4().hex[:8]}"


def test_strict_disabled_mode_no_host_exec():
    _env_strict_container()
    os.environ["GENIO_SANDBOX_MODE"] = ""
    canary = "/tmp/ph6_canary_disabled"
    if os.path.exists(canary):
        os.remove(canary)
    try:
        res = sc.exec_in_container(_sid(), f"touch {canary} && echo PWNED")
        assert res.get("returncode") == 125
        assert "SANDBOX_UNAVAILABLE" in str(res.get("stderr", ""))
        assert not os.path.exists(canary), "HOST EXECUTION LEAK in strict mode"
    finally:
        _env_dev()
        if os.path.exists(canary):
            os.remove(canary)


def test_strict_docker_missing_no_host_exec(monkeypatch):
    _env_strict_container()
    monkeypatch.setattr(sc, "_docker_available", lambda: False)
    canary = "/tmp/ph6_canary_nodocker"
    if os.path.exists(canary):
        os.remove(canary)
    try:
        res = sc.exec_in_container(_sid(), f"touch {canary} && echo PWNED")
        assert res.get("returncode") == 125
        assert "SANDBOX_UNAVAILABLE" in str(res.get("stderr", ""))
        assert not os.path.exists(canary), "HOST EXECUTION LEAK in strict mode"
    finally:
        _env_dev()
        if os.path.exists(canary):
            os.remove(canary)


def test_dev_fallback_preserved(monkeypatch):
    _env_dev()
    os.environ["GENIO_SANDBOX_MODE"] = "container"
    monkeypatch.setattr(sc, "_docker_available", lambda: False)
    try:
        res = sc.exec_in_container(_sid(), "echo dev-ok")
    finally:
        _env_dev()
    assert res.get("returncode") == 0
    assert "dev-ok" in str(res.get("stdout", ""))
    assert res.get("sandbox_fallback") is True


def test_live_container_quotas():
    _env_dev()
    os.environ["GENIO_SANDBOX_MODE"] = "container"
    sid = _sid()
    try:
        res = sc.exec_in_container(sid, "echo live-ok")
        assert res.get("returncode") == 0, res
        assert "live-ok" in str(res.get("stdout", ""))
        name = sc._container_name(sid)
        insp = json.loads(subprocess.run(
            ["docker", "inspect", name], capture_output=True, text=True,
            timeout=20).stdout)[0]
        hc = insp["HostConfig"]
        assert hc["Memory"] == 512 * 1024 * 1024, hc["Memory"]
        assert hc["PidsLimit"] == 256, hc["PidsLimit"]
        assert hc.get("NanoCpus", 0) > 0, hc.get("NanoCpus")
        assert hc.get("ReadonlyRootfs") is True, "root FS must be read-only"
        # FS lecture seule : écriture hors /work et /tmp doit échouer.
        ro = sc.exec_in_container(sid, "touch /should_fail_ph6 && echo WROTE")
        assert ro.get("returncode") != 0, f"root FS writable! {ro}"
        assert "WROTE" not in str(ro.get("stdout", ""))
        # /work reste inscriptible (workspace).
        wok = sc.exec_in_container(sid, "touch /work/ok_ph6 && echo WROTE")
        assert wok.get("returncode") == 0 and "WROTE" in str(wok.get("stdout"))
    finally:
        _env_dev()
        subprocess.run(["docker", "rm", "-f", sc._container_name(sid)],
                       capture_output=True, timeout=30)


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
