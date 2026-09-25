"""Adaptateur HiTech-OS — Phase 14 (contrat, pas d'implémentation OS).

`HitechOSAdapter.infer()` parle au daemon via UDS quand il existe, sinon
retourne UNAVAILABLE structuré — jamais de repli silencieux vers un autre
backend (le routeur décide explicitement, Phase 13).
"""
from __future__ import annotations

import time
from typing import Any, Dict, Optional

from . import DEFAULT_SOCK_GENIO, DEFAULT_SOCK_HITECHOS, PROTOCOL_VERSION
from .protocol import InferenceRequest, InferenceResponse, ProtocolError
from .transport import TransportError, query


class DaemonUnavailable(RuntimeError):
    """Le daemon HiTech-OS ne répond pas (socket absent/refus)."""


class HitechOSAdapter:
    def __init__(self, sock_path: Optional[str] = None):
        self.sock_path = sock_path or DEFAULT_SOCK_HITECHOS
        self.fallback_sock = DEFAULT_SOCK_GENIO

    def available(self) -> bool:
        import os
        return (os.path.exists(self.sock_path)
                or os.path.exists(self.fallback_sock))

    def _sock(self) -> str:
        import os
        if os.path.exists(self.sock_path):
            return self.sock_path
        return self.fallback_sock

    def infer(self, prompt: str, model: str = "default",
              max_tokens: int = 512, temperature: float = 0.2,
              context: Optional[Dict[str, Any]] = None,
              timeout: float = 60.0) -> Dict[str, Any]:
        """Inférence via daemon. Lève DaemonUnavailable si injoignable."""
        from .protocol import new_request_id
        try:
            req = InferenceRequest(
                request_id=new_request_id(), model=model, prompt=prompt,
                context=context or {}, max_tokens=max_tokens,
                temperature=temperature)
        except ProtocolError as e:
            return {"status": "error", "error": f"bad request: {e}",
                    "protocol_version": PROTOCOL_VERSION}
        t0 = time.monotonic()
        try:
            raw = query(self._sock(), req.to_dict(), timeout=timeout)
        except TransportError as e:
            raise DaemonUnavailable(str(e))
        try:
            resp = InferenceResponse.from_dict(raw)
        except ProtocolError as e:
            raise DaemonUnavailable(f"bad daemon response: {e}")
        if resp.request_id != req.request_id:
            raise DaemonUnavailable("request_id mismatch (wrong daemon?)")
        d = resp.to_dict()
        d["latency_ms"] = round((time.monotonic() - t0) * 1000.0, 1)
        return d
