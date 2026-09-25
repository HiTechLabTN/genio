"""Phase 3 regression tests — agent runtime hardening.

Two layers, both real (no faked PASS):
A. Pure unit tests on LoopGuard / fingerprint / quota synthesis / registry gate.
B. Scripted-turn harness: a subclass overriding ONLY the model call (_chat)
   with canned assistant strings, exercising the REAL run() loop — detection,
   budgets, clamping, registry gate — with REAL tool execution (echo/sleep via
   invoke) and REAL timeouts. Documented, deterministic, no network, no GPU.
"""
import asyncio
import sys
import threading

sys.path.insert(0, "/data/ai_tools/genio")

import pytest

import genio_server.core.agent_loop as AL
from genio_server.core.agent_loop import (
    AgentLoop,
    LoopGuard,
    command_fingerprint,
)


# ---------------- A. pure units ----------------

def test_fingerprint_stable_and_normalized():
    a = command_fingerprint("bash", "ls  -R\n /tmp")
    b = command_fingerprint("bash", "ls -R /tmp")
    assert a == b
    assert command_fingerprint("bash", "ls /tmp") != a
    assert command_fingerprint("bash", {"command": "x"}) == \
        command_fingerprint("bash", {"command": "x"})


def test_guard_allows_two_repeats():
    g = LoopGuard()
    assert g.note_call("fp1", "bash", False) is None
    assert g.note_call("fp1", "bash", False) is None
    assert g.repeats == 2


def test_guard_loop_detected_on_third_identical():
    g = LoopGuard()
    assert g.note_call("fp1", "bash", False) is None
    assert g.note_call("fp1", "bash", False) is None
    assert g.note_call("fp1", "bash", False) == "LOOP_DETECTED"


def test_guard_resets_on_new_command():
    g = LoopGuard()
    g.note_call("fp1", "bash", False)
    g.note_call("fp1", "bash", False)
    assert g.note_call("fp2", "bash", False) is None
    assert g.repeats == 1


def test_guard_would_loop_precheck():
    g = LoopGuard()
    assert g.would_loop("fp1") is False
    g.note_call("fp1", "bash", False)
    assert g.would_loop("fp1") is False
    g.note_call("fp1", "bash", False)
    assert g.would_loop("fp1") is True
    assert g.would_loop("other") is False


def test_guard_retry_budget():
    g = LoopGuard()
    assert g.note_call("a", "bash", True) is None
    assert g.note_call("b", "bash", True) is None
    assert g.note_call("c", "bash", True) == "RETRY_EXHAUSTED"


def test_tool_known_uses_registry():
    assert AgentLoop._tool_known("bash") is True
    assert AgentLoop._tool_known("teleport") is False
    assert AgentLoop._tool_known("") is False


def test_quota_synthesis_mentions_steps():
    traj = [{"command": "echo hi",
             "result": {"stdout": "hi", "returncode": 0}}]
    s = AgentLoop._quota_synthesis(traj)
    assert "echo hi" in s and "hi" in s


# ---------------- B. scripted-turn harness (real run()) ----------------

class ScriptedLoop(AgentLoop):
    """AgentLoop with scripted model turns (no Ollama)."""

    def __init__(self, script, **kw):
        kw.setdefault("session_id", None)
        super().__init__(**kw)
        self._script = list(script)
        self.tools_invoked = []

    async def _chat(self, client, messages):
        if not self._script:
            return "تمام، كملت.", 0, 0.0
        return self._script.pop(0), 0, 0.0


def run_loop(loop):
    async def _collect():
        return [ev async for ev in loop.run("do the thing please")]
    return asyncio.run(_collect())


def _real_invoke_spy(monkeypatch):
    """Wrap the real invoke to count calls (still executes for real)."""
    import genio_server.core.agent_loop as mod
    real = mod.invoke
    calls = []

    def spy(tool, payload, session_id=None):
        calls.append((tool, payload))
        return real(tool, payload, session_id)
    monkeypatch.setattr(mod, "invoke", spy)
    return calls


def test_infinite_loop_detected_after_two_identical(monkeypatch):
    calls = _real_invoke_spy(monkeypatch)
    script = ['{"tool": "bash", "command": "echo loop"}'] * 6
    events = run_loop(ScriptedLoop(script))
    kinds = [e.get("type") for e in events]
    assert "tool_call" in kinds and "tool_result" in kinds
    loop_errs = [e for e in events if e.get("type") == "error"
                 and "LOOP_DETECTED" in str(e.get("message", ""))]
    assert loop_errs, f"no LOOP_DETECTED in {kinds}"
    assert len(calls) == 2, f"tool must run exactly twice, ran {len(calls)}"
    answers = [e for e in events if e.get("type") == "answer"]
    assert answers and "توقّف" in answers[-1].get("text", "")


def test_unknown_tool_no_crash(monkeypatch):
    _real_invoke_spy(monkeypatch)
    script = ['{"tool": "teleport", "command": "mars"}',
              "تمام، فهمت."]
    events = run_loop(ScriptedLoop(script))
    kinds = [e.get("type") for e in events]
    assert "answer" in kinds
    rej = [e for e in events if e.get("type") == "error"
           and "unknown tool" in str(e.get("message", ""))]
    assert rej and "bash" in rej[0]["message"]


def test_iteration_cap_clean_fallback(monkeypatch):
    _real_invoke_spy(monkeypatch)
    script = [f'{{"tool": "bash", "command": "echo step{i}"}}' for i in range(9)]
    events = run_loop(ScriptedLoop(script, max_iterations=3))
    answers = [e for e in events if e.get("type") == "answer"]
    assert answers
    assert "تلخيص مرحلي" in answers[-1].get("text", "")


def test_output_clamped(monkeypatch):
    _real_invoke_spy(monkeypatch)
    script = ['{"tool": "bash", "command": "python3 -c \\"print(chr(88)*20000)\\""}',
              "تمام."]
    events = run_loop(ScriptedLoop(script))
    results = [e for e in events if e.get("type") == "tool_result"]
    assert results
    out = str(results[0]["result"].get("stdout", ""))
    assert len(out) <= AL.MAX_TOOL_OUTPUT + len(AL.TRUNCATE_MARKER)
    assert "truncated" in out.lower()


def test_tool_timeout(monkeypatch):
    _real_invoke_spy(monkeypatch)
    monkeypatch.setattr(AL, "TOOL_TIMEOUT_SECONDS", 2.0)
    script = ['{"tool": "bash", "command": "sleep 30"}', "تمام."]
    events = run_loop(ScriptedLoop(script))
    results = [e for e in events if e.get("type") == "tool_result"]
    assert results
    res = results[0]["result"]
    assert res.get("returncode") == 124 and "timeout" in str(res.get("error", ""))


def test_cancel_halts():
    ev = threading.Event()
    ev.set()
    loop = ScriptedLoop(['{"tool": "bash", "command": "echo x"}'],
                        cancel_event=ev)
    events = run_loop(loop)
    assert any(e.get("type") == "error" and "HALTED" in str(e.get("message", ""))
               for e in events)
    assert not any(e.get("type") == "answer" for e in events)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
