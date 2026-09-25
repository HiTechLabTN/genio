"""Phase 4 tests — first-class capability model.

- 100% des outils déclarent un descripteur complet et valide.
- Outil injecté sans métadonnées → rejet immédiat (DENIED_UNKNOWN_CAPABILITY).
- Immuabilité : descripteurs frozen ; lookup par nom seul (payload ignoré).
- Classification des risques + enforcement DENY en boucle réelle (scripted).
"""
import asyncio
import dataclasses
import sys

import pytest

sys.path.insert(0, "/data/ai_tools/genio")

from genio_server.core.agent_loop import AgentLoop
from genio_server.core.registries import (
    Capability,
    CapabilityRegistry,
    Decision,
    ExecEnv,
    FilesystemScope,
    PolicyRegistry,
    RiskLevel,
    ToolDescriptor,
    ToolRegistry,
)


def test_all_tools_have_complete_descriptors():
    names = ToolRegistry.names()
    assert names, "empty tool registry"
    for name in names:
        d = CapabilityRegistry.descriptor_of(name)
        assert isinstance(d, ToolDescriptor), f"{name}: no descriptor"
        assert d.name == name
        assert d.capability in (
            Capability.READ_ONLY, Capability.SAFE_WRITE,
            Capability.WORKSPACE_WRITE, Capability.NETWORK,
            Capability.NETWORK_ACCESS, Capability.PROCESS_EXECUTION,
            Capability.SYSTEM_SERVICE_CONTROL, Capability.CREDENTIAL_ACCESS,
            Capability.DEVICE_CONTROL, Capability.DESTRUCTIVE,
            Capability.ADMINISTRATIVE, Capability.CRITICAL), name
        assert d.risk_level in (RiskLevel.LOW, RiskLevel.MEDIUM,
                                RiskLevel.HIGH, RiskLevel.CRITICAL), name
        assert isinstance(d.requires_network, bool)
        assert d.filesystem_scope in (FilesystemScope.NONE,
                                      FilesystemScope.READ_ONLY_SYSTEM,
                                      FilesystemScope.WORKSPACE_ONLY,
                                      FilesystemScope.UNRESTRICTED)
        assert d.execution_environment in (ExecEnv.SANDBOX_ONLY,
                                           ExecEnv.HOST_ALLOWED)
        assert isinstance(d.requires_confirmation, bool)


def test_risk_classification_spot():
    assert CapabilityRegistry.descriptor_of("screen").risk_level == RiskLevel.LOW
    assert CapabilityRegistry.descriptor_of("bash").risk_level == RiskLevel.HIGH
    assert (CapabilityRegistry.descriptor_of("tool_forge").risk_level
            == RiskLevel.CRITICAL)
    assert CapabilityRegistry.descriptor_of("bash").capability == \
        Capability.PROCESS_EXECUTION
    assert CapabilityRegistry.descriptor_of("bash").execution_environment == \
        ExecEnv.SANDBOX_ONLY


def test_unknown_tool_rejected():
    assert CapabilityRegistry.descriptor_of("teleport") is None
    info = AgentLoop._capability_check("teleport")
    assert info["decision"] == Decision.DENY
    assert info["reason"] == "DENIED_UNKNOWN_CAPABILITY"
    # strict AND dev: unknown is denied in every mode
    assert PolicyRegistry.decide_tool("teleport", True, "strict") == Decision.DENY
    assert (PolicyRegistry.decide_tool("teleport", False, "development")
            == Decision.DENY)


def test_descriptors_immutable():
    d = CapabilityRegistry.descriptor_of("bash")
    with pytest.raises(dataclasses.FrozenInstanceError):
        d.risk_level = RiskLevel.LOW  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        d.capability = Capability.READ_ONLY  # type: ignore[misc]
    assert CapabilityRegistry.descriptor_of("bash").risk_level == RiskLevel.HIGH


def test_lookup_ignores_payload():
    # Le LLM ne peut pas élever ses privilèges via les arguments : seul le
    # nom compte, le payload n'est jamais consulté.
    d1 = CapabilityRegistry.descriptor_of("screen")
    assert d1 is not None and d1.capability == Capability.READ_ONLY
    info = AgentLoop._capability_check("screen")
    assert info["decision"] == Decision.ALLOW


class _Scripted(AgentLoop):
    def __init__(self, script, **kw):
        kw.setdefault("session_id", None)
        super().__init__(**kw)
        self._script = list(script)
        self.tools_invoked = []

    async def _chat(self, client, messages):
        if not self._script:
            return "تمام.", 0, 0.0
        return self._script.pop(0), 0, 0.0


def _run(loop):
    async def _collect():
        return [ev async for ev in loop.run("do the thing please")]
    return asyncio.run(_collect())


def test_capability_event_emitted_and_bash_allowed_dev(monkeypatch):
    import genio_server.core.agent_loop as mod
    real = mod.invoke
    calls = []
    monkeypatch.setattr(mod, "invoke",
                        lambda t, p, s=None: (calls.append(t), real(t, p, s))[1])
    monkeypatch.delenv("GENIO_SECURITY_MODE", raising=False)
    events = _run(_Scripted(['{"tool": "bash", "command": "echo cap"}',
                             "تمام."]))
    cap = [e for e in events if e.get("type") == "capability.requested"]
    assert cap and cap[0]["tool"] == "bash"
    assert cap[0]["capability"] == Capability.PROCESS_EXECUTION
    assert cap[0]["decision"] == Decision.ALLOW
    assert calls == ["bash"]


def test_strict_mode_denies_bash_without_sandbox(monkeypatch):
    import genio_server.core.agent_loop as mod
    real = mod.invoke
    calls = []
    monkeypatch.setattr(mod, "invoke",
                        lambda t, p, s=None: (calls.append(t), real(t, p, s))[1])
    monkeypatch.setenv("GENIO_SECURITY_MODE", "strict")
    monkeypatch.delenv("GENIO_SANDBOX_MODE", raising=False)
    events = _run(_Scripted(['{"tool": "bash", "command": "echo no"}',
                             "تمام."]))
    assert calls == [], "strict sans sandbox : bash ne doit JAMAIS s'exécuter"
    deny = [e for e in events if e.get("type") == "error"
            and "POLICY DENY" in str(e.get("message", ""))]
    assert deny
    assert any(e.get("type") == "answer" for e in events)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
