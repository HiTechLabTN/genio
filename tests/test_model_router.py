"""Phase 13 tests — resilient sovereign router.

Backends déclarés, porte cloud (fail-closed vie privée), failover ordonné,
timeouts, disjoncteur. Ollama réel non requis (endpoints mockés au niveau
_call_chat_endpoint comme les tests existants) ; un seul test d'inventaire
touche la config réelle en lecture seule.
"""
import asyncio
import os
import sys
import time

sys.path.insert(0, "/data/ai_tools/genio")

from unittest import mock

from core.model_router import (
    Backend,
    ModelEndpoint,
    ModelRouter,
    cloud_authorized,
    declared_backends,
)


def test_backend_inventory_declares_all():
    inv = declared_backends()
    by = {b["backend"]: b for b in inv}
    for k in (Backend.OLLAMA_LOCAL, Backend.GGUF_DIRECT,
              Backend.HITECH_OS_DAEMON, Backend.CLOUD_FALLBACK):
        assert k in by and "available" in by[k] and "reason" in by[k]
    # Sur cet hôte : pas de llama-server ni de socket HiTech-OS.
    assert by[Backend.GGUF_DIRECT]["available"] is False
    assert by[Backend.HITECH_OS_DAEMON]["available"] is False


def test_cloud_gate_defaults_closed(monkeypatch):
    monkeypatch.delenv("GENIO_ALLOW_CLOUD", raising=False)
    assert cloud_authorized() is False
    r = ModelRouter()
    ep = ModelEndpoint(name="x", base_url="https://x", model="m",
                       backend=Backend.CLOUD_FALLBACK)
    errors: list = []
    assert r._cloud_ok(ep, errors) is False
    assert any("not authorized" in e for e in errors)


def test_cloud_gate_explicit_open(monkeypatch):
    monkeypatch.setenv("GENIO_ALLOW_CLOUD", "1")
    assert cloud_authorized() is True
    r = ModelRouter()
    ep = ModelEndpoint(name="x", base_url="https://x", model="m",
                       backend=Backend.CLOUD_FALLBACK)
    assert r._cloud_ok(ep, []) is True


def test_local_never_gated():
    r = ModelRouter()
    ep = ModelEndpoint(name="ollama-primary", base_url="http://x", model="m",
                       backend=Backend.OLLAMA_LOCAL)
    assert r._cloud_ok(ep, []) is True


def test_ordered_failover_primary_to_backup():
    async def go():
        r = ModelRouter()
        calls = []

        async def fake(self, ep, messages, cancel_event=None):
            calls.append(ep.name)
            if ep.name == "ollama-primary":
                raise ConnectionError("primary down")
            return "backup-ok", 5, 10.0

        with mock.patch.object(ModelRouter, "_call_chat_endpoint", fake):
            out = await r.chat([{"role": "user", "content": "hi"}])
        return out, calls

    (content, n, tps), calls = asyncio.run(go())
    assert content == "backup-ok"
    assert calls[0] == "ollama-primary" and "ollama-backup-0" in calls


def test_turn_timeout_respected(monkeypatch):
    async def go():
        r = ModelRouter()

        async def slow(self, ep, messages, cancel_event=None):
            await asyncio.sleep(30)
            return "never", 0, 0.0

        with mock.patch.object(ModelRouter, "_call_chat_endpoint", slow):
            await r.chat([{"role": "user", "content": "hi"}])

    monkeypatch.setenv("GENIO_MODEL_TURN_TIMEOUT", "0.5")
    t0 = time.monotonic()
    try:
        asyncio.run(go())
        raise SystemExit("should have raised")
    except RuntimeError as e:
        assert "timed out" in str(e) or "failed" in str(e)
    assert time.monotonic() - t0 < 25, "timeout not respected"


def test_breaker_backoff_and_reset():
    r = ModelRouter()
    ep = ModelEndpoint(name="eph", base_url="http://x", model="m")
    assert r._is_available(ep) is True
    r._mark_failure(ep)
    s1 = r.breaker_state("eph")
    assert s1["failures"] == 1 and s1["in_cooldown"] is True
    assert r._is_available(ep) is False
    r._mark_failure(ep)
    s2 = r.breaker_state("eph")
    assert s2["failures"] == 2
    assert (s2["cooldown_until"] - s1["cooldown_until"]) > 0  # backoff croît
    r._mark_success(ep)
    assert r.breaker_state("eph")["failures"] == 0
    assert r._is_available(ep) is True


def test_backends_view():
    inv = ModelRouter().backends()
    assert "declared" in inv and "endpoints" in inv
    assert any(e["name"] == "ollama-primary" for e in inv["endpoints"])


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
