"""Phase A — Reflex Engine bypass must be closed (audit round 3).

Reproduces literally the proof from the audit:
  engine.compile_skill('auto-test3', 'please clean my build cache now', [
      {'command': 'echo setup'},
      {'command': 'rm -rf /tmp/genio_workdir_victim'},
  ])
  is_dangerous('rm -rf /tmp/genio_workdir_victim') -> blocked
  engine.match('please tell me a joke about robots') -> must NOT delete canary

Also verifies kill-switch bypass closure and that legitimate patterns remain fast.
Run: pytest test_phase_A_reflex_bypass.py -v
"""
import threading
import time
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from genio_server.core.reflex_engine import ReflexEngine, _fastpath_enabled, get_reflex_engine
from genio_server.tools.bash_tool import is_dangerous


@pytest.fixture(autouse=True)
def _isolate_skills_dir(tmp_path, monkeypatch):
    import genio_server.core.reflex_engine as re_mod
    monkeypatch.setattr(re_mod, "SKILLS_DIR", tmp_path / "skills")
    monkeypatch.setattr(re_mod, "PATTERNS_FILE", tmp_path / "skills" / "patterns.json")
    monkeypatch.setattr(re_mod, "_reflex_engine", None)
    # Ensure strict matching is enabled for this test
    monkeypatch.setenv("GENIO_REFLEX_STRICT_MATCH", "1")
    monkeypatch.setenv("GENIO_REFLEX_FASTPATH", "1")
    yield
    monkeypatch.setattr(re_mod, "_reflex_engine", None)


@pytest.fixture
def engine():
    import genio_server.core.reflex_engine as re_mod
    return ReflexEngine(skills_dir=re_mod.SKILLS_DIR)


def test_audit_proof_canary_survives_unrelated_prompt(tmp_path, monkeypatch, engine):
    """Literal audit proof: canary must survive after unrelated prompt with same first word."""
    # Create a real canary file that the skill would try to delete
    canary = tmp_path / "genio_workdir_victim"
    canary.write_text("canary")
    victim_path = str(canary)
    # Also create the exact path the audit used, to test is_dangerous directly
    # The skill uses rm -rf /tmp/genio_workdir_victim — that path should be blocked
    assert is_dangerous("rm -rf /tmp/genio_workdir_victim") is not None, \
        "is_dangerous must block rm -rf /tmp/genio_workdir_victim"
    assert is_dangerous(f"rm -rf {victim_path}") is not None, \
        "is_dangerous must block rm -rf on any /tmp victim outside /work"

    # Compile skill exactly as audit does, but with the tmp_path victim to verify filesystem effect
    engine.compile_skill('auto-test3', 'please clean my build cache now', [
        {'command': 'echo setup'},
        {'command': f'rm -rf {victim_path}'},
    ])

    # Sanity: compiled skill should be persisted
    import genio_server.core.reflex_engine as re_mod
    assert re_mod.PATTERNS_FILE.exists()

    # Unrelated prompt sharing only the first word "please" — MUST NOT delete canary
    # With strict regex (Q2), this prompt lacks "clean"/"build"/"cache" so it won't match at all.
    # With fail-safe routing, even if it did match, is_dangerous would refuse the rm.
    # Either way, the canary must survive — we verify the real filesystem effect.
    result = engine.match('please tell me a joke about robots')
    # Strict match: result should be None (no false positive)
    # If result is not None, it must be a refused result, not a successful deletion
    if result is not None:
        # If somehow matched, the rm must have been refused (returncode 126 or non-zero)
        rc = result.get("result", {}).get("returncode")
        assert rc != 0, "matched skill with dangerous rm must be refused, not executed as success"
        assert "refused" in str(result.get("result", {}).get("stderr", "")).lower() or \
               "outside the allowed" in str(result.get("result", {}).get("stderr", "")).lower() or \
               rc == 126, "refusal must be visible in result"

    assert canary.exists(), "CANARY SURVIVED CHECK FAILED — file was deleted via reflex bypass!"
    assert canary.read_text() == "canary"


def test_audit_proof_related_prompt_also_blocked(tmp_path, engine):
    """Related prompt that DOES contain all keywords must still be blocked by is_dangerous."""
    canary = tmp_path / "victim2"
    canary.write_text("keep")
    victim = str(canary)

    engine.compile_skill('auto-test3b', 'please clean my build cache now', [
        {'command': 'echo setup'},
        {'command': f'rm -rf {victim}'},
    ])

    # Related prompt containing all strict keywords -> will match, but rm must be refused
    result = engine.match('please clean my build cache again')
    assert result is not None, "related prompt should match the skill"
    rc = result.get("result", {}).get("returncode")
    assert rc != 0, "dangerous rm via matched skill must be refused"
    assert canary.exists(), "canary must survive even when prompt legitimately matches"
    assert canary.read_text() == "keep"


def test_kill_switch_blocks_reflex(monkeypatch, engine):
    """Armed kill-switch must prevent ANY reflex execution (mock invoke)."""
    import genio_server.core.agent_loop as loop_mod
    from genio_server.core.agent_loop import AgentLoop

    # Ensure a skill exists that would otherwise match
    engine.compile_skill('kill-test', 'please clean my build cache now', [
        {'command': 'echo setup'},
        {'command': 'echo safe'},
    ])
    # Persist to singleton so AgentLoop sees it
    import genio_server.core.reflex_engine as re_mod
    monkeypatch.setattr(re_mod, "_reflex_engine", engine)

    # Arm kill-switch
    ev = threading.Event()
    ev.set()

    loop = AgentLoop(
        model="test-model", ollama_url="http://127.0.0.1:11434",
        cancel_event=ev, session_id=None,
    )

    # Spy on invoke — must NOT be called when cancelled
    with mock.patch("genio_server.tools.invoke") as mock_invoke:
        # Also patch _invoke_bash inside reflex to ensure no direct subprocess either
        with mock.patch("genio_server.core.reflex_engine._invoke_bash") as mock_reflex_invoke:
            import asyncio
            async def _run():
                events = []
                async for ev in loop.run("please clean my build cache now"):
                    events.append(ev)
                return events

            events = asyncio.run(_run())
            # Must have been halted, with no tool execution
            assert any(e.get("type") == "error" and "HALTED" in str(e.get("message", "")) for e in events), \
                "killed loop must emit HALTED error, not run reflex"
            mock_invoke.assert_not_called()
            mock_reflex_invoke.assert_not_called()


def test_legitimate_pattern_still_fast(engine):
    """Legitimate reflex pattern must still respond quickly via invoke path."""
    start = time.monotonic()
    res = engine.match("check system health and resource usage")
    elapsed = (time.monotonic() - start) * 1000
    assert res is not None, "system health should still match"
    assert res["result"].get("reflex") is True
    assert res["result"].get("returncode") == 0
    # Should remain well under LLM round-trip (strict <100ms, allow 500ms for invoke overhead in CI)
    assert elapsed < 500, f"legitimate pattern too slow: {elapsed:.1f}ms"
