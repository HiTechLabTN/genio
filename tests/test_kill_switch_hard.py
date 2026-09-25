"""Phase 17 tests — kill-switch préemptif réel.

Interruption d'une commande longue en cours, refus sans re-arm, pas de
désactivation par le flux outil. Vrais processus, vrais timeouts.
"""
import sys
import threading
import time

sys.path.insert(0, "/data/ai_tools/genio")

from genio_server.tools import invoke
from genio_server.tools.bash_tool import run_command
from genio_server.tools.safety import SAFETY


def setup_function(_):
    if not SAFETY.armed:
        SAFETY.arm()


def teardown_function(_):
    if not SAFETY.armed:
        SAFETY.arm()


def test_long_command_interrupted_mid_flight():
    out = {}
    t = threading.Thread(
        target=lambda: out.update(
            res=run_command("sleep 30", timeout=60)))
    t0 = time.monotonic()
    t.start()
    time.sleep(1.0)
    SAFETY.halt("phase17 test")
    t.join(timeout=15)
    dt = time.monotonic() - t0
    assert not t.is_alive(), "sleep 30 survived halt"
    assert dt < 12, f"kill not preemptive ({dt:.1f}s)"
    assert out["res"]["returncode"] != 0


def test_no_relaunch_without_rearm():
    SAFETY.halt("phase17 test")
    try:
        r1 = invoke("bash", "echo should-not-run")
        assert "KILL SWITCH" in str(r1.get("error", ""))
        r2 = invoke("bash", "echo still-blocked")
        assert "KILL SWITCH" in str(r2.get("error", ""))
        assert SAFETY.armed is False, "halt auto-cleared (LLM could re-arm!)"
    finally:
        SAFETY.arm()
    r3 = invoke("bash", "echo back")
    assert r3.get("returncode") == 0 and "back" in str(r3.get("stdout", ""))


def test_proc_registry_cleaned():
    n_before = len(SAFETY._procs)
    run_command("echo cleanup-check", timeout=10)
    assert len(SAFETY._procs) == n_before


def test_halt_blocks_computer_tool():
    from genio_server.tools import computer_tool as ct
    SAFETY.halt("phase17 test")
    try:
        r = ct.handle({"action": "click", "x": 5, "y": 5})
        assert "KILL SWITCH" in str(r.get("error", ""))
    finally:
        SAFETY.arm()


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
