"""Genio — FastAPI Backend with SSE Streaming, WebSocket & Static Frontend.

Serves the cyberpunk landing page at / and provides the full pipeline API.
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import (
    StreamingResponse, JSONResponse, HTMLResponse, FileResponse
)
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import get_config

app = FastAPI(title="Genio API", version="4.0.0")

cfg = get_config()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).resolve().parent / "static"


class PromptRequest(BaseModel):
    prompt: str
    auto: bool = False
    publish: bool = False


@app.get("/health")
async def health():
    return {"status": "healthy", "version": "4.0.0"}


@app.post("/api/generate")
async def generate(req: PromptRequest):
    from core.executive_director import (
        build_autonomous_plan, SelfHealingExecutor,
        AgentContext, NodeResult
    )
    try:
        plan = build_autonomous_plan(req.prompt)
        ctx = AgentContext(goal=plan.goal, dry_run=False, publish=req.publish)
        healing = SelfHealingExecutor(default_retries=2)
        results = {}
        t0 = time.time()
        for node in plan.topological():
            try:
                result = await asyncio.wait_for(
                    healing.execute_node(node, ctx), timeout=node.timeout_s)
            except asyncio.TimeoutError:
                result = NodeResult(node.id, False, error="TIMEOUT")
            except Exception as exc:
                result = NodeResult(node.id, False, error=f"{type(exc).__name__}: {exc}")
            results[node.id] = result

        elapsed = int(time.time() - t0)
        ok_count = sum(1 for r in results.values() if r.ok)
        total = len(results)
        report = (
            f"Pipeline complete: {ok_count}/{total} nodes passed in {elapsed}s\n\n"
            + plan.to_json()
        )
        return {
            "report": report,
            "plan": plan.to_json(),
            "results": {
                k: {"ok": v.ok, "output": v.output, "error": v.error}
                for k, v in results.items()
            },
        }
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"error": str(exc), "report": f"Pipeline failed: {exc}"}
        )


@app.post("/api/generate/stream")
async def generate_stream(req: PromptRequest):
    async def event_generator():
        yield f"data: {json.dumps({'status': 'started', 'prompt': req.prompt})}\n\n"
        try:
            from core.executive_director import (
                build_autonomous_plan, SelfHealingExecutor,
                AgentContext, NodeResult
            )
            plan = build_autonomous_plan(req.prompt)
            ctx = AgentContext(goal=plan.goal, dry_run=False, publish=req.publish)
            healing = SelfHealingExecutor(default_retries=2)
            results = {}
            t0 = time.time()

            for node in plan.topological():
                yield f"data: {json.dumps({'status': 'running', 'node': node.id, 'agent': node.agent})}\n\n"
                try:
                    result = await asyncio.wait_for(
                        healing.execute_node(node, ctx), timeout=node.timeout_s)
                except asyncio.TimeoutError:
                    result = NodeResult(node.id, False, error="TIMEOUT")
                except Exception as exc:
                    result = NodeResult(node.id, False, error=f"{type(exc).__name__}: {exc}")
                results[node.id] = result
                yield f"data: {json.dumps({'status': 'completed', 'node': node.id, 'ok': result.ok, 'output': result.output or result.error})}\n\n"

            elapsed = int(time.time() - t0)
            ok_count = sum(1 for r in results.values() if r.ok)
            total = len(results)
            yield f"data: {json.dumps({'status': 'done', 'ok_count': ok_count, 'total': total, 'elapsed': elapsed})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'status': 'error', 'error': str(exc)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.websocket("/ws/thoughts")
async def thought_stream(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            data = await ws.receive_text()
            req = json.loads(data)
            prompt = req.get("prompt", "")
            publish = req.get("publish", False)

            await ws.send_json({"type": "thinking", "text": f"Analyzing: {prompt}"})
            await asyncio.sleep(0.3)

            try:
                from core.executive_director import (
                    build_autonomous_plan, SelfHealingExecutor,
                    AgentContext, NodeResult
                )
                plan = build_autonomous_plan(prompt)
                await ws.send_json({
                    "type": "decomposing",
                    "text": f"DAG ready: {len(plan.nodes)} nodes",
                    "nodes": [{"id": n.id, "agent": n.agent, "deps": n.deps} for n in plan.nodes]
                })

                ctx = AgentContext(goal=plan.goal, dry_run=False, publish=publish)
                healing = SelfHealingExecutor(default_retries=2)
                results = {}
                t0 = time.time()

                for node in plan.topological():
                    await ws.send_json({
                        "type": "node_started", "node": node.id, "agent": node.agent
                    })
                    try:
                        result = await asyncio.wait_for(
                            healing.execute_node(node, ctx), timeout=node.timeout_s)
                    except asyncio.TimeoutError:
                        result = NodeResult(node.id, False, error="TIMEOUT")
                    except Exception as exc:
                        result = NodeResult(node.id, False, error=f"{type(exc).__name__}: {exc}")
                    results[node.id] = result
                    await ws.send_json({
                        "type": "node_completed",
                        "node": node.id,
                        "ok": result.ok,
                        "output": result.output or result.error,
                        "elapsed": int(time.time() - t0),
                    })

                ok_count = sum(1 for r in results.values() if r.ok)
                total = len(results)
                await ws.send_json({
                    "type": "complete",
                    "ok_count": ok_count,
                    "total": total,
                    "elapsed": int(time.time() - t0),
                })
            except Exception as exc:
                await ws.send_json({"type": "error", "error": str(exc)})

    except WebSocketDisconnect:
        pass


@app.get("/api/memory")
async def get_memory_stats():
    from core.memory_engine import get_memory
    mem = get_memory()
    return {"rules": len(mem.rules), "stats": mem.data.get("stats", {})}


@app.get("/api/artifacts")
async def list_artifacts():
    media_dir = Path(__file__).resolve().parent.parent.parent / "webapp" / "backend" / "media"
    video_dir = media_dir / "video"
    artifacts = []
    if video_dir.exists():
        for f in sorted(video_dir.glob("*.mp4"), key=lambda x: x.stat().st_mtime, reverse=True)[:10]:
            artifacts.append({
                "name": f.name,
                "size_mb": round(f.stat().st_size / 1024 / 1024, 2),
                "path": str(f),
            })
    reports_dir = Path(__file__).resolve().parent.parent / "reports"
    youtube_payloads = []
    if reports_dir.exists():
        for f in sorted(reports_dir.glob("yt_*.json"), key=lambda x: x.stat().st_mtime, reverse=True)[:5]:
            try:
                data = json.loads(f.read_text())
                youtube_payloads.append({"name": f.name, "title": data.get("title", ""), "chapters": len(data.get("chapters", []))})
            except Exception:
                pass
    return {"videos": artifacts, "youtube_payloads": youtube_payloads}


@app.get("/api/health/deep")
async def deep_health():
    checks = {}
    import shutil
    checks["ffmpeg"] = shutil.which("ffmpeg") is not None
    checks["docker"] = shutil.which("docker") is not None
    try:
        import httpx
        async with httpx.AsyncClient(timeout=3) as c:
            r = await c.get("http://localhost:11434/api/tags")
            models = [m["name"] for m in r.json().get("models", [])]
            checks["ollama"] = True
            checks["ollama_models"] = models
    except Exception:
        checks["ollama"] = False
        checks["ollama_models"] = []
    try:
        import httpx
        async with httpx.AsyncClient(timeout=3) as c:
            r = await c.get("http://localhost:9876/health")
            checks["cinema_engine"] = r.status_code == 200
    except Exception:
        checks["cinema_engine"] = False
    return checks


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_path = STATIC_DIR / "index.html"
    return HTMLResponse(content=index_path.read_text(encoding="utf-8"))


@app.get("/{full_path:path}")
async def catch_all(full_path: str):
    file_path = STATIC_DIR / full_path
    if file_path.is_file():
        return FileResponse(str(file_path))
    return HTMLResponse(content=(STATIC_DIR / "index.html").read_text(encoding="utf-8"))
