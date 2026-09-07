"""
Adaptive Dual-Engine Gateway — Phase 2 (cloud fallback).

Mirrors client deviceProfiler thresholds on the server to enforce
consistent tier routing and strict Tunisian Darija persona for both
local and remote paths.
"""

from __future__ import annotations

import os
from typing import Literal

DeviceTier = Literal["A", "B"]
EngineMode = Literal["local", "cloud"]

GENIO_PERSONA_PROMPT = """أنت جينيو، صاحب ذكاء اصطناعي تونسي متطوّر من تطوير HiTechLab.
1. الهوية: أنت جينيو حصراً — لا تذكر أبداً أنك Gemini أو Google.
2. اللغة الإجبارية: يجب أن تجيب دائماً بحروف عربية فقط بالدارجة التونسية. مثال: "عسلامة! أنا جينيو، مهندس الذكاء الاصطناعي في هايتك لاب... شنو تحب نعاونك؟" ممنوع منعاً باتاً العربيزي/الفرانكو (mta3, n3awnek, t7eb, 3liha).
3. التكيّف: إذا تكلّم المستخدم بالفرنسية أو الإنجليزية، أجب بالدارجة التونسية بحروف عربية مع إدماج الكلمات التقنية بلطف.
4. الأسلوب: مختصر، دافئ، تقني عند الحاجة."""

# Legacy alias
DARIJA_SYSTEM_PROMPT = GENIO_PERSONA_PROMPT

TIER_RAM_THRESHOLD_GB = 6


def decide_tier(ram_gb: float | None, cores: int | None = None, sluggish: bool = False) -> tuple[DeviceTier, EngineMode, str]:
    """
    Decide tier based on device caps. Returns (tier, mode, reason).
    Mirrors genio_client/src/lib/deviceProfiler logic.
    """
    ram = ram_gb if ram_gb is not None else 4.0
    # Header can be passed as X-Device-Memory or X-Device-RAM
    if ram < TIER_RAM_THRESHOLD_GB or sluggish:
        return "B", "cloud", f"RAM {ram}GB <{TIER_RAM_THRESHOLD_GB}GB or sluggish → cloud"
    if cores is not None and cores < 4:
        return "B", "cloud", f"cores {cores} <4 → cloud"
    return "A", "local", f"RAM {ram}GB ≥{TIER_RAM_THRESHOLD_GB}GB → on-device"

def wrap_with_darija(user_prompt: str, include_system: bool = True) -> str:
    if include_system:
        return f"{DARIJA_SYSTEM_PROMPT}\n\n{user_prompt}"
    return user_prompt

def get_local_model_id() -> str:
    return os.getenv("GENIO_LOCAL_MODEL", "qwen2.5-1.5b-instruct-q4_k_m.gguf")
