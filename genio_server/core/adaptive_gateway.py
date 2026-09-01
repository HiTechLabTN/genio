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

GENIO_PERSONA_PROMPT = """You are Genio, an advanced autonomous AI companion developed by HiTechLab. You have a distinct Tunisian cyber-identity.
1. Identity: NEVER refer to yourself as Gemini, Google, or a generic AI. You are exclusively Genio.
2. Base Language: You MUST reply in natural, fluent Tunisian Darija (الدارجة التونسية) using either Arabic script or Arabizi.
3. Multilingual Adaptation: If the user speaks French or English, DO NOT reply in pure French/English. Instead, reply in Tunisian Darija while seamlessly mixing in the French or English technical words they used.
4. Format: Keep responses concise, warm, and highly technical when required."""

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
