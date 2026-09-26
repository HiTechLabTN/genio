"""IPC v1.x envelope layer — identity, negotiation, errors, events.

Couche ADDITIVE au-dessus du protocole v1.0 (protocol.py inchangé :
compatibilité ascendante garantie par les tests). Définit :

- méthodes : hello, capabilities, infer, goodbye (+ infer legacy v1.0)
- négociation de version v1.x (pas d'égalité stricte imposée au client)
- codes d'erreur machine-readable (jamais de texte seul)
- schéma d'événements versionnés (transportés via télémétrie d'audit)
- garde anti-rejeu (nonce request_id + fenêtre ts)
- rate-limit par pair (token bucket en mémoire)

Aucun import HiTech-OS : dicts + JSON uniquement.
"""
from __future__ import annotations

import time
from collections import OrderedDict
from typing import Any, Dict, List, Tuple

from . import PROTOCOL_VERSION

PROTOCOL_MIN_SUPPORTED = "1.0"

METHODS = ("hello", "capabilities", "infer", "goodbye")

# Codes d'erreur machine-readable (§17).
ERROR_CODES = (
    "UNSUPPORTED_PROTOCOL",
    "MALFORMED",
    "UNAUTHORIZED",
    "EXPIRED",
    "TIMEOUT",
    "CANCELLED",
    "OVERSIZED",
    "DUPLICATE",
    "UNAVAILABLE",
    "POLICY_DENY",
    "NOT_CONFIGURED",
    "INTERNAL",
)

MAX_PROMPT_BYTES = 256 * 1024
NONCE_WINDOW_S = 300
NONCE_CACHE_MAX = 10000


class EnvelopeError(ValueError):
    """Enveloppe v1.x invalide (avec code machine-readable)."""

    def __init__(self, code, message, request_id=None):
        assert code in ERROR_CODES, f"unknown error code {code!r}"
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.request_id = request_id


def error_envelope(code, message, request_id=None) -> Dict[str, Any]:
    assert code in ERROR_CODES
    return {"protocol_version": PROTOCOL_VERSION, "status": "error",
            "error": {"code": code, "message": str(message)[:500]},
            "request_id": request_id}


def _parse_version(v) -> Tuple[int, ...]:
    try:
        return tuple(int(x) for x in str(v).split("."))
    except (ValueError, AttributeError):
        raise EnvelopeError("MALFORMED", f"bad version {v!r}")


def negotiate(client_min="1.0", client_max="1.0") -> str:
    """Négocie la version v1.x. Retourne la version servie ou lève."""
    cmin, cmax = _parse_version(client_min), _parse_version(client_max)
    smin, sver = _parse_version(PROTOCOL_MIN_SUPPORTED), _parse_version(PROTOCOL_VERSION)
    if cmin > cmax:
        raise EnvelopeError("MALFORMED", "proto_min > proto_max")
    if cmax < smin or cmin > sver:
        raise EnvelopeError(
            "UNSUPPORTED_PROTOCOL",
            f"server speaks {PROTOCOL_MIN_SUPPORTED}..{PROTOCOL_VERSION}, "
            f"client offers {client_min}..{client_max}")
    return PROTOCOL_VERSION


def check_hello(d: Dict[str, Any]) -> Dict[str, Any]:
    """Valide un hello client, retourne les champs normalisés."""
    if not isinstance(d, dict):
        raise EnvelopeError("MALFORMED", "hello: object required")
    if d.get("method") != "hello":
        raise EnvelopeError("MALFORMED", "method must be 'hello'")
    version = negotiate(d.get("proto_min", "1.0"), d.get("proto_max", "1.0"))
    instance = d.get("instance_id")
    if not instance or not isinstance(instance, str):
        raise EnvelopeError("MALFORMED", "instance_id: non-empty string required")
    return {"version": version, "instance_id": instance,
            "product": d.get("product", "unknown"),
            "product_version": d.get("product_version", "unknown")}


# Événements versionnés (§17) : noms + schémas + version.
EVENTS = {
    "genio.ready": {"version": "1.0", "fields": ("instance_id", "protocol_version", "capabilities")},
    "genio.degraded": {"version": "1.0", "fields": ("instance_id", "reason")},
    "genio.request": {"version": "1.0", "fields": ("request_id", "method", "peer_uid", "decision")},
    "genio.shutdown": {"version": "1.0", "fields": ("instance_id",)},
}


def make_event(name, payload: Dict[str, Any]) -> Dict[str, Any]:
    spec = EVENTS.get(name)
    if spec is None:
        raise EnvelopeError("MALFORMED", f"unknown event {name!r}")
    missing = [f for f in spec["fields"] if f not in payload]
    if missing:
        raise EnvelopeError("MALFORMED", f"event {name} missing {missing}")
    return {"event": name, "event_version": spec["version"],
            "ts": time.time(), "payload": payload}


class NonceGuard:
    """Anti-rejeu : request_id uniques + fenêtre ts (±NONCE_WINDOW_S)."""

    def __init__(self, window_s=NONCE_WINDOW_S):
        self.window_s = window_s
        self._seen: "OrderedDict[str, float]" = OrderedDict()

    def check(self, request_id, ts=None):
        now = time.time()
        if not request_id or not isinstance(request_id, str):
            raise EnvelopeError("MALFORMED", "request_id required", request_id)
        if request_id in self._seen:
            raise EnvelopeError("DUPLICATE", "request_id already seen", request_id)
        if ts is not None:
            try:
                skew = abs(float(ts) - now)
            except (TypeError, ValueError):
                raise EnvelopeError("MALFORMED", "ts must be numeric", request_id)
            if skew > self.window_s:
                raise EnvelopeError("EXPIRED", f"ts skew {skew:.0f}s > {self.window_s}s",
                                    request_id)
        self._seen[request_id] = now
        while len(self._seen) > NONCE_CACHE_MAX:
            self._seen.popitem(last=False)
        # purge opportuniste
        cutoff = now - self.window_s
        for k, v in list(self._seen.items()):
            if v < cutoff:
                del self._seen[k]
            else:
                break


class RateLimiter:
    """Token bucket par pair (peer key -> tokens)."""

    def __init__(self, rate_per_min=60, burst=10):
        self.rate = rate_per_min / 60.0
        self.burst = burst
        self._state: Dict[str, List[float]] = {}

    def allow(self, key) -> bool:
        now = time.time()
        tokens, updated = self._state.get(key, [float(self.burst), now])
        tokens = min(float(self.burst), tokens + (now - updated) * self.rate)
        if tokens < 1.0:
            self._state[key] = [tokens, now]
            return False
        self._state[key] = [tokens - 1.0, now]
        return True
