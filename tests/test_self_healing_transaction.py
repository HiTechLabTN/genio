"""Phase 18 tests — self-healing transactionnel.

Réparation qui commit, échec vérifié qui restaure (octets prouvés),
gate policy, chemins hors workspace refusés. Fichiers /tmp réels.
"""
import os
import sys

sys.path.insert(0, "/data/ai_tools/genio")

from genio_server.core.healing import HealingTransaction

WS = "/tmp/opencode/ph18_ws"


def setup_function(_):
    os.makedirs(WS, exist_ok=True)


def _w(name, data):
    p = os.path.join(WS, name)
    with open(p, "wb") as f:
        f.write(data)
    return p


def test_commit_on_healthy_repair():
    p = _w("a.txt", b"broken v1")
    tx = HealingTransaction(WS)
    r = tx.run([{"path": p, "content": "fixed v2"}],
               verify=lambda: open(p, "rb").read() == b"fixed v2",
               policy="ALLOW", diagnosis="typo")
    assert r.status == "committed" and r.verified is True
    assert open(p, "rb").read() == b"fixed v2"
    assert r.applied == [p] and r.diagnosis == "typo"


def test_failed_verification_restores_proven():
    p = _w("b.txt", b"original-bytes-123")
    tx = HealingTransaction(WS)
    r = tx.run([{"path": p, "content": "bad-fix"}],
               verify=lambda: False, policy="ALLOW")
    assert r.status == "rolled_back"
    assert open(p, "rb").read() == b"original-bytes-123"
    assert r.rolled_back == [p]


def test_policy_deny_touches_nothing():
    p = _w("c.txt", b"untouched")
    tx = HealingTransaction(WS)
    r = tx.run([{"path": p, "content": "evil"}],
               verify=lambda: True, policy="DENY")
    assert r.status == "denied"
    assert open(p, "rb").read() == b"untouched"


def test_outside_workspace_refused():
    tx = HealingTransaction(WS)
    r = tx.run([{"path": "/etc/ph18_evil", "content": "x"}],
               verify=lambda: True, policy="ALLOW")
    assert r.status == "denied"
    assert not os.path.exists("/etc/ph18_evil")


def test_new_file_rolled_back_on_failure():
    p = os.path.join(WS, "fresh.txt")
    if os.path.exists(p):
        os.remove(p)
    tx = HealingTransaction(WS)
    r = tx.run([{"path": p, "content": "temp"}],
               verify=lambda: False, policy="ALLOW")
    assert r.status == "rolled_back" and not os.path.exists(p)


def test_diagnose_uses_healer_or_fallback():
    tx = HealingTransaction(WS)
    d = tx.diagnose("ModuleNotFoundError: No module named 'foo'")
    assert isinstance(d, str) and len(d) > 0
    assert isinstance(tx.diagnose(""), str)


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
