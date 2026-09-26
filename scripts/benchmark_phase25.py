#!/usr/bin/env python3
"""Phase 25 benchmarks — mesures réelles, aucune optimisation prématurée.

Sortie : docs/audit/PERFORMANCE_BENCHMARK.md (régénéré à chaque run).
"""
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, "/data/ai_tools/genio")
R = {}


def measure(name, fn, unit="s"):
    t0 = time.monotonic()
    try:
        out = fn()
        dt = time.monotonic() - t0
        R[name] = {"ok": True, "value": round(dt, 3), "unit": unit,
                   "detail": str(out)[:120]}
    except Exception as e:
        R[name] = {"ok": False, "error": str(e)[:200]}
    print(f"{name}: {R[name]}", flush=True)


def cold_start():
    t0 = time.monotonic()
    import subprocess as sp
    r = sp.run([sys.executable, "-c",
                "import sys; sys.path.insert(0,'/data/ai_tools/genio');"
                "from genio_server.core.agent_loop import AgentLoop;"
                "print(AgentLoop().model)"],
               capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-300:]
    return f"import+init in {time.monotonic()-t0:.1f}s model={r.stdout.strip()}"


def fast_path():
    from genio_server.core.reflex_engine import get_reflex_engine
    t0 = time.monotonic()
    r = get_reflex_engine().match("xxx-unmatchable")
    t1 = time.monotonic()
    assert r is None
    t2 = time.monotonic()
    r = get_reflex_engine().match("عسلامة", session_id="bench")
    dt = time.monotonic() - t2
    assert r is not None
    return f"miss {t1-t0:.3f}s / greeting-hit {dt:.3f}s"


def routing_latency():
    import httpx
    t0 = time.monotonic()
    r = httpx.post("http://127.0.0.1:11434/api/generate",
                   json={"model": "gemma4:12b", "prompt": "قول عسلامة",
                         "stream": False, "options": {"num_predict": 20}},
                   timeout=180)
    d = r.json()
    dt = time.monotonic() - t0
    ec, ed = d.get("eval_count", 0), d.get("eval_duration", 0)
    tps = round(ec / (ed / 1e9), 1) if ed else 0
    return f"{dt:.1f}s total, {tps} tok/s (eval {ec} tok)"


def tool_exec():
    from genio_server.tools.bash_tool import run_command
    t0 = time.monotonic()
    r = run_command("echo bench-ok")
    assert r["returncode"] == 0
    return f"{(time.monotonic()-t0)*1000:.0f}ms"


def sandbox_startup():
    # Mode conteneur RÉEL (sinon mesure locale trompeuse) + cleanup.
    os.environ["GENIO_SANDBOX_MODE"] = "container"
    from genio_server.tools.session_container import (
        cleanup_container, exec_in_container)
    try:
        t0 = time.monotonic()
        r = exec_in_container("bench_ph25", "echo sb-ok")
        dt = time.monotonic() - t0
        assert r["returncode"] == 0, r
        assert not r.get("sandbox_fallback"), "fallback local mesuré !"
        return f"{dt:.1f}s (create+exec, conteneur réel)"
    finally:
        try:
            cleanup_container("bench_ph25")
        except Exception:
            pass
        os.environ.pop("GENIO_SANDBOX_MODE", None)


def memory_retrieval():
    from genio_server.core.session_store import SessionStore
    import asyncio
    t0 = time.monotonic()
    sess = asyncio.run(SessionStore().load_session("azmi"))
    dt = time.monotonic() - t0
    return f"{dt*1000:.0f}ms turns={len(sess.get('turns', []))}"


def ws_latency():
    import asyncio
    import websockets

    async def _go():
        t0 = time.monotonic()
        async with websockets.connect("ws://127.0.0.1:8000/ws/agent") as ws:
            await ws.send(json.dumps({"action": "prompt", "text": "عسلامة"}))
            async for raw in ws:
                ev = json.loads(raw)
                if ev.get("type") == "answer":
                    return time.monotonic() - t0
    return f"{asyncio.run(_go()):.2f}s greeting turn"


def footprints():
    import psutil
    rss = 0
    for p in psutil.process_iter(["name", "memory_info"]):
        try:
            if "uvicorn" in (p.info["name"] or ""):
                rss = max(rss, p.info["memory_info"].rss)
        except Exception:
            continue
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total",
             "--format=csv,noheader,nounits"], capture_output=True, text=True,
            timeout=10)
        vram = out.stdout.strip()
    except Exception as e:
        vram = f"n/a ({e})"
    vm = psutil.virtual_memory()
    return (f"server-rss={rss/1e9:.2f}GB host-ram={vm.percent}% "
            f"vram={vram}")


measure("cold_start", cold_start)
measure("fast_path_reflex", fast_path)
measure("routing_inference", routing_latency)
measure("tool_exec_bash", tool_exec)
measure("sandbox_startup", sandbox_startup)
measure("memory_retrieval", memory_retrieval)
measure("ws_greeting_turn", ws_latency)
measure("footprints", footprints)

doc = ["# PERFORMANCE_BENCHMARK — Phase 25 (mesuré, non estimé)",
       "", f"Date : {time.strftime('%Y-%m-%d %H:%M %Z')} · hôte Pop!_OS local.",
       "", "| Métrique | Résultat |", "|---|---|"]
for k, v in R.items():
    if v.get("ok"):
        doc.append(f"| {k} | {v['value']}{v['unit']} — {v['detail']} |")
    else:
        doc.append(f"| {k} | FAILED — {v.get('error')} |")
doc += ["",
        "Notes : le fast-path salutations répond en millisecondes (pas de LLM) ;",
        "l'inférence locale domine tout tour LLM ; le sandbox inclut create+exec.",
        "Aucune optimisation appliquée — mesure d'abord (règle master)."]
open("/data/ai_tools/genio/docs/audit/PERFORMANCE_BENCHMARK.md", "w").write(
    "\n".join(doc) + "\n")
print("BENCHMARK WRITTEN")
