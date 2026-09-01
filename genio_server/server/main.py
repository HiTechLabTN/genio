"""Genio Server Daemon — FastAPI + WebSocket backend for the distributed harness.

The daemon runs on the target node (Pop!_OS GPU box, TN VPS, ...) and exposes:

* ``GET /api/v1/status``       — one-shot JSON snapshot (CPU/RAM/GPU/model/uptime).
* ``GET /api/v1/telemetry``    — SSE stream of real-time CPU/RAM/GPU telemetry.
* ``POST /api/v1/safety``      — kill / re-arm the autonomous actuators.
* ``POST /api/v1/voice/transcribe`` — Phase 3: multipart raw audio → local
  faster-whisper/whisper transcription (gated by GENIO_AUDIO_PIPELINE=1).
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
import logging
import os
import shutil
import subprocess
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

import psutil
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, Header, HTTPException, Query, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from genio_server.core.agent_loop import AgentLoop, OllamaConnectionError
from genio_server.core.session_store import get_session_store
from genio_server.tools import invoke as invoke_tool
from genio_server.tools import safe_cwd
from genio_server.tools import computer_tool
from genio_server.tools.safety import SAFETY

logger = logging.getLogger(__name__)

API_KEY = os.environ.get("GENIO_API_KEY", "")
NODE_NAME = os.environ.get("GENIO_NODE_NAME", "HiTech-Node")
SERVICE_DIR = safe_cwd()

# Runtime environment guard: production REQUIRES an API key.
GENIO_ENV = os.environ.get("GENIO_ENV", "dev").strip().lower()
if GENIO_ENV == "prod" and not API_KEY:
    raise RuntimeError(
        "GENIO_ENV=prod requires GENIO_API_KEY to be set. Refusing to start an "
        "unauthenticated server. Export GENIO_API_KEY=<secret> (or run "
        "`python genio_server.py --api-key <secret>`) and retry."
    )

# CORS allow-list is explicit (defaults to the Tauri dev origin). Never "*".
_CORS_DEFAULT = "http://localhost:1420"
_CORS_CSV = os.environ.get("GENIO_CORS_ORIGINS", "") or _CORS_DEFAULT
CORS_ORIGINS = [o.strip() for o in _CORS_CSV.split(",") if o.strip()] or [_CORS_DEFAULT]

# Latest run stats (heartbeat for the telemetry dock — updated on every run).
LAST_STATS: Dict[str, Any] = {"tokens": 0, "tok_per_s": 0.0}
# Live per-connection state (guards against concurrent agent runs).
_ACTIVE_RUNS: Dict[int, bool] = {}
# Per-connection KILL SWITCH events — setting one halts the in-flight loop.
_KILL_EVENTS: Dict[int, threading.Event] = {}
# Per-connection screenshot streaming tasks.
_SCREEN_TASKS: Dict[int, asyncio.Task] = {}
# Phase D: track session_ids per connection for container cleanup
_SESSION_IDS: Dict[int, set] = {}
_CLEANUP_TASK: Optional[asyncio.Task] = None

app = FastAPI(
    title="Genio Server",
    version="1.0.0",
    description="Distributed Genio harness — ReAct loop, tools and telemetry.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _idle_timeout() -> int:
    return int(os.getenv("GENIO_SESSION_CONTAINER_IDLE_TIMEOUT", "1800"))


async def _periodic_container_cleanup():
    """Phase D: détruit les conteneurs genio-session-* inactifs depuis > timeout."""
    while True:
        await asyncio.sleep(60)
        try:
            from genio_server.tools.session_container import _LAST_USED, cleanup_container, _container_name
            import subprocess as _sp, time as _time, shutil as _sh
            if not _sh.which("docker"):
                continue
            res = _sp.run(["docker", "ps", "--filter", "name=genio-session-", "--format", "{{.Names}}"],
                          capture_output=True, text=True, timeout=5)
            if res.returncode != 0:
                continue
            names = [n.strip() for n in res.stdout.splitlines() if n.strip()]
            now = _time.time()
            timeout = _idle_timeout()
            for name in names:
                for sess_id, last in list(_LAST_USED.items()):
                    if _container_name(sess_id) == name and now - last > timeout:
                        cleanup_container(sess_id)
                        _LAST_USED.pop(sess_id, None)
                        # Also clean cwd map
                        try:
                            from genio_server.tools.session_container import _CWD_MAP
                            _CWD_MAP.pop(sess_id, None)
                        except Exception:
                            pass
                        break
        except Exception:
            pass


@app.on_event("startup")
async def _start_periodic_cleanup():
    global _CLEANUP_TASK
    _CLEANUP_TASK = asyncio.create_task(_periodic_container_cleanup())


@app.on_event("shutdown")
async def _stop_periodic_cleanup():
    global _CLEANUP_TASK
    if _CLEANUP_TASK:
        _CLEANUP_TASK.cancel()
        try:
            await _CLEANUP_TASK
        except asyncio.CancelledError:
            pass


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


async def _telemetry_snapshot_async() -> Dict[str, Any]:
    """Build a telemetry snapshot without blocking the event loop.

    ``psutil`` reads and any subprocess calls (``nvidia-smi``) run in a worker
    thread so the SSE generator / status endpoint keep yielding control even
    while the agent is busy thinking or executing heavy tools.
    """
    vm = psutil.virtual_memory()
    gpu = await asyncio.to_thread(_gpu_stats)
    # Phase E: router state (Q4 endpoints valid as-is)
    router_health = {}
    try:
        from core.model_router import ModelRouter
        router_health = ModelRouter().health()
    except Exception:
        router_health = {}
    return {
        "node": NODE_NAME,
        "hostname": os.uname().nodename,
        "uptime_s": int(time.time() - psutil.boot_time()),
        "cpu_percent": float(psutil.cpu_percent(interval=None)),
        "ram_percent": float(vm.percent),
        "ram_used_gb": round(vm.used / 1e9, 1),
        "ram_total_gb": round(vm.total / 1e9, 1),
        "gpu": gpu,
        "model": AgentLoop().model,
        "mode": os.environ.get("GENIO_MODE", "autonomous"),
        "last_tok_per_s": float(LAST_STATS.get("tok_per_s", 0.0)),
        "clients": sum(_ACTIVE_RUNS.values()),
        "armed": SAFETY.armed,
        "router": router_health,
        "ts": int(time.time()),
    }


@app.get("/api/v1/status")
async def get_status(_: None = Depends(require_key)) -> Dict[str, Any]:
    snap = await _telemetry_snapshot_async()
    # Also expose router separately for clarity
    return snap


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
            yield f"data: {json.dumps(await _telemetry_snapshot_async())}\n\n"
            await asyncio.sleep(1.0)

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/api/v1/sessions/{sid}")
async def get_session(sid: str,
                      _: None = Depends(require_key)) -> Dict[str, Any]:
    """Bounded session checkpoint — last N turns + compressed summary.

    Never returns unbounded raw history (fault-tolerant resume endpoint).
    """
    try:
        session = await get_session_store().load_session(sid)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"session load failed: {exc}")
    if not session.get("exists"):
        raise HTTPException(status_code=404, detail="session not found")
    return session


def _has_multipart() -> bool:
    try:
        import python_multipart  # noqa: F401
        return True
    except ImportError:
        try:
            import multipart  # noqa: F401
            return True
        except ImportError:
            return False

if _has_multipart():
    @app.post("/api/v1/voice/transcribe")
    async def voice_transcribe(
        audio: UploadFile = File(...),
        language: str = "auto",
        _: None = Depends(require_key),
    ) -> Dict[str, Any]:
        """Phase 3 v2.1 — Native audio pipeline transcription endpoint.

        Accepts a multipart upload of raw audio (WAV / WebM/Opus / M4A) and routes
        to the best available local transcriber (faster-whisper > whisper) with a
        deterministic fallback. Gated by ``GENIO_AUDIO_PIPELINE=1``.
        """
        if os.getenv("GENIO_AUDIO_PIPELINE", "0").strip().lower() not in ("1", "true", "yes"):
            raise HTTPException(status_code=403,
                                detail="audio pipeline disabled (set GENIO_AUDIO_PIPELINE=1)")
        data = await audio.read()
        if not data or len(data) == 0:
            raise HTTPException(status_code=400, detail="empty audio payload")
        try:
            from genio_server.server.voice_pipeline import transcribe_audio
            result = await asyncio.to_thread(
                transcribe_audio, data,
                audio.content_type or "audio/wav",
                None if language in ("auto", "") else language,
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"transcription failed: {exc}")
        return result
else:
    @app.post("/api/v1/voice/transcribe")
    async def voice_transcribe(_: None = Depends(require_key)) -> Dict[str, Any]:  # type: ignore[no-redef]
        raise HTTPException(status_code=500,
                            detail='Form data requires "python-multipart" to be installed. pip install python-multipart')


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
# Phase 3 v2.1: conn_id -> last transcribed voice text, injected into the next
# prompt action so the raw audio flows into the agent transcript cleanly.
_PENDING_TRANSCRIPT: Dict[str, str] = {}


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
    _SESSION_IDS[conn_id] = set()
    try:
        while True:
            raw = await ws.receive_text()
            # Yield control back to the event loop so in-flight tasks (the SSE
            # telemetry stream, screen capture loop, kill handling) keep running
            # even while this connection is busy processing a prompt/exec.
            await asyncio.sleep(0)
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
                # Propagate kill to all active runners (global halt)
                for ev in _KILL_EVENTS.values():
                    ev.set()
                # Phase D: destroy containers for killed session(s) immediately
                try:
                    from genio_server.tools.session_container import cleanup_container, _CWD_MAP, _LAST_USED
                    kill_sid = str(msg.get("session_id") or "").strip()
                    if kill_sid:
                        cleanup_container(kill_sid)
                        _CWD_MAP.pop(kill_sid, None)
                        _LAST_USED.pop(kill_sid, None)
                    else:
                        for sid in list(_SESSION_IDS.get(conn_id, set())):
                            cleanup_container(sid)
                            _CWD_MAP.pop(sid, None)
                            _LAST_USED.pop(sid, None)
                except Exception:
                    pass
                await safe_send(ws, {"type": "killed", **SAFETY.snapshot()})
                continue

            if action == "rearm":
                SAFETY.arm()
                _KILL_EVENTS[conn_id].clear()
                await safe_send(ws, {"type": "armed", **SAFETY.snapshot()})
                continue

            if action == "resume":
                # Bounded checkpoint of a previous session (last N turns +
                # compressed summary). NEVER sends unbounded raw history.
                sid = str(msg.get("session_id") or "").strip()
                if not sid:
                    await safe_send(ws, {"type": "error", "message": "missing session_id"})
                    continue
                try:
                    store = get_session_store()
                    session = await store.load_session(sid)
                except Exception as exc:
                    await safe_send(ws, {"type": "error", "message": f"resume failed: {exc}"})
                    continue
                await safe_send(ws, {"type": "session", "session": session})
                continue

            if action == "prompt":
                if _ACTIVE_RUNS.get(conn_id):
                    await safe_send(ws, {"type": "error", "message": "agent is already busy"})
                    continue
                text = str(msg.get("text", "")).strip()
                # Phase 3 v2.1: prepend a pending voice transcript (if any) so
                # the audio pipeline routes into the agent prompt cleanly.
                pending = _PENDING_TRANSCRIPT.pop(str(conn_id), "")
                if pending and pending not in text:
                    text = (pending + "\n" + text).strip() if text else pending
                if not text:
                    await safe_send(ws, {"type": "error", "message": "empty prompt"})
                    continue
                _ACTIVE_RUNS[conn_id] = True
                sid = str(msg.get("session_id") or "").strip() or None
                if sid:
                    _SESSION_IDS.setdefault(conn_id, set()).add(sid)
                agent = AgentLoop(
                    mode=str(msg.get("mode", "autonomous")),
                    cancel_event=_KILL_EVENTS[conn_id],
                    session_id=sid,
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
                    # Phase 3 v2.1: transcribe the raw audio and cache the
                    # result so the next prompt action can route it cleanly.
                    pending = _PENDING_TRANSCRIPT.pop(str(conn_id), "")
                    if os.getenv("GENIO_AUDIO_PIPELINE", "0").strip().lower() \
                            in ("1", "true", "yes"):
                        try:
                            from genio_server.server.voice_pipeline import transcribe_audio
                            with open(path, "rb") as fh:
                                audio_bytes = fh.read()
                            res = await asyncio.to_thread(
                                transcribe_audio, audio_bytes, "audio/wav", None)
                            pending = (pending + " " + str(res.get("text") or "")) \
                                if pending and res.get("text") else \
                                (str(res.get("text") or "") or pending)
                        except Exception:
                            logger.exception("voice transcription failed")
                    if pending:
                        _PENDING_TRANSCRIPT[str(conn_id)] = pending
                    await safe_send(ws, {"type": "voice_ready", "path": path,
                                         "duration": float(msg.get("duration", 0.0)),
                                         "transcript": pending or None})
                continue

            if action == "exec":
                # "target system commands" — run bash directly without the LLM.
                command = str(msg.get("command", "")).strip()
                if not command:
                    await safe_send(ws, {"type": "error", "message": "empty command"})
                    continue
                await safe_send(ws, {"type": "tool_call", "command": command})
                sid = str(msg.get("session_id") or "").strip() or None
                if sid:
                    _SESSION_IDS.setdefault(conn_id, set()).add(sid)
                result = await asyncio.to_thread(invoke_tool, "bash", command, sid)
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
        _PENDING_TRANSCRIPT.pop(str(conn_id), None)
        # Phase D: cleanup containers for this connection's sessions
        for sid in _SESSION_IDS.pop(conn_id, set()):
            try:
                from genio_server.tools.session_container import cleanup_container
                cleanup_container(sid)
                # Also clean cwd/last_used tracking
                try:
                    from genio_server.tools.session_container import _CWD_MAP, _LAST_USED
                    _CWD_MAP.pop(sid, None)
                    _LAST_USED.pop(sid, None)
                except Exception:
                    pass
            except Exception:
                pass


# --------------------------------------------------------------------------- #
# Service info
# --------------------------------------------------------------------------- #
@app.get("/")
def root() -> Dict[str, Any]:
    return {
        "service": "Genio Server",
        "version": app.version,
        "node": NODE_NAME,
        "endpoints": ["/api/v1/status", "/api/v1/telemetry", "/api/v1/voice/transcribe", "/ws/agent"],
        "auth_required": bool(API_KEY),
        "model": AgentLoop().model,
    }