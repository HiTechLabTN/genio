"""
Genio — Autonomous LPI Tutorial Series Generator (Local-First).

For each of the 8 core LPI / DevOps modules, asks the local `genio-brain`
model (Ollama) to produce a Tunisian-Arabic / White-Arabic technical tutorial
and saves:
  - reports/lpi_series/module_{idx}_{slug}.md            (clean Markdown)
  - reports/lpi_series/module_{idx}_storyboard.json      (motion video script)

Robust by design: exponential backoff + jitter, per-request timeouts,
skip-existing (--force to regenerate) and timestamped logging.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
LPI_DIR = REPO_ROOT / "reports" / "lpi_series"
LPI_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = LPI_DIR / "generation.log"
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
MODEL = os.getenv("GENIO_MODEL", "genio-brain")
GENERATE_URL = f"{OLLAMA_BASE_URL}/api/generate"
TAGS_URL = f"{OLLAMA_BASE_URL}/api/tags"

MAX_RETRIES = int(os.getenv("GENIO_MAX_RETRIES", "5"))
REQUEST_TIMEOUT_S = int(os.getenv("GENIO_TIMEOUT_S", "900"))
BACKOFF_BASE_S = float(os.getenv("GENIO_BACKOFF_S", "5"))
TEMPERATURE = float(os.getenv("GENIO_TEMPERATURE", "0.7"))
NUM_CTX = int(os.getenv("GENIO_NUM_CTX", "8192"))
MIN_CHARS = int(os.getenv("GENIO_MIN_CHARS", "600"))
REQUIRED_SECTIONS = ["1", "2", "3", "4"]

PALETTE = {
    "background": "#030712",
    "surface": "#0f172a",
    "primary": "#00f0ff",
    "accent": "#00ff87",
    "warn": "#f43f5e",
    "text": "#f8fafc",
}

SFX = {
    "whoosh": "soft whoosh sweep (150ms)",
    "glitch": "digital glitch stutter x2",
    "pop": "soft pop reveal",
    "tap": "typewriter tick per card",
    "count_up": "number count-up ticks",
    "impact": "bass impact hit",
    "chime": "bright confirmation chime",
    "scan": "radar scan sweep",
    "slide": "card slide-in swish",
    "zap": "electric zap burst",
}

MODULES: List[Dict[str, Any]] = [
    {
        "idx": 1,
        "slug": "linux-filesystem-hierarchy",
        "title": "Linux Filesystem Hierarchy & Navigation",
        "keywords": "FHS, ls, cd, find",
    },
    {
        "idx": 2,
        "slug": "permissions-ownership-security",
        "title": "Permissions, Ownership & Security",
        "keywords": "chmod, chown, umask, sudo",
    },
    {
        "idx": 3,
        "slug": "systemd-service-management",
        "title": "Service Management with Systemd & Journalctl",
        "keywords": "systemctl, journalctl, unit, enable",
    },
    {
        "idx": 4,
        "slug": "process-monitoring-troubleshooting",
        "title": "Process Monitoring & Troubleshooting",
        "keywords": "ps, top, kill, htop",
    },
    {
        "idx": 5,
        "slug": "storage-disk-management",
        "title": "Storage & Disk Management",
        "keywords": "df, du, mount, fdisk",
    },
    {
        "idx": 6,
        "slug": "network-diagnostics-sockets",
        "title": "Network Diagnostics & Socket Inspection",
        "keywords": "ip, ss, curl, ping, netstat",
    },
    {
        "idx": 7,
        "slug": "package-management-repositories",
        "title": "Package Management & Repositories",
        "keywords": "apt, dpkg, ppa",
    },
    {
        "idx": 8,
        "slug": "docker-containers-from-scratch",
        "title": "Docker Containers from Scratch",
        "keywords": "run, ps, exec, volumes, networks",
    },
]

PROMPT_TEMPLATE = """إنت Genio في HiTech Lab بتونس. ولّد درس تعليمي كامل حول: «{title}».

المواضيع اللي لازم تتغطى: {keywords}

اخرج الدروس بالدارجة التونسية التقنية والعربية البيضاء، بأسلوب طبيعي ومباشر، بلا حشو ولا مقدمات. الاصطلاحات التقنية تخليها بالإنجليزية (zoom, filesystem, service...) واشرحها ببساطة.

الدرس يلزم يتبع بالضبط هذا الهيكل بعناوين Markdown:

## 1. الشرح التقني
اشرح المفهوم بتشبيه واضح من الحياة اليومية للتونسي (2-4 سطور)، ثم شو ستفيدك في السيرفرات الواقعية. زيرو فلّف.

## 2. تفصيل الأوامر
كل أمر في block Monospace مع التعليق بالدارجة، واكتب الأعلام (flags) الدقيقة ومعناها واحد بواحد. أعط 3 إلى 5 أوامر أساسية.

## 3. سيناريو Self-Healing في الواقع
مشكل حقيقي وقع في سيرفر (ابدأ بخطأ aktual يعطي "Permission denied" أو "failed" أو شهوة ممتلئة...)، ثم خطوات التشخيص والاكتشاف والإصلاح الجذري خطوة بخطوة بالأوامر.

## 4. تمرين المخبر العملي (Lab Sandbox)
تمارين عملية يحلها القارئ بنفسه في sandbox أو VM، بأهداف واضحة و خطوات مرقمة، و منتهية بسؤال تحقق ذاتي.

قواعد صارمة:
- أجب فقط بمحتوى الدرس Markdown، بلا أي نص خارج الهيكل.
- كل الأكواد داخل fenced blocks بـ bash.
- لا تذكر تكاليف أو تسويق. الهدف: تعليم تقني مباشر.
"""


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("genio.lpi")
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s")

    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(fmt)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(fmt)

    logger.handlers = [file_handler, stream_handler]
    logger.propagate = False
    return logger


logger = setup_logging()


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def now_ms() -> float:
    return time.time() * 1000.0


def modules_available() -> List[str]:
    try:
        resp = httpx.get(TAGS_URL, timeout=30)
        resp.raise_for_status()
        return [m.get("name", "") for m in resp.json().get("models", [])]
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not reach Ollama tags endpoint (%s) — continuing.", exc)
        return []


def module_available_now(model: str, available: List[str]) -> bool:
    return (model in available) or any(
        m.startswith(model.split(":")[0] + ":") for m in available
    )


def validate_tutorial(text: str, module: Dict[str, Any]) -> tuple[bool, str]:
    """Reject truncated or structurally incomplete tutorials."""
    if len(text) < MIN_CHARS:
        return False, f"too short ({len(text)} chars < {MIN_CHARS})"
    sections = split_sections(text)
    missing = [s for s in REQUIRED_SECTIONS if s not in sections]
    if missing:
        return False, f"missing sections {missing} (found: {sorted(sections.keys())})"
    fenced = re.search(r"```(?:bash)?", text)
    inline = re.findall(r"`[^`\n]{2,}`", text)
    if not fenced and len(inline) < 3:
        return False, "almost no code (no fenced block, < 3 inline code spans)"
    return True, ""


def call_generate(prompt: str, module: Dict[str, Any]) -> str:
    """POST /api/generate with retry + exponential backoff + jitter + quality gate."""
    module_title = module["title"]
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": TEMPERATURE, "num_ctx": NUM_CTX},
    }

    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        started = now_ms()
        try:
            with httpx.Client(timeout=httpx.Timeout(REQUEST_TIMEOUT_S, connect=30)) as client:
                resp = client.post(GENERATE_URL, json=payload)
                resp.raise_for_status()
                data = resp.json()
                text = (data.get("response") or "").strip()
            if not text:
                raise ValueError("ollama returned an empty response")

            ok, reason = validate_tutorial(text, module)
            if not ok:
                raise ValueError(f"quality gate rejected output: {reason}")

            elapsed = (now_ms() - started) / 1000.0
            logger.info("[%s] attempt %d OK in %.1fs (%d chars)",
                        module_title, attempt, elapsed, len(text))
            return text
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            wait = min(120.0, (BACKOFF_BASE_S * (2 ** (attempt - 1))) + random.uniform(0, 2))
            logger.warning("[%s] attempt %d/%d failed (%s) — retrying in %.1fs",
                           module_title, attempt, MAX_RETRIES, exc, wait)
            time.sleep(wait)

    raise RuntimeError(f"[{module_title}] all {MAX_RETRIES} attempts failed: {last_error}")


def ensure_title(text: str, title: str) -> str:
    first_line = text.strip().splitlines()[0] if text.strip() else ""
    if not re.match(r"^#\s+", first_line):
        text = f"# {title}\n\n{text.strip()}"
    return text


def split_sections(markdown: str) -> Dict[str, str]:
    """Heuristic split of the tutorial into its 4 required sections."""
    headers = [h for h in re.split(r"\n(?=##\s)", markdown) if h.strip()]
    sections: Dict[str, str] = {}
    order = ["1", "2", "3", "4"]
    for block in headers:
        m = re.match(r"##\s+(\d)\.?\s*(.*)", block)
        if m:
            idx = m.group(1)
            if idx in order:
                body = re.sub(r"^##\s+[^\n]*\n", "", block).strip()
                sections[idx] = body
    return sections


def voiceover_line(section_body: str, default: str, max_len: int = 220) -> str:
    """Pick the first plausible sentence from a section as voiceover.

    Backticked inline code is kept as plain text (backticks removed) so
    commands stay readable in the voiceover instead of being stripped.
    """
    lines = [ln.strip() for ln in section_body.splitlines()
             if ln.strip() and not ln.lstrip().startswith("```")
             and not ln.lstrip().startswith("#") and not ln.lstrip().startswith("~")]
    for ln in lines:
        cleaned = re.sub(r"`([^`]*)`", r"\1", ln).strip()
        if cleaned:
            return cleaned[:max_len]
    return default


def build_storyboard(module: Dict[str, Any], markdown: str) -> Dict[str, Any]:
    idx = module["idx"]
    sections = split_sections(markdown)
    title = module["title"]

    act_defs = [
        ("hook",
         f"⚠️ المشكل اللي يقع للكل؟",
         "لقطة تحذير: شاشة حمراء فيها مثلا 'Permission denied' أو 'unit failed' ترتج ثم تستقر",
         "glitch_in", ["glitch", "whoosh"], "#f43f5e", "warning",
         ""),
        ("concept",
         "التشبيه: إيش نتصورو باش تفهم؟",
         "بطاقة مركزية تكبر؛ النص بالعربية RTL مع وميض توسيط",
         "scale_in", ["pop", "slide"], "#00f0ff", "metaphor",
         "1"),
        ("commands",
         "تفصيل الأوامر واحد بواحد",
         "نافذة Terminal بتأثير typing مع إظهار flags ومغزى كل أمر",
         "typewriter_grid", ["tap", "count_up"], "#00ff87", "spec_breakdown",
         "2"),
        ("scenario",
         "سيناريو الواقع: التشخيص، الاكتشاف، الإصلاح الجذري",
         "مخطط خطوات Diagnosis → Discovery → Fix بتأكيدات خضراء",
         "cards_explode", ["scan", "pop"], "#f59e0b", "scenario",
         "3"),
        ("lab",
         "تمرين المخبر العملي (Sandbox)",
         "شاشة sandbox: قائمة خطوات مرقمة وأسئلة تحقق ذاتي",
         "slide_grid", ["slide", "chime"], "#22d3ee", "lab",
         "4"),
        ("cta",
         "التطبيق والخطوة الجاية",
         "Zoom punch إلى خلفية بيضاء ثم رابط الـ LPI Series بألوان النيون",
         "zoom_punch", ["impact", "chime"], "#00f0ff", "cta",
         ""),
    ]

    default_lines = {
        "hook": f"{title} يبدو سهل لكن الاختبار الجاد يكشف الأخطاء الشائعة.",
        "concept": f"نفسّرو {title} بتشبيه من الحياة اليومية.",
        "commands": "الأوامر الأساسية للوحدة مع تحليل الأعلام بالدارجة.",
        "scenario": "سيناريو واقعي للتشخيص والإصلاح الذاتي على السيرفر.",
        "lab": "تمرين عملي في sandbox باش تطبق ما تعلمته.",
        "cta": "واصل مع بقية سلسلة LPI Series في HiTech Lab.",
    }

    duration_per = 8
    total = len(act_defs) * duration_per

    acts: Dict[str, Any] = {}
    cursor = 0
    for act, title_text, scene, anim, sfx_keys, color, kind, section_key in act_defs:
        body = sections.get(section_key, "")
        default = default_lines[act]
        vo = voiceover_line(body, default)

        start = cursor
        cursor += duration_per
        acts[act] = {
            "act": act,
            "dialogue_text": title_text,
            "voiceover": vo,
            "scene": scene,
            "visual_cue": f"{anim} on surface; on-screen Arabic RTL text",
            "animation": anim,
            "sfx": [{"trigger": k, "desc": SFX[k]} for k in sfx_keys],
            "color": color,
            "timing_s": {"start": start, "end": cursor},
            "time_code": f"00:{start:02d} - 00:{cursor:02d}",
            "warning": kind == "warning",
        }

    return {
        "schema": "genio.motion_storyboard.v1",
        "project": "HiTech Lab — Genio LPI Series",
        "topic": title,
        "title": title,
        "slug": module["slug"],
        "lang": "ar-TN",
        "total_duration_s": total,
        "resolution": "1920x1080",
        "fps": 30,
        "palette": PALETTE,
        "motion": {
            "transitions": [
                {"from": "hook", "to": "concept", "style": "glitch_split_wipe"},
                {"from": "concept", "to": "commands", "style": "cards_explode"},
                {"from": "commands", "to": "scenario", "style": "slide_transition"},
                {"from": "scenario", "to": "lab", "style": "grid_roll"},
                {"from": "lab", "to": "cta", "style": "zoom_punch_white_flash"},
            ],
            "sfx_library": SFX,
            "typography": {"font": "Cairo", "mono": "JetBrains Mono", "direction": "rtl"},
        },
        "acts": acts,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Genio LPI tutorial series via local Ollama.")
    parser.add_argument("--force", action="store_true", help="Regenerate modules even if output exists.")
    args = parser.parse_args()

    available = modules_available()
    if available and not module_available_now(MODEL, available):
        logger.warning("Model '%s' not in Ollama tags (%s) — generation may fail.",
                       MODEL, ", ".join(available))
    else:
        logger.info("Ollama reachable. Model '%s' confirmed.", MODEL)

    total = len(MODULES)
    failed: List[Dict[str, Any]] = []

    for i, module in enumerate(MODULES, start=1):
        idx = module["idx"]
        md_path = LPI_DIR / f"module_{idx:02d}_{module['slug']}.md"
        sb_path = LPI_DIR / f"module_{idx:02d}_storyboard.json"

        if md_path.exists() and not args.force:
            logger.info("[%d/%d] module %02d exists — skipping (%s)",
                        i, total, idx, md_path.name)
            continue

        logger.info("[%d/%d] generating module %02d: %s", i, total, idx, module["title"])

        prompt = PROMPT_TEMPLATE.format(title=module["title"], keywords=module["keywords"])
        try:
            markdown = call_generate(prompt, module)
        except Exception as exc:  # noqa: BLE001
            logger.error("[%d/%d] module %02d FAILED after retries: %s", i, total, idx, exc)
            failed.append({"idx": idx, "title": module["title"], "error": str(exc)})
            continue

        markdown = ensure_title(markdown, module["title"])
        md_path.write_text(markdown + "\n", encoding="utf-8")
        logger.info("[%d/%d] saved %s (%d bytes)", i, total, md_path.name, md_path.stat().st_size)

        storyboard = build_storyboard(module, markdown)
        sb_path.write_text(json.dumps(storyboard, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        logger.info("[%d/%d] saved %s", i, total, sb_path.name)

        ctx = int(os.getenv("GENIO_COOLDOWN_S", "0"))
        if ctx > 0 and i < total:
            logger.info("Cooldown %.0fs between modules to keep VRAM low...", ctx)
            time.sleep(ctx)

    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "model": MODEL,
        "modules_total": total,
        "modules_failed": len(failed),
        "failed": failed,
    }
    (LPI_DIR / "generation_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    logger.info("SUMMARY: %d/%d modules generated. Failed: %s",
                total - len(failed), total, failed or "none")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())