"""Safety-reliability gate — P0/P1 regression tests.

Deterministic, no network, no model, no GPU. Covers the P0 root cause
(relative-path recursive deletes executed silently in development mode)
and the P1 empty-answer / workspace-scoping fixes.

Fail-closed: any regression here blocks the gate.
"""
import json
import sys

sys.path.insert(0, "/data/ai_tools/genio")

from genio_server.core.registries import Decision, PolicyRegistry


def test_destructive_rm_escalates_in_development():
    # P0: `rm -rf *` relatif ne doit JAMAIS être ALLOW silencieux.
    # P0-bis (live 2026-10-09): `rm` NU Supprime aussi — tout rm/unlink
    # monte en confirmation, avec ou sans flags.
    for cmd in ("rm -rf *", "rm -rf .", "rm -fr ./build",
                "sudo rm -rf /tmp/x", "rm -rf /", "rm -rf /*",
                "rm CANARY.txt scratch.tmp", "rm file.txt",
                "rm -f old.log", "rm -i old.log", "unlink data.db",
                "rm -rf assets-pipeline/", "rm -rf ./build_cache"):
        d = PolicyRegistry.decide_tool("bash", False, "development",
                                       command=cmd)
        assert d == Decision.REQUIRE_CONFIRMATION, cmd


def test_destructive_patterns_escalate_in_development():
    for cmd in ("mkfs.ext4 /dev/sda1", "dd if=/dev/zero of=/dev/sda",
                "chmod -R 777 /", ":(){ :|:& };:",
                "bash -c \"rm -rf /\"", "cd / && rm -rf ."):
        d = PolicyRegistry.decide_tool("bash", False, "development",
                                       command=cmd)
        assert d == Decision.REQUIRE_CONFIRMATION, cmd


def test_benign_commands_stay_allow_in_development():
    for cmd in ("ls -la", "pwd && git status", "echo hello",
                "top -b -n1 | head -20",
                "cat README.md", "grep -rn firmware src | head",
                "mkdir -p build && touch build/out.txt", ""):
        d = PolicyRegistry.decide_tool("bash", False, "development",
                                       command=cmd)
        assert d == Decision.ALLOW, cmd


def test_backward_compat_no_command():
    # Anciens appelants sans `command` : comportement historique inchangé.
    assert PolicyRegistry.decide_tool("bash", False, "development") \
        == Decision.ALLOW
    assert PolicyRegistry.decide_tool("bash", False, "strict") \
        == Decision.DENY
    assert PolicyRegistry.decide_tool("nope", False, "strict") \
        == Decision.DENY


def test_strict_never_relaxes_on_content():
    # Le contenu ne peut qu'ESCALADER, jamais assouplir.
    assert PolicyRegistry.decide_tool("bash", False, "strict",
                                      command="ls") == Decision.DENY
    assert PolicyRegistry.decide_tool("bash", True, "strict",
                                      command="ls") == Decision.SANDBOX_ONLY


def test_escalation_never_relaxes_other_tools():
    # Outils non-bash : contenu ignoré, décision historique.
    assert PolicyRegistry.decide_tool("screen", False, "development",
                                      command="rm -rf /") == Decision.ALLOW


def test_looks_destructive_unit():
    from genio_server.core.registries import _looks_destructive
    assert _looks_destructive("rm -rf *")
    assert _looks_destructive("rm CANARY.txt")
    assert _looks_destructive("MKFS.ext4 /dev/sda1")
    assert not _looks_destructive("ls -la")
    assert not _looks_destructive("")
    assert not _looks_destructive("grep -rn firmware src")


def test_workspace_scoping_pwd(tmp_path, monkeypatch):
    # GENIO_WORKSPACE borne le cwd ; repli cwd serveur sinon.
    from genio_server.tools.bash_tool import run_command
    monkeypatch.setenv("GENIO_WORKSPACE", str(tmp_path))
    res = run_command("pwd")
    assert res["returncode"] == 0
    assert str(tmp_path) in str(res["stdout"]).strip()
    monkeypatch.delenv("GENIO_WORKSPACE", raising=False)
    res2 = run_command("pwd")
    assert res2["returncode"] == 0
    assert str(tmp_path) not in str(res2["stdout"]).strip()


def test_workspace_invalid_falls_back(monkeypatch):
    from genio_server.tools.bash_tool import run_command
    monkeypatch.setenv("GENIO_WORKSPACE", "/nonexistent-genio-ws-xyz")
    res = run_command("pwd")
    assert res["returncode"] == 0
    assert "nonexistent-genio-ws-xyz" not in str(res["stdout"])


def test_final_text_never_empty_nor_misleading():
    # P1-a closure: the end-of-run answer path can never yield an empty
    # (or whitespace-only) "success" — real answer, else synthesis, else
    # an explicit TN could-not-complete fallback.
    from genio_server.core.agent_loop import AgentLoop
    loop = AgentLoop()
    assert loop._final_text("  done  ", []) == "  done  "
    synth = loop._final_text("", [{"command": "ls",
                                   "result": {"returncode": 0,
                                              "stdout": "x"}}])
    assert synth.strip()
    assert "ls" in synth
    fallback = loop._final_text("", None)  # malformed trajectory
    assert fallback.strip()
    assert "ما نجمتش" in fallback
    for claim in ("نجاح", "تمت", "بنحاح"):
        assert claim not in fallback


def test_reflex_skill_with_destructive_step_refused_not_executed(tmp_path):
    # P0 2nd hole: fast-path skills bypass the policy gate (no human in
    # the loop) -> destructive steps must be REFUSED pre-exec, rc != 0.
    from genio_server.core.reflex_engine import get_reflex_engine
    engine = get_reflex_engine()
    skill = {"name": "poison-probe",
             "prompt_re": r"(?=.*\bzigzag\b)(?=.*\bquux\b)(?=.*\bploof\b).*",
             "params": [],
             "steps": [{"command": "echo before"},
                       {"command": "rm -rf ./build_cache"},
                       {"command": "echo after"}]}
    res = engine._exec_skill(skill, "zigzag quux ploof", 0.0)
    body = json.dumps(res.get("result", {}), ensure_ascii=False)
    assert "REFUSED" in body
    assert int(res["result"]["returncode"]) != 0
    assert "echo after" not in body  # fail-safe break: rien après le refus


def test_reflex_finalize_destructive_pattern_refused():
    from genio_server.core.reflex_engine import get_reflex_engine
    engine = get_reflex_engine()
    res = engine._finalize({"name": "probe"}, "rm -rf *", 0.0)
    assert int(res["result"]["returncode"]) == 126
    assert "REFUSED" in str(res["result"]["stdout"])


def test_compile_skill_refuses_destructive_trajectory():
    from genio_server.core.reflex_engine import get_reflex_engine
    engine = get_reflex_engine()
    traj = [{"command": "ls -F", "result": {"returncode": 0}},
            {"command": "rm -rf *", "result": {"returncode": 0}},
            {"command": "echo done", "result": {"returncode": 0}}]
    assert engine.compile_skill("poison-never", "zigzag quux ploof vittime",
                                traj) is False


def test_explicit_relative_rm_closed_at_both_layers():
    # Closure: `rm -rf <relatif>` no longer passes EITHER layer silently.
    # Tool layer refuses (SCOPED, approval-overridable); policy escalates.
    from genio_server.tools.bash_tool import is_dangerous, refusal_overridable
    reason = is_dangerous("rm -rf ./build_cache")
    assert reason is not None
    assert refusal_overridable(reason) is True
    d = PolicyRegistry.decide_tool("bash", False, "development",
                                   command="rm -rf ./build_cache")
    assert d == Decision.REQUIRE_CONFIRMATION
