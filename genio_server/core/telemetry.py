"""Deterministic telemetry — Phase 16 (HiTech-OS integrable).

Événements structurés fermés (pas d'invention libre), scrubbing strict
(secrets/tokens/CoT jamais consignés), buffer borné + JSONL append.
"""
from __future__ import annotations

import json
import re
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any, Dict, List, Optional

EVENTS = frozenset({
    "agent.started", "agent.completed", "agent.failed",
    "tool.requested", "tool.allowed", "tool.denied", "tool.completed",
    "policy.allowed", "policy.denied",
    "sandbox.created", "sandbox.destroyed",
    "model.requested", "model.completed",
    "memory.read", "memory.write",
    "security.event", "kill_switch.triggered",
})

_SCRUB_RES = [
    ("private-key", re.compile(
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
        re.S)),
    ("bearer", re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/=]{8,}")),
    ("api-key", re.compile(r"\bsk-[A-Za-z0-9\-_]{10,}")),
    ("api-key", re.compile(r"\b(ghp_|github_pat_|gho_|xox[baprs]-)[A-Za-z0-9_]+")),
    ("api-key", re.compile(r"\bAKIA[0-9A-Z]{16}")),
    ("api-key", re.compile(r"\bAIza[0-9A-Za-z\-_]{20,}")),
    ("secret", re.compile(
        r"(?i)(password|passwd|secret|api[_-]?key|app[_-]?secret|"
        r"client[_-]?secret|access[_-]?token)[\"'\s]*[:=][\"'\s]*\S+")),
]

_CHAIN_OF_THOUGHT_MARKERS = ("thinking:", "thought:", "reasoning:",
                              "chain-of-thought")


def scrub_text(text: str) -> str:
    """Scrub secrets + marqueurs de raisonnement brut (jamais loggés)."""
    if not isinstance(text, str):
        return text
    for name, rx in _SCRUB_RES:
        text = rx.sub(f"[REDACTED:{name}]", text)
    low = text.lower()
    if any(m in low for m in _CHAIN_OF_THOUGHT_MARKERS):
        lines = [ln for ln in text.splitlines()
                 if not ln.strip().lower().startswith(_CHAIN_OF_THOUGHT_MARKERS)]
        text = "\n".join(lines) or "[REDACTED:reasoning]"
    return text


def scrub_obj(o: Any) -> Any:
    if isinstance(o, str):
        return scrub_text(o)
    if isinstance(o, list):
        return [scrub_obj(x) for x in o]
    if isinstance(o, dict):
        return {k: scrub_obj(v) for k, v in o.items()}
    return o


_DEFAULT_LOG = Path(__file__).resolve().parents[2] / "state" / "telemetry.jsonl"


class Telemetry:
    """Émetteur borné (ring 500) + append JSONL. Thread-safe."""

    def __init__(self, log_path: Optional[Path] = None, ring: int = 500):
        self.log_path = Path(log_path) if log_path else _DEFAULT_LOG
        self._buf: deque = deque(maxlen=ring)
        self._lock = threading.Lock()

    def emit(self, event: str, session_id: str = "",
             actor: str = "agent", capability: str = "",
             tool: str = "", result: str = "",
             duration_ms: float = 0.0, risk: str = "",
             decision: str = "") -> Optional[Dict[str, Any]]:
        """Retourne None si event inconnu (pas d'invention libre)."""
        if event not in EVENTS:
            return None
        rec = {"ts": int(time.time()), "event": event,
               "session_id": session_id, "actor": actor,
               "capability": capability, "tool": tool,
               "result": str(result)[:500], "duration_ms": round(duration_ms, 1),
               "risk": risk, "decision": decision}
        rec = scrub_obj(rec)
        with self._lock:
            self._buf.append(rec)
            try:
                self.log_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.log_path, "a") as f:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            except Exception:
                pass
        return rec

    def recent(self, n: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._buf)[-n:]


_TELEMETRY: Optional[Telemetry] = None
_TELEMETRY_LOCK = threading.Lock()


def get_telemetry() -> Telemetry:
    global _TELEMETRY
    with _TELEMETRY_LOCK:
        if _TELEMETRY is None:
            _TELEMETRY = Telemetry()
        return _TELEMETRY
