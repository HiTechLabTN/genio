"""Genio — FastAPI Backend with SSE Streaming, WebSocket & Tool Calling.

Provides the web API for the Genio Jarvis HUD interface.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
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


class PromptRequest(BaseModel):
    prompt: str
    auto: bool = False
    publish: bool = True


@app.get("/health")
async def health():
    return {"status": "healthy", "version": "4.0.0"}


@app.post("/api/generate")
async def generate(req: PromptRequest):
    from core.executive_director import execute_autonomous
    report, plan, results, ctx = await execute_autonomous(
        req.prompt, publish=req.publish)
    return {
        "report": report,
        "plan": plan.to_json(),
        "results": {k: {"ok": v.ok, "output": v.output, "error": v.error}
                    for k, v in results.items()},
    }


@app.post("/api/generate/stream")
async def generate_stream(req: PromptRequest):
    async def event_generator():
        yield f"data: {json.dumps({'status': 'started', 'prompt': req.prompt})}\n\n"
        try:
            from core.executive_director import execute_autonomous
            report, plan, results, ctx = await execute_autonomous(
                req.prompt, publish=req.publish)
            yield f"data: {json.dumps({'status': 'completed', 'report': report[:2000]})}\n\n"
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
            await ws.send_json({"type": "thinking", "text": "Analyzing request..."})
            await asyncio.sleep(0.5)
            await ws.send_json({"type": "decomposing", "text": "Building DAG..."})
            await asyncio.sleep(0.5)
            await ws.send_json({"type": "executing", "text": "Running pipeline..."})
            from core.executive_director import execute_autonomous
            report, plan, results, ctx = await execute_autonomous(
                req.get("prompt", ""), publish=req.get("publish", True))
            await ws.send_json({"type": "complete", "report": report[:2000]})
    except WebSocketDisconnect:
        pass


@app.get("/api/memory")
async def get_memory_stats():
    from core.memory_engine import get_memory
    mem = get_memory()
    return {"rules": len(mem.rules), "stats": mem.data.get("stats", {})}


@app.post("/api/feedback")
async def record_feedback(feedback: str):
    from core.memory_engine import get_memory
    added = get_memory().record_feedback(feedback)
    return {"added": added, "total_rules": len(get_memory().rules)}
