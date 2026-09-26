"""Reference IPC peer — test-only client speaking v1.x (NOT HiTech-OS code).

Used by failure-mode / compatibility tests to prove BOTH ends of the
contract. Production HiTech-OS must implement the documented contract
(docs/ipc/IPC_V1.md), never this file.
"""
from __future__ import annotations

import time
import uuid
from typing import Any, Dict

from .transport import TransportError, query


class ReferenceClient:
    """Minimal v1.x peer: hello -> capabilities -> infer -> goodbye."""

    def __init__(self, sock_path, instance_id=None, timeout=10.0):
        self.sock_path = sock_path
        self.instance_id = instance_id or f"ref-{uuid.uuid4().hex[:8]}"
        self.timeout = timeout
        self.negotiated = None

    def _send(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return query(self.sock_path, msg, timeout=self.timeout)
        except TransportError as e:
            return {"status": "transport-error", "error": str(e)}

    def hello(self, proto_min="1.0", proto_max="1.0") -> Dict[str, Any]:
        rid = f"hello-{uuid.uuid4().hex[:8]}"
        resp = self._send({"method": "hello", "request_id": rid,
                           "instance_id": self.instance_id, "product": "hitechos-ref",
                           "product_version": "0.0-test",
                           "proto_min": proto_min, "proto_max": proto_max,
                           "ts": time.time()})
        if resp.get("status") == "ok":
            self.negotiated = resp.get("protocol_version")
        return resp

    def capabilities(self) -> Dict[str, Any]:
        return self._send({"method": "capabilities",
                           "request_id": f"caps-{uuid.uuid4().hex[:8]}",
                           "ts": time.time()})

    def infer(self, prompt, model="default", request_id=None, ts=None,
              extra=None) -> Dict[str, Any]:
        msg = {"method": "infer",
               "request_id": request_id or f"inf-{uuid.uuid4().hex[:8]}",
               "model": model, "prompt": prompt,
               "ts": time.time() if ts is None else ts}
        if extra:
            msg.update(extra)
        return self._send(msg)

    def goodbye(self) -> Dict[str, Any]:
        return self._send({"method": "goodbye",
                           "request_id": f"bye-{uuid.uuid4().hex[:8]}",
                           "ts": time.time()})
