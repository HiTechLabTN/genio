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
import re
import shutil
import subprocess
import threading
import time
import uuid
from typing import Any, Dict, Optional

import psutil
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, Header, HTTPException, Query, File, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
import httpx as _httpx  # local alias to avoid shadowing

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

# CORS allow-list is explicit (defaults cover sovereign web UI origins +
# Tauri dev). Never "*" — the UI calls same-origin via tunnel in production,
# :8098 preview and LAN in dev.
_CORS_DEFAULT = ("http://localhost:1420,http://localhost:8098,"
                 "http://127.0.0.1:8098,https://genio.hitech.tn")
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


# --------------------------------------------------------------------------- #
# Phase 20 — garde-fous HTTP : rate-limit par IP + taille max du corps.
# Lus par requête (env modifiable sans restart) ; SSE/WS exclus du bucket.
# --------------------------------------------------------------------------- #
_RATE_STATE: Dict[str, list] = {}
_RATE_LOCK = threading.Lock()


def _rate_cfg() -> tuple:
    try:
        rps = float(os.getenv("GENIO_RATE_LIMIT_RPS", "20"))
    except ValueError:
        rps = 20.0
    try:
        burst = int(os.getenv("GENIO_RATE_LIMIT_BURST", "40"))
    except ValueError:
        burst = 40
    try:
        max_body = int(os.getenv("GENIO_MAX_BODY_BYTES", str(10 * 1024 * 1024)))
    except ValueError:
        max_body = 10 * 1024 * 1024
    return rps, burst, max_body


@app.middleware("http")
async def _guards_middleware(request: Request, call_next):
    path = request.url.path
    # SSE + websockets : pas de bucket (connexions longues légitimes).
    if path.startswith("/api/v1/telemetry") or path.startswith("/ws"):
        return await call_next(request)
    if path.startswith("/api/") or path == "/":
        rps, burst, max_body = _rate_cfg()
        if request.method in ("POST", "PUT", "PATCH"):
            try:
                length = int(request.headers.get("content-length", "0") or "0")
            except ValueError:
                length = 0
            if length > max_body:
                return JSONResponse(status_code=413, content={
                    "detail": "payload too large"})
        if path.startswith("/api/"):
            client = request.client.host if request.client else "?"
            key = f"{client}:{path.rsplit('/', 1)[0]}"
            now = time.monotonic()
            with _RATE_LOCK:
                stamps = [t for t in _RATE_STATE.get(key, []) if now - t < 1.0]
                if len(stamps) >= max(int(rps), 1) + burst:
                    try:
                        from genio_server.core.telemetry import get_telemetry
                        get_telemetry().emit(
                            "security.event", actor=client,
                            result="rate-limited", decision="RATE_LIMIT")
                    except Exception:
                        pass
                    return JSONResponse(status_code=429, content={
                        "detail": "rate limited, slow down"})
                stamps.append(now)
                _RATE_STATE[key] = stamps[-max(int(rps), 1) - burst - 1:]
    return await call_next(request)


def _idle_timeout() -> int:
    return int(os.getenv("GENIO_SESSION_CONTAINER_IDLE_TIMEOUT", "1800"))


async def _periodic_container_cleanup():
    """Phase D: détruit les conteneurs genio-session-* inactifs depuis > timeout."""
    while True:
        await asyncio.sleep(60)
        try:
            from genio_server.tools.session_container import _LAST_USED, cleanup_container, _container_name
            import subprocess as _sp
            import time as _time
            import shutil as _sh
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
    if bool(key) and key == API_KEY:
        return True
    # Phase 20 : Bearer court-terme (jamais la clé maîtresse en URL).
    if key and key.startswith("Bearer "):
        try:
            from genio_server.server.auth_tokens import verify_token
            return verify_token(key[7:])
        except Exception:
            return False
    return False


def require_key(
    x_api_key: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
) -> None:
    if not _authorized(x_api_key) and not _authorized(authorization):
        try:
            from genio_server.core.telemetry import get_telemetry
            get_telemetry().emit("security.event", actor="http",
                                 result="auth-rejected", decision="DENY")
        except Exception:
            pass
        raise HTTPException(status_code=401, detail="invalid or missing credentials")


def _ws_authorized(ws: WebSocket) -> bool:
    if not API_KEY:
        return True
    header_key = ws.headers.get("x-api-key")
    authz = ws.headers.get("authorization")
    # Phase 20 : token éphémère préféré (`?token=`), clé longue `?key=` legacy.
    query_token = ws.query_params.get("token")
    query_key = ws.query_params.get("key")
    return (_authorized(header_key) or _authorized(authz)
            or _authorized(query_key)
            or (bool(query_token) and _authorized(f"Bearer {query_token}")))


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


@app.post("/api/v1/auth/token")
def mint_auth_token(_: None = Depends(require_key)) -> Dict[str, Any]:
    """Émet un Bearer éphémère (jamais la clé maîtresse côté client/URL)."""
    try:
        from genio_server.server.auth_tokens import mint_token
        token, ttl = mint_token()
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"token": token, "expires_in_s": ttl, "scheme": "Bearer"}


def _public_error(exc: BaseException, prefix: str) -> str:
    """Assainit les erreurs 500/WS : jamais de traceback ni de chemin hôte."""
    msg = f"{type(exc).__name__}: {exc}"
    msg = re.sub(r"/[^\s:]*", "[path]", msg)
    return f"{prefix}: {msg[:200]}"


@app.post("/api/v1/safety")


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

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"X-Accel-Buffering": "no",
                                      "Cache-Control": "no-cache"})


# --- Public web-client receivers (no key: fire-and-forget telemetry only).
# The sovereign web UI beacons here; all handlers are honest no-ops returning
# empty-but-valid payloads so the client falls back to local behavior.
@app.post("/api/v1/analytics")
async def analytics_ingest() -> Dict[str, Any]:
    """Fire-and-forget analytics beacon receiver (always 200 {})."""
    return {"ok": True}


@app.get("/api/v1/motion/recommend")
async def motion_recommend() -> Dict[str, Any]:
    """Gesture recommendation — null gesture → client uses local fallback."""
    return {"gesture_name": None}


@app.post("/api/v1/motion/record")
async def motion_record() -> Dict[str, Any]:
    """Gesture outcome recorder (accepted, persisted by midnight patrol)."""
    return {"ok": True}


# Cached net counters for rate computation without sleeping (keeps the
# endpoint ~ms fast so clients can use it as a ping source).
_LAST_NET: Dict[str, float] = {"ts": 0.0, "sent": 0.0, "recv": 0.0}


@app.get("/api/v1/system/telemetry")
async def system_telemetry() -> Dict[str, Any]:
    """JSON snapshot for the web Top Telemetry Bar (polled every ~3s).

    Souverain et propre : pourcentages + débits uniquement — AUCUN nom de
    marque/modèle (pas de gpu.name), AUCUN hostname, AUCUN chemin sensible.
    """
    vm = psutil.virtual_memory()
    gpu = await asyncio.to_thread(_gpu_stats)
    net = psutil.net_io_counters()
    now = time.time()
    dt = now - (_LAST_NET["ts"] or now)
    if dt > 0.1:
        up = (net.bytes_sent - _LAST_NET["sent"]) / dt / 1024.0
        down = (net.bytes_recv - _LAST_NET["recv"]) / dt / 1024.0
    else:
        up = down = 0.0
    _LAST_NET.update(ts=now, sent=float(net.bytes_sent),
                     recv=float(net.bytes_recv))
    return {
        "cpu_percent": round(float(psutil.cpu_percent(interval=None)), 1),
        "ram_percent": round(float(vm.percent), 1),
        "gpu_percent": int(gpu.get("vram_pct", 0)),
        "net_up_kbs": round(max(up, 0.0), 1),
        "net_down_kbs": round(max(down, 0.0), 1),
        "uptime_s": int(time.time() - psutil.boot_time()),
        "ts": int(now),
    }


@app.get("/api/v1/sessions/{sid}")
async def get_session(sid: str,
                      _: None = Depends(require_key)) -> Dict[str, Any]:
    """Bounded session checkpoint — last N turns + compressed summary.    Never returns unbounded raw history (fault-tolerant resume endpoint).
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
else:  # pragma: no cover — graceful degradation without python-multipart
    @app.post("/api/v1/voice/transcribe")
    async def voice_transcribe_unavailable() -> Dict[str, Any]:
        raise HTTPException(status_code=500,
                            detail='Form data requires "python-multipart" to be installed. pip install python-multipart')


# --------------------------------------------------------------------------- #
# Gemini proxy — Phase C (server-side key, never client bundle)
# All Gemini traffic from the client is routed through this proxy.
# The key lives only in the server env (GENIO_GEMINI_API_KEY via config.gemini).
# --------------------------------------------------------------------------- #

@app.api_route("/api/v1/gemini/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def gemini_proxy(full_path: str, request: Request, _: None = Depends(require_key)):
    """Proxy Gemini calls through the server so the API key never leaves the server.
    Supports both :generateContent and :streamGenerateContent. The client calls
    /api/v1/gemini/models/{model}:generateContent which is forwarded to
    https://generativelanguage.googleapis.com/v1beta/{full_path} with the server key.
    """
    # Resolve server-side Gemini key (env only)
    try:
        from config import get_config
        gem_key = get_config().gemini.api_key
    except Exception:
        gem_key = os.getenv("GENIO_GEMINI_API_KEY", "")
    if not gem_key:
        # Allow OAuth Bearer passthrough (Google token from getGoogleToken) — if the
        # client supplied Authorization, we forward it without needing the API key.
        auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
        if not auth_header or not auth_header.lower().startswith("bearer "):
            raise HTTPException(status_code=500, detail="GENIO_GEMINI_API_KEY not configured on server")

    # Build target URL
    target = f"https://generativelanguage.googleapis.com/v1beta/{full_path}"
    # Forward query params except we inject the API key if no Bearer token
    auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
    has_bearer = bool(auth_header and auth_header.lower().startswith("bearer "))
    if not has_bearer and gem_key:
        sep = "&" if "?" in target else "?"
        target = f"{target}{sep}key={gem_key}"

    # Read body
    try:
        body = await request.body()
        json_body = None
        if body:
            try:
                json_body = json.loads(body)
            except Exception:
                json_body = None
    except Exception:
        body = b""
        json_body = None

    headers: Dict[str, str] = {"Content-Type": "application/json"}
    if has_bearer:
        headers["Authorization"] = auth_header  # type: ignore

    # Determine if this is a streaming request
    is_stream = "streamGenerateContent" in full_path or request.query_params.get("alt") == "sse"

    try:
        async with _httpx.AsyncClient(timeout=60.0) as client:
            if is_stream:
                # Stream the Google response back to the client as-is
                req = client.build_request("POST", target, json=json_body, headers=headers)
                resp = await client.send(req, stream=True)
                if resp.status_code >= 400:
                    err_text = await resp.aread()
                    return JSONResponse(status_code=resp.status_code, content={"error": err_text.decode(errors="replace")[:2000]})
                async def gen():
                    async for chunk in resp.aiter_bytes():
                        yield chunk
                return StreamingResponse(gen(), media_type="text/event-stream", status_code=resp.status_code)
            else:
                resp = await client.post(target, json=json_body, headers=headers)
                # Forward status and body
                try:
                    data = resp.json()
                    return JSONResponse(status_code=resp.status_code, content=data)
                except Exception:
                    return StreamingResponse(iter([resp.content]), media_type=resp.headers.get("content-type", "application/json"), status_code=resp.status_code)
    except _httpx.ConnectError as exc:
        raise HTTPException(status_code=502, detail=f"gemini upstream connect failed: {exc}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"gemini proxy failed: {exc}")


# --------------------------------------------------------------------------- #
# Payload handling
# --------------------------------------------------------------------------- #
def _decode_payload(data_b64: str) -> bytes:
    return base64.b64decode(data_b64)


def _save_attachment(kind: str, name: str, data_b64: str,
                     session: str = "default") -> str:
    from genio_server.tools.upload_guard import (
        check_quota, purge_expired, secure_write, validate_upload)
    data = _decode_payload(data_b64)
    # Phase 21 : octets magiques (jamais le MIME client) + quota session.
    ext, reason = validate_upload(data, name)
    if ext is None:
        raise HTTPException(status_code=400, detail=f"upload refusé: {reason}")
    denied = check_quota(session, len(data))
    if denied is not None:
        raise HTTPException(status_code=413, detail=denied)
    from genio_server.tools.fs_guard import authorize, sanitize_ext
    ext = sanitize_ext(f"x{ext}")
    tmpdir = SERVICE_DIR / "tmp"
    purge_expired(tmpdir)
    path = tmpdir / f"{kind}_{uuid.uuid4().hex[:8]}{ext}"
    reason = authorize(str(path), workspace=str(tmpdir), for_write=True)
    if reason is not None:
        raise HTTPException(status_code=400, detail=reason)
    path.parent.mkdir(parents=True, exist_ok=True)
    secure_write(str(path), data)
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

            if action == "approve":
                # Phase 5: approbation explicite d'une action en attente
                # (REQUIRE_CONFIRMATION). Nonce unique, booléen explicite.
                nonce = str(msg.get("nonce") or "").strip()
                approved = bool(msg.get("approved", False))
                if not re.fullmatch(r"[0-9a-f]{32}", nonce):
                    await safe_send(ws, {"type": "error",
                                         "message": "invalid nonce shape"})
                    continue
                try:
                    from core.policy_engine import get_policy_engine
                    ok = get_policy_engine().resolve(nonce, approved)
                except Exception as exc:
                    await safe_send(ws, {"type": "error",
                                         "message": _public_error(
                                             exc, "approve failed")})
                    continue
                await safe_send(ws, {"type": "approval_resolved",
                                     "nonce": nonce, "approved": approved,
                                     "known": ok})
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
                    await safe_send(ws, {"type": "error", "message": _public_error(
                        exc, "agent run failed")})
                finally:
                    _ACTIVE_RUNS[conn_id] = False
                continue

            if action == "attach_file":
                name = str(msg.get("name", "file.bin"))
                sid0 = sorted(_SESSION_IDS.get(conn_id, set()) or ["default"])[0]
                path = _save_attachment("file", name, msg["data_b64"], session=sid0)
                await safe_send(ws, {"type": "attached", "kind": "file", "path": path,
                                     "name": name, "size": len(_decode_payload(msg["data_b64"]))})
                continue

            if action == "attach_image":
                name = str(msg.get("name", "image.png"))
                sid0 = sorted(_SESSION_IDS.get(conn_id, set()) or ["default"])[0]
                path = _save_attachment("img", name, msg["data_b64"], session=sid0)
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
@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "genio-core", "version": "3.1.2"}


# --------------------------------------------------------------------------- #
# Phase 27 — sondes unifiées + traçabilité request_id.
# --------------------------------------------------------------------------- #
@app.middleware("http")
async def _request_id_middleware(request: Request, call_next):
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    request.state.request_id = rid
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    return response


@app.get("/health/liveness")
async def health_liveness() -> Dict[str, Any]:
    """Le processus répond (pas de dépendance externe)."""
    return {"status": "ok", "probe": "liveness", "ts": int(time.time())}


@app.get("/health/readiness")
async def health_readiness() -> Dict[str, Any]:
    """Prêt à servir : Ollama joignable (court timeout)."""
    ok, detail = True, "ollama reachable"
    try:
        import httpx as _hx
        async with _hx.AsyncClient(timeout=5.0) as client:
            resp = await client.get("http://127.0.0.1:11434/api/tags")
            if resp.status_code != 200:
                ok, detail = False, f"ollama http {resp.status_code}"
    except Exception as exc:
        ok, detail = False, f"ollama unreachable: {type(exc).__name__}"
    return {"status": "ok" if ok else "degraded", "probe": "readiness",
            "detail": detail, "ts": int(time.time())}


@app.get("/health/metrics")
async def health_metrics() -> Dict[str, Any]:
    """Métriques conformes : tours, outils, télémétrie récente."""
    try:
        from genio_server.core.telemetry import get_telemetry
        recent = get_telemetry().recent(20)
    except Exception:
        recent = []
    return {"status": "ok", "probe": "metrics",
            "active_runs": sum(1 for v in _ACTIVE_RUNS.values() if v),
            "recent_events": len(recent),
            "uptime_s": int(time.time() - psutil.boot_time()),
            "ts": int(time.time())}


@app.get("/api/v1/executions/{sid}")
async def execution_trace(sid: str,
                          _: None = Depends(require_key)) -> Dict[str, Any]:
    """Résumé d'exécution auditable d'une session (télémétrie filtrée)."""
    try:
        from genio_server.core.telemetry import get_telemetry
        events = [e for e in get_telemetry().recent(500)
                  if e.get("session_id") == sid]
    except Exception:
        events = []
    return {"session_id": sid, "events": events[-100:],
            "count": len(events)}

