"""IPC v1.x + failure modes + compatibility (§17/§21/§24).

Both ends proven: IpcServer (Genio) <-> ReferenceClient (test peer).
Legacy v1.0 protocol.py untouched and still green (test_hitechos_contract).
"""
import os
import threading
import time

import pytest

from genio.integrations.hitechos import PROTOCOL_VERSION
from genio.integrations.hitechos.capabilities import advertise, catalog
from genio.integrations.hitechos.envelope import (
    ERROR_CODES, EnvelopeError, NonceGuard, RateLimiter, error_envelope, make_event, negotiate,
)
from genio.integrations.hitechos.reference_client import ReferenceClient
from genio.integrations.hitechos.server import IpcServer, peer_uid


@pytest.fixture()
def server(tmp_path):
    sock = str(tmp_path / "ipc-test.sock")
    srv = IpcServer(sock_path=sock, product_version="test")
    srv.infer_handler = lambda req: {
        "protocol_version": PROTOCOL_VERSION, "status": "ok",
        "request_id": req["request_id"], "text": f"echo:{req['prompt'][:20]}",
        "model": req["model"], "backend": "test-handler", "tokens": 1,
        "latency_ms": 0.5}
    srv.start()
    time.sleep(0.2)
    yield srv
    srv.stop()


@pytest.fixture()
def client(server):
    return ReferenceClient(server.sock_path)


def test_negotiate_overlap():
    assert negotiate("1.0", "1.0") == PROTOCOL_VERSION
    assert negotiate("0.9", "1.5") == PROTOCOL_VERSION


def test_negotiate_mismatch():
    with pytest.raises(EnvelopeError) as e:
        negotiate("2.0", "2.5")
    assert e.value.code == "UNSUPPORTED_PROTOCOL"
    with pytest.raises(EnvelopeError):
        negotiate("9.9", "0.1")


def test_error_codes_closed_set():
    assert set(ERROR_CODES) >= {"UNSUPPORTED_PROTOCOL", "MALFORMED", "UNAUTHORIZED",
                                "EXPIRED", "DUPLICATE", "OVERSIZED", "UNAVAILABLE"}
    env = error_envelope("MALFORMED", "x", "r1")
    assert env["error"]["code"] == "MALFORMED" and env["request_id"] == "r1"
    with pytest.raises(AssertionError):
        error_envelope("NOPE", "x")


def test_events_schema():
    ev = make_event("genio.ready", {"instance_id": "i", "protocol_version": "1.0",
                                    "capabilities": []})
    assert ev["event_version"] == "1.0" and "ts" in ev
    with pytest.raises(EnvelopeError):
        make_event("nope.event", {})
    with pytest.raises(EnvelopeError):
        make_event("genio.ready", {"instance_id": "i"})


def test_nonce_replay_and_expiry():
    g = NonceGuard(window_s=300)
    g.check("a", time.time())
    with pytest.raises(EnvelopeError) as e:
        g.check("a", time.time())
    assert e.value.code == "DUPLICATE"
    with pytest.raises(EnvelopeError) as e:
        g.check("b", time.time() - 10000)
    assert e.value.code == "EXPIRED"


def test_rate_limiter():
    lim = RateLimiter(rate_per_min=60, burst=2)
    assert lim.allow("k") and lim.allow("k") and not lim.allow("k")


def test_capabilities_honest():
    cat = catalog()
    assert "sandbox" in cat["available"] or "sandbox" in cat["unavailable"]
    assert "vision" in cat["unavailable"]  # not-configured is honest
    for c in advertise():
        assert set(c) >= {"capability", "available", "version", "detail"}
        if c["available"]:
            assert c["version"] == "1.0"


def test_full_flow(server, client):
    h = client.hello()
    assert h["status"] == "ok" and client.negotiated == PROTOCOL_VERSION
    assert h["instance_id"] == server.instance_id
    caps = client.capabilities()
    assert caps["status"] == "ok" and isinstance(caps["capabilities"], list)
    r = client.infer("salam", model="m")
    assert r["status"] == "ok" and r["text"].startswith("echo:salam")
    bye = client.goodbye()
    assert bye["status"] == "ok"


def test_legacy_v10_infer_still_accepted(server, client):
    # No method + v1.0 schema == legacy path (backward compat).
    r = client._send({"request_id": "leg-1", "model": "m", "prompt": "hi",
                      "ts": time.time()})
    assert r["status"] == "ok"


def test_wrong_version_rejected(client):
    r = client.hello(proto_min="2.0", proto_max="2.0")
    assert r["error"]["code"] == "UNSUPPORTED_PROTOCOL"


def test_malformed_rejected(client):
    r = client._send({"method": "hello", "request_id": "m1"})
    assert r["error"]["code"] == "MALFORMED"
    r = client._send({"nope": True})
    assert r["error"]["code"] == "MALFORMED"


def test_unauthorized_uid(tmp_path):
    srv = IpcServer(sock_path=str(tmp_path / "auth.sock"),
                    allow_uids={424242})
    srv.start()
    try:
        c = ReferenceClient(srv.sock_path)
        r = c.hello()
        assert r["error"]["code"] == "UNAUTHORIZED"
    finally:
        srv.stop()


def test_duplicate_and_expired_live(server, client):
    rid = "dup-live-1"
    r1 = client.infer("a", request_id=rid)
    assert r1["status"] == "ok"
    r2 = client.infer("a", request_id=rid)
    assert r2["error"]["code"] == "DUPLICATE"
    r3 = client.infer("a", ts=time.time() - 10000)
    assert r3["error"]["code"] == "EXPIRED"


def test_oversized_prompt_live(server, client):
    r = client.infer("x" * (300 * 1024))
    assert r["error"]["code"] == "OVERSIZED"


def test_daemon_absent_graceful(tmp_path):
    c = ReferenceClient(str(tmp_path / "nope.sock"), timeout=2.0)
    r = c.hello()
    assert r["status"] == "transport-error"
    assert "unavailable" in r["error"] or "No such" in r["error"]


def test_concurrent_requests(server):
    errors = []

    def worker(n):
        c = ReferenceClient(server.sock_path)
        r = c.infer(f"job-{n}")
        if r.get("status") != "ok":
            errors.append(r)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
    [t.start() for t in threads]
    [t.join(timeout=30) for t in threads]
    assert not errors


def test_no_handler_means_unavailable(tmp_path):
    srv = IpcServer(sock_path=str(tmp_path / "bare.sock"))
    srv.start()
    try:
        c = ReferenceClient(srv.sock_path)
        assert c.hello()["status"] == "ok"
        r = c.infer("hi")
        assert r["error"]["code"] == "UNAVAILABLE"
    finally:
        srv.stop()


def test_peer_uid_self():
    import socket
    a, b = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        assert peer_uid(a) == os.geteuid()
    finally:
        a.close()
        b.close()
