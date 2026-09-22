"""Server-side voice transcription pipeline (Phase 3 v2.1).

Accepts raw audio bytes (WAV/WebM/Opus) and routes to the best available local
transcriber:

1. ``faster-whisper`` if installed (CTranslate2, CPU-friendly).
2. ``whisper`` (OpenAI) if installed.
3. Ollama ``/api/generate`` with a tiny audio-capable model is NOT used (audio
   transcription across providers is unreliable); instead a deterministic stub
   transcribes empty/silence and returns a structured fallback so the client
   prompt pipeline never breaks.

Gating: ``GENIO_AUDIO_PIPELINE=1`` enables the route. When disabled, the
endpoint returns a 403 with a clear diagnostic.
"""
from __future__ import annotations

import os
import tempfile
from typing import Dict, Optional

AUDIO_PIPELINE = os.environ.get("GENIO_AUDIO_PIPELINE", "0").strip().lower() in ("1", "true", "yes")
TMP_DIR = os.environ.get("GENIO_AUDIO_TMP", "").strip()

_whisper_backend: Optional[str] = None


def _detect_backend() -> Optional[str]:
    """Return 'faster-whisper', 'whisper', or None if neither available."""
    global _whisper_backend
    if _whisper_backend is not None:
        return _whisper_backend
    try:
        import faster_whisper  # noqa: F401
        _whisper_backend = "faster-whisper"
        return _whisper_backend
    except Exception:
        pass
    try:
        import whisper  # noqa: F401
        _whisper_backend = "whisper"
        return _whisper_backend
    except Exception:
        pass
    _whisper_backend = ""
    return None


def transcribe_audio(data: bytes, mime: str = "audio/wav",
                     language: Optional[str] = None) -> Dict[str, object]:
    """Transcribe raw audio bytes to text.

    Returns ``{"text": ..., "backend": ..., "language": ..., "status": ...}``.
    Never raises: any failure degrades to a structured fallback so the client
    VoicePrompt can still route cleanly.
    """
    if not data or len(data) == 0:
        return {"text": "", "backend": "none", "status": "empty",
                "language": language or "und", "error": "no audio payload"}
    backend = _detect_backend()
    if backend is None:
        return _fallback(data, mime, language, reason="no whisper backend")

    # Route to the best available transcriber.
    try:
        if backend == "faster-whisper":
            text = _transcribe_faster_whisper(data, mime, language)
            if text.strip():
                return {"text": text, "backend": "faster-whisper",
                        "language": language or "und", "status": "ok"}
        else:
            text = _transcribe_whisper(data, mime, language)
            if text.strip():
                return {"text": text, "backend": "whisper",
                        "language": language or "und", "status": "ok"}
    except Exception as exc:
        return _fallback(data, mime, language, reason=f"whisper failed: {exc}")
    return _fallback(data, mime, language, reason="empty transcription")


def _transcribe_faster_whisper(data: bytes, mime: str,
                               language: Optional[str]) -> str:
    from faster_whisper import WhisperModel
    path = _write_tmp(data, mime)
    try:
        model = WhisperModel("small", compute_type="int8")
        segments, info = model.transcribe(path, language=language or "auto")
        return " ".join(s.text.strip() for s in segments if s.text.strip())
    finally:
        _cleanup(path)


def _transcribe_whisper(data: bytes, mime: str,
                        language: Optional[str]) -> str:
    import whisper
    path = _write_tmp(data, mime)
    try:
        model = whisper.load_model("small")
        result = model.transcribe(path, language=language)
        return str(result.get("text") or "").strip()
    finally:
        _cleanup(path)


def _write_tmp(data: bytes, mime: str) -> str:
    ext = _ext_for_mime(mime)
    base = TMP_DIR or (tempfile.gettempdir() if False else "")
    import uuid
    path = os.path.join(base or tempfile.gettempdir(),
                        f"genio_audio_{uuid.uuid4().hex[:10]}{ext}")
    with open(path, "wb") as f:
        f.write(data)
    return path


def _cleanup(path: str) -> None:
    try:
        os.remove(path)
    except Exception:
        pass


def _ext_for_mime(mime: str) -> str:
    m = (mime or "").lower()
    if "wav" in m:
        return ".wav"
    if "webm" in m:
        return ".webm"
    if "mp4" in m or "m4a" in m:
        return ".m4a"
    return ".bin"


def _fallback(data: bytes, mime: str, language: Optional[str],
              reason: str) -> Dict[str, object]:
    """Deterministic fallback so the audio pipeline still routes cleanly."""
    return {
        "text": "",
        "backend": "none",
        "status": "fallback",
        "language": language or "und",
        "error": reason,
        "audio_bytes": len(data),
        "mime": mime,
    }