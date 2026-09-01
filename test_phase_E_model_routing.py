"""Phase E — ModelRouter branché dans AgentLoop + vraie race cancel.

Run: pytest test_phase_E_model_routing.py -v
Q4: endpoints valid as-is, must exercise AgentLoop._chat directly
"""
import asyncio
import threading
import time
from unittest import mock

import pytest

from genio_server.core.agent_loop import AgentLoop


@pytest.mark.asyncio
async def test_chat_cancel_race_closes_request():
    # Track whether mock was cancelled
    cancelled_flag = {"was_cancelled": False}
    async def mock_call_chat(self, ep, messages, cancel_event=None):
        try:
            await asyncio.sleep(2)  # simulate long generation
            return "should not reach", 0, 0.0
        except asyncio.CancelledError:
            cancelled_flag["was_cancelled"] = True
            raise

    # Patch ModelRouter to use our mock
    with mock.patch("core.model_router.ModelRouter._call_chat_endpoint", mock_call_chat):
        # Also need to ensure health doesn't fail
        cancel_event = threading.Event()
        loop = AgentLoop(cancel_event=cancel_event, model="test-model", ollama_url="http://127.0.0.1:11434")
        # Prepare mock client (not used when router is used, but _chat signature requires it)
        import httpx
        async with httpx.AsyncClient() as client:
            # Start _chat and cancel after 200ms
            start = time.monotonic()
            async def trigger_cancel():
                await asyncio.sleep(0.2)
                cancel_event.set()
            cancel_task = asyncio.create_task(trigger_cancel())
            with pytest.raises(asyncio.CancelledError):
                await loop._chat(client, [{"role": "user", "content": "hello"}])
            elapsed = time.monotonic() - start
            cancel_task.cancel()
            try:
                await cancel_task
            except asyncio.CancelledError:
                pass
            # Must be fast (tens of ms after cancel, not 2s)
            assert elapsed < 1.0, f"cancel took too long: {elapsed:.2f}s (should be <1s, not 2s)"
            assert cancelled_flag["was_cancelled"] is True, "underlying request was not cancelled, just ignored"

@pytest.mark.asyncio
async def test_chat_without_cancel_succeeds():
    async def mock_call_chat(self, ep, messages, cancel_event=None):
        return "hello world", 10, 5.0
    with mock.patch("core.model_router.ModelRouter._call_chat_endpoint", mock_call_chat):
        loop = AgentLoop(model="test", ollama_url="http://127.0.0.1:11434")
        import httpx
        async with httpx.AsyncClient() as client:
            content, count, tps = await loop._chat(client, [{"role": "user", "content": "hi"}])
            assert content == "hello world"
            assert count == 10

def test_status_exposes_router():
    # Verify /api/v1/status includes router
    import asyncio
    from genio_server.server.main import _telemetry_snapshot_async
    async def run():
        snap = await _telemetry_snapshot_async()
        assert "router" in snap
        assert isinstance(snap["router"], dict)
    asyncio.run(run())
