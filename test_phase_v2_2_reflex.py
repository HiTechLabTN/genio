"""Phase 2 v2.1 — System 1 Reflex Engine & Autonomous Skill Compilation.

Verifies:
1. A benchmark system audit query executes via the Fast-Path in under 100ms.
2. Zero Ollama tokens are generated (ModelRouter._chat is never reached).
3. Known fatal stderr (ModuleNotFoundError) maps to a deterministic pip install.
4. A >1 tool-turn trajectory compiles into a reusable skill persisted to
   state/skills_library/patterns.json, and a similar prompt matches it.

Run: pytest test_phase_v2_2_reflex.py -v
"""
import json
import threading
import time
from unittest import mock

import pytest

from genio_server.core.agent_loop import AgentLoop
from genio_server.core.reflex_engine import (
    ReflexEngine,
    _fastpath_enabled,
)


@pytest.fixture(autouse=True)
def _isolate_skills_dir(tmp_path, monkeypatch):
    """Point the ReflexEngine's persistence at a throwaway dir."""
    import genio_server.core.reflex_engine as re_mod
    monkeypatch.setattr(re_mod, "SKILLS_DIR", tmp_path / "skills")
    monkeypatch.setattr(re_mod, "PATTERNS_FILE", tmp_path / "skills" / "patterns.json")
    monkeypatch.setattr(re_mod, "_reflex_engine", None)
    yield
    monkeypatch.setattr(re_mod, "_reflex_engine", None)


@pytest.fixture
def engine():
    import genio_server.core.reflex_engine as re_mod
    return ReflexEngine(skills_dir=re_mod.SKILLS_DIR)


def test_fastpath_enabled():
    assert _fastpath_enabled() is True


def test_system_audit_fastpath_under_100ms(engine):
    start = time.monotonic()
    res = engine.match("check system health and resource usage")
    elapsed = (time.monotonic() - start) * 1000
    assert res is not None, "system health should match a fast-path handler"
    assert res["result"].get("reflex") is True
    assert res["result"].get("returncode") == 0
    assert elapsed < 100, f"fast-path too slow: {elapsed:.1f}ms (must be <100ms)"


@pytest.mark.asyncio
async def test_reflex_loop_never_calls_ollama():
    """A matching prompt short-circuits AgentLoop.run without any Ollama call."""
    async def explode(*args, **kwargs):
        raise AssertionError("LLM should never be called for a fast-path prompt")

    with mock.patch.object(AgentLoop, "_chat", explode):
        loop = AgentLoop(
            model="test-model", ollama_url="http://127.0.0.1:11434",
            cancel_event=threading.Event(),
        )
        events = []
        async for ev in loop.run("show me git status of the repo"):
            events.append(ev)
        kinds = [e["type"] for e in events]
        assert "tool_result" in kinds
        # No stats event => no Ollama tokens were generated.
        assert "stats" not in kinds
        assert any(e.get("type") == "answer" for e in events)


def test_auto_fix_module_not_found(engine):
    fix = engine.auto_fix("ModuleNotFoundError: No module named 'requests'")
    assert fix is not None
    assert "pip install requests" in fix


def test_compile_skill_and_match_similar_prompt(tmp_path, monkeypatch):
    import genio_server.core.reflex_engine as re_mod

    engine = ReflexEngine(skills_dir=tmp_path / "skills")
    trajectory = [
        {"command": "ls", "result": {"returncode": 0, "stdout": "/work"}},
        {"command": "python3 run_tests.py", "result": {"returncode": 0, "stdout": "OK"}},
    ]
    assert engine.compile_skill("run-tests", "run the project tests", trajectory) is True
    assert re_mod.PATTERNS_FILE.exists(), "skill must be persisted to patterns.json"
    data = json.loads(re_mod.PATTERNS_FILE.read_text())
    assert any("run" in str(s.get("name")) for s in data)
    assert len(data[0]["steps"]) == 2

    monkeypatch.setattr(re_mod, "_reflex_engine", engine)
    # A similar prompt must match the compiled skill via fast-path.
    match = engine.match("please run the project tests now")
    assert match is not None, "compiled skill should match a similar prompt"
    assert match.get("result", {}).get("skill") == "run-tests"