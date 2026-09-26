"""Protocole JSON v1.0 strict — requêtes/réponses d'inférence.

Schémas validés à la construction : champs requis, types, bornes.
Aucune importation du code HiTech-OS : que des dicts + JSON.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict

from . import PROTOCOL_VERSION


class ProtocolError(ValueError):
    """Schéma v1.0 violé (requête ou réponse)."""


@dataclass(frozen=True)
class InferenceRequest:
    request_id: str
    model: str
    prompt: str
    context: Dict[str, Any] = field(default_factory=dict)
    max_tokens: int = 512
    temperature: float = 0.2
    protocol_version: str = PROTOCOL_VERSION

    def __post_init__(self) -> None:
        if self.protocol_version != PROTOCOL_VERSION:
            raise ProtocolError(f"protocol_version must be {PROTOCOL_VERSION}")
        if not self.request_id or not isinstance(self.request_id, str):
            raise ProtocolError("request_id: non-empty string required")
        if not self.model or not isinstance(self.model, str):
            raise ProtocolError("model: non-empty string required")
        if not isinstance(self.prompt, str):
            raise ProtocolError("prompt: string required")
        if not isinstance(self.context, dict):
            raise ProtocolError("context: object required")
        if not isinstance(self.max_tokens, int) or not 1 <= self.max_tokens <= 8192:
            raise ProtocolError("max_tokens: int 1..8192 required")
        if not isinstance(self.temperature, (int, float)) \
                or not 0.0 <= float(self.temperature) <= 2.0:
            raise ProtocolError("temperature: 0.0..2.0 required")

    def to_dict(self) -> Dict[str, Any]:
        return {"protocol_version": self.protocol_version,
                "request_id": self.request_id, "model": self.model,
                "prompt": self.prompt, "context": self.context,
                "max_tokens": self.max_tokens,
                "temperature": float(self.temperature)}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "InferenceRequest":
        if not isinstance(d, dict):
            raise ProtocolError("request: object required")
        try:
            return cls(request_id=d["request_id"], model=d["model"],
                       prompt=d["prompt"], context=d.get("context", {}),
                       max_tokens=d.get("max_tokens", 512),
                       temperature=d.get("temperature", 0.2),
                       protocol_version=d.get("protocol_version",
                                              PROTOCOL_VERSION))
        except KeyError as e:
            raise ProtocolError(f"request: missing field {e}")


@dataclass(frozen=True)
class InferenceResponse:
    request_id: str
    text: str
    model: str
    backend: str
    tokens: int = 0
    latency_ms: float = 0.0
    status: str = "ok"
    protocol_version: str = PROTOCOL_VERSION

    def __post_init__(self) -> None:
        if self.protocol_version != PROTOCOL_VERSION:
            raise ProtocolError(f"protocol_version must be {PROTOCOL_VERSION}")
        if not self.request_id or not isinstance(self.request_id, str):
            raise ProtocolError("request_id: non-empty string required")
        if not isinstance(self.text, str):
            raise ProtocolError("text: string required")
        if self.status not in ("ok", "error"):
            raise ProtocolError("status: ok|error required")

    def to_dict(self) -> Dict[str, Any]:
        return {"protocol_version": self.protocol_version,
                "request_id": self.request_id, "text": self.text,
                "model": self.model, "backend": self.backend,
                "tokens": self.tokens, "latency_ms": float(self.latency_ms),
                "status": self.status}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "InferenceResponse":
        if not isinstance(d, dict):
            raise ProtocolError("response: object required")
        try:
            return cls(request_id=d["request_id"], text=d["text"],
                       model=d.get("model", "?"), backend=d.get("backend", "?"),
                       tokens=int(d.get("tokens", 0)),
                       latency_ms=float(d.get("latency_ms", 0.0)),
                       status=d.get("status", "ok"),
                       protocol_version=d.get("protocol_version",
                                              PROTOCOL_VERSION))
        except KeyError as e:
            raise ProtocolError(f"response: missing field {e}")
        except (TypeError, ValueError) as e:
            raise ProtocolError(f"response: bad field type ({e})")


def new_request_id() -> str:
    import uuid
    return uuid.uuid4().hex
