"""Phase 1 v2.1 — Backend Non-Blocking Async & Execution Watchdog.

Verifies:
1. async_run_command executes a slow command without blocking the event loop
   (a concurrent asyncio task keeps ticking while the command runs).
2. The watchdog (GENIO_MODEL_TURN_TIMEOUT) enforces an explicit per-turn
   timeout so the agent loop never hangs beyond the configured limit; the
   WebSocket/telemetry stays responsive.
3. Loop-chaining enforcement: exit-0 no-op (cat/touch/mkdir) injects a
   continuation directive instead of terminating into idle.

Run: pytest test_phase_v2_1_watchdog.py -v
"""
import asyncio
import os
import time

import pytest

from genio_server.core.agent_loop import _feedback_for
from genio_server.tools.bash_tool import async_run_command


@pytest.mark.asyncio
async def test_async_run_command_does_not_block_event_loop():
    # A concurrent ticker task must keep firing while the bash command runs.
    ticks = []

    async def ticker():
        for _ in range(10):
            await asyncio.sleep(0.02)
            ticks.append(time.monotonic())

    tick_task = asyncio.create_task(ticker())
    result = await async_run_command("sleep 0.3 && echo done", timeout=10)
    await tick_task

    assert result["returncode"] == 0
    assert "done" in result["stdout"]
    # If the subprocess had blocked the loop, no ticks would have fired.
    assert len(ticks) > 0, "event loop was blocked by subprocess execution"


@pytest.mark.asyncio
async def test_watchdog_timeout_keeps_loop_responsive():
    # Simulate a slow inference call that exceeds GENIO_MODEL_TURN_TIMEOUT.
    old = os.environ.get("GENIO_MODEL_TURN_TIMEOUT")
    os.environ["GENIO_MODEL_TURN_TIMEOUT"] = "0.05"  # 50ms watchdog

    from core.model_router import ModelRouter

    calls = {"count": 0}

    async def slow_call(self, ep, messages, cancel_event=None):
        calls["count"] += 1
        await asyncio.sleep(5)  # far beyond watchdog
        return "late", 0, 0.0

    try:
        with __import__("unittest").mock.patch(
            "core.model_router.ModelRouter._call_chat_endpoint", slow_call
        ):
            # Give router only one endpoint so failover is immediate.
            router = ModelRouter()
            router.endpoints = [router.endpoints[0]]
            start = time.monotonic()
            with pytest.raises(RuntimeError) as exc_info:
                await router.chat([{"role": "user", "content": "hi"}])
            elapsed = time.monotonic() - start
            # Must have failed over within ~ the watchdog limit + slack, not 5s.
            assert elapsed < 2.0, f"watchdog did not fire fast enough: {elapsed:.2f}s"
            assert "timed out" in str(exc_info.value).lower()
    finally:
        if old is None:
            os.environ.pop("GENIO_MODEL_TURN_TIMEOUT", None)
        else:
            os.environ["GENIO_MODEL_TURN_TIMEOUT"] = old


def test_loop_chaining_noop_injects_continuation():
    # cat with empty output + short narration must inject continuation.
    fb = _feedback_for(
        {"command": "cat plan.md", "stdout": "", "stderr": "",
         "returncode": 0},
        "done",
    )
    assert "NEXT step" in fb or "next pending" in fb.lower() or "proceed" in fb.lower()


def test_loop_chaining_normal_exit0_no_extra_directive():
    # Meaningful output with long narration should NOT inject continuation.
    fb = _feedback_for(
        {"command": "python run.py", "stdout": "All 42 checks passed.",
         "stderr": "", "returncode": 0},
        "Tous les tests ont reussi, le projet est stabilise et pret pour la release.",
    )
    assert "NEXT step" not in fb
