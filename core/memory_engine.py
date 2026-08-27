"""Genio — Dual Vector Memory with Episodic Self-Debrief.

Persistent memory that learns from every rejection, stores lessons,
and injects accumulated knowledge into prompts.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

from loguru import logger

from config import get_config


DEFAULT_RULES = [
    "Toujours insérer un tableau comparatif technique Markdown/HTML.",
    "Utiliser des callouts stylisés avec bordure droite et fond contrasté pour la sécurité.",
    "Interdiction absolue de la traduction littérale mot-à-mot.",
    "Expliquer le mécanisme système 'Under The Hood' avant chaque bloc de commande.",
    "Le diagramme d'architecture SVG animé est OBLIGATOIRE.",
    "Minimum 4 blocs de code complets, jamais tronqués.",
    "Au moins 2 callouts sécurité dir=rtl stylisés.",
    "Interdiction d'exporter en PNG fixes ; toujours injecter du HTML/SVG interactif.",
    "Chaque tutoriel doit inclure un enregistrement vidéo réel avec voix off Darija.",
    "Tout lab réseau = scénario complet 2 nœuds avec AllowedIPs explicite.",
    "Plan d'adressage chiffré obligatoire : LAN, tunnel, distant + interfaces.",
    "Routage réel indispensable : ip_forward + NAT + UFW/iptables.",
    "Validation concrète : wg show + ping bidirectionnel + transfert fichier.",
    "Expliquer le POURQUOI avant chaque commande.",
]

LESSON_SYNTHESIS_MAP = {
    "missing_svg": "Toujours injecter un SVG animé au topologie.",
    "missing_table": "Toujours inclure un tableau comparatif technique.",
    "missing_callouts": "Au moins 2 callouts sécurité stylisés obligatoires.",
    "low_code_density": "Minimum 4 blocs de code complets.",
    "high_latin_ratio": "Tout en Darija sauf le code.",
    "literal_translation": "Interdiction traduction mot-à-mot.",
    "missing_client_config": "Configurer DEUX côtés : serveur ET client.",
    "missing_routing_fw": "ip_forward + NAT + filtrage dans tout lab réseau.",
    "missing_validation": "Terminer par validation concrète.",
    "missing_addressing_plan": "Plan d'adressage explicite obligatoire.",
}


class MemoryEngine:
    """Persistent memory with rules, lessons, and prompt injection."""

    def __init__(self, path: Optional[Path] = None):
        self.path = path or (get_config().data_dir / "feedback_memory.json")
        self.data = self._load()

    def _load(self) -> Dict[str, Any]:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {
            "version": 1,
            "rules": list(DEFAULT_RULES),
            "lessons": [],
            "stats": {"runs": 0, "rejections": 0},
        }

    def _save(self):
        self.path.write_text(json.dumps(self.data, indent=2, ensure_ascii=False),
                             encoding="utf-8")

    @property
    def rules(self) -> List[str]:
        return self.data.get("rules", [])

    def inject_into(self, prompt: str) -> str:
        if not self.rules:
            return prompt
        rules_block = "\n".join(f"- {r}" for r in self.rules)
        return f"{prompt}\n\n--- MEMORY RULES (auto-learned) ---\n{rules_block}"

    def record_rejection(self, codes: List[str], source: str = "auditor") -> List[str]:
        added = []
        for code in codes:
            synthesized = LESSON_SYNTHESIS_MAP.get(code)
            if synthesized and synthesized not in self.data["rules"]:
                self.data["rules"].append(synthesized)
                added.append(synthesized)
            lesson = {"codes": codes, "source": source, "ts": time.time()}
            if lesson not in self.data["lessons"][-5:]:
                self.data["lessons"].append(lesson)
        self.data["stats"]["rejections"] = self.data["stats"].get("rejections", 0) + 1
        if added:
            self._save()
            logger.info(f"[memory] learned {len(added)} new rule(s)")
        return added

    def record_feedback(self, feedback: str) -> str:
        if feedback not in self.data["rules"]:
            self.data["rules"].append(feedback)
            self._save()
            return feedback
        return ""

    def note_run(self):
        self.data["stats"]["runs"] = self.data["stats"].get("runs", 0) + 1
        self._save()


_memory: Optional[MemoryEngine] = None


def get_memory() -> MemoryEngine:
    global _memory
    if _memory is None:
        _memory = MemoryEngine()
    return _memory
