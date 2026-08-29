"""
Genio — Publish LPI series modules to Ghost CMS as Drafts.

Reads credentials from `.env` (or environment variables):
    GHOST_URL        e.g. https://lab.hitech.tn
    GHOST_ADMIN_KEY  Ghost Admin API key in "<id>:<secret>" form

For each reports/lpi_series/module_*.md:
  - extracts the title from the first H1 header,
  - converts Markdown -> HTML (Ghost converts it to its editor format
    through /ghost/api/admin/posts/?source=html),
  - creates an unpublished draft with standard Genio tags and a custom
    excerpt summarizing the tutorial's 4 parts.
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
import jwt
import markdown as md_lib

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None  # type: ignore[assignment]

REPO_ROOT = Path(__file__).resolve().parent.parent
SERIES_DIR = REPO_ROOT / "reports" / "lpi_series"
ENV_FILE = REPO_ROOT / ".env"
LOG_FILE = SERIES_DIR / "ghost_publish.log"

BASE_URL_DEFAULT = "https://lab.hitech.tn"
TAGS = ["LPI Essentials", "DevOps", "Genio-Brain", "Self-Hosting"]
SECTION_LABELS = {
    "1": "الشرح التقني",
    "2": "تفصيل الأوامر",
    "3": "سيناريو Self-Healing",
    "4": "تمرين المخبر العملي",
}
ADMIN_API_PATH = "/ghost/api/admin/posts/"

MAX_RETRIES = int(os.getenv("GHOST_MAX_RETRIES", "4"))
RETRY_BACKOFF_BASE = float(os.getenv("GHOST_RETRY_BACKOFF", "2"))
REQUEST_TIMEOUT_S = int(os.getenv("GHOST_TIMEOUT_S", "90"))

logger = logging.getLogger("genio.ghost")
logger.setLevel(logging.INFO)
_fmt = logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s")
_file = logging.FileHandler(LOG_FILE, encoding="utf-8")
_file.setFormatter(_fmt)
_stream = logging.StreamHandler(sys.stdout)
_stream.setFormatter(_fmt)
logger.handlers = [_file, _stream]
logger.propagate = False


# --------------------------------------------------------------------------- #
# Credentials / token
# --------------------------------------------------------------------------- #
def load_env() -> None:
    if load_dotenv is not None:
        load_dotenv(ENV_FILE, override=False)
    else:  # minimal manual .env parse fallback
        if ENV_FILE.exists():
            for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def get_ghost_config() -> Tuple[str, str]:
    load_env()
    base_url = os.getenv("GHOST_URL", BASE_URL_DEFAULT).rstrip("/")
    admin_key = os.getenv("GHOST_ADMIN_KEY", "").strip()
    if not admin_key:
        raise ValueError(
            "GHOST_ADMIN_KEY is not set. Add it to .env as '<id>:<secret>' "
            "(GHOST_URL defaults to https://lab.hitech.tn)."
        )
    if ":" not in admin_key:
        raise ValueError("GHOST_ADMIN_KEY must have the form '<id>:<secret>'.")
    return base_url, admin_key


def generate_jwt(admin_key: str) -> str:
    """Signed HS256 Ghost Admin JWT (https://ghost.org/docs/admin-api/)."""
    key_id, secret_hex = admin_key.split(":")
    iat = int(time.time())
    payload = {"iat": iat, "exp": iat + 300, "aud": "/admin/"}
    headers = {"alg": "HS256", "typ": "JWT", "kid": key_id}
    return jwt.encode(payload, bytes.fromhex(secret_hex), algorithm="HS256", headers=headers)


# --------------------------------------------------------------------------- #
# Markdown parsing
# --------------------------------------------------------------------------- #
def derive_title(md_text: str, fallback_name: str) -> str:
    for line in md_text.splitlines():
        stripped = line.strip().strip("#").strip()
        if line.strip().startswith("# ") and stripped:
            return stripped
    stem = Path(fallback_name).stem
    stem = re.sub(r"^module_\d+_", "", stem)
    return stem.replace("-", " ").title()


def split_sections(markdown: str) -> Dict[str, str]:
    headers = [h for h in re.split(r"\n(?=##\s)", markdown) if h.strip()]
    sections: Dict[str, str] = {}
    for block in headers:
        match = re.match(r"##\s+(\d)\.?\s*(.*)", block)
        if match and match.group(1) in SECTION_LABELS:
            body = re.sub(r"^##\s+[^\n]*\n", "", block).strip()
            sections[match.group(1)] = body
    return sections


def section_snippet(body: str, max_len: int = 110) -> str:
    """First meaningful line of a section, backticks flattened to plain text."""
    for line in body.splitlines():
        line = line.strip()
        if not line or line.lstrip().startswith(("```", "#", "~")):
            continue
        flat = re.sub(r"`([^`]*)`", r"\1", line).strip()
        flat = re.sub(r"^\s*[-\*]\s*", "", flat)
        flat = re.sub(r"^\d+[\.\)]\s*", "", flat)
        if flat:
            return flat[:max_len]
    return ""


def build_excerpt(markdown: str) -> str:
    sections = split_sections(markdown)
    parts = []
    for idx in ("1", "2", "3", "4"):
        label = SECTION_LABELS[idx]
        if idx in sections:
            parts.append(f"{label}: {section_snippet(sections[idx])}")
        else:
            parts.append(f"{label}: —")
    return " | ".join(parts)[:300]


def markdown_to_html(md_text: str) -> str:
    """The top-level H1 becomes the Ghost title, so drop it from the body."""
    body = re.sub(r"^#\s+.*$", "", md_text, count=1, flags=re.MULTILINE)
    return md_lib.markdown(body, extensions=["extra", "fenced_code"])


# --------------------------------------------------------------------------- #
# Ghost API
# --------------------------------------------------------------------------- #
def create_draft(base_url: str, admin_key: str, title: str, html: str,
                 excerpt: str, tags: List[str]) -> Optional[Dict[str, Any]]:
    token = generate_jwt(admin_key)
    headers = {
        "Authorization": f"Ghost {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "posts": [{
            "title": title,
            "html": html,
            "status": "draft",
            "custom_excerpt": excerpt,
            "tags": [{"name": tag} for tag in tags],
        }]
    }

    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with httpx.Client(timeout=httpx.Timeout(REQUEST_TIMEOUT_S, connect=30)) as client:
                resp = client.post(
                    base_url + ADMIN_API_PATH,
                    params={"source": "html"},
                    headers=headers,
                    json=payload,
                )
            if resp.status_code in (401, 403):
                raise RuntimeError(f"Ghost auth failed ({resp.status_code}): {resp.text[:300]}")
            if resp.status_code == 429:
                retry_after = float(resp.headers.get("Retry-After", RETRY_BACKOFF_BASE ** attempt))
                logger.warning("[%s] rate limited — waiting %.0fs", title, retry_after)
                time.sleep(retry_after)
                continue
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            wait = RETRY_BACKOFF_BASE ** attempt
            logger.warning("[%s] attempt %d/%d failed (%s) — retrying in %.0fs",
                           title, attempt, MAX_RETRIES, exc, wait)
            time.sleep(wait)

    raise RuntimeError(f"[{title}] all {MAX_RETRIES} attempts failed: {last_error}")


def main() -> int:
    base_url, admin_key = get_ghost_config()
    logger.info("Ghost admin configured: %s (credentials OK)", base_url)

    modules = sorted(SERIES_DIR.glob("module_*.md"))
    if not modules:
        logger.error("No module_*.md files found in %s", SERIES_DIR)
        return 1

    logger.info("Found %d LPI modules to publish as drafts.", len(modules))
    created: List[Dict[str, str]] = []

    for path in modules:
        md_text = path.read_text(encoding="utf-8")
        title = derive_title(md_text, path.name)
        excerpt = build_excerpt(md_text)
        html = markdown_to_html(md_text)

        logger.info("Publishing draft: %s", title)
        try:
            result = create_draft(base_url, admin_key, title, html, excerpt, TAGS)
        except Exception as exc:  # noqa: BLE001
            logger.error("FAILED to publish '%s': %s", title, exc)
            continue

        post = result["posts"][0]
        post_id = post.get("id", "")
        slug = post.get("slug", "")
        editor_url = f"{base_url}/ghost/#/editor/post/{post_id}"
        preview_url = f"{base_url}/{slug}/" if slug else ""

        created.append({"title": title, "id": post_id, "slug": slug,
                        "editor_url": editor_url, "preview_url": preview_url})
        logger.info("DRAFT CREATED: %s | ID %s | %s", title, post_id, editor_url)

    summary_path = SERIES_DIR / "ghost_publish_summary.json"
    summary_path.write_text(
        json.dumps({"published_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "total": len(modules),
                    "created": len(created),
                    "drafts": created},
                   ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print("\n=== GHOST DRAFT URLS ===")
    for draft in created:
        print(f"{draft['title']}\n    {draft['editor_url']}\n    {draft['preview_url']}")
    print(f"\n{len(created)}/{len(modules)} drafts created.")
    return 0 if len(created) == len(modules) else 1


if __name__ == "__main__":
    raise SystemExit(main())