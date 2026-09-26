"""Phase 26 tests — gouvernance des ressources.

Plafonds configurables, interruption propre au dépassement (sans
déstabiliser), parallélisme borné à 1, lecture hôte réelle.
"""
import sys
import time

sys.path.insert(0, "/data/ai_tools/genio")

from genio_server.core.budgets import BudgetConfig, BudgetTracker


def _cfg(**kw):
    base = dict(max_iterations=5, max_tool_calls=10, max_tokens=8000,
                max_runtime_s=600.0)
    base.update(kw)
    return BudgetConfig(**base)


def test_defaults_sane():
    c = BudgetConfig()
    assert (c.max_iterations, c.max_tool_calls, c.max_tokens,
            c.max_parallel_tools) == (5, 10, 8000, 1)


def test_tool_calls_quota():
    t = BudgetTracker(config=_cfg(max_tool_calls=2))
    t.note_tool_call()
    t.note_tool_call()
    assert t.ok()
    t.note_tool_call()
    assert not t.ok()
    assert any("tool_calls" in v for v in t.violations())


def test_tokens_quota():
    t = BudgetTracker(config=_cfg(max_tokens=100))
    t.note_tokens(60)
    assert t.ok()
    t.note_tokens(50)
    assert not t.ok()


def test_runtime_quota():
    t = BudgetTracker(config=_cfg(max_runtime_s=0.05))
    time.sleep(0.08)
    assert not t.ok()
    assert any("runtime" in v for v in t.violations())


def test_iterations_quota():
    t = BudgetTracker(config=_cfg(max_iterations=2))
    t.note_iteration()
    t.note_iteration()
    assert t.ok()
    t.note_iteration()
    assert not t.ok()


def test_parallel_is_one_by_design():
    assert BudgetConfig().max_parallel_tools == 1


def test_host_usage_real_shape():
    u = BudgetTracker().host_usage()
    assert set(u) >= {"memory_mb", "memory_pct", "cpu_pct"}
    assert u["memory_mb"] > 0 and 0 <= u["memory_pct"] <= 100


def test_env_override(monkeypatch):
    monkeypatch.setenv("GENIO_MAX_TOOL_CALLS", "3")
    assert BudgetConfig.from_env().max_tool_calls == 3


def test_loop_stops_cleanly_on_tool_quota(monkeypatch):
    import asyncio
    import genio_server.core.agent_loop as mod
    from genio_server.core.agent_loop import AgentLoop
    monkeypatch.setenv("GENIO_MAX_TOOL_CALLS", "1")

    async def fake_chat(client, messages):
        return '{"tool": "bash", "command": "echo hi"}', 0, 0.0

    async def _collect():
        loop = AgentLoop(session_id=None)
        loop._chat = fake_chat
        return [ev async for ev in loop.run("do the thing please")]

    events = asyncio.run(_collect())
    answers = [e for e in events if e.get("type") == "answer"]
    assert answers and "quota" in answers[-1].get("text", "")


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
