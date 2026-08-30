"""Genio — Dynamic LLM Router with automatic failover.

Routes complex coding/reasoning tasks to the most suitable LLM with
automatic fallback on rate limits or API downtime.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional

import httpx
from loguru import logger

from config import get_config


@dataclass
class ModelEndpoint:
    name: str
    base_url: str
    model: str
    api_key: str = ""
    timeout: float = 180.0
    priority: int = 0


@dataclass
class RouterState:
    failures: dict = field(default_factory=dict)
    last_success: dict = field(default_factory=dict)
    cooldown_until: dict = field(default_factory=dict)


class ModelRouter:
    """Intelligent LLM dispatch with failover chain."""

    def __init__(self):
        cfg = get_config()
        self.endpoints = [
            ModelEndpoint(
                name="ollama-primary",
                base_url=cfg.ollama.base_url,
                model=cfg.ollama.primary_model,
                timeout=180.0,
                priority=0,
            ),
            *[ModelEndpoint(
                name=f"ollama-backup-{i}",
                base_url=cfg.ollama.base_url,
                model=m,
                timeout=120.0,
                priority=i + 1,
            ) for i, m in enumerate(cfg.ollama.backup_models)],
        ]
        if cfg.openrouter.api_key:
            self.endpoints.append(ModelEndpoint(
                name="openrouter",
                base_url=cfg.openrouter.base_url,
                model=cfg.openrouter.model,
                api_key=cfg.openrouter.api_key,
                timeout=60.0,
                priority=100,
            ))
        self.state = RouterState()
        self.endpoints.sort(key=lambda e: e.priority)

    def _is_available(self, ep: ModelEndpoint) -> bool:
        cooldown = self.state.cooldown_until.get(ep.name, 0)
        if time.monotonic() < cooldown:
            return False
        return True

    def _mark_failure(self, ep: ModelEndpoint):
        count = self.state.failures.get(ep.name, 0) + 1
        self.state.failures[ep.name] = count
        cooldown = min(300, 2 ** count * 5)
        self.state.cooldown_until[ep.name] = time.monotonic() + cooldown
        logger.warning(f"[router] {ep.name} failed (attempt {count}), "
                       f"cooldown {cooldown}s")

    def _mark_success(self, ep: ModelEndpoint):
        self.state.failures[ep.name] = 0
        self.state.last_success[ep.name] = time.monotonic()
        self.state.cooldown_until[ep.name] = 0

    async def generate(self, prompt: str, temperature: float = 0.6,
                       max_tokens: int = 4096) -> str:
        """Generate text with automatic failover across all endpoints."""
        errors = []
        for ep in self.endpoints:
            if not self._is_available(ep):
                continue
            for attempt in range(1, 3):  # one retry for gemma4 empty-generation bug
                try:
                    result = await self._call_endpoint(ep, prompt, temperature, max_tokens)
                    if result:
                        self._mark_success(ep)
                        logger.info(f"[router] ✅ {ep.name} succeeded (attempt {attempt})")
                        return result
                    if attempt == 1 and "11434" in ep.base_url:
                        logger.warning(f"[router] {ep.name} returned empty result, retrying")
                        await asyncio.sleep(0.5)
                        continue
                except Exception as exc:
                    self._mark_failure(ep)
                    errors.append(f"{ep.name}: {exc}")
                    logger.warning(f"[router] ❌ {ep.name} failed: {exc}")
                    break
        raise RuntimeError(f"All LLM endpoints failed: {errors}")

    async def _call_endpoint(self, ep: ModelEndpoint, prompt: str,
                             temperature: float, max_tokens: int) -> str:
        headers = {}
        if ep.api_key:
            headers["Authorization"] = f"Bearer {ep.api_key}"

        async with httpx.AsyncClient(timeout=ep.timeout) as client:
            response = await client.post(
                f"{ep.base_url}/api/generate" if "11434" in ep.base_url
                else f"{ep.base_url}/chat/completions",
                json=self._build_payload(ep, prompt, temperature, max_tokens),
                headers=headers,
            )
            if response.status_code == 200:
                data = response.json()
                if "response" in data:
                    return data["response"]
                if "choices" in data:
                    return data["choices"][0]["message"]["content"]
            elif response.status_code in (429, 500, 502, 503):
                raise ConnectionError(f"HTTP {response.status_code}")
        return ""

    @staticmethod
    def _build_payload(ep: ModelEndpoint, prompt: str,
                       temperature: float, max_tokens: int) -> dict:
        if "11434" in ep.base_url:
            # Ollama/Gemma4 quirk: num_predict <= 512 returns an empty
            # response (done_reason=length, 0 visible tokens). Floor it.
            num_predict = max(max_tokens, 1024) if ep.model.startswith("gemma") else max_tokens
            return {
                "model": ep.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "top_p": 0.9,
                    "num_predict": num_predict,
                    "num_ctx": 8192,
                },
            }
        return {
            "model": ep.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

    def health(self) -> dict:
        return {
            ep.name: {
                "available": self._is_available(ep),
                "failures": self.state.failures.get(ep.name, 0),
                "last_success": self.state.last_success.get(ep.name),
            }
            for ep in self.endpoints
        }
