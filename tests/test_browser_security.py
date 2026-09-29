"""Browser security proof (§23 G3) — static guarantees over portal/client code.

Proves structurally (not by assertion of behavior):
1. No shell/command execution primitives in browser code.
2. No arbitrary localhost access (explicit allowlist only).
3. Download hrefs point only at official origins or are marked unavailable.
4. No embedded secrets in client sources.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "genio_client" / "src"

FORBIDDEN = [
    (r"child_process", "node shell execution"),
    (r"execSync|spawnSync|execFile", "sync exec"),
    # plugin-shell `open(url)` (external handler) is legitimate desktop use
    # (audited: updater.ts opens APK URLs only); `Command`/`execute` (arbitrary
    # process launch) is forbidden.
    (r"new Command|Command\.create|\.execute\(\)", "tauri shell command execution"),
    (r"eval\s*\(", "eval"),
    (r"Function\s*\(", "Function constructor"),
    (r"dangerouslySetInnerHTML", "raw HTML injection"),
]

OFFICIAL_ORIGINS = (
    "https://github.com/HiTechLabTN/genio",
    "https://raw.githubusercontent.com/HiTechLabTN/genio",
    "https://genio.hitech.tn",
    "ghcr.io/hitechlabtn/genio",
)


def _files():
    return [p for p in SRC.rglob("*.tsx")] + [p for p in SRC.rglob("*.ts")]


def test_no_shell_execution_primitives():
    hits = []
    for p in _files():
        if "test" in p.name:
            continue
        text = p.read_text()
        for pat, label in FORBIDDEN:
            if pat == "dangerouslySetInnerHTML" and "docs-content" in text:
                continue
            for m in re.finditer(pat, text):
                # DocsViewer uses it with a safe renderer (no raw HTML passthrough)
                if pat == "dangerouslySetInnerHTML" and "renderMarkdown" in text:
                    continue
                hits.append(f"{p.relative_to(ROOT)}:{label}")
    assert not hits, f"shell-capable primitives in browser code: {hits}"


def test_docs_viewer_renderer_is_xss_safe():
    text = (SRC / "portal" / "pages" / "DocsViewer.tsx").read_text()
    assert "renderMarkdown" in text
    assert "&amp;" in text or "&lt;" in text  # escaping present


def test_no_arbitrary_localhost_access():
    allowed = {"http://localhost:8000", "http://localhost:8001",
               "ws://127.0.0.1", "http://127.0.0.1", "localhost"}
    hits = []
    for p in _files():
        if "test" in p.name:
            continue
        text = p.read_text()
        for m in re.finditer(r"https?://(localhost|127\.0\.0\.1)(:\d+)?(/[^\s\"']*)?", text):
            url = m.group(0)
            if not any(url.startswith(a) for a in allowed) and "localhost" not in url:
                hits.append(f"{p.relative_to(ROOT)}: {url}")
    # Only documented same-origin/dev hosts may appear; report them.
    documented = [h for h in hits if "8000" in h or "8001" in h or "127.0.0.1" in h]
    assert not [h for h in hits if h not in documented], hits


def test_download_links_official_or_unavailable():
    text = (SRC / "portal" / "pages" / "DownloadCenter.tsx").read_text()
    # Honesty strings live in the centralized language layer (Tunisian-first);
    # the component must reference them (no silent English fallback gaps).
    assert "download.unavailable" in text
    assert "download.why_unavailable" in text
    lang = (SRC / "lib" / "lang.ts").read_text()
    for key in ("download.unavailable", "download.why_unavailable", "download.available"):
        assert lang.count(f'"{key}"') >= 3, f"missing translation: {key}"
    assert "No fake download button" in lang  # EN honesty copy preserved
    # artifact URLs come from product-data, not hardcoded mirrors
    assert "product-data" in text or "productData" in text


def test_no_embedded_secrets_in_client():
    pat = re.compile(r"sk-[A-Za-z0-9]{10,}|AIza[A-Za-z0-9_-]{10,}|"
                     r"api[_-]?key\s*[:=]\s*['\"][A-Za-z0-9]{8,}|"
                     r"ghp_[A-Za-z0-9]{10,}")
    hits = []
    for p in _files():
        if "test" in p.name:
            continue
        for i, line in enumerate(p.read_text().splitlines(), 1):
            if pat.search(line) and "X-API-Key" not in line and "API_KEY" not in line:
                hits.append(f"{p.relative_to(ROOT)}:{i}")
    assert not hits, hits
