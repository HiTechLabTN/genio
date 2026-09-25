"""Phase 2 regression tests — canonical registries.

Deterministic, no network, no model, no GPU. Asserts single-source-of-truth
wiring (reads owners, never copies) and fail-closed policy decisions.
"""
import sys

sys.path.insert(0, "/data/ai_tools/genio")

from genio_server.core.registries import (
    ActionRegistry,
    Capability,
    CapabilityRegistry,
    Decision,
    MemoryRegistry,
    ModelRegistry,
    PolicyRegistry,
    RiskLevel,
    SkillRegistry,
    ToolRegistry,
)


def test_tool_registry_mirrors_owner():
    from genio_server.tools import TOOLS
    assert set(ToolRegistry.names()) == set(TOOLS.keys())
    for name in ToolRegistry.names():
        assert ToolRegistry.describe(name) == TOOLS[name]
    assert ToolRegistry.has("bash") and not ToolRegistry.has("nope")


def test_capability_unknown_is_critical():
    assert CapabilityRegistry.capability_of("nope") == Capability.CRITICAL
    assert CapabilityRegistry.risk_of("nope") == RiskLevel.CRITICAL
    assert CapabilityRegistry.capability_of("bash") == Capability.PROCESS_EXECUTION
    assert set(CapabilityRegistry.all().keys()) >= set(ToolRegistry.names())


def test_actions_defined():
    for name in ("prompt", "kill", "rearm", "transcribe", "synthesize",
                 "telemetry"):
        a = ActionRegistry.get(name)
        assert a is not None and a.timeout_s > 0 and a.capability
    assert ActionRegistry.get("nope") is None


def test_policy_fail_closed():
    # unknown tool + strict + no sandbox -> DENY
    assert PolicyRegistry.decide_tool("nope", False, "strict") == Decision.DENY
    assert PolicyRegistry.decide("whatever", False, "strict") == Decision.DENY
    # strict gates dangerous execution
    assert PolicyRegistry.decide_tool("bash", False, "strict") == Decision.DENY
    assert (PolicyRegistry.decide_tool("bash", True, "strict")
            == Decision.SANDBOX_ONLY)
    # read-only stays open in both modes
    assert PolicyRegistry.decide_tool("screen", False, "strict") == Decision.ALLOW
    assert (PolicyRegistry.decide_tool("screen", False, "development")
            == Decision.ALLOW)
    # deterministic: same inputs -> same outputs
    assert (PolicyRegistry.decide_tool("bash", True, "strict")
            == PolicyRegistry.decide_tool("bash", True, "strict"))


def test_model_registry_reads_router():
    eps = ModelRegistry.backends()
    assert isinstance(eps, list) and len(eps) >= 1
    assert all({"name", "base_url", "model"} <= set(e.keys()) for e in eps)


def test_skill_registry_reads_compiled():
    skills = SkillRegistry.compiled()
    assert isinstance(skills, list) and len(skills) >= 1
    assert "greeting" in SkillRegistry.reflex_patterns()


def test_memory_registry_paths_exist():
    import os
    stores = MemoryRegistry.stores()
    assert stores["sessions_db"].endswith("state/sessions.db")
    assert os.path.exists(stores["sessions_db"])
    assert os.path.isdir(stores["compiled_skills"])


if __name__ == "__main__":
    test_tool_registry_mirrors_owner()
    test_capability_unknown_is_critical()
    test_actions_defined()
    test_policy_fail_closed()
    test_model_registry_reads_router()
    test_skill_registry_reads_compiled()
    test_memory_registry_paths_exist()
    print("registries: 7/7 PASS")
