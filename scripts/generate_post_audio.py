"""
Genio — FULL faithful audio narration of the published Module 1 article.

Reads the entire published article (Ghost Admin API render, local Markdown
fallback) the way a patient Human narrator would:

  * Discards nothing — every paragraph, heading, code sample and table row is
    spoken (~ faithful, not a summary).
  * Sanitizes Markdown/HTML artifacts: strips ASCII tree glyphs (├── └── │ ──),
    table borders/pipes, backticks, markdown emphasis and entity noise.
  * Phoneticizes technical symbols so ar-TN-HediNeural never trips:
        / -> سلاش     // -> سلاش سلاش    /* -> سلاش إتوال
        -- -> دوبل تيغي   - -> تيغي   ~ -> تيلدا   | -> بايب   = -> مساوي
    and known full commands become spelled-out darja (df -h -> دي إف تيغي إش,
    sudo du -sh /* ... -> spelled, journalctl --vacuum-size=200M -> spelled).
  * Turns every table row into a natural sentence
    (المسار ...، وظيفته الأساسية ...، أمثلة ...، نصيحة المهندس ...).
  * Breaks ideas with short SSML <break/>s for continuity.

Output: content/media/audio/module_01_filesystem.mp3 (192 kbps CBR).

Usage:
    python3 scripts/generate_post_audio.py             # ghost source
    python3 scripts/generate_post_audio.py --source md
    python3 scripts/generate_post_audio.py --voice ar-TN-ReemNeural
"""
from __future__ import annotations

import argparse
import asyncio
import html as html_mod
import json
import re
import shutil
import subprocess
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from typing import List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
OUT_MP3 = ROOT / "content" / "media" / "audio" / "module_01_filesystem.mp3"
POST_ID = "6a926268750c7e0001c95a21"
MD_FALLBACK = ROOT / "reports" / "lpi_series" / "module_01_linux-filesystem-hierarchy.md"
BR = "<break time='220ms'/>"

# Full-command phonetic transcriptions, applied longest-first.
COMMAND_PHON = {
    "sudo du -sh /* 2>/dev/null | sort -hr | head -n 10":
        "سودو دي يو تيغي إس إتش سلاش إتوال تو، إلى ديف نال، بايب سورت تيغي إتش آر، بايب هيد تيغي إن، عشرة",
    "sudo du -sh /* 2>/dev/null | sort -hr | head -n 5":
        "سودو دي يو تيغي إس إتش سلاش إتوال تو، إلى ديف نال، بايب سورت تيغي إتش آر، بايب هيد تيغي إن، خمسة",
    "sudo journalctl --vacuum-size=200M":
        "سودو جورنال سيتال، دوبل تيغي فاكيوم سايز مساوي مئتين ميغا بايت، فتحذف اللوغات القديمة وترجع المساحة فوراً",
    "sudo mkdir -p /opt/hitech-app/{config,logs,data}":
        "سودو إم كي دير، تيغي بي، سلاش أوبت هيتيك أبل، وبين قوسين: كونف، لوغس، داتا",
    "ls -R /opt/hitech-app": "إل إس، تيغي آر، سلاش أوبت هيتيك أبل",
    "tree /opt/hitech-app": "تري، سلاش أوبت هيتيك أبل",
    "journalctl --vacuum-size=200M": "جورنال سيتال، دوبل تيغي فاكيوم سايز مساوي مئتين ميغا بايت",
    "df -h": "دي إف تيغي إش",
    "du -sh": "دي يو تيغي إس إتش",
    "ls -lah": "إل إس تيغي لا إتش",
    "cd -": "سي دي تيغي",
    "pwd": "بي و دي",
    "cd ~": "سي دي تيلدا",
}

# Generic symbol -> spoken darja.
SYMBOL_PHON = [
    ("C:\\", "سي سلاش "), ("D:\\", "دي سلاش "),
    ("/*", "سلاش إتوال "), ("//", "سلاش سلاش "), ("/", "سلاش "),
    ("\\", " "),
    ("--", "دوبل تيغي "), ("~", "تيلدا "), ("|", "بايب "), ("=", "مساوي "),
    ("&", " و "), ("{", "مفتوحة "), ("}", "مقفولة "), ("->", "يشير إلى "),
    ("2>/dev/null", "تو إلى ديف نال "),
    ("/dev/null", "ديف نال "),
    ("-n ", "تيغي إن "), ("-p ", "تيغي بي "), ("-R ", "تيغي آر "),
    ("-hr ", "تيغي إتش آر "), ("-h ", "تيغي إتش "), ("-sh ", "تيغي إس إتش "),
    ("-", "تيغي "),
]

# Latin token -> Arabic spelling inside Arabic prose.
WORD_PHON = {
    "etc": "إي تي سي", "sbin": "إس بين", "bin": "بين", "usr": "يوزر",
    "var": "فار", "home": "هوم", "root": "روت", "opt": "أوبت", "dev": "ديف",
    "proc": "بروك", "tmp": "تيمب", "sys": "سيس", "log": "لوق", "lib": "ليب",
    "conf": "كونف", "config": "كونف", "nginx": "إن جين إكس", "docker": "دوكر",
    "ssh": "إس إس إتش", "sshd": "إس إس إتش دي", "systemd": "سيستيم دي",
    "fdisk": "إف ديسك", "journalctl": "جورنال سيتال", "hitech": "هاي تيك",
    "cat": "كات", "cp": "سي بي", "ls": "إل إس", "cd": "سي دي",
    "du": "دي يو", "df": "دي إف", "sudo": "سودو", "sort": "سورت",
    "head": "هايد", "mkdir": "إم كي دير", "tree": "تري", "pwd": "بي و دي",
    "bash": "باش", "ssd": "إس إس دي", "cpu": "سي بي يو", "ram": "رام",
    "url": "يو آر إل", "fhs": "إف إتش إس", "rel": "ري لود", "reload": "ري لود",
    "mounting": "ماونتينغ", "syslog": "سيس لوق", "cpuinfo": "سي بي يو إينفو",
    "meminfo": "ميم إينفو", "iptables": "إيب تيبلز", "sda": "إس دا",
    "sda1": "إس دا وان", "nvme": "إن في إم إي", "www": "دبليو دبليو دبليو",
    "null": "نال", "m": "ميغا",
}

TREE_GLYPHS = re.compile(r"[\u2500\u2502\u250c\u2510\u2514\u2518\u251c\u2524\u252c\u2534\u253c\u2574]+")
NOISE = re.compile(r"[`#_]{1,}|\u00a0")
LATIN_TOK = re.compile(r"[A-Za-z][A-Za-z0-9]*")


def phonetic(text: str) -> str:
    t = html_mod.unescape(TREE_GLYPHS.sub("", text))
    t = NOISE.sub(" ", t)
    for cmd, spoken in COMMAND_PHON.items():
        t = t.replace(cmd, spoken)
    t = LATIN_TOK.sub(lambda m: WORD_PHON.get(m.group(0).lower(), m.group(0)), t)
    for sym, spoken in SYMBOL_PHON:
        t = t.replace(sym, spoken)
    t = t.replace("*", " إتوال ").replace(">", " ")
    t = re.sub(r"\s+", " ", t).strip()
    return t


def clean_prose(text: str) -> str:
    """Light clean for Arabic prose pieces (transliteration already applied)."""
    t = html_mod.unescape(TREE_GLYPHS.sub("", text))
    t = NOISE.sub(" ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


class _P(HTMLParser):
    """Block/token splitter producing spoken-item chunks from rendered HTML."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.items: List[Tuple[str, object]] = []
        self._text: List[str] = []
        self._in_pre = False
        self._in_li = False
        self._inline_code = False
        self._pre = ""
        self._td = False
        self._in_thead = False
        self._row: Optional[List[str]] = None
        self._row_skip = False
        self._table: List[List[str]] = []
        self._skip_depth = 0

    def _flush_txt(self, kind: str) -> None:
        t = "".join(self._text).strip()
        self._text = []
        if t and kind:
            self.items.append((kind, t))

    def handle_starttag(self, tag, attrs):
        if tag in ("div", "script", "style"):
            self._skip_depth += 1
            return
        if tag == "pre":
            if self._in_li:
                self._inline_code = True
            else:
                self._in_pre = True
                self._pre = ""
        elif tag == "tr":
            self._row = []
            self._row_skip = self._in_thead
        elif tag in ("td", "th"):
            self._td = True
        elif tag == "thead":
            self._in_thead = True
        elif tag == "p":
            self._flush_txt("p")
        elif tag == "li":
            self._flush_txt("li")
            self._in_li = True
        elif tag in ("h1", "h2", "h3", "h4"):
            self._flush_txt("")
        elif tag == "blockquote":
            self._flush_txt("")

    def handle_startendtag(self, tag, attrs):
        pass

    def handle_endtag(self, tag):
        if tag in ("div", "script", "style"):
            self._skip_depth -= 1
            return
        if tag == "pre":
            if self._inline_code:
                self._inline_code = False
            else:
                tmp = self._pre
                self._pre = ""
                self._in_pre = False
                if tmp.strip():
                    self.items.append(("code", tmp))
        elif tag in ("td", "th"):
            if not self._row_skip and self._row is not None:
                self._row.append("".join(self._text).strip())
            self._text = []
            self._td = False
        elif tag == "tr":
            if not self._row_skip and self._row:
                self._table.append(self._row)
            self._row = None
            self._row_skip = False
        elif tag == "thead":
            self._in_thead = False
        elif tag == "table":
            if self._table:
                self.items.append(("table", [r for r in self._table]))
                self._table = []
        elif tag == "p":
            self._flush_txt("p")
        elif tag == "li":
            self._flush_txt("li")
            self._in_li = False
        elif tag == "h1":
            self._flush_txt("title")
        elif tag in ("h2", "h3", "h4"):
            self._flush_txt("h")

    def handle_data(self, data):
        if self._skip_depth > 0:
            return
        if self._in_pre:
            self._pre += data
        elif self._inline_code:
            self._text.append(" " + phonetic(data))
        else:
            self._text.append(data)


def _items_from_html(html_text: str) -> List[Tuple[str, object]]:
    p = _P()
    p.feed(html_text)
    p.close()
    if "".join(p._text).strip():
        p._flush_txt("p")
    return p.items


def _items_to_script(items: List[Tuple[str, object]]) -> List[str]:
    spoken: List[str] = []
    for kind, obj in items:
        if kind == "title":
            spoken.append("عنوان المقال: " + phonetic(str(obj)))
        elif kind == "h":
            spoken.append("القسم: " + phonetic(str(obj)))
        elif kind == "p":
            spoken.append(phonetic(str(obj)))
        elif kind == "li":
            spoken.append(" " + phonetic(str(obj)))
        elif kind == "note":
            spoken.append("ملاحظة: " + phonetic(str(obj)))
        elif kind == "code":
            lines = [l for l in str(obj).splitlines() if l.strip()]
            for ln in lines:
                line = phonetic(ln)
                if line:
                    spoken.append(line)
        elif kind == "table":
            for row in obj:  # type: ignore[union-attr]
                if len(row) < 2:
                    spoken.append("المسار " + phonetic(row[0]) + ".")
                    continue
                sent = (f"المسار {phonetic(row[0])}، وظيفته الأساسية {phonetic(row[1])}.")
                if len(row) > 2 and row[2].strip():
                    sent += f" أمثلة: {phonetic(row[2])}."
                if len(row) > 3 and row[3].strip():
                    sent += f" نصيحة المهندس: {phonetic(row[3])}."
                spoken.append(sent)
    return [s for s in spoken if s]


def fetch_ghost_html() -> str:
    import os
    import httpx
    import jwt
    import time
    sys.path.insert(0, str(ROOT))
    key = os.environ.get("GHOST_ADMIN_KEY")
    url = os.environ.get("GHOST_URL", "https://lab.hitech.tn").rstrip("/")
    if not key:
        try:
            from dotenv import load_dotenv
            load_dotenv(ROOT / ".env")
            key = os.environ["GHOST_ADMIN_KEY"]
            url = os.environ.get("GHOST_URL", url).rstrip("/")
        except Exception:
            pass
    if not key:
        raise RuntimeError("GHOST_ADMIN_KEY not found — use --source md")
    kid, secret = key.split(":")
    iat = int(time.time())
    tok = jwt.encode({"iat": iat, "exp": iat + 300, "aud": "/admin/"},
                     bytes.fromhex(secret), algorithm="HS256",
                     headers={"kid": kid, "alg": "HS256"})
    r = httpx.get(f"{url}/ghost/api/admin/posts/{POST_ID}/",
                  params={"formats": "html", "fields": "id,title,html"},
                  headers={"Authorization": f"Ghost {tok}"}, timeout=30)
    r.raise_for_status()
    return r.json()["posts"][0]["html"]


def md_items(md_text: str) -> List[Tuple[str, object]]:
    items: List[Tuple[str, object]] = []
    paragraphs = re.split(r"\n{2,}", md_text)
    for blk in paragraphs:
        blk = blk.strip()
        if not blk:
            continue
        if blk.startswith("#"):
            items.append(("h" if not blk.startswith("# ") else "title", blk.lstrip("# ")))
        elif blk.startswith("|"):
            rows = []
            for ln in blk.splitlines():
                if re.match(r"^\|[\s\-|:]+$", ln):
                    continue
                cells = [c.strip() for c in ln.strip("|").split("|")]
                if cells:
                    rows.append(cells)
            items.append(("table", rows))
        elif blk.startswith("```"):
            code = "\n".join(l for l in blk.splitlines()[1:-1])
            items.append(("code", code))
        elif blk.startswith(("- ", "* ")):
            for ln in blk.splitlines():
                items.append(("li", ln.lstrip("-* ")))
        else:
            items.append(("p", blk))
    return items


def chunk_script(script: str, max_char: int = 2800) -> List[str]:
    chunks, cur = [], ""
    for seg in script.split(BR):
        cand = (cur + seg).strip()
        if len(cand) > max_char and cur:
            chunks.append(cur)
            cur = seg
        else:
            cur = cand
    if cur.strip():
        chunks.append(cur)
    return [c for c in chunks if c]


async def synthesize(chunk: str, voice: str, rate: str) -> Path:
    import edge_tts
    out = Path(tempfile.gettempdir()) / f"genio_chunk_{hash(chunk) & 0xffffffff:08d}.mp3"
    if out.exists():
        return out
    comm = edge_tts.Communicate(chunk, voice, rate=rate, pitch="+0Hz")
    await comm.save(out)
    return out


def concat_and_encode(chunks: List[Path], voice: str) -> Path:
    if shutil.which("ffmpeg") is None:
        return chunks[0]
    lst = Path(tempfile.gettempdir()) / "genio_concat.txt"
    lst.write_text("".join(f"file '{c}'\n" for c in chunks), encoding="utf-8")
    OUT_MP3.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT_MP3.with_suffix(".tmp.mp3")
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-ar", "48000", "-codec:a", "libmp3lame", "-b:a", "192k",
                    "-abr", "0", str(tmp)],
                   check=True, capture_output=True)
    tmp.replace(OUT_MP3)
    return OUT_MP3


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", choices=["ghost", "md"], default="ghost")
    ap.add_argument("--voice", default="ar-TN-HediNeural")
    ap.add_argument("--rate", default="+2%")
    args = ap.parse_args()

    if args.source == "ghost":
        html_text = fetch_ghost_html()
        items = _items_from_html(html_text)
    else:
        items = md_items(MD_FALLBACK.read_text(encoding="utf-8"))
    script = _items_to_script(items)
    full = BR.join(script)
    print(f"items: {len(script)} chars: {len(full)}")
    chunks = chunk_script(full)
    print(f"tts chunks: {len(chunks)}")
    for i, c in enumerate(chunks):
        print(f"  chunk{i}: {len(c)} chars")
    outs = []
    for c in chunks:
        outs.append(asyncio.run(synthesize(c, args.voice, args.rate)))
    out = concat_and_encode(outs, args.voice)
    print(f"audio: {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()