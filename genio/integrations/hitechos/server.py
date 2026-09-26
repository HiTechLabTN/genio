"""Genio IPC server — le bout Genio du contrat v1.x (§17/§20).

Expose sur UDS : hello (identité + négociation), capabilities,
infer (enveloppe + requête v1.0), goodbye. Sécurité :

- peer UID via SO_PEERCRED ; politique par défaut same-uid-only
  (localhost != trusted) ; allow_uids explicite ; refus = UNAUTHORIZED.
- anti-rejeu (nonce) + fenêtre ts, rate-limit par UID, tailles bornées.
- chaque requête est auditée (télémétrie, sans secrets).
- erreurs toujours en ErrorEnvelope (codes machine-readable).
"""
from __future__ import annotations

import json
import os
import socket
import struct
import threading
import time
import uuid

from . import DEFAULT_SOCK_GENIO, PROTOCOL_VERSION
from .capabilities import catalog
from .envelope import (MAX_PROMPT_BYTES, EnvelopeError,
                       NonceGuard, RateLimiter, check_hello, error_envelope,
                       make_event)
from .protocol import InferenceRequest, ProtocolError
from .transport import MAX_FRAME

SO_PEERCRED = 17


def peer_uid(conn) -> int | None:
    """UID du pair UDS via SO_PEERCRED (Linux). None si indisponible."""
    try:
        raw = conn.getsockopt(socket.SOL_SOCKET, SO_PEERCRED, struct.calcsize("3i"))
        _pid, uid, _gid = struct.unpack("3i", raw)
        return int(uid)
    except OSError:
        return None


class IpcServer:
    def __init__(self, sock_path=None, allow_uids=None, instance_id=None,
                 product_version="unknown", rate_per_min=600):
        self.sock_path = sock_path or DEFAULT_SOCK_GENIO
        self.allow_uids = set(allow_uids) if allow_uids else None  # None = same-uid
        self.instance_id = instance_id or f"genio-{uuid.uuid4().hex[:8]}"
        self.product_version = product_version
        self.nonces = NonceGuard()
        self.limiter = RateLimiter(rate_per_min=rate_per_min)
        self._stop = threading.Event()
        self._thread = None
        self.infer_handler = None  # optionnel : callable(dict) -> dict

    # -- politique ----------------------------------------------------- #
    def _authorized(self, uid) -> bool:
        if uid is None:
            return False  # pas d'identité = pas d'accès (fail closed)
        if self.allow_uids is not None:
            return uid in self.allow_uids
        return uid == os.geteuid()

    def _audit(self, request_id, method, uid, decision):
        try:
            from genio_server.core.telemetry import get_telemetry
            get_telemetry().emit("hitechos-ipc", actor=f"uid:{uid}",
                                 result=decision,
                                 decision="ALLOW" if decision == "ok" else "DENY")
        except Exception:
            pass
        try:
            ev = make_event("genio.request", {"request_id": str(request_id),
                                              "method": method, "peer_uid": uid,
                                              "decision": decision})
            _ = ev
        except EnvelopeError:
            pass

    # -- dispatch ------------------------------------------------------ #
    def handle(self, msg, uid) -> dict:
        if not isinstance(msg, dict):
            return error_envelope("MALFORMED", "object required")
        method = msg.get("method", "infer" if "prompt" in msg else None)
        if method not in ("hello", "capabilities", "infer", "goodbye", None):
            return error_envelope("MALFORMED", f"unknown method {method!r}",
                                  msg.get("request_id"))
        if not self._authorized(uid):
            rid = msg.get("request_id")
            self._audit(rid, method or "?", uid, "unauthorized")
            return error_envelope("UNAUTHORIZED", "peer uid not authorized", rid)
        if not self.limiter.allow(f"uid:{uid}"):
            return error_envelope("POLICY_DENY", "rate limit exceeded",
                                  msg.get("request_id"))
        try:
            if method == "hello":
                info = check_hello(msg)
                self._audit(msg.get("request_id"), "hello", uid, "ok")
                return {"protocol_version": info["version"], "status": "ok",
                        "instance_id": self.instance_id, "product": "genio",
                        "product_version": self.product_version,
                        "capabilities": [c["capability"] for c in catalog()["capabilities"]
                                         if c["available"]],
                        "request_id": msg.get("request_id")}
            if method == "capabilities":
                self.nonces.check(msg.get("request_id"), msg.get("ts", time.time()))
                self._audit(msg.get("request_id"), "capabilities", uid, "ok")
                out = catalog()
                out.update({"status": "ok", "request_id": msg.get("request_id")})
                return out
            if method == "goodbye":
                self._audit(msg.get("request_id"), "goodbye", uid, "ok")
                return {"protocol_version": PROTOCOL_VERSION, "status": "ok",
                        "request_id": msg.get("request_id")}
            return self._handle_infer(msg, uid)
        except EnvelopeError as e:
            self._audit(msg.get("request_id"), method or "?", uid, e.code.lower())
            return error_envelope(e.code, str(e), e.request_id or msg.get("request_id"))

    def _handle_infer(self, msg, uid) -> dict:
        self.nonces.check(msg.get("request_id"), msg.get("ts", time.time()))
        prompt = msg.get("prompt", "")
        if isinstance(prompt, str) and len(prompt.encode("utf-8")) > MAX_PROMPT_BYTES:
            raise EnvelopeError("OVERSIZED", f"prompt > {MAX_PROMPT_BYTES} bytes",
                                msg.get("request_id"))
        try:
            req = InferenceRequest.from_dict(msg)
        except ProtocolError as e:
            raise EnvelopeError("MALFORMED", str(e), msg.get("request_id"))
        if self.infer_handler is not None:
            try:
                out = self.infer_handler(req.to_dict())
            except Exception as e:
                raise EnvelopeError("INTERNAL", f"handler failed: {e}",
                                    req.request_id)
            self._audit(req.request_id, "infer", uid, "ok")
            return out
        self._audit(req.request_id, "infer", uid, "unavailable")
        return error_envelope("UNAVAILABLE", "no inference handler attached "
                                            "(standalone Genio without model)",
                              req.request_id)

    # -- boucle serveur ------------------------------------------------ #
    def start(self):
        if self._thread and self._thread.is_alive():
            return
        try:
            if os.path.exists(self.sock_path):
                os.remove(self.sock_path)
        except OSError:
            pass
        parent = os.path.dirname(self.sock_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        srv.bind(self.sock_path)
        srv.listen(32)
        srv.settimeout(0.5)
        self._srv = srv
        self._stop.clear()
        try:
            from genio_server.core.telemetry import get_telemetry
            get_telemetry().emit("hitechos-ipc", actor="server",
                                 result="ready", decision="ALLOW")
        except Exception:
            pass
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self):
        while not self._stop.is_set():
            try:
                conn, _ = self._srv.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            t = threading.Thread(target=self._one, args=(conn,), daemon=True)
            t.start()

    def _one(self, conn):
        uid = peer_uid(conn)
        try:
            conn.settimeout(30)
            raw_len = conn.recv(4)
            if len(raw_len) < 4:
                return
            (size,) = struct.unpack(">I", raw_len)
            if size > MAX_FRAME or size <= 0:
                return
            raw = b""
            while len(raw) < size:
                chunk = conn.recv(size - len(raw))
                if not chunk:
                    return
                raw += chunk
            try:
                msg = json.loads(raw.decode("utf-8"))
            except Exception:
                resp = error_envelope("MALFORMED", "invalid JSON")
            else:
                resp = self.handle(msg, uid)
            payload = json.dumps(resp, ensure_ascii=False).encode("utf-8")
            conn.sendall(struct.pack(">I", len(payload)) + payload)
        except (OSError, BrokenPipeError):
            pass
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def stop(self):
        self._stop.set()
        try:
            self._srv.close()
        except Exception:
            pass
        if self._thread:
            self._thread.join(timeout=5)
        try:
            if os.path.exists(self.sock_path):
                os.remove(self.sock_path)
        except OSError:
            pass
