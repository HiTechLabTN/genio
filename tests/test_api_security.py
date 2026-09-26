"""Phase 20 tests — API & WS security.

Auth (401 sans crédents quand clé configurée), Bearer éphémère mint+usage,
rate-limit 429, taille 413, nonce approve validé, erreurs assainies.
Serveur FastAPI réel via TestClient (pas de réseau externe).
"""
import sys

sys.path.insert(0, "/data/ai_tools/genio")

import pytest
from fastapi.testclient import TestClient

import genio_server.server.main as main


@pytest.fixture()
def authed(monkeypatch):
    monkeypatch.setenv("GENIO_API_KEY", "test-key-123")
    monkeypatch.setattr(main, "API_KEY", "test-key-123")
    with TestClient(main.app) as client:
        yield client


def test_no_auth_rejected_when_key_configured(authed):
    r = authed.get("/api/v1/status")
    assert r.status_code == 401


def test_bearer_mint_and_use(authed, monkeypatch):
    r = authed.post("/api/v1/auth/token",
                    headers={"X-API-Key": "test-key-123"})
    assert r.status_code == 200
    token = r.json()["token"]
    assert token.startswith("gsk_")
    r2 = authed.get("/api/v1/status",
                    headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 200
    # token falsifié / expiré refusé
    r3 = authed.get("/api/v1/status",
                    headers={"Authorization": "Bearer gsk_1_deadbeef"})
    assert r3.status_code == 401


def test_expired_bearer_rejected(monkeypatch):
    import time
    from genio_server.server import auth_tokens
    monkeypatch.setenv("GENIO_API_KEY", "k")
    tok, _ = auth_tokens.mint_token(now=time.time() - 2000)
    assert auth_tokens.verify_token(tok) is False


def test_rate_limit_429(authed, monkeypatch):
    monkeypatch.setenv("GENIO_RATE_LIMIT_RPS", "1")
    monkeypatch.setenv("GENIO_RATE_LIMIT_BURST", "0")
    monkeypatch.setattr(main, "API_KEY", "test-key-123")
    codes = [authed.get("/api/v1/status",
                        headers={"X-API-Key": "test-key-123"}).status_code
             for _ in range(4)]
    assert 429 in codes, codes


def test_body_too_large_413(authed, monkeypatch):
    monkeypatch.setenv("GENIO_MAX_BODY_BYTES", "100")
    r = authed.post("/api/v1/safety", json={"action": "kill", "pad": "x" * 500},
                    headers={"X-API-Key": "test-key-123"})
    assert r.status_code == 413


def test_ws_approve_nonce_shape(authed):
    from genio_server.server.auth_tokens import mint_token
    token, _ = mint_token()
    with authed.websocket_connect(f"/ws/agent?token={token}") as ws:
        ws.send_json({"action": "approve", "nonce": "not-a-nonce",
                      "approved": True})
        msg = ws.receive_json()
        assert msg["type"] == "error" and "nonce" in msg["message"]


def test_ws_no_auth_rejected(authed):
    from starlette.websockets import WebSocketDisconnect
    with authed.websocket_connect("/ws/agent") as ws:
        try:
            msg = ws.receive_json()
            assert msg.get("type") == "error", msg
        except WebSocketDisconnect as e:
            assert e.code == 4401


def test_error_sanitized():
    assert "/tmp/" not in main._public_error(ValueError("/tmp/x failed"), "p")
    assert "Traceback" not in main._public_error(RuntimeError("boom"), "p")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
