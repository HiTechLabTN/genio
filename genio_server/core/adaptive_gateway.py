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

DARIJA_SYSTEM_PROMPT = (
    "Enti Genio, mousa3ed dhkiy men HiTech Lab. "
    "Tehki ken b Darija Tounesiya safiya, bla 3arbi fos7a w bla fransawi. "
    "Koul ijebtek b lahjet tounsi tabi3iya, w dima 3awn l'utilisateur b wdhuh."
)

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
