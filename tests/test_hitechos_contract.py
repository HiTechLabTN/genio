"""Phase 14 tests — contrat HiTech-OS (protocole v1.0 + UDS réel).

Aucun daemon réel requis : serveur de test éphémère (vrai socket Unix,
vrais octets). Déconnexion et trames corrompues testées pour de vrai.
"""
import json
import os
import socket
import struct
import sys
import tempfile
import threading

sys.path.insert(0, "/data/ai_tools/genio")

import pytest

from genio.integrations.hitechos import PROTOCOL_VERSION
from genio.integrations.hitechos.adapter import DaemonUnavailable, HitechOSAdapter
from genio.integrations.hitechos.protocol import (
    InferenceRequest,
    InferenceResponse,
    ProtocolError,
    new_request_id,
)
from genio.integrations.hitechos.transport import TransportError, query


_SOCKDIR = tempfile.mkdtemp(prefix="ph14_sock_")
SOCK = os.path.join(_SOCKDIR, "ph14_test.sock")


def _serve_once(handler, ready):
    if os.path.exists(SOCK):
        os.remove(SOCK)
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(SOCK)
    srv.listen(1)
    srv.settimeout(10)
    ready.set()
    try:
        conn, _ = srv.accept()
        with conn:
            conn.settimeout(10)
            (size,) = struct.unpack(">I", conn.recv(4))
            raw = b""
            while len(raw) < size:
                chunk = conn.recv(size - len(raw))
                if not chunk:
                    break
                raw += chunk
            resp = handler(json.loads(raw.decode()))
            if resp is not None:
                payload = json.dumps(resp).encode()
                conn.sendall(struct.pack(">I", len(payload)) + payload)
    finally:
        srv.close()
        if os.path.exists(SOCK):
            os.remove(SOCK)


def _run_server(handler):
    ready = threading.Event()
    t = threading.Thread(target=_serve_once, args=(handler, ready),
                         daemon=True)
    t.start()
    assert ready.wait(timeout=10)
    return t


def test_request_schema_strict():
    r = InferenceRequest(request_id="a", model="m", prompt="hi")
    assert r.to_dict()["protocol_version"] == "1.0"
    assert InferenceRequest.from_dict(r.to_dict()).request_id == "a"
    with pytest.raises(ProtocolError):
        InferenceRequest(request_id="", model="m", prompt="hi")
    with pytest.raises(ProtocolError):
        InferenceRequest(request_id="a", model="m", prompt="hi",
                         max_tokens=99999)
    with pytest.raises(ProtocolError):
        InferenceRequest.from_dict({"model": "m"})
    with pytest.raises(ProtocolError):
        InferenceRequest(request_id="a", model="m", prompt="hi",
                         protocol_version="9.9")


def test_response_schema_strict():
    r = InferenceResponse(request_id="a", text="t", model="m", backend="b")
    assert InferenceResponse.from_dict(r.to_dict()).status == "ok"
    with pytest.raises(ProtocolError):
        InferenceResponse.from_dict({"request_id": "a"})
    assert PROTOCOL_VERSION == "1.0"
    assert new_request_id() != new_request_id()


def test_ipc_roundtrip_real_socket():
    def handler(req):
        return {"protocol_version": "1.0", "request_id": req["request_id"],
                "text": "salam", "model": "m", "backend": "daemon",
                "tokens": 2, "latency_ms": 1.0, "status": "ok"}

    t = _run_server(handler)
    out = query(SOCK, {"protocol_version": "1.0", "request_id": "r1",
                       "model": "m", "prompt": "hi"})
    t.join(timeout=10)
    assert out["text"] == "salam" and out["request_id"] == "r1"


def test_disconnect_resilience():
    def handler(req):
        return None  # ferme sans répondre

    t = _run_server(handler)
    with pytest.raises(TransportError):
        query(SOCK, {"a": 1}, timeout=5)
    t.join(timeout=10)


def test_daemon_unavailable_structured(tmp_path):
    a = HitechOSAdapter(sock_path=str(tmp_path / "nope.sock"))
    assert a.available() is False
    with pytest.raises(DaemonUnavailable):
        a.infer("hi", timeout=5)


def test_adapter_full_flow_real_socket():
    def handler(req):
        return {"protocol_version": "1.0", "request_id": req["request_id"],
                "text": "ok", "model": req.get("model", "?"),
                "backend": "hitechos", "tokens": 1, "latency_ms": 0.5,
                "status": "ok"}

    t = _run_server(handler)
    a = HitechOSAdapter(sock_path=SOCK)
    out = a.infer("hi", model="m", timeout=10)
    t.join(timeout=10)
    assert out["status"] == "ok" and out["backend"] == "hitechos"
    assert out["latency_ms"] >= 0


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
