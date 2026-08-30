"""
Genio — Side-by-side benchmark: Gemma 4 12B (Unified, encoder-free multimodal)
              vs Qwen2.5-VL 7B, driven through local Ollama on RTX 3060 (12 GB).

Measures for each model:
  - resident VRAM footprint after load (nvidia-smi sampling)
  - peak VRAM during image-text and text-only inference
  - total latency, generated tokens, throughput (tok/s)
  - terminal-error diagnosis quality on a synthetic screenshot (vision)
  - docker permission-denied diagnosis on a textual report (text)
  - bilingual Tunisian/Arabic + technical English reasoning

Output: JSON results file (default reports/models/gemma4_vs_qwen_results.json) + console table.

Usage:
  python3 scripts/benchmark_gemma4_vs_qwen.py [--models gemma4:12b,qwen2.5vl:7b] [--out PATH]
"""
from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
BENCH_DIR = REPO_ROOT / "reports" / "models"
DEFAULT_IMAGE = REPO_ROOT / "reports" / "vision_benchmark" / "test_sample.png"
DEFAULT_OUT = BENCH_DIR / "gemma4_vs_qwen_results.json"

GENERATE_URL = "http://localhost:11434/api/generate"

IMAGE_PROMPT = (
    "أنت Genio مهندس الـ DevOps والبنية التحتية في HiTech Lab. حلل لقطة الشاشة هذه، "
    "شخص المشكل التقني بدقة، وأعطني خطوات الـ Self-Healing والإصلاح الجذري "
    "بالدارجة التونسية التقنية والعربية."
)

DOCKER_TEXT = (
    "**Issue report**: `docker ps` fails on the host: `Got permission denied while "
    "trying to connect to the Docker daemon socket at unix:///var/run/docker.sock`. "
    "The user is in the `devops` group but not a member of `docker`. systemd shows "
    "containerd running, dockerd crash-looping with exit status 1.\n"
    "**Diagnose the root cause and write the exact self-healing commands in Tunisian Arabic.**"
)

BILINGUAL_Q = (
    "صايع علينا الـ nginx من البارح، POSTs كيتعرفو على الـ API réellement marchent، "
    "أما uploads ديما تنجم blanche: upstream backend (uwsgi) yerjaa 413. "
    "Give me the most likely root cause and the exact fix, w-ach nahkiw fi journald?"
)

KEYWORDS_VISION = [
    "502", "bad gateway", "systemctl", "app-worker", "permission",
    "docker", "127.0.0.1:8080", "exit-code", "chmod", "systemctl restart",
    "upstream",
]
KEYWORDS_TEXT = [
    "docker", "permission denied", "socket", "/var/run/docker.sock", "group",
    "usermod", "docker group", "chmod", "666", "sudo", "restart",
]
KEYWORDS_BILINGUAL = [
    "nginx", "413", "upload", "uwsgi", "backend", "client_max_body_size",
    "body_size", "journald", "journalctl", "fix",
]


class VramSampler:
    """Samples nvidia-smi used-MiB on an interval and records peak/to/before."""

    def __init__(self, interval: float = 0.3):
        self.interval = interval
        self._samples: List[int] = []
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def _read(self) -> int:
        try:
            out = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=10,
            ).stdout.strip()
            return int(out.splitlines()[0].split()[0])
        except Exception:  # noqa: BLE001
            return 0

    def start(self) -> int:
        self._samples = [self._read()]
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self._samples[0]

    def _run(self) -> None:
        while not self._stop.is_set():
            with self._lock:
                self._samples.append(self._read())
            time.sleep(self.interval)

    def stop(self, peek: bool = False) -> Dict[str, int]:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
        with self._lock:
            end = self._read()
            seq = self._samples + [end]
            return {
                "start_mb": seq[0],
                "end_mb": end,
                "peak_mb": max(seq),
                "samples": len(seq),
            }


def ollama_generate(model: str, prompt: str, image_b64: Optional[str] = None,
                    unload_after: bool = False) -> Tuple[str, Dict[str, Any]]:
    payload: Dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.3, "top_p": 0.9, "num_ctx": 4096},
        "keep_alive": 0 if unload_after else "30m",
    }
    if image_b64:
        payload["images"] = [image_b64]
    started = time.time()
    with httpx.Client(timeout=httpx.Timeout(600, connect=30)) as client:
        resp = client.post(GENERATE_URL, json=payload)
        resp.raise_for_status()
        data = resp.json()
    elapsed = time.time() - started
    data = dict(data)
    text = (data.pop("response", "") or "").strip()
    tok_s = (data.get("eval_count") or 0) / ((data.get("eval_duration") or 1) / 1e9)
    meta = {
        "latency_s": round(elapsed, 3),
        "eval_count": data.get("eval_count", 0),
        "prompt_eval_count": data.get("prompt_eval_count", 0),
        "load_duration_ms": round((data.get("load_duration") or 0) / 1e6, 1),
        "eval_duration_ms": round((data.get("eval_duration") or 0) / 1e6, 1),
        "tokens_per_s": round(tok_s, 2),
        "done_reason": data.get("done_reason", "?"),
    }
    return text, meta


def unload_all(models: List[str]) -> None:
    for m in models:
        try:
            ollama_generate(m, "x", unload_after=True)
        except Exception:  # noqa: BLE001
            pass


def quant_of(model: str) -> str:
    try:
        r = httpx.post("http://localhost:11434/api/show", json={"model": model}, timeout=15)
        det = r.json().get("details", {})
        return f"{det.get('family')}/{det.get('quantization_level')}"
    except Exception:  # noqa: BLE001
        return "?"


def keyword_score(text: str, keywords: List[str]) -> Tuple[int, int, List[str]]:
    low = text.lower()
    hits = [k for k in keywords if k.lower() in low]
    return len(hits), len(keywords), hits


def bench_model(model: str, image_b64: str,
                unload_ids: List[str]) -> Dict[str, Any]:
    res: Dict[str, Any] = {"model": model, "quant": quant_of(model)}
    unload_all(unload_ids)

    # warmup + resident footprint
    sampler = VramSampler()
    sampler.start()
    _, m1 = ollama_generate(model, "Halo, chnowa tsm3?" )
    time.sleep(1.5)
    vram_idle = sampler.stop()
    res["vram_after_load_mb"] = vram_idle["end_mb"]
    res["warmup"] = m1

    scenarios = [
        ("vision_terminal" if image_b64 else "", IMAGE_PROMPT, image_b64, KEYWORDS_VISION),
        ("docker_text", DOCKER_TEXT, None, KEYWORDS_TEXT),
        ("bilingual", BILINGUAL_Q, None, KEYWORDS_BILINGUAL),
    ]
    for name, prompt, img, kws in scenarios:
        s = VramSampler()
        s.start()
        text, meta = ollama_generate(model, prompt, img)
        v = s.stop()
        ok, total, hits = keyword_score(text, kws)
        res[name] = {
            **meta,
            "vram": v,
            "kw_hits": hits,
            "kw_score": f"{ok}/{total}",
            "response": text,
        }
        print(f"  [{model}] {name or 'warmup'}: {meta['latency_s']}s "
              f"{meta['tokens_per_s']} tok/s peak={v['peak_mb']}MiB kw={ok}/{total}")
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="gemma4:12b,qwen2.5vl:7b")
    ap.add_argument("--image", default=str(DEFAULT_IMAGE))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args()

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    image_path = Path(args.image)
    image_b64 = base64.b64encode(image_path.read_bytes()).decode("ascii") if image_path.exists() else ""

    BENCH_DIR.mkdir(parents=True, exist_ok=True)
    print(f"# Genio multimodal benchmark  {datetime.now().isoformat(timespec='seconds')}")
    print(f"GPU:", subprocess.run(
        ["nvidia-smi", "--query-gpu=name,memory.total,memory.used", "--format=csv,noheader"],
        capture_output=True, text=True).stdout.strip())
    print(f"image: {image_path} ({image_path.stat().st_size if image_path.exists() else 'MISSING'} bytes)")

    shell = {"ran_at": datetime.now().isoformat(timespec="seconds"),
             "models": models, "image": str(image_path)}
    first_unload_ids = models[:]  # clear everything before model #1
    last = None
    try:
        for i, m in enumerate(models):
            shell[m] = bench_model(m, image_b64, unload_ids=(
                models if i == 0 else [m]))
            last = m
    finally:
        unload_all([last] if last else models)

    (Path(args.out)).write_text(json.dumps(shell, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nresults -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())