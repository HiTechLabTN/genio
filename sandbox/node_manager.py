"""Genio — Ephemeral Multi-Node Network Orchestration.

Manages Docker containers, custom bridges, WireGuard tunnels, and NAT
for real multi-node validation scenarios.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Dict

from loguru import logger

from config import get_config

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class NodeManagerAgent:
    """Multi-container network orchestration with self-healing."""

    def __init__(self):
        self.config = get_config().sandbox
        self._recorder = None

    async def _get_recorder(self):
        if self._recorder is None:
            from livetest_recorder import LiveLabRecorder
            self._recorder = LiveLabRecorder()
        return self._recorder

    async def run(self, node, ctx):
        from genio_executive_core import PlanNode, NodeResult, AgentContext
        action = node.action

        if action == "check_environment":
            return await self._check_environment(node, ctx)
        elif action == "setup_sandbox":
            return await self._setup_sandbox(node, ctx)
        elif action == "teardown_sandbox":
            return await self._teardown_sandbox(node, ctx)
        else:
            return NodeResult(node.id, False, error=f"Unknown action: {action}")

    async def _check_environment(self, node, ctx):
        from genio_executive_core import NodeResult
        checks = {}
        try:
            import httpx
            tts_url = get_config().cinema.tts_url
            async with httpx.AsyncClient(timeout=6.0) as client:
                r = await client.get(f"{tts_url}/health")
                checks["cinema_engine"] = r.status_code == 200
        except Exception:
            checks["cinema_engine"] = False

        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "info", stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL)
            await proc.wait()
            checks["docker"] = proc.returncode == 0
        except Exception:
            checks["docker"] = False

        try:
            proc = await asyncio.create_subprocess_exec(
                "ffmpeg", "-version", stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL)
            await proc.wait()
            checks["ffmpeg"] = proc.returncode == 0
        except Exception:
            checks["ffmpeg"] = False

        ctx.scratch["env_checks"] = checks
        detail = ", ".join(f"{k}={'OK' if v else 'DOWN'}" for k, v in checks.items())
        ok = checks.get("docker", False)
        return NodeResult(node.id, ok, output=detail,
                          error=None if ok else "Docker not available")

    async def _setup_sandbox(self, node, ctx):
        from genio_executive_core import NodeResult
        recorder = await self._get_recorder()
        try:
            plan = await recorder.setup_two_node_network()
            ctx.scratch["sandbox_plan"] = plan
            return NodeResult(node.id, True,
                              output=f"2-node: srv={plan['srv_wan_ip']} cli={plan['cli_wan_ip']}")
        except Exception as exc:
            return NodeResult(node.id, False, error=str(exc))

    async def _teardown_sandbox(self, node, ctx):
        from genio_executive_core import NodeResult
        recorder = await self._get_recorder()
        await recorder.stop_sandbox()
        return NodeResult(node.id, True, output="sandbox torn down")
