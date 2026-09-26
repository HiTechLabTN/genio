"""Memory architecture OS-grade — Phase 12.

Registres canoniques : WorkingMemory (éphémère bornée), EpisodicMemory
(façade lecture sur session_store, isolation par session), SemanticMemory
(faits durables JSONL + métadonnées d'audit), SystemKnowledge (statique).

Tout item persisté porte : source, timestamp, confidence_score, provenance,
trust_level, expiration, scope. Jamais d'item autoritaire sans provenance ;
quarantaine anti-empoisonnement ; purge à expiration.
"""
from __future__ import annotations

import json
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


class TrustLevel:
    SYSTEM = "SYSTEM"          # writers de confiance (code, policy)
    OPERATOR = "OPERATOR"      # opérateur humain explicite
    VERIFIED = "VERIFIED"      # vérifié par exécution/outil
    UNVERIFIED = "UNVERIFIED"  # contenu externe non vérifié
    QUARANTINED = "QUARANTINED"  # suspect — jamais autoritaire


class MemoryKind:
    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    SYSTEM = "system"


@dataclass(frozen=True)
class MemoryItem:
    text: str
    kind: str = MemoryKind.SEMANTIC
    source: str = "unknown"
    timestamp: float = field(default_factory=time.time)
    confidence_score: float = 0.5
    provenance: str = ""
    trust_level: str = TrustLevel.UNVERIFIED
    expiration: float = 0.0  # 0 = jamais
    scope: str = "global"    # session_id ou "global"
    origin: str = ""

    @property
    def id(self) -> str:
        import hashlib
        raw = f"{self.kind}|{self.text}|{self.source}|{self.scope}"
        return hashlib.sha1(raw.encode()).hexdigest()[:12]

    def is_expired(self, now: Optional[float] = None) -> bool:
        if not self.expiration:
            return False
        return (now or time.time()) >= self.expiration

    def is_authoritative(self) -> bool:
        return (self.trust_level in (TrustLevel.SYSTEM, TrustLevel.OPERATOR,
                                     TrustLevel.VERIFIED)
                and not self.is_expired())


class WorkingMemory:
    """Tampon éphémère borné du tour courant (jamais persisté)."""

    def __init__(self, max_items: int = 20):
        self._buf: deque = deque(maxlen=max_items)

    def push(self, text: str, **kw) -> MemoryItem:
        item = MemoryItem(text=text, kind=MemoryKind.WORKING, **kw)
        self._buf.append(item)
        return item

    def items(self) -> List[MemoryItem]:
        return list(self._buf)

    def clear(self) -> None:
        self._buf.clear()


class EpisodicMemory:
    """Façade lecture sur session_store — isolation stricte par session.

    Aucune écriture directe : les turns sont persistés par la boucle.
    Toute lecture est filtrée par session_id (anti-fuite cross-session).
    """

    def __init__(self, session_id: str):
        self.session_id = session_id

    def read(self, limit: int = 10) -> List[MemoryItem]:
        try:
            from genio_server.core.session_store import SessionStore
        except Exception:
            return []
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop is not None and loop.is_running():
            return []  # appel sync depuis une loop : refusé (fail-safe)
        store = SessionStore()
        sess = asyncio.run(store.load_session(self.session_id))
        out = []
        for t in (sess.get("turns") or [])[-limit:]:
            out.append(MemoryItem(
                text=str(t.get("content", ""))[:2000], kind=MemoryKind.EPISODIC,
                source="sessions.db", trust_level=TrustLevel.VERIFIED,
                provenance=f"session:{self.session_id}",
                scope=self.session_id, origin="agent-loop"))
        return out


_DEFAULT_SEM_PATH = Path(__file__).resolve().parents[2] / "state" \
    / "semantic_memory.jsonl"


class SemanticMemory:
    """Faits durables JSONL : upsert par clé, correction = supersède (chaîne
    de provenance conservée), purge à expiration, suppression explicite."""

    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path else _DEFAULT_SEM_PATH

    def _load(self) -> List[Dict[str, Any]]:
        if not self.path.exists():
            return []
        rows = []
        for ln in self.path.read_text().splitlines():
            ln = ln.strip()
            if not ln:
                continue
            try:
                rows.append(json.loads(ln))
            except Exception:
                continue
        return rows

    def _save(self, rows: List[Dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("\n".join(
            json.dumps(r, ensure_ascii=False) for r in rows) + "\n")

    @staticmethod
    def _key(text: str) -> str:
        import hashlib
        norm = " ".join(text.lower().split())[:80]
        return hashlib.sha1(norm.encode()).hexdigest()[:12]

    def add(self, text: str, trust_level: str = TrustLevel.UNVERIFIED,
            quarantine_external: bool = True, **kw) -> MemoryItem:
        """Ajout : contenu externe non vérifié → QUARANTINED (anti-poison)."""
        if quarantine_external and trust_level == TrustLevel.UNVERIFIED and \
                kw.get("source", "") not in ("operator", "system", "verified-tool"):
            trust_level = TrustLevel.QUARANTINED
        item = MemoryItem(text=text, kind=MemoryKind.SEMANTIC,
                          trust_level=trust_level, **kw)
        rows = self._load()
        key = self._key(text)
        rows = [r for r in rows if r.get("key") != key]
        d = {"key": key, **{k: v for k, v in
                            {"text": item.text, "source": item.source,
                             "timestamp": item.timestamp,
                             "confidence_score": item.confidence_score,
                             "provenance": item.provenance,
                             "trust_level": item.trust_level,
                             "expiration": item.expiration,
                             "scope": item.scope,
                             "origin": item.origin}.items()}}
        rows.append(d)
        self._save(rows)
        return item

    def correct(self, old_text: str, new_text: str,
                by: str = "operator") -> MemoryItem:
        """Correction utilisateur : supersède, chaîne de provenance gardée."""
        old_key = self._key(old_text)
        rows = self._load()
        old = next((r for r in rows if r.get("key") == old_key), {})
        rows = [r for r in rows if r.get("key") != old_key]
        self._save(rows)
        return self.add(new_text, trust_level=TrustLevel.OPERATOR,
                        quarantine_external=False, source="operator",
                        provenance=f"supersedes:{old_key} prev-trust:"
                                   f"{old.get('trust_level', '?')} by:{by}",
                        confidence_score=1.0)

    def delete(self, text: str) -> bool:
        key = self._key(text)
        rows = self._load()
        kept = [r for r in rows if r.get("key") != key]
        if len(kept) == len(rows):
            return False
        self._save(kept)
        return True

    def purge_expired(self, now: Optional[float] = None) -> int:
        now = now or time.time()
        rows = self._load()
        kept = [r for r in rows
                if not r.get("expiration") or r["expiration"] > now]
        self._save(kept)
        return len(rows) - len(kept)

    def read_authoritative(self, limit: int = 20) -> List[MemoryItem]:
        out = []
        for r in self._load():
            item = MemoryItem(
                text=r.get("text", ""), source=r.get("source", "?"),
                timestamp=float(r.get("timestamp", 0)),
                confidence_score=float(r.get("confidence_score", 0)),
                provenance=r.get("provenance", ""),
                trust_level=r.get("trust_level", TrustLevel.UNVERIFIED),
                expiration=float(r.get("expiration", 0) or 0),
                scope=r.get("scope", "global"),
                origin=r.get("origin", ""))
            if item.is_authoritative():
                out.append(item)
        out.sort(key=lambda i: -i.confidence_score)
        return out[:limit]


class SystemKnowledge:
    """Faits système statiques (version, nœud, politiques) — lecture seule."""

    @staticmethod
    def items() -> List[MemoryItem]:
        import platform
        return [
            MemoryItem("genio-agent-runtime/1 wiring: ReAct loop, tool gating",
                       kind=MemoryKind.SYSTEM, source="code",
                       trust_level=TrustLevel.SYSTEM, confidence_score=1.0,
                       provenance="registries+agent_loop"),
            MemoryItem(f"host-python {platform.python_version()}",
                       kind=MemoryKind.SYSTEM, source="runtime",
                       trust_level=TrustLevel.SYSTEM, confidence_score=1.0,
                       provenance="platform"),
        ]
