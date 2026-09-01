"""Phase 7 — model routing + kill propagation.

Run: pytest test_phase7_routing_kill.py -v
"""
import asyncio
import threading
import pytest

from core.model_router import ModelRouter


@pytest.mark.asyncio
async def test_router_cancel_before_start():
    router = ModelRouter()
    # make endpoints empty to avoid network, but kill should abort before trying
    router.endpoints = router.endpoints[:1]  # at least one
    ev = threading.Event()
    ev.set()  # already killed
    with pytest.raises(asyncio.CancelledError):
        await router.generate("hello", cancel_event=ev)


@pytest.mark.asyncio
async def test_router_cancel_propagates_midway(monkeypatch):
    router = ModelRouter()
    # mock _call_endpoint to sleep then return, but event set during call
    async def fake_call(ep, prompt, temp, tokens, images=None, cancel_event=None):
        await asyncio.sleep(0.05)
        if cancel_event and cancel_event.is_set():
            raise asyncio.CancelledError("killed")
        return "ok"

    monkeypatch.setattr(router, "_call_endpoint", fake_call)
    ev = threading.Event()

    async def setter():
        await asyncio.sleep(0.02)
        ev.set()

    asyncio.create_task(setter())
    with pytest.raises(asyncio.CancelledError):
        await router.generate("long prompt", cancel_event=ev)


def test_agent_loop_cancelled_check():
    import asyncio as aio
    from genio_server.core.agent_loop import AgentLoop

    ev = threading.Event()
    ev.set()
    loop = AgentLoop(cancel_event=ev)
    assert loop.cancelled() is True

    ev2 = threading.Event()
    loop2 = AgentLoop(cancel_event=ev2)
    assert loop2.cancelled() is False


@pytest.mark.asyncio
async def test_agent_chat_aborts_when_killed():
    from genio_server.core.agent_loop import AgentLoop
    import httpx

    ev = threading.Event()
    ev.set()
    loop = AgentLoop(cancel_event=ev)
    async with httpx.AsyncClient() as client:
        with pytest.raises(asyncio.CancelledError):
            await loop._chat(client, [{"role": "user", "content": "hi"}])
