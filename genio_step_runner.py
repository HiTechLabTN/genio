#!/usr/bin/env python3
"""Chunked Genio driver — same agents, persistent state between steps.
Usage:
  python3 genio_step_runner.py auto "Sujet du Lab"    ← FULL AUTONOMOUS
  python3 genio_step_runner.py content "PROMPT"
  python3 genio_step_runner.py audio
  python3 genio_step_runner.py video
  python3 genio_step_runner.py cover
  python3 genio_step_runner.py audit-publish
"""
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, "/data/ai_tools/genio")
STATE = Path("/tmp/opencode/genio_v23_state.json")


def load_state() -> dict:
    return json.loads(STATE.read_text()) if STATE.exists() else {}


def save_state(s: dict) -> None:
    STATE.write_text(json.dumps(s, ensure_ascii=False))


def new_ctx(goal: str) -> "AgentContext":
    from genio_executive_core import AgentContext
    return AgentContext(goal=goal)


async def run_node(agent_name: str, action: str, params: dict,
                   goal: str, depends: list = None):
    from genio_executive_core import (PlanNode, SelfHealingExecutor,
                                      dispatch)
    s = load_state()
    ctx = new_ctx(goal or s.get("goal", "lab"))
    ctx.dry_run = False
    ctx.publish = True
    # restore scratch
    for k, v in (s.get("scratch") or {}).items():
        ctx.scratch[k] = v
    arts = s.get("artifacts") or {}
    from genio_executive_core import Artifact
    for k, v in arts.items():
        ctx.artifacts[k] = Artifact(**v)

    node = PlanNode(id=f"chunk_{agent_name}", agent=agent_name,
                    action=action, params=params,
                    depends_on=depends or [], timeout_s=1500)
    healing = SelfHealingExecutor(default_retries=2)
    t0 = time.monotonic()
    res = await healing.execute_node(node, ctx)

    # persist
    s.setdefault("goal", goal)
    s["scratch"] = {k: v for k, v in ctx.scratch.items()
                    if k not in ("env_checks",)}
    s["scratch"]["env_checks"] = ctx.scratch.get("env_checks")
    s["audit"] = ctx.scratch.get("audit")
    s["artifacts"] = {k: {"kind": a.kind, "path_or_url": a.path_or_url,
                          "meta": a.meta}
                      for k, a in ctx.artifacts.items()}
    save_state(s)
    print(f"[{action}] ok={res.ok} ({time.monotonic()-t0:.0f}s) "
          f"-> {res.output or res.error}")
    return 0 if res.ok else 1


def main():
    cmd = sys.argv[1]
    if cmd == "auto":
        prompt = sys.argv[2] if len(sys.argv) > 2 else "WireGuard VPN Multi-Node Lab"
        from genio_executive_core import execute_autonomous
        report, plan, results, ctx = asyncio.run(execute_autonomous(prompt))
        print(report)
        sys.exit(0 if all(r.ok for r in results.values()) else 1)
    elif cmd == "content":
        prompt = sys.argv[2] if len(sys.argv) > 2 else "WireGuard lab"
        sys.exit(asyncio.run(run_node(
            "content", "generate_darija_lab",
            {"topic": prompt}, prompt)))
    elif cmd == "audio":
        sys.exit(asyncio.run(run_node("media", "generate_audio", {},
                                      load_state().get("goal", ""))))
    elif cmd == "video":
        sys.exit(asyncio.run(run_node("media", "generate_video", {},
                                      load_state().get("goal", ""))))
    elif cmd == "cover":
        sys.exit(asyncio.run(run_node("media", "generate_cover", {},
                                      load_state().get("goal", ""))))
    elif cmd == "audit-publish":
        # audit first (with memory learning), publish gated on success
        rc_audit = asyncio.run(run_node("auditor", "full_audit", {},
                                        load_state().get("goal", "")))
        if rc_audit != 0:
            print("AUDIT FAILED - publishing blocked by quality gate")
            sys.exit(1)
        sys.exit(asyncio.run(run_node("media", "publish_ghost", {},
                                      load_state().get("goal", ""))))
    else:
        print(f"unknown step {cmd}")
        sys.exit(2)


if __name__ == "__main__":
    main()
