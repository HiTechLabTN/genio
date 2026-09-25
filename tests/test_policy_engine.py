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
