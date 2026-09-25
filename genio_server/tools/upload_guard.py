"""Upload security — Phase 21 (octets magiques, jamais le MIME client).

- sniff(data) : type réel par magic bytes (binaires) ou heuristique texte.
- validate_upload : extension déclarée compatible avec le contenu réel.
- Quota par session (défaut 50MB) + purge des stagings expirés (>1h).
- Fichiers stagés en 0o600 (défense en profondeur ; noexec = montage hôte).
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

SESSION_QUOTA_BYTES = int(os.getenv("GENIO_UPLOAD_QUOTA_BYTES",
                                    str(50 * 1024 * 1024)))
STAGE_TTL_SECONDS = int(os.getenv("GENIO_UPLOAD_TTL_SECONDS", "3600"))

_MAGIC: Tuple[Tuple[bytes, str], ...] = (
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"\xff\xd8\xff", "jpg"),
    (b"GIF87a", "gif"),
    (b"GIF89a", "gif"),
    (b"RIFF", "wav"),       # + "WAVE" à l'offset 8 (vérifié ci-dessous)
    (b"\x1a\x45\xdf\xa3", "webm"),
    (b"%PDF", "pdf"),
    (b"PK\x03\x04", "zip"),
    (b"ID3", "mp3"),
)

_EXT_OF_MAGIC = {"png": {".png"}, "jpg": {".jpg", ".jpeg"},
                 "gif": {".gif"}, "wav": {".wav"}, "webm": {".webm"},
                 "pdf": {".pdf"}, "zip": {".zip"}, "mp3": {".mp3"}}

# Extensions texte/code admises SANS magie (contenu décodable requis).
_TEXT_EXTS = {".txt", ".md", ".py", ".js", ".ts", ".json", ".yaml", ".yml",
              ".log", ".csv", ".xml", ".html", ".css", ".c", ".cpp", ".java",
              ".rs", ".go", ".rb", ".sh", ".sql"}
_MEDIA_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".mp3", ".wav",
               ".m4a", ".ogg", ".pdf", ".mp4", ".webm", ".mov", ".avi",
               ".mkv", ".xlsx", ".docx"}


def sniff(data: bytes) -> str:
    """Type réel : 'png'|'jpg'|…|'text'|'binary'|'empty'."""
    if not data:
        return "empty"
    for magic, kind in _MAGIC:
        if data.startswith(magic):
            if kind == "wav" and data[8:12] != b"WAVE":
                continue
            return kind
    # MP3 sans ID3 (sync frame) / M4A (ftyp) / WEBP (RIFF+WEBP).
    if data[:2] == b"\xff\xfb" or data[:2] == b"\xff\xf3":
        return "mp3"
    if data[4:8] == b"ftyp":
        return "m4a"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "webp"
    try:
        data.decode("utf-8")
        return "text"
    except Exception:
        return "binary"


def validate_upload(data: bytes, filename: str) -> tuple:
    """(ext_ok | None, raison). Jamais de confiance au MIME client."""
    from genio_server.tools.fs_guard import sanitize_ext
    ext = sanitize_ext(filename)
    if ext == ".bin":
        return None, "extension refusée"
    kind = sniff(data)
    if kind == "empty":
        return None, "payload vide"
    if kind == "text":
        if ext in _TEXT_EXTS:
            return ext, ""
        return None, f"texte déguisé en {ext}"
    if kind == "binary":
        return None, "binaire non identifié refusé"
    allowed = _EXT_OF_MAGIC.get(kind, set()) | (
        {".mp4", ".mov", ".avi", ".mkv"} if kind == "webm" else set()) | (
        {".m4a"} if kind in ("m4a",) else set())
    # webp/mp4/mov/avi/mkv, m4a : conteneurs sans magie stricte -> tolérés
    # si l'extension est média (sniff a déjà exclu l'exécutable brut).
    if ext in allowed or (ext in _MEDIA_EXTS and kind in ("webm", "m4a", "mp3")):
        return ext, ""
    return None, f"contenu {kind} incompatible avec {ext}"


_session_usage: Dict[str, int] = {}


def check_quota(session: str, nbytes: int,
                quota: int = SESSION_QUOTA_BYTES) -> Optional[str]:
    """Retourne None si OK (et comptabilise), sinon la raison du refus."""
    used = _session_usage.get(session, 0)
    if used + nbytes > quota:
        return (f"quota session dépassé ({used + nbytes} > {quota} octets)")
    _session_usage[session] = used + nbytes
    return None


def reset_quota(session: str) -> None:
    _session_usage.pop(session, None)


def purge_expired(root: str | Path, ttl: int = STAGE_TTL_SECONDS) -> int:
    """Supprime les stagings plus vieux que ttl. Retourne le nombre."""
    root = Path(root)
    if not root.is_dir():
        return 0
    now = time.time()
    n = 0
    for p in root.iterdir():
        try:
            if p.is_file() and now - p.stat().st_mtime > ttl:
                p.unlink()
                n += 1
        except Exception:
            continue
    return n


def secure_write(path: str, data: bytes) -> None:
    """Écriture 0o600 (défense en profondeur)."""
    with open(path, "wb") as f:
        f.write(data)
    try:
        os.chmod(path, 0o600)
    except Exception:
        pass
