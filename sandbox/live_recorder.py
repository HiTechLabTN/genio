"""Genio — 1080p Playwright Terminal Recording & Validation.

Records real terminal sessions in Docker sandboxes with synchronized
Darija voice-over and chapter title cards.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Re-export from legacy module for backward compatibility
from livetest_recorder import (
    LiveLabRecorder,
    wireguard_lab_steps,
    wireguard_lab_chapters,
    flatten_chapters,
    LabStep,
    RecordingResult,
)


class ContentArchitectAgent:
    """Content generation with 8-pass IT-Connect pedagogical structure."""

    def __init__(self, generate_fn=None):
        from core.memory_engine import get_memory
        self.memory = get_memory()
        self._generate_fn = generate_fn

    async def _gen(self, prompt: str) -> str:
        prompt = self.memory.inject_into(prompt)
        if self._generate_fn is not None:
            return await self._generate_fn(prompt=prompt)
        from core.model_router import ModelRouter
        router = ModelRouter()
        return await router.generate(prompt)

    async def run(self, node, ctx):
        from genio_executive_core import PlanNode, NodeResult
        topic = node.params.get("topic", ctx.goal)
        try:
            # Import the full content architect from legacy
            from genio_executive_core import ContentArchitectAgent as LegacyCA
            legacy = LegacyCA(generate_fn=self._generate_fn)
            result = await legacy.run(node, ctx)
            return result
        except Exception as exc:
            return NodeResult(node.id, False, error=str(exc))
