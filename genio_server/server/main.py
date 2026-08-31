"""Genio Server Daemon — FastAPI + WebSocket backend for the distributed harness.

The daemon runs on the target node (Pop!_OS GPU box, TN VPS, ...) and exposes:

* ``GET /api/v1/status``       — one-shot JSON snapshot (CPU/RAM/GPU/model/uptime).
* ``GET /api/v1/telemetry``    — SSE stream of real-time CPU/RAM/GPU telemetry.
* ``POST /api/v1/safety``      — kill / re-arm the autonomous actuators.
* ``WS /ws/agent``             — bidirectional agent channel:
    * client → server: ``{"action":"prompt"|"attach_file"|"attach_image"|
      "voice_wav"|"exec"|"screenshot"|"screen_stream"|"kill"|"rearm"|"ping"}``
    * server → client: ``{"type":"thought"|"tool_call"|"tool_result"|
      "stats"|"answer"|"screen"|"error"|"attached"|"voice_ready"|"killed"|...}``

Security: set ``GENIO_API_KEY`` (or run ``genio_server.py --api-key``) to require
an ``X-API-Key`` header on every HTTP request and WebSocket upgrade.
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import shutil
import subprocess
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

import psutil
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from genio_server.core.agent_loop import AgentLoop, OllamaConnectionError
from genio_server.tools import invoke as invoke_tool
from genio_server.tools import safe_cwd
from genio_server.tools import computer_tool
from genio_server.tools.safety import SAFETY

API_KEY = os.environ.get("GENIO_API_KEY", "")
NODE_NAME = os.environ.get("GENIO_NODE_NAME", "HiTech-Node")
SERVICE_DIR = safe_cwd()

# Latest run stats (heartbeat for the telemetry dock — updated on every run).
LAST_STATS: Dict[str, Any] = {"tokens": 0, "tok_per_s": 0.0}
# Live per-connection state (guards against concurrent agent runs).
_ACTIVE_RUNS: Dict[int, bool] = {}
# Per-connection KILL SWITCH events — setting one halts the in-flight loop.
_KILL_EVENTS: Dict[int, threading.Event] = {}
# Per-connection screenshot streaming tasks.
_SCREEN_TASKS: Dict[int, asyncio.Task] = {}

app = FastAPI(
    title="Genio Server",
    version="1.0.0",
    description="Distributed Genio harness — ReAct loop, tools and telemetry.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------- #
# Auth helpers
# --------------------------------------------------------------------------- #
def _authorized(key: Optional[str]) -> bool:
    if not API_KEY:
        return True
    return bool(key) and key == API_KEY


def require_key(
    x_api_key: Optional[str] = Header(default=None),
) -> None:
    if not _authorized(x_api_key):
        raise HTTPException(status_code=401, detail="invalid or missing API key")


def _ws_authorized(ws: WebSocket) -> bool:
    if not API_KEY:
        return True
    header_key = ws.headers.get("x-api-key")
    query_key = ws.query_params.get("key")
    return _authorized(header_key) or _authorized(query_key)


# --------------------------------------------------------------------------- #
# Telemetry
# --------------------------------------------------------------------------- #
def _gpu_stats() -> Dict[str, Any]:
    info = {"name": "unknown", "used_gb": 0.0, "total_gb": 0.0, "vram_pct": 0}
    try:
        key_tool = shutil.which("nvidia-smi")
        if not key_tool:
            return info
        out = subprocess.run(
            [key_tool, "--query-gpu=name,memory.used,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=3,
        )
        if out.returncode != 0:
            return info
        name, used, total = [p.strip() for p in out.stdout.strip().splitlines()[0].split(",")]
        info = {
            "name": name,
            "used_gb": round(int(used) / 1024.0, 1),
            "total_gb": round(int(total) / 1024.0, 1),
            "vram_pct": int(round(int(used) / int(total) * 100)) if int(total) else 0,
        }
    except Exception:
        pass
    return info


def _telemetry_snapshot() -> Dict[str, Any]:
    vm = psutil.virtual_memory()
    return {
        "node": NODE_NAME,
        "hostname": os.uname().nodename,
        "uptime_s": int(time.time() - psutil.boot_time()),
        "cpu_percent": float(psutil.cpu_percent(interval=None)),
        "ram_percent": float(vm.percent),
        "ram_used_gb": round(vm.used / 1e9, 1),
        "ram_total_gb": round(vm.total / 1e9, 1),
        "gpu": _gpu_stats(),
        "model": AgentLoop().model,
        "mode": os.environ.get("GENIO_MODE", "autonomous"),
        "last_tok_per_s": float(LAST_STATS.get("tok_per_s", 0.0)),
        "clients": sum(_ACTIVE_RUNS.values()),
        "armed": SAFETY.armed,
        "ts": int(time.time()),
    }


@app.get("/api/v1/status")
def get_status(_: None = Depends(require_key)) -> Dict[str, Any]:
    return _telemetry_snapshot()


@app.get("/api/v1/safety")
def get_safety(_: None = Depends(require_key)) -> Dict[str, Any]:
    return {"ok": True, **SAFETY.snapshot()}


@app.post("/api/v1/safety")
async def set_safety(payload: Dict[str, Any],
                     _: None = Depends(require_key)) -> Dict[str, Any]:
    action = payload.get("action")
    if action == "kill":
        SAFETY.halt(str(payload.get("reason") or "HTTP kill"))
        for ev in _KILL_EVENTS.values():
            ev.set()
        return {"ok": True, **SAFETY.snapshot()}
    if action == "arm":
        SAFETY.arm()
        for ev in _KILL_EVENTS.values():
            ev.clear()
        return {"ok": True, **SAFETY.snapshot()}
    raise HTTPException(status_code=400, detail="action must be 'kill' or 'arm'")


@app.get("/api/v1/telemetry")
def telemetry_stream(_: None = Depends(require_key)) -> StreamingResponse:
    """SSE stream of live CPU / RAM / GPU telemetry (one event per second)."""

    async def gen():
        while True:
            yield f"data: {json.dumps(_telemetry_snapshot())}\n\n"
            await asyncio.sleep(1.0)

    return StreamingResponse(gen(), media_type="text/event-stream")


# --------------------------------------------------------------------------- #
# Payload handling
# --------------------------------------------------------------------------- #
def _decode_payload(data_b64: str) -> bytes:
    return base64.b64decode(data_b64)


def _save_attachment(kind: str, name: str, data_b64: str) -> str:
    data = _decode_payload(data_b64)
    ext = os.path.splitext(name)[1]
    path = SERVICE_DIR / "tmp" / f"{kind}_{uuid.uuid4().hex[:8]}{ext}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return str(path)


def _save_wav(data_b64: str, session_id: str, final: bool) -> Optional[str]:
    state = _VOICE_STATE.setdefault(session_id, bytearray())
    state.extend(_decode_payload(data_b64))
    if not final:
        return None
    wav_path = SERVICE_DIR / "tmp" / f"voice_{uuid.uuid4().hex[:8]}.wav"
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    wav_path.write_bytes(bytes(state))
    _VOICE_STATE.pop(session_id, None)
    return str(wav_path)


_VOICE_STATE: Dict[str, bytearray] = {}


# --------------------------------------------------------------------------- #
# Screen frame streaming
# --------------------------------------------------------------------------- #
def _capture_screen_png() -> Optional[bytes]:
    """Capture the host display to PNG bytes (via mss)."""
    try:
        import io
        shot = computer_tool.screenshot()
        if isinstance(shot, dict) and shot.get("path"):
            return open(shot["path"], "rb").read()
        return None
    except Exception:
        return None


async def _screen_stream_loop(ws: WebSocket, conn_id: int, interval: float = 1.0) -> None:
    while True:
        frame = await asyncio.to_thread(_capture_screen_png)
        if frame is None:
            await safe_send(ws, {"type": "error",
                                 "message": "screen capture failed — empty display?"})
            return
        if not await safe_send(ws, {"type": "screen",
                                    "data_b64": base64.b64encode(frame).decode()}):
            return  # socket closed
        await asyncio.sleep(interval)


def _stop_screen_task(conn_id: int) -> None:
    task = _SCREEN_TASKS.pop(conn_id, None)
    if task is not None:
        task.cancel()


# --------------------------------------------------------------------------- #
# Agent WebSocket
# --------------------------------------------------------------------------- #
async def safe_send(ws: WebSocket, payload: dict) -> bool:
    """Send JSON over WebSocket only if still connected. Returns False if socket is closed."""
    try:
        if ws.client_state.name == "CONNECTED":
            await ws.send_json(payload)
            return True
    except Exception:
        pass
    return False


def _emit(ws: WebSocket, event: Dict[str, Any]) -> None:
    try:
        asyncio.get_running_loop().create_task(safe_send(ws, event))
    except Exception:
        pass  # socket already closed — events are best-effort here


@app.websocket("/ws/agent")
async def ws_agent(ws: WebSocket, node: str = Query(default=None)) -> None:
    await ws.accept()
    if not _ws_authorized(ws):
        await safe_send(ws, {"type": "error", "message": "invalid or missing API key"})
        await ws.close(code=4401)
        return

    conn_id = id(ws)
    _ACTIVE_RUNS[conn_id] = False
    _KILL_EVENTS[conn_id] = threading.Event()
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await safe_send(ws, {"type": "error", "message": "invalid JSON payload"})
                continue

            action = msg.get("action")
            if action == "ping":
                await safe_send(ws, {"type": "pong", "node": node or NODE_NAME, "ts": int(time.time())})
                continue

            if action == "screenshot":
                frame = await asyncio.to_thread(_capture_screen_png)
                if frame is None:
                    await safe_send(ws, {"type": "error",
                                         "message": "screen capture failed — empty display?"})
                else:
                    await safe_send(ws, {"type": "screen",
                                         "data_b64": base64.b64encode(frame).decode()})
                continue

            if action == "screen_stream":
                active = bool(msg.get("active", False))
                interval = max(float(msg.get("interval", 1.0)), 0.3)
                _stop_screen_task(conn_id)
                if active:
                    _SCREEN_TASKS[conn_id] = asyncio.create_task(
                        _screen_stream_loop(ws, conn_id, interval))
                await safe_send(ws, {"type": "screen_stream", "active": active,
                                     "interval": interval})
                continue

            if action == "kill":
                SAFETY.halt(str(msg.get("reason") or "KILL SWITCH — operator"))
                _KILL_EVENTS[conn_id].set()
                await safe_send(ws, {"type": "killed", **SAFETY.snapshot()})
                continue

            if action == "rearm":
                SAFETY.arm()
                _KILL_EVENTS[conn_id].clear()
                await safe_send(ws, {"type": "armed", **SAFETY.snapshot()})
                continue

            if action == "prompt":
                if _ACTIVE_RUNS.get(conn_id):
                    await safe_send(ws, {"type": "error", "message": "agent is already busy"})
                    continue
                text = str(msg.get("text", "")).strip()
                if not text:
                    await safe_send(ws, {"type": "error", "message": "empty prompt"})
                    continue
                _ACTIVE_RUNS[conn_id] = True
                agent = AgentLoop(
                    mode=str(msg.get("mode", "autonomous")),
                    cancel_event=_KILL_EVENTS[conn_id],
                )
                try:
                    async for event in agent.run(text):
                        if not await safe_send(ws, event):
                            break
                        if event.get("type") == "stats":
                            LAST_STATS.update(
                                tokens=event.get("tokens", 0),
                                tok_per_s=event.get("tok_per_s", 0.0),
                            )
                except OllamaConnectionError as exc:
                    await safe_send(ws, {"type": "error", "message": str(exc)})
                except Exception as exc:  # never let one run kill the socket
                    await safe_send(ws, {"type": "error", "message": f"agent run failed: {exc}"})
                finally:
                    _ACTIVE_RUNS[conn_id] = False
                continue

            if action == "attach_file":
                name = str(msg.get("name", "file.bin"))
                path = _save_attachment("file", name, msg["data_b64"])
                await safe_send(ws, {"type": "attached", "kind": "file", "path": path,
                                     "name": name, "size": len(_decode_payload(msg["data_b64"]))})
                continue

            if action == "attach_image":
                name = str(msg.get("name", "image.png"))
                path = _save_attachment("img", name, msg["data_b64"])
                await safe_send(ws, {"type": "attached", "kind": "image", "path": path,
                                     "name": name, "size": len(_decode_payload(msg["data_b64"]))})
                continue

            if action == "voice_wav":
                final = bool(msg.get("final", True))
                path = _save_wav(msg["data_b64"], str(conn_id), final)
                if path:
                    await safe_send(ws, {"type": "voice_ready", "path": path,
                                         "duration": float(msg.get("duration", 0.0))})
                continue

            if action == "exec":
                # "target system commands" — run bash directly without the LLM.
                command = str(msg.get("command", "")).strip()
                if not command:
                    await safe_send(ws, {"type": "error", "message": "empty command"})
                    continue
                await safe_send(ws, {"type": "tool_call", "command": command})
                result = invoke_tool("bash", command)
                await safe_send(ws, {"type": "tool_result", "result": result})
                continue

            await safe_send(ws, {"type": "error",
                                 "message": f"unknown action '{action}' "
                                            "(prompt|attach_file|attach_image|voice_wav|exec|ping)"})
    except WebSocketDisconnect:
        pass
    finally:
        _stop_screen_task(conn_id)
        _ACTIVE_RUNS.pop(conn_id, None)
        _KILL_EVENTS.pop(conn_id, None)
        _VOICE_STATE.pop(str(conn_id), None)


# --------------------------------------------------------------------------- #
# Service info
# --------------------------------------------------------------------------- #
@app.get("/")
def root() -> Dict[str, Any]:
    return {
        "service": "Genio Server",
        "version": app.version,
        "node": NODE_NAME,
        "endpoints": ["/api/v1/status", "/api/v1/telemetry", "/ws/agent"],
        "auth_required": bool(API_KEY),
        "model": AgentLoop().model,
    }