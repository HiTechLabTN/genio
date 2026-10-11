"""Closure gate — tool-layer enforcement boundary matrix.

Lowest shared enforcement point: run_command/async_run_command
(via tools.invoke). Every test uses disposable dirs + real fixtures and
asserts ZERO destructive effect on denial (fixtures intact on disk).

Conventions under test:
- HARD refusals (roots, system, devices, privesc, fork, mkfs): never
  overridable, even approved.
- SCOPED refusals ("scoped: ..." + historic workspace messages):
  executable ONLY with a fresh single-use approval bound to the exact
  command (policy-engine consume). Replay / altered command / expired /
  denied / concurrent-second all fail closed.
"""
import asyncio
import os
import sys
import threading
import time

import pytest

sys.path.insert(0, "/data/ai_tools/genio")

from core.policy_engine import PolicyEngine
from genio_server.tools import invoke
from genio_server.tools.bash_tool import (
    async_run_command,
    is_dangerous,
    refusal_overridable,
    run_command,
    verify_approval,
)


def _tree(base, files=("keep.txt", "sub/drop.txt")):
    for f in files:
        p = base / f
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("fixture")
    return base


def _approve(cmd, timeout_s=30.0):
    # Production wiring: agent_loop AND run_command share the singleton
    # (get_policy_engine). Tests use it too so approval actually flows.
    from core.policy_engine import get_policy_engine
    eng = get_policy_engine()
    pend = eng.request_confirmation("bash", cmd, timeout_s=timeout_s)
    assert eng.resolve(pend.nonce, True) is True
    return eng, {"nonce": pend.nonce, "command": cmd}


def _fresh_nonce(cmd, timeout_s=30.0):
    from core.policy_engine import get_policy_engine
    eng = get_policy_engine()
    return eng, eng.request_confirmation("bash", cmd, timeout_s=timeout_s)


# ------------------------------------------------------------------ #
# 1. Workspace scoping at the exec boundary
# ------------------------------------------------------------------ #

def test_relative_recursive_refused_in_default_cwd(tmp_path, monkeypatch):
    _tree(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GENIO_WORKSPACE", raising=False)
    res = run_command("rm -rf sub")
    assert res["returncode"] == 126
    assert "scoped:" in res["stderr"]
    assert (tmp_path / "sub" / "drop.txt").read_text() == "fixture"
    assert (tmp_path / "keep.txt").read_text() == "fixture"


def test_relative_glob_refused_in_default_cwd(tmp_path, monkeypatch):
    _tree(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GENIO_WORKSPACE", raising=False)
    res = run_command("rm -rf *")
    assert res["returncode"] == 126
    assert (tmp_path / "keep.txt").exists()


def test_absolute_inside_explicit_workspace_executes(tmp_path, monkeypatch):
    _tree(tmp_path)
    monkeypatch.setenv("GENIO_WORKSPACE", str(tmp_path))
    res = run_command(f"rm -rf {tmp_path}/sub")
    assert res["returncode"] == 0, res
    assert not (tmp_path / "sub").exists()
    assert (tmp_path / "keep.txt").read_text() == "fixture"


def test_relative_inside_explicit_workspace_executes(tmp_path, monkeypatch):
    _tree(tmp_path)
    monkeypatch.setenv("GENIO_WORKSPACE", str(tmp_path))
    res = run_command("rm -rf sub")
    assert res["returncode"] == 0, res
    assert not (tmp_path / "sub").exists()
    assert (tmp_path / "keep.txt").exists()


def test_absolute_outside_workspace_refused(tmp_path, monkeypatch):
    inside = tmp_path / "ws"
    outside = tmp_path / "outside"
    _tree(inside)
    _tree(outside)
    monkeypatch.setenv("GENIO_WORKSPACE", str(inside))
    res = run_command(f"rm -rf {outside}/sub")
    assert res["returncode"] == 126
    assert (outside / "sub" / "drop.txt").read_text() == "fixture"


def test_multi_target_first_escape_fails_closed(tmp_path, monkeypatch):
    _tree(tmp_path)
    monkeypatch.setenv("GENIO_WORKSPACE", str(tmp_path))
    res = run_command(f"rm -rf {tmp_path}/sub /etc/hostname")
    assert res["returncode"] == 126
    # NOTHING executed: even the in-workspace target survives.
    assert (tmp_path / "sub" / "drop.txt").exists()


def test_parent_traversal_refused(tmp_path, monkeypatch):
    ws = tmp_path / "ws"
    _tree(ws)
    (tmp_path / "sibling.txt").write_text("fixture")
    monkeypatch.setenv("GENIO_WORKSPACE", str(ws))
    res = run_command("rm -rf ../sibling.txt")
    assert res["returncode"] == 126
    assert (tmp_path / "sibling.txt").read_text() == "fixture"


def test_symlink_escape_refused(tmp_path, monkeypatch):
    ws = tmp_path / "ws"
    ws.mkdir()
    real = tmp_path / "real"
    real.mkdir()
    (real / "precious.txt").write_text("fixture")
    os.symlink(str(real), str(ws / "link"))
    monkeypatch.setenv("GENIO_WORKSPACE", str(ws))
    res = run_command("rm -rf link/")
    assert res["returncode"] == 126
    assert (real / "precious.txt").read_text() == "fixture"


def test_missing_workspace_fails_closed_for_destructive(tmp_path, monkeypatch):
    _tree(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GENIO_WORKSPACE", "/nonexistent-genio-ws-xyz")
    res = run_command("rm -rf sub")
    assert res["returncode"] == 126
    assert "GENIO_WORKSPACE" in res["stderr"]
    assert (tmp_path / "sub" / "drop.txt").exists()
    # Non-destructive still works (no silent broadening, no total outage).
    ok = run_command("ls")
    assert ok["returncode"] == 0


def test_bare_single_file_rm_allowed_at_tool_layer(tmp_path, monkeypatch):
    # Documented semantics: single explicit-file rm is ordinary work at
    # the tool layer (the interactive policy gate still escalates it).
    _tree(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GENIO_WORKSPACE", raising=False)
    res = run_command("rm keep.txt")
    assert res["returncode"] == 0, res
    assert not (tmp_path / "keep.txt").exists()
    assert (tmp_path / "sub" / "drop.txt").exists()


def test_hard_root_never_overridable_even_approved(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GENIO_WORKSPACE", raising=False)
    from core.policy_engine import get_policy_engine
    eng = get_policy_engine()
    pend = eng.request_confirmation("bash", "rm -rf /", timeout_s=30.0)
    assert eng.resolve(pend.nonce, True) is True
    res = run_command("rm -rf /", approval={"nonce": pend.nonce,
                                            "command": "rm -rf /"})
    assert res["returncode"] == 126
    assert "destructive rm target" in res["stderr"]


def test_mv_devnull_and_shred_and_dd_scoped(tmp_path, monkeypatch):
    _tree(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GENIO_WORKSPACE", raising=False)
    for cmd in ("mv keep.txt /dev/null",
                "shred -u keep.txt",
                "dd if=/dev/zero of=keep.txt bs=1 count=1"):
        res = run_command(cmd)
        assert res["returncode"] == 126, cmd
        assert "scoped:" in res["stderr"], cmd
    assert (tmp_path / "keep.txt").read_text() == "fixture"


# ------------------------------------------------------------------ #
# 2. Approval binding: fresh, single-use, exact-command
# ------------------------------------------------------------------ #

def test_approved_scoped_command_executes_narrowly(tmp_path, monkeypatch):
    _tree(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GENIO_WORKSPACE", raising=False)
    eng, approval = _approve("rm -rf sub")
    res = run_command("rm -rf sub", approval=approval)
    assert res["returncode"] == 0, res
    assert not (tmp_path / "sub").exists()
    assert (tmp_path / "keep.txt").exists()
    assert eng.pending_count() == 0  # consumed


def test_changed_targets_after_approval_fail_closed(tmp_path, monkeypatch):
    _tree(tmp_path, files=("a.txt", "b.txt"))
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GENIO_WORKSPACE", raising=False)
    from core.policy_engine import get_policy_engine
    eng = get_policy_engine()
    pend = eng.request_confirmation("bash", "rm -rf a.txt", timeout_s=30.0)
    assert eng.resolve(pend.nonce, True) is True
    res = run_command("rm -rf b.txt",
                      approval={"nonce": pend.nonce, "command": "rm -rf b.txt"})
    assert res["returncode"] == 126
    assert (tmp_path / "a.txt").exists() and (tmp_path / "b.txt").exists()


def test_denied_approval_executes_nothing(tmp_path, monkeypatch):
    _tree(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GENIO_WORKSPACE", raising=False)
    from core.policy_engine import get_policy_engine
    eng = get_policy_engine()
    pend = eng.request_confirmation("bash", "rm -rf sub", timeout_s=30.0)
    assert eng.resolve(pend.nonce, False) is True
    res = run_command("rm -rf sub",
                      approval={"nonce": pend.nonce, "command": "rm -rf sub"})
    assert res["returncode"] == 126
    assert (tmp_path / "sub" / "drop.txt").exists()


def test_expired_approval_cannot_authorize(tmp_path, monkeypatch):
    _tree(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GENIO_WORKSPACE", raising=False)
    from core.policy_engine import get_policy_engine
    eng = get_policy_engine()
    pend = eng.request_confirmation("bash", "rm -rf sub", timeout_s=0.05)
    time.sleep(0.15)
    assert eng.resolve(pend.nonce, True) is False  # stale decide rejected
    res = run_command("rm -rf sub",
                      approval={"nonce": pend.nonce, "command": "rm -rf sub"})
    assert res["returncode"] == 126
    assert (tmp_path / "sub" / "drop.txt").exists()


def test_replayed_approval_fails(tmp_path, monkeypatch):
    _tree(tmp_path, files=("a.txt", "b.txt"))
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GENIO_WORKSPACE", raising=False)
    from core.policy_engine import get_policy_engine
    eng = get_policy_engine()
    pend = eng.request_confirmation("bash", "rm -rf a.txt", timeout_s=30.0)
    assert eng.resolve(pend.nonce, True) is True
    assert eng.resolve(pend.nonce, True) is False  # second decide rejected
    first = run_command("rm -rf a.txt",
                        approval={"nonce": pend.nonce,
                                  "command": "rm -rf a.txt"})
    assert first["returncode"] == 0
    replay = run_command("rm -rf b.txt",
                         approval={"nonce": pend.nonce,
                                   "command": "rm -rf b.txt"})
    assert replay["returncode"] == 126  # nonce consumed; also wrong command
    assert (tmp_path / "b.txt").exists()


def test_concurrent_resolve_single_winner():
    eng = PolicyEngine()
    pend = eng.request_confirmation("bash", "rm -rf sub", timeout_s=30.0)
    wins = []

    def go():
        if eng.resolve(pend.nonce, True):
            wins.append(1)

    threads = [threading.Thread(target=go) for _ in range(10)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(wins) == 1


def test_concurrent_consume_single_winner():
    eng = PolicyEngine()
    pend = eng.request_confirmation("bash", "rm -rf sub", timeout_s=30.0)
    assert eng.resolve(pend.nonce, True) is True
    wins = []

    def go():
        # verify_approval uses the singleton; emulate consume directly.
        if eng.consume(pend.nonce, "rm -rf sub"):
            wins.append(1)

    threads = [threading.Thread(target=go) for _ in range(10)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(wins) == 1


def test_release_abandons_without_decision():
    eng = PolicyEngine()
    pend = eng.request_confirmation("bash", "rm -rf sub", timeout_s=30.0)
    assert eng.release(pend.nonce) is True
    assert eng.await_decision(pend.nonce, timeout_s=0.1) is False
    assert eng.consume(pend.nonce, "rm -rf sub") is False


def test_verify_approval_rejects_garbage():
    assert verify_approval(None, "rm -rf sub") is False
    assert verify_approval({}, "rm -rf sub") is False
    assert verify_approval({"nonce": "x"}, "rm -rf sub") is False
    assert verify_approval({"nonce": "0" * 32, "command": "rm -rf sub"},
                           "rm -rf sub") is False


# ------------------------------------------------------------------ #
# 3. Dispatch + async parity
# ------------------------------------------------------------------ #

def test_invoke_threads_approval(tmp_path, monkeypatch):
    _tree(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GENIO_WORKSPACE", raising=False)
    denied = invoke("bash", "rm -rf sub")
    assert denied["returncode"] == 126
    eng, approval = _approve("rm -rf sub")
    done = invoke("bash", "rm -rf sub", approval=approval)
    assert done["returncode"] == 0, done
    assert not (tmp_path / "sub").exists()


def test_async_parity(tmp_path, monkeypatch):
    _tree(tmp_path, files=("a.txt", "b.txt"))
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GENIO_WORKSPACE", raising=False)

    async def go():
        denied = await async_run_command("rm -rf a.txt")
        assert denied["returncode"] == 126
        eng, approval = _approve("rm -rf a.txt")
        done = await async_run_command("rm -rf a.txt", approval=approval)
        assert done["returncode"] == 0, done

    asyncio.run(go())
    assert not (tmp_path / "a.txt").exists()
    assert (tmp_path / "b.txt").exists()


def test_container_fallback_is_checked(tmp_path, monkeypatch):
    # Closure audit: exec_in_container fallbacks used to run raw
    # subprocess, bypassing every content check. Now they route through
    # the checked run_command (no docker here -> fallback path).
    import genio_server.tools.session_container as sc
    from genio_server.tools.session_container import exec_in_container
    _tree(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GENIO_WORKSPACE", raising=False)
    monkeypatch.setenv("GENIO_SANDBOX_MODE", "container")
    monkeypatch.delenv("GENIO_SECURITY_MODE", raising=False)
    monkeypatch.setattr(sc, "_docker_available", lambda: False)
    res = exec_in_container("closure-probe", "rm -rf sub")
    assert res["returncode"] == 126, res
    assert "refused" in str(res.get("stderr", ""))
    assert (tmp_path / "sub" / "drop.txt").exists()
    ok = exec_in_container("closure-probe", "echo fb-ok")
    assert ok["returncode"] == 0, ok
    assert ok.get("sandbox_fallback") is True
    assert "fb-ok" in str(ok.get("stdout", ""))


def test_container_fallback_honors_approval(tmp_path, monkeypatch):
    import genio_server.tools.session_container as sc
    from genio_server.tools.session_container import exec_in_container
    _tree(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GENIO_WORKSPACE", raising=False)
    monkeypatch.setenv("GENIO_SANDBOX_MODE", "container")
    monkeypatch.delenv("GENIO_SECURITY_MODE", raising=False)
    monkeypatch.setattr(sc, "_docker_available", lambda: False)
    eng, approval = _approve("rm -rf sub")
    res = exec_in_container("closure-probe", "rm -rf sub", approval=approval)
    assert res["returncode"] == 0, res
    assert not (tmp_path / "sub").exists()
    assert (tmp_path / "keep.txt").exists()


def test_descriptor_confirmation_honored_in_development():
    # Closure audit: requires_confirmation=True was decorative —
    # computer (GUI typing bypasses every shell check) and tool_forge
    # were silently ALLOW in development. Now they gate.
    from genio_server.core.registries import Decision, PolicyRegistry
    assert PolicyRegistry.decide_tool("computer", False, "development") \
        == Decision.REQUIRE_CONFIRMATION
    assert PolicyRegistry.decide_tool("tool_forge", False, "development") \
        == Decision.REQUIRE_CONFIRMATION
    # Unaffected: benign bash still ALLOW, screen read-only ALLOW.
    assert PolicyRegistry.decide_tool("bash", False, "development",
                                      command="ls -la") == Decision.ALLOW
    assert PolicyRegistry.decide_tool("screen", False, "development") \
        == Decision.ALLOW


def test_refusal_classes_pinned():
    # HARD — never overridable.
    for cmd in ("rm -rf /", "rm -rf /*", "sudo rm -rf /",
                "mkfs.ext4 /dev/sda", "dd of=/dev/sda",
                ":(){ :|:& };:", "chmod -R 777 /"):
        reason = is_dangerous(cmd)
        assert reason is not None, cmd
        assert refusal_overridable(reason) is False, (cmd, reason)
    # SCOPED — operator-decidable with exact command.
    for reason in ("scoped: recursive/force rm under server cwd /x",
                   "rm target '/tmp/x' is outside the allowed working directory",
                   "rm target '~' expands outside the allowed working directory",
                   "rm target '.' is ambiguous at filesystem root",
                   "structured block: destructive rm target: *"):
        assert refusal_overridable(reason) is True, reason
