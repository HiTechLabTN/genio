"""
Genio Autonomous Model Router
Dynamically routes inference requests between Local Ollama and OpenRouter
based on task complexity, VRAM headroom, and GPU thermals.
"""

from __future__ import annotations
import os
import logging
import requests
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from core.evolution.skill_engine import DynamicSkillRegistry

logger = logging.getLogger("genio.evolution.router")

raw_ollama_host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
if not raw_ollama_host.startswith("http"):
    OLLAMA_BASE_URL = f"http://{raw_ollama_host}"
else:
    OLLAMA_BASE_URL = raw_ollama_host

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")


@dataclass
class ModelProfile:
    id: str
    provider: str
    min_vram_mb: int
    context_window: int
    strengths: List[str]


class ModelRouter:
    def __init__(self, registry: Optional[DynamicSkillRegistry] = None):
        self.registry = registry or DynamicSkillRegistry()
        self.registry.load_all()

    def get_gpu_telemetry(self) -> Dict[str, Any]:
        """Queries the hardware_monitor skill if loaded."""
        if "hardware_monitor" in self.registry.active_skills:
            return self.registry.active_skills["hardware_monitor"]()
        return {"gpu_available": False, "vram_free_mb": 0, "status": "unknown"}

    def list_local_ollama_models(self) -> List[str]:
        """Queries local Ollama instance for pulled models."""
        try:
            res = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
            if res.status_code == 200:
                data = res.json()
                return [m["name"] for m in data.get("models", [])]
        except Exception as e:
            logger.warning(f"Could not reach Ollama at {OLLAMA_BASE_URL}: {e}")
        return []

    def select_best_model(self, task_type: str = "general") -> Dict[str, str]:
        """
        Decides the optimal model based on task requirements and current hardware load.
        """
        telemetry = self.get_gpu_telemetry()
        free_vram = telemetry.get("vram_free_mb", 0)
        gpu_status = telemetry.get("status", "safe")
        local_models = self.list_local_ollama_models()

        logger.info(f"Routing task '{task_type}' | Free VRAM: {free_vram}MB | GPU Status: {gpu_status}")

        if gpu_status == "warning_hot":
            logger.warning("GPU thermal warning. Falling back to OpenRouter cloud inference.")
            return {"provider": "openrouter", "model": "anthropic/claude-3.5-sonnet"}

        if task_type in ("deep_reasoning", "architecture"):
            for high_end in ["qwen2.5-coder:14b", "deepseek-r1:14b", "command-r:latest"]:
                if high_end in local_models and free_vram >= 8000:
                    return {"provider": "ollama", "model": high_end}
            return {"provider": "openrouter", "model": "deepseek/deepseek-r1"}

        if task_type in ("fast_draft", "media_script", "general"):
            for mid_end in ["qwen2.5:7b", "llama3.1:8b", "mistral:latest", "gemma2:9b"]:
                if mid_end in local_models and free_vram >= 4500:
                    return {"provider": "ollama", "model": mid_end}

        if local_models:
            return {"provider": "ollama", "model": local_models[0]}

        return {"provider": "openrouter", "model": "meta-llama/llama-3.1-8b-instruct"}
