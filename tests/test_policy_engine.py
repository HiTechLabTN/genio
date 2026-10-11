"""Phase 5 tests — PolicyEngine centralisé.

Déterministe, fail-closed, indépendant du LLM. Aucun réseau/modèle/GPU.
- évaluation déterministe (mêmes entrées -> même décision)
- fail-closed (inconnu/registry HS = DENY)
- interrupteur : nonce unique, approve/deny, timeout d'approbation
"""
import sys
import threading
import time

sys.path.insert(0, "/data/ai_tools/genio")

from core.policy_engine import PolicyEngine, get_policy_engine


def test_evaluate_deterministic():
    e = PolicyEngine()
    a = e.evaluate("bash", sandbox_available=True, mode="development")
    b = e.evaluate("bash", sandbox_available=True, mode="development")
    assert (a.decision, a.reason, a.capability) == \
        (b.decision, b.reason, b.capability)
    assert a.capability == "PROCESS_EXECUTION"


def test_fail_closed_unknown():
    e = PolicyEngine()
    for mode in ("development", "strict"):
        d = e.evaluate("teleport", sandbox_available=True, mode=mode)
        assert d.decision == "DENY", mode


def test_strict_gates_execution():
    e = PolicyEngine()
    assert e.evaluate("bash", False, "strict").decision == "DENY"
    assert e.evaluate("bash", True, "strict").decision == "SANDBOX_ONLY"
    assert e.evaluate("screen", False, "strict").decision == "ALLOW"


def test_singleton_shared():
    assert get_policy_engine() is get_policy_engine()


def test_nonce_unique_and_pending_visible():
    e = PolicyEngine()
    d1 = e.request_confirmation("computer", "click 1 2", timeout_s=30)
    d2 = e.request_confirmation("computer", "click 1 2", timeout_s=30)
    assert d1.nonce and d2.nonce and d1.nonce != d2.nonce
    assert e.pending_count() == 2
    p = e.pending(d1.nonce)
    assert p and p["tool"] == "computer" and p["expires_in_s"] > 0
    e.resolve(d1.nonce, True)
    e.resolve(d2.nonce, False)
    assert e.await_decision(d1.nonce, timeout_s=1) is True
    assert e.await_decision(d2.nonce, timeout_s=1) is False
    # Closure gate: await no longer pops (execution consumes single-use
    # against the exact command). Complete the lifecycle explicitly.
    assert e.consume(d1.nonce, "click 1 2") is True
    assert e.release(d2.nonce) is True
    assert e.pending_count() == 0


def test_resolve_unknown_nonce_false():
    assert PolicyEngine().resolve("deadbeef", True) is False


def test_approve_path():
    e = PolicyEngine()
    d = e.request_confirmation("bash", "echo hi", timeout_s=30)

    def _approve():
        time.sleep(0.2)
        assert e.resolve(d.nonce, True) is True
    t = threading.Thread(target=_approve)
    t.start()
    assert e.await_decision(d.nonce, timeout_s=5) is True
    t.join()


def test_approval_timeout_denies():
    e = PolicyEngine()
    d = e.request_confirmation("bash", "echo hi", timeout_s=0.3)
    assert e.await_decision(d.nonce) is False
    # Closure gate: timed-out entries linger for explicit
    # consume/release/purge (no silent pop) — then purge reaps them.
    assert e.purge_expired() == 1
    assert e.pending_count() == 0


def test_purge_expired():
    e = PolicyEngine()
    e.request_confirmation("bash", "echo hi", timeout_s=0.1)
    time.sleep(0.25)
    assert e.purge_expired() == 1
    assert e.pending_count() == 0


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))


# --------------------------------------------------------------------------- #
# Closure gate (pre-merge fix): full-command binding + workspace binding
# --------------------------------------------------------------------------- #
def test_overlong_command_rejected_at_request():
    # Commands longer than MAX_APPROVED_COMMAND_CHARS are refused outright
    # (the operator must see the whole command they approve — no truncation).
    from core.policy_engine import MAX_APPROVED_COMMAND_CHARS
    e = PolicyEngine()
    long_cmd = "echo " + "A" * (MAX_APPROVED_COMMAND_CHARS + 1)
    d = e.request_confirmation("bash", long_cmd, timeout_s=30)
    assert d.decision == "DENY"
    assert "too long" in d.reason
    assert d.nonce == ""  # no pending created
    assert e.pending_count() == 0


def test_exactly_500_chars_accepted():
    # Boundary: a command of EXACTLY the limit is accepted (pending created).
    from core.policy_engine import MAX_APPROVED_COMMAND_CHARS
    e = PolicyEngine()
    cmd = "x" * MAX_APPROVED_COMMAND_CHARS
    assert len(cmd) == MAX_APPROVED_COMMAND_CHARS
    d = e.request_confirmation("bash", cmd, timeout_s=30)
    assert d.decision == "REQUIRE_CONFIRMATION", d.reason
    assert d.nonce != ""
    assert e.pending_count() == 1
    e.release(d.nonce)


def test_501_chars_refused_at_request():
    # 501 chars (over limit): DENY, empty nonce, NO pending created —
    # never truncated, never silently matched to another command.
    from core.policy_engine import MAX_APPROVED_COMMAND_CHARS
    e = PolicyEngine()
    cmd = "x" * (MAX_APPROVED_COMMAND_CHARS + 1)
    assert len(cmd) == MAX_APPROVED_COMMAND_CHARS + 1
    d = e.request_confirmation("bash", cmd, timeout_s=30)
    assert d.decision == "DENY"
    assert "too long" in d.reason
    assert d.nonce == ""
    assert e.pending_count() == 0


def test_commands_differing_after_char_500_do_not_share_nonce(monkeypatch):
    # THE truncation-bug test: two commands identical in the first 500
    # chars but different after must NOT share one approval. We raise the
    # limit for this test so both commands reach consume(); the FULL
    # comparison (not [:500]) must reject the altered command.
    import core.policy_engine as pe
    monkeypatch.setattr(pe, "MAX_APPROVED_COMMAND_CHARS", 2000)
    e = PolicyEngine()
    prefix = "rm -rf " + "x" * 493          # 500 chars exactly
    assert len(prefix) == 500
    cmd_a = prefix + "AAA-target"            # 510 chars, under raised limit
    cmd_b = prefix + "BBB-target"            # same first 500, differs after
    assert cmd_a[:500] == cmd_b[:500] and cmd_a != cmd_b
    d = e.request_confirmation("bash", cmd_a, timeout_s=30)
    assert d.decision == "REQUIRE_CONFIRMATION", d.reason
    e.resolve(d.nonce, True)
    # Altered command (differs only after char 500) must FAIL consume —
    # this is what the old [:500] truncation broke.
    assert e.consume(d.nonce, cmd_b) is False
    # Nonce NOT consumed by the failed check — exact command still works.
    assert e.consume(d.nonce, cmd_a) is True


def test_nonce_single_use_even_concurrent():
    # Replay: two simultaneous consume() calls on one approval — exactly
    # one wins (atomic pop under the engine lock).
    import threading
    e = PolicyEngine()
    d = e.request_confirmation("bash", "rm -rf sub", timeout_s=30)
    e.resolve(d.nonce, True)
    wins = []
    barrier = threading.Barrier(2)

    def _racer():
        barrier.wait()
        if e.consume(d.nonce, "rm -rf sub", workspace=""):
            wins.append(1)

    # No workspace bound here (empty), so both racers pass the workspace
    # gate and only the single-use pop decides the winner.
    t1 = threading.Thread(target=_racer)
    t2 = threading.Thread(target=_racer)
    t1.start(); t2.start(); t1.join(); t2.join()
    assert len(wins) == 1, f"nonce must be single-use, got {len(wins)} wins"


def test_workspace_binding_mismatch_refused():
    # An approval bound to workspace A must not authorize execution in B.
    e = PolicyEngine()
    d = e.request_confirmation("bash", "rm -rf sub", timeout_s=30,
                               workspace="/tmp/ws-a")
    e.resolve(d.nonce, True)
    assert e.consume(d.nonce, "rm -rf sub", workspace="/tmp/ws-b") is False
    # The nonce was NOT consumed by the failed workspace check — retry with
    # the correct workspace succeeds (single-use preserved).
    assert e.consume(d.nonce, "rm -rf sub", workspace="/tmp/ws-a") is True


def test_workspace_binding_no_workspace_refused():
    # If the approval has a workspace bound, consume WITHOUT a workspace
    # must fail closed.
    e = PolicyEngine()
    d = e.request_confirmation("bash", "rm -rf sub", timeout_s=30,
                               workspace="/tmp/ws-a")
    e.resolve(d.nonce, True)
    assert e.consume(d.nonce, "rm -rf sub") is False


def test_workspace_realpath_normalized():
    # Workspace is stored/compared as realpath — trailing slashes and
    # relative segments do not create a mismatch.
    e = PolicyEngine()
    d = e.request_confirmation("bash", "echo hi", timeout_s=30,
                               workspace="/tmp/ws-a/")
    e.resolve(d.nonce, True)
    assert e.consume(d.nonce, "echo hi", workspace="/tmp/ws-a") is True
