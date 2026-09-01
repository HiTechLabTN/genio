"""Phase 1 — memory/agent unification: durable session context is injected
into the interactive agent's system prompt (distinct from content rules).

Run:  pytest test_phase1_memory_agent.py -v
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from core.memory_engine import MemoryEngine
from genio_server.core.agent_loop import AgentLoop, build_instructions


def _fresh_memory() -> MemoryEngine:
    tmp = tempfile.mkdtemp()
    return MemoryEngine(Path(tmp) / "feedback_memory.json")


def test_add_context_is_persisted_and_distinct_from_rules():
    mem = _fresh_memory()
    before_rules = list(mem.rules)
    mem.add_context("Le client préfère une stack Python/React sur Ubuntu.", category="project")
    mem.add_context("Toujours répondre en tunisien dans l'agent interactif.", category="prefs")

    assert len(mem.rules) == len(before_rules), "rules must not be modified by add_context"
    assert len(mem.session_context) == 2
    assert "Le client préfère" in mem.context_text()
    assert mem.context_text().count("- [") == 2


def test_context_text_is_bounded():
    mem = _fresh_memory()
    for i in range(60):
        mem.add_context(f"fact #{i}", category="project")
    # Only the most recent `limit` (default 20) appear.
    rendered = mem.context_text()
    assert "fact #0" not in rendered
    assert "fact #59" in rendered


def test_build_instructions_injects_context_into_system_prompt():
    mem = _fresh_memory()
    mem.add_context("Stockage préféré : PostgreSQL géré.", category="project")
    prompt = build_instructions(mode="autonomous", memory=mem)
    assert "PostgreSQL géré" in prompt
    assert "SESSION CONTEXT" in prompt


def test_agentloop_system_prompt_contains_context():
    mem = _fresh_memory()
    mem.add_context("Utiliser un naming kebab-case.", category="project")
    loop = AgentLoop(system_prompt=build_instructions(mode="autonomous", memory=mem))
    assert "kebab-case" in loop.system_prompt
