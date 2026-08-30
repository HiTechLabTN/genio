"""
Genio — Live vision-CLI diagnostic test.

1. Generates a realistic multi-stage failure screenshot (Docker Exit-137 OOM
   + Nginx 502 Bad Gateway) using PIL.
2. Monitors peak VRAM via nvidia-smi polling during inference.
3. Sends the screenshot + a Tunisian Arabic diagnostic prompt through
   core/model_router.py (gemma4:12b primary).
4. Verifies root-cause keywords, validates fix language, and logs latency / VRAM.
5. Writes results to reports/tri_track/.

Run:
    python3 scripts/test_live_terminal_inspection.py
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
REPORT_DIR = ROOT / "reports" / "tri_track"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

TS = datetime.now().strftime("%Y%m%d_%H%M%S")
SCREENSHOT_PATH = REPORT_DIR / f"live_inspection_screenshot_{TS}.png"
JSON_PATH = REPORT_DIR / f"live_inspection_{TS}.json"
MD_PATH = REPORT_DIR / f"live_inspection_{TS}.md"

sys.path.insert(0, str(ROOT))

PROMPT = (
    "أنت Genio مهندس الـ DevOps في HiTech Lab. هاذي لقطة شاشة فيها مشكلين: "
    "Docker container قتلو الـ OOM-killer (Exit 137) + Nginx 502 Bad Gateway على "
    "الـ frontend. شخص الـ root cause لكل واحد بالتفصيل، أعطني الـ bash commands "
    "للإصلاح بالدارجة التونسية التقنية، وفهم logs coupling الداخلي بين المشكليـن."
)

# terminal screenshot colours
BG     = (18, 22, 30)
PANEL  = (24, 30, 42)
EDGE   = (51, 65, 89)
TXT    = (222, 230, 240)
DIM    = (140, 155, 175)
RED    = (248, 113, 113)
AMBER  = (251, 191, 36)
GREEN  = (52, 211, 153)
CYAN   = (96, 222, 244)
ORANGE = (251, 146, 60)
W, H   = 1280, 720

logger = logging.getLogger("genio.live_test")
logger.setLevel(logging.INFO)
_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s"))
logger.addHandler(_handler)
logger.propagate = False

# --------------------------------------------------------------------------- VRAM

_VRAM_STATE: dict = {"peak": 0, "baseline": 0}
_VRAM_LOCK = threading.Lock()


def nvidia_vram_mb() -> int:
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10,
        )
        return int(result.stdout.strip().splitlines()[0].strip())
    except Exception:
        return 0


def _monitor_vram(stop: threading.Event) -> None:
    peak = _VRAM_STATE["baseline"]
    while not stop.is_set():
        cur = nvidia_vram_mb()
        if cur > peak:
            peak = cur
        time.sleep(0.35)
    with _VRAM_LOCK:
        _VRAM_STATE["peak"] = peak
    logger.info("peak vram: %d MiB", peak)

# --------------------------------------------------------------------------- PIL

def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    for p in (("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf" if bold
               else "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"),):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def draw_terminal_screenshot() -> Path:
    img = Image.new("RGB", (W, H), BG)
    d  = ImageDraw.Draw(img)

    fm  = _font(17)
    fmb = _font(17, bold=True)
    ft  = _font(16, bold=True)

    # title bar
    d.rectangle([0, 0, W, 34], fill=(36, 42, 56))
    d.ellipse([14, 12, 22, 20], fill=RED)
    d.ellipse([28, 12, 36, 20], fill=AMBER)
    d.ellipse([42, 12, 50, 20], fill=GREEN)
    d.text((60, 10), "root@hitech-prod: /var/log # docker ps -a", font=ft, fill=DIM)

    left = 28
    y = 52
    def ln(txt, c=TXT, f=None, dy=22):
        nonlocal y
        d.text((left, y), txt, font=f or fm, fill=c); y += dy; return y

    # --- docker panel ---
    ln("$ docker ps --format 'table {{.Names}}\\t{{.Status}}\\t{{.ExitCode}}'", f=fmb, c=CYAN)
    ln("NAMES             STATUS                      EXIT", f=fmb, c=DIM)
    ln("nginx-frontend    Exited (0) 14 minutes ago   0", c=GREEN)
    ln("app-worker        Exited (137) 20 min ago     137", c=RED, f=fmb)
    ln("postgres-db       Up 3 hours                  -", c=GREEN)
    ln("redis-cache       Up 3 hours                  -", c=GREEN)
    y += 8
    ln("$ docker logs app-worker 2>&1 | tail -12", f=fmb, c=CYAN)
    ln("[worker] request processed: 2341", c=TXT)
    ln("[worker] RSS memory: 2.1 GB -> 2.9 GB (heap near limit)", c=ORANGE)
    ln("[Killed] process killed by OOM-killer (score 1024)", c=RED, f=fmb)
    ln("[kernel] Out of memory: Killed process 18472 (python) with total-vm:3.1g", c=RED)
    ln("[worker] app-worker.service: Main process exited, code=killed, status=9/KILL")
    y += 8
    ln("dmesg | grep -i oom | tail -3", f=fmb, c=CYAN)
    ln("[Thu Aug 29 04:22:10 2026] oom-kill: Invoked, score_adj=0", c=AMBER)
    ln("[Thu Aug 29 04:22:10 2026] Out of memory: Killed process 18472 (python)")

    # --- nginx panel (right column) ---
    px0, py0, px1, py1 = 760, 82, 1252, 340
    d.rounded_rectangle([px0, py0, px1, py1], radius=10, fill=PANEL, outline=EDGE, width=2)
    d.text((px0+16, py0+14), "Nginx 502 Bad Gateway — app.hitech.tn", font=ft, fill=RED)
    py = py0 + 42
    def pln(txt, c=TXT, f=None):
        nonlocal py
        d.text((px0+16, py), txt, font=f or fm, fill=c); py += 22
    pln("$ curl -sI https://app.hitech.tn/api/status", f=fmb, c=CYAN)
    pln("HTTP/1.1 502 Bad Gateway", c=RED, f=fmb)
    pln("server: nginx/1.24.0", c=DIM)
    pln("date: Thu, 29 Aug 2026 04:45:12 GMT", c=DIM)
    pln("")
    pln("$ cat /var/log/nginx/error.log | tail -3", f=fmb, c=CYAN)
    pln("connect() failed (111: Connection refused)", c=ORANGE)
    pln("upstream: http://127.0.0.1:8080/app", c=DIM)
    pln("nginx: upstream prematurely closed", c=ORANGE)
    pln("                            connection during handshake", c=DIM)

    # --- bottom coupling note ---
    py2 = 370
    d.rounded_rectangle([90, py2, W-90, py2+110], radius=10,
                        fill=(40, 20, 20), outline=RED, width=2)
    d.text((110, py2+14), "root cause correlation:", font=ft, fill=AMBER)
    d.text((110, py2+44), "app-worker (port 8080) OOM-killed at 04:22; nginx upstream",
           font=fm, fill=TXT)
    d.text((110, py2+66), "refuses port 8080 from 04:23 onward  =>  502 is downstream",
           font=fm, fill=TXT)

    img.save(SCREENSHOT_PATH, "PNG")
    logger.info("screenshot → %s", SCREENSHOT_PATH)
    return SCREENSHOT_PATH


# ------------------------------------------------------------- verify / report

KEYWORDS = {
    "oom":     ["oom", "out of memory", "oom-killer", "killed process"],
    "exit137": ["exit", "137", "status=9"],
    "nginx502":["502", "bad gateway", "upstream"],
    "fix":     ["journalctl", "docker logs", "free -h", "mem_limit", "memswap"],
    "arabic":  ["المشكل", "حل", "إصلاح", "جلسة", "cahier"],
}


def evaluate(response: str) -> dict:
    text = response.lower()
    hits = {}
    for cat, keys in KEYWORDS.items():
        hits[cat] = any(k in text for k in keys)
    return hits


# --------------------------------------------------------------- main

async def run() -> None:
    _VRAM_STATE["baseline"] = nvidia_vram_mb()
    logger.info("baseline VRAM: %d MiB", _VRAM_STATE["baseline"])

    img_path = draw_terminal_screenshot()
    b64 = base64.b64encode(img_path.read_bytes()).decode()

    from core.model_router import ModelRouter
    router = ModelRouter()
    logger.info("router endpoints: %s", [e.name for e in router.endpoints])

    stop = threading.Event()
    t = threading.Thread(target=_monitor_vram, args=(stop,), daemon=True)
    t.start()

    t0 = time.time()
    response = await router.generate(PROMPT, temperature=0.3, max_tokens=4096, images=[b64])
    latency = time.time() - t0

    stop.set()
    t.join(timeout=3)

    hits = evaluate(response)
    peak = _VRAM_STATE["peak"]

    result = {
        "ts": TS,
        "screenshot": str(img_path),
        "prompt": PROMPT,
        "response": response,
        "latency_s": round(latency, 3),
        "vram_baseline_mb": _VRAM_STATE["baseline"],
        "vram_peak_mb": peak,
        "keyword_hits": hits,
        "all_keywords_detected": all(hits.values()),
    }
    JSON_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("JSON → %s", JSON_PATH)

    md = [
        "# Genio — Live Vision-CLI Diagnostic Test",
        "",
        f"- **Date**: {TS}",
        f"- **Model used**: gemma4:12b (primary, with qwen2.5vl:7b fallback)",
        f"- **Screenshot**: `{SCREENSHOT_PATH.name}`",
        f"- **Latency**: {result['latency_s']}s",
        f"- **VRAM**: {_VRAM_STATE['baseline']} MiB baseline → {peak} MiB peak",
        f"- **All keywords detected**: {'yes' if result['all_keywords_detected'] else 'no'}",
        "",
        "## Keyword Verification",
        "",
        "| Category | Detected |",
        "|----------|----------|",
        *(f"| {k} | {'✅' if v else '❌'} |" for k, v in hits.items()),
        "",
        "## Model Response (verbatim)",
        "",
        "```",
        response,
        "```",
    ]
    MD_PATH.write_text("\n".join(md), encoding="utf-8")
    logger.info("MD → %s", MD_PATH)
    print("\n=== RESULT ===")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(run())
