"""Genio — Canonical Persistent Memory (single source of truth).

Learns from every rejection, stores lessons durably under ONE locked file,
and injects accumulated rules into prompts.  This module is the only Memory
engine in the codebase: `genio_executive_core` re-exports it.
"""
from __future__ import annotations

import datetime
import fcntl
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

from config import get_config


DEFAULT_RULES = [
    "Toujours insérer un tableau comparatif technique Markdown/HTML.",
    "Utiliser des callouts stylisés avec bordure droite et fond contrasté "
    "pour la sécurité (au moins 2 par article).",
    "Interdiction absolue de la traduction littérale mot-à-mot ; parler "
    "comme un Senior Engineer tunisien (نركبو، نفعلو ديريكت).",
    "Expliquer le mécanisme système 'Under The Hood' avant chaque bloc "
    "de commande.",
    # ---- Directives définitives v3.0 ----
    "Interdiction d'exporter en PNG fixes ; toujours injecter du "
    "HTML/SVG interactif Dark/Cyberpunk dans Ghost via cartes mobiledoc.",
    "Chaque tutoriel doit obligatoirement inclure un enregistrement vidéo "
    "réel des commandes avec voix off explicative en Darija Blanche.",
    "Chaque production doit être automatiquement publiée sur Ghost et "
    "dispatchée sur YouTube avec description et chapitres.",
    # ---- Standard pédagogique IT-Connect v3.5 ----
    "Tout lab réseau/infrastructure = scénario complet 2 nœuds "
    "(Serveur + Client distant) avec échange des clés publiques et "
    "directive AllowedIPs explicite.",
    "Toujours définir un plan d'adressage chiffré : LAN local, sous-réseau "
    "du tunnel, LAN distant + interfaces (wg0/eth0), IPs fixes et port "
    "d'écoute (ex: 51820/UDP).",
    "Le routage réel est INDISPENSABLE : net.ipv4.ip_forward=1 dans "
    "sysctl.conf + NAT/Masquerading + règles de filtrage UFW/iptables "
    "documentées.",
    "Toujours finir par une phase de validation concrète : diagnostic "
    "wg show, ping bidirectionnel à travers le tunnel et transfert de "
    "fichier réel.",
    "Style rédactionnel : expliquer le POURQUOI avant chaque commande "
    "(pourquoi save_config=true, pourquoi cette règle évite de perdre "
    "le SSH...) - zéro ligne de commande jetée sans mécanisme expliqué.",
]

FINDING_LESSONS = {
    "high_latin_ratio": "Tout paragraphe de prose doit être en Darija "
                        "blanche technique - zéro phrase entière en anglais.",
    "literal_translation": "Bannir les formulations passives/mot-à-mot "
                           "(نحن نقوم بتثبيت) : utiliser نركبو / نفعلو ديريكت.",
    "low_code_density": "Minimum 4 blocs de code complets, jamais tronqués.",
    "weak_troubleshooting": "Toujours au moins 2 erreurs réelles avec "
                            "commandes de diagnostic (wg show, tcpdump...).",
    "missing_svg": "Le diagramme d'architecture SVG animé est OBLIGATOIRE.",
    "invalid_svg": "Le SVG doit être du XML valide et autonome.",
    "missing_table": "Un tableau comparatif technique est OBLIGATOIRE.",
    "missing_callouts": "Au moins 2 callouts sécurité dir=rtl stylisés "
                        "(⚠️ نقطة أمنية حساسة...).",
    "gold:hero_box": "Commencer par une Hero Box 🎯 accrocheuse.",
    "gold:architecture_section": "Toujours expliquer le 'Under the Hood'.",
    # v3.5 pedagogical standards
    "missing_client_config": "Configurer les DEUX côtés : Peer serveur ET "
                              "Peer client (clés croisées + AllowedIPs).",
    "missing_routing_fw": "Inclure ip_forward=1 + NAT/Masquerade + filtrage "
                          "réel (UFW/iptables) dans tout lab réseau.",
    "missing_validation": "Terminer par validation concrète : wg show + "
                          "ping bidirectionnel + transfert de fichier.",
    "missing_addressing_plan": "Plan d'adressage explicite obligatoire "
                               "(LAN local / tunnel / LAN distant).",
}


class MemoryEngine:
    """Persistent self-learning memory: lessons become hard prompt rules.

    A single instance is shared process-wide (`get_memory()`).  Writes are
    guarded by an exclusive advisory file lock + atomic rename so concurrent
    agents (or multiple workers) can never corrupt the JSON store.
    """

    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path or (get_config().data_dir / "feedback_memory.json"))
        self.data = self._load()

    # ------------------------------------------------------------------ #
    def _lock_path(self) -> Path:
        return self.path.parent / f"{self.path.name}.lock"

    def _load(self) -> Dict[str, Any]:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                logger.warning("feedback_memory.json corrupted -> reseeding")
        data = {"version": 1, "rules": list(DEFAULT_RULES),
                "lessons": [], "session_context": [],
                "stats": {"runs": 0, "rejections": 0}}
        self._write(data)
        return data

    def _write(self, data: Dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(data, indent=2, ensure_ascii=False)
        lock_path = self._lock_path()
        with lock_path.open("a+", encoding="utf-8") as lock:
            try:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            except OSError:
                pass  # non-POSIX filesystems without flock support
            try:
                tmp = self.path.with_suffix(self.path.suffix + ".tmp")
                tmp.write_text(payload, encoding="utf-8")
                tmp.replace(self.path)  # atomic on POSIX
            finally:
                try:
                    fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
                except OSError:
                    pass

    # ------------------------------------------------------------------ #
    @property
    def rules(self) -> List[str]:
        return self.data.get("rules", [])

    def rules_text(self, limit: int = 24) -> str:
        rules = self.data.get("rules", [])[:limit]
        if not rules:
            return ""
        return "\n".join(f"{i}. {r}" for i, r in enumerate(rules, 1))

    def inject_into(self, prompt: str) -> str:
        block = self.rules_text()
        if not block:
            return prompt
        return (prompt + "\n\nMEMORY RULES (learned from past rejections - "
                "MUST be followed):\n" + block)

    # ------------------------------------------------------------------ #
    # session_context — durable project/user facts, DISTINCT from rules.
    # These are editorial/publishing rules above (content pipeline); this
    # category holds interactive-agent context facts for the chat loop.
    # ------------------------------------------------------------------ #
    @property
    def session_context(self) -> List[Dict[str, str]]:
        ctx = self.data.setdefault("session_context", [])
        if not isinstance(ctx, list):
            ctx = []
            self.data["session_context"] = ctx
        return ctx

    def add_context(self, text: str, category: str = "general") -> None:
        """Persist a durable project/user fact for the interactive agent."""
        text = str(text or "").strip()
        if not text:
            return
        entry = {
            "ts": datetime.datetime.utcnow().isoformat(),
            "category": str(category or "general").strip() or "general",
            "text": text,
        }
        ctx = self.session_context
        # De-duplicate identical recent facts (avoid unbounded growth).
        if ctx and ctx[-1].get("text") == text:
            ctx[-1]["ts"] = entry["ts"]
        else:
            ctx.append(entry)
            self.data["session_context"] = ctx[-200:]
        self._write(self.data)

    def context_text(self, limit: int = 20) -> str:
        """Render up to ``limit`` recent context facts as a prompt block."""
        ctx = self.session_context[-limit:]
        if not ctx:
            return ""
        lines = [
            f"- [{c.get('category', 'general')}] {c.get('text', '')}"
            for c in ctx
        ]
        return "\n".join(lines)

    def record_rejection(self, codes: List[str], source: str = "auditor") -> List[str]:
        """Synthesize auditor/user rejection codes into durable rules."""
        added = []
        existing = set(self.data.get("rules", []))
        for code in codes:
            rule = FINDING_LESSONS.get(code)
            if not rule:
                continue
            rule = rule.strip()
            if rule not in existing:
                self.data["rules"].append(rule)
                existing.add(rule)
                added.append(rule)
        self.data["lessons"].append({
            "ts": datetime.datetime.utcnow().isoformat(),
            "source": source,
            "codes": codes,
            "new_rules": added,
        })
        self.data["lessons"] = self.data["lessons"][-200:]
        self.data["stats"]["rejections"] = \
            self.data["stats"].get("rejections", 0) + 1
        self._write(self.data)
        return added

    def record_feedback(self, rule: str, source: str = "user") -> str:
        """Direct user feedback becomes a first-class rule."""
        rule = rule.strip()
        if rule and rule not in set(self.data.get("rules", [])):
            self.data["rules"].append(rule)
            self.data["lessons"].append({
                "ts": datetime.datetime.utcnow().isoformat(),
                "source": source, "codes": [], "new_rules": [rule]})
            self._write(self.data)
        return rule

    def note_run(self) -> None:
        self.data["stats"]["runs"] = self.data["stats"].get("runs", 0) + 1
        self._write(self.data)


_memory_singleton: Optional[MemoryEngine] = None


def get_memory() -> MemoryEngine:
    global _memory_singleton
    if _memory_singleton is None:
        _memory_singleton = MemoryEngine()
    return _memory_singleton