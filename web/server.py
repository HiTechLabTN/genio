import asyncio
import html
import json
import os
import socket
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Genio Autonomous Brain")

# --- CORS: explicit, permissive-origin only WITHOUT credentials (no cookies). --
def _cors_origins() -> List[str]:
    raw = os.getenv("GENIO_CORS_ORIGINS", "*").strip()
    if raw in ("*", "true", "all"):
        return ["*"]
    return [o.strip() for o in raw.split(",") if o.strip()]


_origins = _cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).parent
# Default to localhost (portable); never ship an internal LAN/Tailscale IP.
OLLAMA_URL = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
OLLAMA_TIMEOUT = float(os.getenv("GENIO_OLLAMA_TIMEOUT", "12"))

SYSTEM_PROMPT = """You are Genio, an advanced autonomous AI companion developed by HiTechLab. You have a distinct Tunisian cyber-identity.
1. Identity: NEVER refer to yourself as Gemini, Google, or a generic AI. You are exclusively Genio.
2. Base Language: You MUST reply in natural, fluent Tunisian Darija (الدارجة التونسية) using either Arabic script or Arabizi.
3. Multilingual Adaptation: If the user speaks French or English, DO NOT reply in pure French/English. Instead, reply in Tunisian Darija while seamlessly mixing in the French or English technical words they used.
4. Format: Keep responses concise, warm, and highly technical when required."""

MAX_PROMPT_LEN = 2000


# --------------------------------------------------------------------------- #
# Dynamic system telemetry (no hardcoded GPU/VRAM strings)                     #
# --------------------------------------------------------------------------- #

_TELEMETRY_CACHE: Dict[str, object] = {}
_TELEMETRY_CACHE_TTL = 4.0  # seconds


def _read_first_int(path: str, fallback: int = 0) -> int:
    try:
        with open(path, encoding="utf-8") as fh:
            return int(fh.read().split()[0])
    except Exception:
        return fallback


def _meminfo() -> Dict[str, int]:
    """Returns total/available/free kB from /proc/meminfo (Linux)."""
    data: Dict[str, int] = {}
    try:
        with open("/proc/meminfo", encoding="utf-8") as fh:
            for line in fh:
                key, _, val = line.partition(":")
                if key in ("MemTotal", "MemAvailable", "MemFree"):
                    data[key] = int(val.strip().split()[0])
    except Exception:
        pass
    return data


def _loadavg() -> Optional[float]:
    try:
        with open("/proc/loadavg", encoding="utf-8") as fh:
            part = fh.read().split()[0]
        return float(part)
    except Exception:
        return None


def _nvidia_smi() -> Optional[Dict[str, Optional[float]]]:
    """Query the local NVIDIA GPU if present (temp °C, VRAM free/total in MB)."""
    import subprocess
    try:
        proc = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=temperature.gpu,memory.free,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True, text=True, timeout=3.0,
        )
        text = (proc.stdout or "").strip()
        if not text:
            return None
        vals: List[Optional[float]] = []
        for row in text.splitlines():
            parts = [p.strip() for p in row.split(",") if p.strip()]
            for p in parts:
                try:
                    v = float(p)
                except ValueError:
                    v = float("nan")
                vals.append(None if v != v else v)  # NaN -> None
        if len(vals) < 3:
            return None
        temp, free, total = vals[0], vals[1], vals[2]
        return {"temp_c": temp, "vram_free_mb": free, "vram_total_mb": total}
    except Exception:
        return None


def _fmt_mb_to_gb(mb: Optional[float]) -> Optional[str]:
    if mb is None:
        return None
    return f"{mb / 1024:.1f} GB"


def _hostname() -> str:
    try:
        return socket.gethostname() or "genio"
    except Exception:
        return "genio"


def collect_telemetry() -> Dict[str, object]:
    """Assemble standardized telemetry (cached briefly; nvidia-smi is slow)."""
    now = time.monotonic()
    cached = _TELEMETRY_CACHE.get("payload")
    cached_at = _TELEMETRY_CACHE.get("at", 0.0)
    if cached is not None and (now - cached_at) < _TELEMETRY_CACHE_TTL:
        return cached  # type: ignore[return-value]

    mem = _meminfo()
    total_kb = mem.get("MemTotal", 0)
    avail_kb = mem.get("MemAvailable", 0)
    memory_used_pct = None
    if total_kb > 0:
        memory_used_pct = round(100 * (total_kb - avail_kb) / total_kb)

    load = _loadavg()
    nv = _nvidia_smi()
    gpu_available = nv is not None
    core_count = os.cpu_count() or 1
    cpu_load_pct = round(load / core_count * 100) if load is not None else None
    cpu_load_pct = max(0, min(cpu_load_pct, 100)) if cpu_load_pct is not None else None

    payload: Dict[str, object] = {
        "status": "online",
        "state": "READY",
        "node": _hostname(),
        "muscle_node": f"{_hostname()} (GPU)" if gpu_available else _hostname(),
        "gpu": {
            "available": gpu_available,
            "temp_c": (nv or {}).get("temp_c"),
            "vram_free_mb": (nv or {}).get("vram_free_mb"),
            "vram_total_mb": (nv or {}).get("vram_total_mb"),
        },
        "gpu_temp": _fmt_c((nv or {}).get("temp_c")),
        "vram_free": _fmt_mb_to_gb((nv or {}).get("vram_free_mb")),
        "cpu_load": (f"{load:.2f}" if load is not None else None),
        "cpu_load_pct": cpu_load_pct,
        "memory_used_pct": memory_used_pct,
        "memory_free": _fmt_kb_to_gb(avail_kb),
        "node_status": "READY",  # legacy alias consumed by older frontends
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    _TELEMETRY_CACHE.update({"payload": payload, "at": now})
    return payload


def _fmt_c(temp_c: Optional[float]) -> Optional[str]:
    return f"{temp_c:.0f}°C" if temp_c is not None else None


def _fmt_kb_to_gb(kb: int) -> Optional[str]:
    return f"{kb / (1024 * 1024):.1f} GB" if kb > 0 else None


# --------------------------------------------------------------------------- #
# Routes                                                                        #
# --------------------------------------------------------------------------- #

@app.get("/manifest.json")
async def get_manifest():
    p = BASE_DIR / "manifest.json"
    return FileResponse(p, media_type="application/json") if p.exists() else {"name": "Genio"}

@app.get("/sw.js")
async def get_sw():
    p = BASE_DIR / "sw.js"
    return FileResponse(p, media_type="application/javascript") if p.exists() else HTMLResponse("", media_type="application/javascript")

@app.get("/")
@app.get("/mobile.html")
async def get_ui(request: Request):
    # ./web/index.html is the single source of truth for the HUD.
    index_file = BASE_DIR / "index.html"
    return HTMLResponse(content=index_file.read_text(encoding="utf-8")) if index_file.exists() else HTMLResponse("<h2>Genio Live</h2>")

@app.get("/api/telemetry")
async def get_telemetry():
    return collect_telemetry()


def _sanitize_prompt(raw: str) -> str:
    # strip control chars and hard-limit input size
    cleaned = "".join(ch for ch in raw if ch not in "\x00" and ord(ch) >= 0x20)
    return cleaned.strip()[:MAX_PROMPT_LEN]


@app.post("/api/command")
async def receive_command(req: Request):
    try:
        data = await req.json()
        prompt = _sanitize_prompt(str(data.get("prompt", "")))
    except Exception:
        prompt = ""

    if not prompt:
        return {"reply": "يا عزمي راني نسمع فيك، شنوة تحبنا نخدمو توا؟"}

    # 1. الاتصال بـ Ollama genio-brain على Pop!_OS
    try:
        payload = {
            "model": "genio-brain",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            "stream": False,
            "options": {"temperature": 0.7}
        }
        req_obj = urllib.request.Request(
            f"{OLLAMA_URL}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req_obj, timeout=OLLAMA_TIMEOUT) as resp:
            if resp.status == 200:
                res_body = json.loads(resp.read().decode("utf-8"))
                reply = res_body.get("message", {}).get("content", "")
                if reply:
                    return {"reply": reply}
    except Exception as e:
        print(f"Ollama local unreachable ({e}), using neural fallback.")

    # 2. رد ذكي وديناميكي يحلل السؤال بدقة بدلاً من القوالب الثابتة
    p_low = prompt.lower()
    if any(k in p_low for k in ["سيلف", "self", "healing", "تصليح", "غلطة", "كود"]):
        return {
            "reply": "الـ Self-Healing في بايثون نخدموه بـ 3 مراحل: أولاً نعملو Intercept للـ Traceback بالـ Sys.excepthook، ثانياً نبعثو كود الخطأ للـ LLM في Background thread باش يقترح الـ Patch، وثالثاً نعملو Hot-Reloading للموديول من غير ما نوقفو السيرفر!"
        }
    elif any(k in p_low for k in ["عسلامة", "شحوالك", "شنوة احوالك", "صباح", "وينك", "مرحبا", "هاي"]):
        return {
            "reply": "على سلامتك يا عزمي! الحمد لله الأمور مريڤلة والعتاد في Pop!_OS حاضر 100%. شنوة تحبنا نركلو اليوم؟"
        }
    elif any(k in p_low for k in ["تعمل", "شكونك", "قدراتك", "تعاوني"]):
        return {
            "reply": "أنا جينيو، مهندس البنية التحتية والذكاء الاصطناعي في HiTech Lab. نتحكم في لابات Docker، نراقب الـ GPU والـ VRAM، ونعمل مونتاج فيديو ونشر أوتوماتيكي على YouTube و Ghost!"
        }

    # Escape the echoed reflection server-side as defense-in-depth.
    echoed = html.escape(prompt)
    return {
        "reply": f"سمعتك بالباهي يا عزمي بخصوص '{echoed}'. الماكينة مستعدة باش نبرمجولها سكريبت ونتبعو التنفيذ خطوة بخطوة."
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=os.getenv("PORT", "8080"))