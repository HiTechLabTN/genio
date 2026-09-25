"""Canonical registries — Phase 2 single source of truth.

ToolRegistry / CapabilityRegistry / ActionRegistry / PolicyRegistry /
ModelRegistry / SkillRegistry / MemoryRegistry.

Rules honoured here (master prompt §§2,4,5):
- Prefer one canonical source of truth: registries READ from existing owners
  (TOOLS dict, ModelRouter config, skills dirs, session store) — never copies.
- New authoritative data (capability taxonomy, action risk, policy defaults)
  lives ONLY here.
- Policy decisions are deterministic, testable, LLM-independent, fail-closed.
- stdlib only at import; owner modules imported lazily (no cycles).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


# --------------------------------------------------------------------------- #
# Capabilities (master prompt Phase 4 taxonomy)
# --------------------------------------------------------------------------- #
class Capability:
    READ_ONLY = "READ_ONLY"
    SAFE_WRITE = "SAFE_WRITE"
    WORKSPACE_WRITE = "WORKSPACE_WRITE"
    NETWORK = "NETWORK"
    PROCESS_EXECUTION = "PROCESS_EXECUTION"
    SYSTEM_SERVICE_CONTROL = "SYSTEM_SERVICE_CONTROL"
    CREDENTIAL_ACCESS = "CREDENTIAL_ACCESS"
    DEVICE_CONTROL = "DEVICE_CONTROL"
    DESTRUCTIVE = "DESTRUCTIVE"
    ADMINISTRATIVE = "ADMINISTRATIVE"
    CRITICAL = "CRITICAL"


class Decision:
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_CONFIRMATION = "REQUIRE_CONFIRMATION"
    SANDBOX_ONLY = "SANDBOX_ONLY"
    RATE_LIMIT = "RATE_LIMIT"
    RESOURCE_LIMIT = "RESOURCE_LIMIT"
    NETWORK_RESTRICTED = "NETWORK_RESTRICTED"


# --------------------------------------------------------------------------- #
# ToolRegistry — canonical view over genio_server.tools.TOOLS (no copy)
# --------------------------------------------------------------------------- #
class ToolRegistry:
    """Single source of truth for the tool catalogue (reads owner dict)."""

    @staticmethod
    def _owner() -> Dict[str, str]:
        from genio_server.tools import TOOLS
        return TOOLS

    @classmethod
    def names(cls) -> List[str]:
        return sorted(cls._owner().keys())

    @classmethod
    def describe(cls, name: str) -> Optional[str]:
        return cls._owner().get(name)

    @classmethod
    def has(cls, name: str) -> bool:
        return name in cls._owner()


# --------------------------------------------------------------------------- #
# CapabilityRegistry — authoritative tool -> capability/risk mapping
# --------------------------------------------------------------------------- #
_TOOL_CAPABILITIES: Dict[str, Dict[str, str]] = {
    "bash": {"capability": Capability.PROCESS_EXECUTION, "risk": "high"},
    "browser": {"capability": Capability.NETWORK, "risk": "medium"},
    "computer": {"capability": Capability.DEVICE_CONTROL, "risk": "high"},
    "screen": {"capability": Capability.READ_ONLY, "risk": "low"},
    "api": {"capability": Capability.NETWORK, "risk": "medium"},
    "social_post": {"capability": Capability.NETWORK, "risk": "low"},
    "tool_forge": {"capability": Capability.ADMINISTRATIVE, "risk": "critical"},
}


class CapabilityRegistry:
    """Authoritative capability + risk per tool (defined ONLY here)."""

    @classmethod
    def capability_of(cls, tool: str) -> str:
        return _TOOL_CAPABILITIES.get(tool, {}).get("capability",
                                                    Capability.CRITICAL)

    @classmethod
    def risk_of(cls, tool: str) -> str:
        return _TOOL_CAPABILITIES.get(tool, {}).get("risk", "critical")

    @classmethod
    def all(cls) -> Dict[str, Dict[str, str]]:
        out = dict(_TOOL_CAPABILITIES)
        for name in ToolRegistry.names():
            out.setdefault(name, {"capability": Capability.CRITICAL,
                                  "risk": "critical"})
        return out


# --------------------------------------------------------------------------- #
# ActionRegistry — canonical WS/API actions
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Action:
    name: str
    capability: str
    risk: str
    timeout_s: float
    requires: tuple = ()
    description: str = ""


_ACTIONS: Dict[str, Action] = {
    "prompt": Action("prompt", Capability.PROCESS_EXECUTION, "high", 600.0,
                     (), "Run one agent turn (may chain tools)"),
    "kill": Action("kill", Capability.ADMINISTRATIVE, "medium", 5.0, (),
                   "Halt all runs (kill switch)"),
    "rearm": Action("rearm", Capability.ADMINISTRATIVE, "medium", 5.0, (),
                    "Re-arm after halt"),
    "resume": Action("resume", Capability.READ_ONLY, "low", 10.0, (),
                     "Load bounded session checkpoint"),
    "screenshot": Action("screenshot", Capability.READ_ONLY, "low", 15.0, (),
                         "Capture host display"),
    "screen_stream": Action("screen_stream", Capability.READ_ONLY, "low", 5.0,
                            (), "Toggle display streaming"),
    "attach_file": Action("attach_file", Capability.WORKSPACE_WRITE, "low",
                          30.0, (), "Stage an uploaded file"),
    "attach_image": Action("attach_image", Capability.WORKSPACE_WRITE, "low",
                           30.0, (), "Stage an uploaded image"),
    "voice_wav": Action("voice_wav", Capability.WORKSPACE_WRITE, "low", 30.0,
                        (), "Stage recorded audio"),
    "transcribe": Action("transcribe", Capability.READ_ONLY, "low", 300.0, (),
                         "STT over staged audio"),
    "synthesize": Action("synthesize", Capability.READ_ONLY, "low", 300.0, (),
                         "VODER TTS synthesis"),
    "telemetry": Action("telemetry", Capability.READ_ONLY, "low", 10.0, (),
                        "System vitals snapshot"),
}


class ActionRegistry:
    """Canonical WS/API actions (defined ONLY here)."""
    @classmethod
    def get(cls, name: str) -> Optional[Action]:
        return _ACTIONS.get(name)

    @classmethod
    def names(cls) -> List[str]:
        return sorted(_ACTIONS.keys())


# --------------------------------------------------------------------------- #
# PolicyRegistry — deterministic, LLM-independent, fail-closed
# --------------------------------------------------------------------------- #
_STRICT_DENY = {Capability.DESTRUCTIVE, Capability.CRITICAL,
                Capability.CREDENTIAL_ACCESS}
_STRICT_SANDBOX = {Capability.PROCESS_EXECUTION, Capability.DEVICE_CONTROL,
                   Capability.ADMINISTRATIVE, Capability.SYSTEM_SERVICE_CONTROL}
_KNOWN_CAPABILITIES = {
    Capability.READ_ONLY, Capability.SAFE_WRITE, Capability.WORKSPACE_WRITE,
    Capability.NETWORK, Capability.PROCESS_EXECUTION,
    Capability.SYSTEM_SERVICE_CONTROL, Capability.CREDENTIAL_ACCESS,
    Capability.DEVICE_CONTROL, Capability.DESTRUCTIVE,
    Capability.ADMINISTRATIVE, Capability.CRITICAL,
}


class PolicyRegistry:
    """decide() is pure: (capability, sandbox_available, mode) -> decision."""

    @staticmethod
    def mode() -> str:
        return os.getenv("GENIO_SECURITY_MODE", "development").strip().lower()

    @classmethod
    def decide(cls, capability: str,
               sandbox_available: bool = False,
               mode: Optional[str] = None) -> str:
        mode = (mode or cls.mode())
        if capability in _STRICT_DENY:
            return Decision.DENY
        if mode == "strict":
            if capability not in _KNOWN_CAPABILITIES:
                return Decision.DENY  # fail-closed : inconnu = refusé
            if capability in (Capability.READ_ONLY,):
                return Decision.ALLOW
            if capability in _STRICT_SANDBOX:
                return (Decision.SANDBOX_ONLY if sandbox_available
                        else Decision.DENY)
            return Decision.REQUIRE_CONFIRMATION
        # development: permissive but explicit
        if capability in (Capability.READ_ONLY,):
            return Decision.ALLOW
        if capability in _STRICT_SANDBOX:
            return (Decision.SANDBOX_ONLY if sandbox_available
                    else Decision.ALLOW)
        return Decision.ALLOW

    @classmethod
    def decide_tool(cls, tool: str,
                    sandbox_available: bool = False,
                    mode: Optional[str] = None) -> str:
        return cls.decide(CapabilityRegistry.capability_of(tool),
                          sandbox_available, mode)


# --------------------------------------------------------------------------- #
# ModelRegistry — read-only view over ModelRouter configuration
# --------------------------------------------------------------------------- #
class ModelRegistry:
    @staticmethod
    def backends() -> List[Dict[str, str]]:
        from core.model_router import ModelRouter
        out = []
        for ep in ModelRouter().endpoints:
            out.append({"name": getattr(ep, "name", "?"),
                        "base_url": getattr(ep, "base_url", "?"),
                        "model": getattr(ep, "model", "?")})
        return out


# --------------------------------------------------------------------------- #
# SkillRegistry — compiled skills + reflex patterns (read-only view)
# --------------------------------------------------------------------------- #
_COMPILED_SKILLS_DIR = Path(__file__).resolve().parents[2] / "genio" / "core" \
    / "compiled_skills"


class SkillRegistry:
    @classmethod
    def compiled(cls) -> List[Dict[str, str]]:
        out = []
        if _COMPILED_SKILLS_DIR.is_dir():
            for p in sorted(_COMPILED_SKILLS_DIR.glob("*.json")):
                try:
                    d = json.loads(p.read_text())
                except Exception:
                    continue
                out.append({"file": p.name,
                            "score": str(d.get("score", "?")),
                            "context": str(d.get("context", "?"))})
        return out

    @classmethod
    def reflex_patterns(cls) -> List[str]:
        from genio_server.core.reflex_engine import _REFLEX_PATTERNS
        return [str(p.get("name")) for p in _REFLEX_PATTERNS]


# --------------------------------------------------------------------------- #
# MemoryRegistry — store descriptors (paths + contracts, never content copies)
# --------------------------------------------------------------------------- #
class MemoryRegistry:
    @staticmethod
    def stores() -> Dict[str, str]:
        root = Path(__file__).resolve().parents[2]
        return {
            "sessions_db": str(root / "state" / "sessions.db"),
            "gestures_db": str(root / "genio_gestures" / "gestures.db"),
            "skills_library": str(root / "state" / "skills_library"),
            "compiled_skills": str(_COMPILED_SKILLS_DIR),
            "drive_agents": "/data/hitech_store/storage/agents",
        }
