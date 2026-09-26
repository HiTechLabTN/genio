"""Phase 27 tests — observabilité.

Sondes 200 (liveness/readiness/metrics), request_id in/out, trace
d'exécution par session. Serveur réel via TestClient.
"""
import sys

sys.path.insert(0, "/data/ai_tools/genio")

from fastapi.testclient import TestClient

import genio_server.server.main as main


def _client():
    return TestClient(main.app, raise_server_exceptions=False)


def test_liveness():
    with _client() as c:
        r = c.get("/health/liveness")
        assert r.status_code == 200
        assert r.json()["probe"] == "liveness"


def test_readiness_reports_ollama():
    with _client() as c:
        r = c.get("/health/readiness")
        assert r.status_code == 200
        d = r.json()
        assert d["probe"] == "readiness" and d["status"] in ("ok", "degraded")


def test_metrics_shape():
    with _client() as c:
        r = c.get("/health/metrics")
        assert r.status_code == 200
        d = r.json()
        assert {"active_runs", "recent_events", "uptime_s", "ts"} <= set(d.keys())


def test_request_id_echo_and_passthrough():
    with _client() as c:
        r = c.get("/health/liveness", headers={"X-Request-ID": "abc123"})
        assert r.status_code == 200
        assert r.headers.get("x-request-id") == "abc123"
        r2 = c.get("/health/liveness")
        assert r2.status_code == 200
        assert len(r2.headers.get("x-request-id", "")) == 12


def test_execution_trace_empty_session():
    with _client() as c:
        r = c.get("/api/v1/executions/ph27_nobody")
        assert r.status_code in (200, 401)
        if r.status_code == 200:
            assert r.json()["count"] == 0


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
