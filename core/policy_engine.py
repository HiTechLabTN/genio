"""PolicyEngine — Phase 5 centralisé, déterministe, indépendant du LLM.

- Évaluation pure : (tool/action, contexte) -> (décision, raison).
- Fail-closed : inconnu = DENY, registry indisponible = DENY.
- Interrupteur de confirmation : REQUIRE_CONFIRMATION suspend le tour,
  émet un payload `action_confirmation_required` (nonce unique) et attend
  l'approbation explicite avec timeout (défaut : refus à l'expiration).
- stdlib uniquement ; aucun état global mutable hors requêtes en cours.
"""
from __future__ import annotations

import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


CONFIRM_TIMEOUT_SECONDS = float(os.getenv("GENIO_CONFIRM_TIMEOUT", "120"))


@dataclass(frozen=True)
class PolicyDecision:
    decision: str
    reason: str
    capability: str = "UNKNOWN"
    risk: str = "CRITICAL"
    nonce: str = ""


@dataclass
class _Pending:
    nonce: str
    tool: str
    capability: str
    risk: str
    command: str
    created: float
    timeout_s: float
    event: threading.Event = field(default_factory=threading.Event)
    approved: Optional[bool] = None

    def expired(self, now: Optional[float] = None) -> bool:
        return (now or time.monotonic()) - self.created >= self.timeout_s


class PolicyEngine:
    """Moteur de politique central (déterministe, testable, fail-closed)."""

    def __init__(self) -> None:
        self._pending: Dict[str, _Pending] = {}
        self._lock = threading.Lock()

    # -- évaluation pure -------------------------------------------------- #
    def evaluate(self, tool: str, sandbox_available: bool = False,
                 mode: Optional[str] = None) -> PolicyDecision:
        try:
            from genio_server.core.registries import (
                CapabilityRegistry, PolicyRegistry)
        except Exception:
            return PolicyDecision("DENY", "registry-unavailable")
        desc = CapabilityRegistry.descriptor_of(tool)
        if desc is None:
            return PolicyDecision("DENY", "DENIED_UNKNOWN_CAPABILITY")
        decision = PolicyRegistry.decide_tool(
            tool, sandbox_available=sandbox_available, mode=mode)
        if decision == "REQUIRE_CONFIRMATION":
            reason = (f"REQUIRE_CONFIRMATION: {tool} "
                      f"[{desc.capability}/{desc.risk_level}] needs explicit "
                      f"operator approval")
        else:
            reason = f"{decision}: {tool} [{desc.capability}]"
        return PolicyDecision(decision, reason, desc.capability,
                              desc.risk_level)

    # -- interrupteur de confirmation -------------------------------------- #
    def request_confirmation(self, tool: str, command: str,
                             timeout_s: float = CONFIRM_TIMEOUT_SECONDS,
                             ) -> PolicyDecision:
        from genio_server.core.registries import CapabilityRegistry
        desc = CapabilityRegistry.descriptor_of(tool)
        cap = desc.capability if desc else "UNKNOWN"
        risk = desc.risk_level if desc else "CRITICAL"
        nonce = uuid.uuid4().hex
        with self._lock:
            self._pending[nonce] = _Pending(
                nonce=nonce, tool=tool, capability=cap, risk=risk,
                command=str(command or "")[:500], created=time.monotonic(),
                timeout_s=timeout_s)
        self.purge_expired()
        return PolicyDecision("REQUIRE_CONFIRMATION",
                              f"awaiting operator approval (nonce {nonce})",
                              cap, risk, nonce)

    def pending(self, nonce: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            p = self._pending.get(nonce)
            if p is None:
                return None
            return {"nonce": p.nonce, "tool": p.tool,
                    "capability": p.capability, "risk": p.risk,
                    "command": p.command,
                    "expires_in_s": max(
                        0.0, p.timeout_s - (time.monotonic() - p.created))}

    def resolve(self, nonce: str, approved: bool) -> bool:
        """Approbation explicite de l'opérateur. Retourne False si inconnu.

        Single-use + expiry enforced HERE (pas seulement à l'attente) :
        un nonce déjà décidé ou expiré ne peut plus autoriser quoi que
        ce soit (anti-rejeu, anti-décision-tardive). N'exécute jamais rien
        lui-même — l'exécution vérifie via consume().
        """
        with self._lock:
            p = self._pending.get(nonce)
            if p is None:
                return False
            if p.approved is not None:
                return False  # déjà décidé : le premier verdict gagne
            if p.expired():
                self._pending.pop(nonce, None)
                p.event.set()
                return False  # expiré : refus fail-closed
            p.approved = bool(approved)
            p.event.set()
            return True

    def await_decision(self, nonce: str,
                       timeout_s: Optional[float] = None) -> bool:
        """Bloque jusqu'à approbation/refus/timeout. False = refus/timeout.

        Ne consomme PAS le nonce : l'exécution doit appeler consume()
        avec la commande exacte (liaison commande↔approbation, anti-TOCTOU).
        Les entrées orphelines expirent (purge_expired / resolve).
        """
        with self._lock:
            p = self._pending.get(nonce)
            if p is None:
                return False
            wait = p.timeout_s if timeout_s is None else timeout_s
        ok = p.event.wait(timeout=wait)
        with self._lock:
            p2 = self._pending.get(nonce)
            if p2 is None:
                return False
            return bool(ok and p2.approved is True and not p2.expired())

    def consume(self, nonce: str, command: str) -> bool:
        """Valide single-use qu'un nonce approuvé couvre EXACTEMENT
        ``command`` (la chaîne montrée à l'opérateur, tronquée à 500 comme
        au request). Pop atomique : rejouer le même nonce échoue ; une
        commande altérée après approbation échoue (anti-TOCTOU).
        """
        with self._lock:
            p = self._pending.get(nonce)
            if p is None:
                return False
            if p.approved is not True or p.expired():
                if p.expired():
                    self._pending.pop(nonce, None)
                    p.event.set()
                return False
            if str(command or "")[:500] != p.command:
                return False  # cible modifiée après approbation : refus
            self._pending.pop(nonce, None)
            return True

    def release(self, nonce: str) -> bool:
        """Abandonne une demande sans décider (l'attente tombe en refus)."""
        with self._lock:
            p = self._pending.pop(nonce, None)
            if p is None:
                return False
            p.event.set()
            return True

    def pending_count(self) -> int:
        with self._lock:
            return len(self._pending)

    def purge_expired(self) -> int:
        now = time.monotonic()
        with self._lock:
            dead = [k for k, p in self._pending.items() if p.expired(now)]
            for k in dead:
                self._pending[k].event.set()
                del self._pending[k]
        return len(dead)


_ENGINE: Optional[PolicyEngine] = None
_ENGINE_LOCK = threading.Lock()


def get_policy_engine() -> PolicyEngine:
    global _ENGINE
    with _ENGINE_LOCK:
        if _ENGINE is None:
            _ENGINE = PolicyEngine()
        return _ENGINE
