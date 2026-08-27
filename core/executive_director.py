"""Genio — Master ReAct Reasoning Loop & Autonomous Task Decomposition.

The Executive Director orchestrates the full pipeline:
Plan → Content → Sandbox → Video → Audio → Cover → Audit → Publish → YouTube
"""
from __future__ import annotations

import asyncio
import argparse
import re
import sys
import time
import traceback
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Awaitable

from loguru import logger

from config import get_config, GENIO_DIR, REPORTS_DIR


# ── Re-export legacy modules for backward compatibility ── #
import sys as _sys
_sys.path.insert(0, str(GENIO_DIR))
_sys.path.insert(0, str(GENIO_DIR.parent / "webapp" / "backend"))


# ── DAG Node Types ── #

@dataclass
class PlanNode:
    id: str
    agent: str
    action: str
    params: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)
    timeout_s: int = 600
    max_retries: Optional[int] = None
    on_error: str = "continue"


@dataclass
class ExecutionPlan:
    goal: str
    nodes: List[PlanNode]
    planner: str = "deterministic_v4"

    def topological(self) -> List[PlanNode]:
        visited, result = set(), []
        node_map = {n.id: n for n in self.nodes}

        def _visit(nid: str):
            if nid in visited:
                return
            visited.add(nid)
            node = node_map.get(nid)
            if node:
                for dep in node.depends_on:
                    _visit(dep)
                result.append(node)

        for n in self.nodes:
            _visit(n.id)
        return result

    def to_json(self) -> str:
        import json
        return json.dumps({
            "goal": self.goal,
            "planner": self.planner,
            "nodes": [{"id": n.id, "agent": n.agent, "action": n.action,
                        "params": n.params, "depends_on": n.depends_on}
                       for n in self.nodes],
        }, indent=2, ensure_ascii=False)


# ── Agent Result ── #

@dataclass
class NodeResult:
    node_id: str
    ok: bool
    output: Optional[str] = None
    error: Optional[str] = None
    artifacts: list = field(default_factory=list)
    duration_s: float = 0.0
    attempts: int = 1


@dataclass
class Artifact:
    kind: str
    path_or_url: str
    meta: Dict[str, Any] = field(default_factory=dict)


# ── Agent Context ── #

@dataclass
class AgentContext:
    goal: str
    dry_run: bool = False
    publish: bool = True
    scratch: Dict[str, Any] = field(default_factory=dict)
    artifacts: Dict[str, Artifact] = field(default_factory=dict)


# ── Base Agent ── #

class BaseAgent:
    async def run(self, node: PlanNode, ctx: AgentContext) -> NodeResult:
        raise NotImplementedError


# ── Autonomous Pipeline ── #

def build_autonomous_plan(topic: str) -> ExecutionPlan:
    """Deterministic pipeline: content → 2-node sandbox → video → audio →
    cover → audit → publish → youtube payload."""
    nodes = [
        PlanNode(id="env_check", agent="sandbox",
                 action="check_environment", timeout_s=60),
        PlanNode(id="content", agent="content",
                 action="generate_darija_lab",
                 params={"topic": topic}, timeout_s=1500),
        PlanNode(id="livetest_recording", agent="media",
                 action="generate_livetest_video",
                 params={"topic": topic},
                 depends_on=["content"], timeout_s=900),
        PlanNode(id="audio", agent="media",
                 action="generate_audio",
                 depends_on=["content"], timeout_s=600),
        PlanNode(id="cover", agent="media",
                 action="generate_cover",
                 depends_on=["content"], timeout_s=120),
        PlanNode(id="audit", agent="auditor",
                 action="full_audit",
                 depends_on=["content"], timeout_s=120),
        PlanNode(id="publish", agent="media",
                 action="publish_ghost",
                 depends_on=["audit", "audio", "cover"],
                 params={"force": True}, timeout_s=120),
        PlanNode(id="youtube", agent="media",
                 action="generate_youtube_payload",
                 depends_on=["livetest_recording", "publish"],
                 timeout_s=60),
    ]
    return ExecutionPlan(goal=f"Autonomous lab: {topic}",
                         nodes=nodes, planner="deterministic_v4")


# ── Dispatcher ── #

def dispatch(agent_name: str) -> BaseAgent:
    from core.model_router import ModelRouter
    from core.memory_engine import get_memory

    if agent_name == "sandbox":
        from sandbox.node_manager import NodeManagerAgent
        return NodeManagerAgent()
    elif agent_name == "content":
        from sandbox.live_recorder import ContentArchitectAgent
        return ContentArchitectAgent()
    elif agent_name == "media":
        from media.cinema_director import CinemaDirectorAgent
        return CinemaDirectorAgent()
    elif agent_name == "auditor":
        from sandbox.self_healer import AuditorAgent
        return AuditorAgent()
    raise ValueError(f"Unknown agent: {agent_name}")


# ── Remediation Engine ── #

class Remediation:
    PATTERNS = [
        (r"regen:[\w,\s]+", "content_regen"),
        (r"Connection refused on :9876|cinema.*down", "wait_for_services"),
        (r"timed out|timeout", "escalate_timeout"),
        (r"401|Unauthorized|invalid api token", "reload_secrets"),
        (r"OperationalError.*database.*locked", "sqlite_backoff"),
        (r"ffmpeg.*nvenc|encoder.*fail", "ffmpeg_fallback"),
        (r"429|rate.limit|Too Many", "backoff_long"),
    ]

    @classmethod
    def classify(cls, error: str) -> str:
        for pattern, strategy in cls.PATTERNS:
            if re.search(pattern, error, re.IGNORECASE):
                return strategy
        return "generic_backoff"

    @classmethod
    def extract_regen_codes(cls, error: str) -> List[str]:
        m = re.search(r"regen:([\w,\s]+)", error or "")
        if m:
            return [c.strip() for c in m.group(1).split(",") if c.strip()]
        return []


class SelfHealingExecutor:
    def __init__(self, default_retries: int = 3):
        self.default_retries = default_retries
        self.recovery_trace: List[Dict[str, str]] = []

    async def _apply_remediation(self, strategy: str, node: PlanNode,
                                  attempt: int, failed_result=None, ctx=None):
        import os
        note = f"[recovery#{attempt}] {strategy} on node={node.id}"
        if strategy == "escalate_timeout":
            node.timeout_s = min(int(node.timeout_s * 2), 3600)
            note += f" -> timeout={node.timeout_s}s"
        elif strategy == "reload_secrets":
            env_path = GENIO_DIR.parent / ".env"
            if env_path.exists():
                for line in env_path.read_text().splitlines():
                    if "=" in line and not line.strip().startswith("#"):
                        k, v = line.split("=", 1)
                        os.environ.setdefault(k.strip(), v.strip())
        elif strategy in ("sqlite_backoff", "generic_backoff"):
            await asyncio.sleep(min(2 ** attempt, 15))
        elif strategy == "backoff_long":
            await asyncio.sleep(min(5 * attempt, 30))
        elif strategy == "wait_for_services":
            await asyncio.sleep(10)
        logger.info(note)
        self.recovery_trace.append({"node": node.id, "attempt": str(attempt),
                                    "strategy": strategy})

    async def execute_node(self, node: PlanNode, ctx: AgentContext,
                           agent_override=None) -> NodeResult:
        agent = agent_override or dispatch(node.agent)
        retries = node.max_retries or self.default_retries
        started = time.monotonic()
        last = None
        for attempt in range(1, retries + 1):
            try:
                result = await asyncio.wait_for(
                    agent.run(node, ctx), timeout=node.timeout_s)
            except asyncio.TimeoutError:
                result = NodeResult(node.id, False, error="node timed out")
            except Exception as exc:
                logger.error(traceback.format_exc(limit=3))
                result = NodeResult(node.id, False,
                                    error=f"{type(exc).__name__}: {exc}")
            result.duration_s = round(time.monotonic() - started, 2)
            result.attempts = attempt
            if result.ok:
                return result
            last = result
            if attempt < retries:
                strategy = Remediation.classify(result.error or "")
                await self._apply_remediation(strategy, node, attempt,
                                              failed_result=result, ctx=ctx)
        return last or NodeResult(node.id, False, error="no attempts")


# ── Report Generator ── #

class ReportGenerator:
    @staticmethod
    def build(plan: ExecutionPlan, results: Dict[str, NodeResult],
              ctx: AgentContext, wall_time: float) -> str:
        import resource
        ru = resource.getrusage(resource.RUSAGE_SELF)
        audit = ctx.scratch.get("audit", {})
        lines = [
            f"# 🤖 Genio Autonomous Report",
            f"**Goal**: {plan.goal}",
            f"**Planner**: {plan.planner}",
            f"**Wall time**: {wall_time:.0f}s",
            f"**Peak RSS**: {ru.ru_maxrss // 1024}MB",
            "",
            "## Pipeline Results",
        ]
        for node in plan.nodes:
            r = results.get(node.id)
            status = "✅" if (r and r.ok) else "❌"
            detail = ""
            if r:
                detail = r.output or r.error or ""
                if r.duration_s:
                    detail += f" ({r.duration_s:.0f}s)"
            lines.append(f"- {status} **{node.id}** [{node.agent}]: {detail}")

        recovery = ctx.scratch.get("recovery_trace", [])
        if recovery:
            lines.append("\n## Auto-Recovery Trace")
            for step in recovery:
                lines.append(f"- [{step['strategy']}] on {step['node']} "
                             f"(attempt {step['attempt']})")

        if audit:
            q = audit.get("quality", 0)
            s = audit.get("security", 0)
            lines.append(f"\n## Quality Gate: {q:.0f}/100 quality, {s:.0f}/100 security")

        return "\n".join(lines)


# ── Autonomous Execution ── #

async def execute_autonomous(topic: str, *, max_retries: int = 3,
                             publish: bool = True,
                             report_dir: Optional[Path] = None,
                             ) -> Tuple[str, ExecutionPlan, Dict[str, NodeResult], AgentContext]:
    """Full autonomous cycle with auto-healing at every friction point."""
    from core.memory_engine import get_memory
    core_start = time.monotonic()
    plan = build_autonomous_plan(topic)
    logger.info(f"🤖 Autonomous plan ready: {len(plan.nodes)} nodes")

    ctx = AgentContext(goal=plan.goal, dry_run=False, publish=publish)
    healing = SelfHealingExecutor(default_retries=max_retries)
    results: Dict[str, NodeResult] = {}

    for node in plan.topological():
        deps_failed = [d for d in node.depends_on
                       if d in results and not results[d].ok]
        if deps_failed:
            results[node.id] = NodeResult(
                node.id, False, error=f"skipped: dependency failed {deps_failed}")
            logger.warning(f"⏭️  {node.id} skipped (deps failed)")
            continue
        logger.info(f"▶️  autonomous [{node.agent}] {node.id}")
        results[node.id] = await healing.execute_node(node, ctx)
        status = "✅" if results[node.id].ok else "❌"
        logger.info(f"{status} {node.id} -> "
                    f"{results[node.id].output or results[node.id].error}")

        if (node.id == "audit" and not results[node.id].ok
                and "regen:" in (results[node.id].output or "")):
            logger.info("🔄 Auto-regenerating content after audit failure...")
            regen_node = PlanNode(id="auto_regen", agent="content",
                                  action="generate_darija_lab",
                                  params={"topic": topic}, timeout_s=1500)
            regen_result = await healing.execute_node(regen_node, ctx)
            if regen_result.ok:
                results["auto_regen"] = regen_result
                re_audit = PlanNode(id="auto_re_audit", agent="auditor",
                                    action="full_audit", timeout_s=120)
                re_audit_result = await healing.execute_node(re_audit, ctx)
                results["auto_re_audit"] = re_audit_result
                if re_audit_result.ok:
                    results["audit"] = re_audit_result

    ctx.scratch["recovery_trace"] = healing.recovery_trace
    wall = time.monotonic() - core_start
    try:
        get_memory().note_run()
    except Exception:
        pass

    report_md = ReportGenerator.build(plan, results, ctx, wall)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    report_file = (report_dir or REPORTS_DIR) / f"autonomous_{stamp}.md"
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(report_md, encoding="utf-8")

    return report_md, plan, results, ctx


# ── CLI ── #

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="genio",
        description="Genio — Autonomous Multimodal AI Executive Director")
    parser.add_argument("--prompt", required=True,
                        help="High-level intent")
    parser.add_argument("--auto", action="store_true",
                        help="Full autonomous pipeline")
    parser.add_argument("--dry-run", action="store_true",
                        help="Plan + environment checks only")
    parser.add_argument("--no-publish", action="store_true",
                        help="Generate assets but do NOT push to Ghost")
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--feedback", type=str, default=None,
                        help="Record a user lesson and exit")
    args = parser.parse_args(argv)

    if args.feedback:
        from core.memory_engine import get_memory
        added = get_memory().record_feedback(args.feedback)
        print(f"🧠 Memory updated ({len(get_memory().rules)} rules). Latest: {added}")
        return 0

    if args.auto:
        report_md, plan, results, ctx = asyncio.run(execute_autonomous(
            args.prompt, max_retries=args.max_retries,
            publish=not args.no_publish))
    else:
        from genio_executive_core import execute_prompt
        report_md, plan, results, ctx = asyncio.run(execute_prompt(
            args.prompt, max_retries=args.max_retries,
            publish=not args.no_publish, dry_run=args.dry_run))

    print("\n" + "=" * 74)
    print(report_md)
    print("=" * 74)
    return 0 if all(r.ok for r in results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
