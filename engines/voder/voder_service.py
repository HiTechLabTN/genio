#!/usr/bin/env python3
"""VODER audio service — Partie voix (port 5050).

POST /synthesize {"text": "...", "speaker_wav": "/path.wav", "language": "ar"}
  → streaming audio/wav chunké (FileResponse, pas de fake : 503 honnête si
  le backend TTS n'est pas chargé).
GET /health → {"status", "backend", "vram_mb", "model"}.

Backend : VODER QwenTTS (Qwen3-TTS-12Hz-1.7B-Base, bf16 cuda:0) —
extract_voice(speaker_wav) puis synthesize(text, out, language).
Lazy-load au premier appel + déchargement sur idle (VRAM cap 3.2GB en régime
établi : le modèle ne reste résident que pendant le service actif).
"""
import os
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "src"))

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

app = FastAPI(title="VODER audio service")
VRAM_CAP_MB = 3200
UNLOAD_IDLE_S = 300

_lock = threading.Lock()
_tts = None
_last_used = 0.0


class SynthReq(BaseModel):
    text: str
    speaker_wav: str = ""
    language: str = "ar"


def _vram_mb() -> float:
    try:
        import torch
        if torch.cuda.is_available():
            return torch.cuda.memory_allocated(0) / 1024 / 1024
    except Exception:
        pass
    return 0.0


def _get_tts():
    global _tts, _last_used
    with _lock:
        _last_used = time.time()
        if _tts is not None:
            return _tts
        from voder import QwenTTS  # noqa: E402  (VODER engine, src/voder.py)
        _tts = QwenTTS()
        if _tts.model is None:
            _tts = None
            raise RuntimeError("QwenTTS backend failed to load "
                               "(poids absents ?)")
        return _tts


def _maybe_unload():
    global _tts
    import torch
    with _lock:
        if _tts is not None and time.time() - _last_used > UNLOAD_IDLE_S:
            _tts = None
            if torch.cuda.is_available():
                torch.cuda.empty_cache()


@app.get("/health")
def health():
    return {"status": "ok" if _tts is not None else "idle",
            "backend": "voder-qwen3-tts-1.7b",
            "vram_mb": round(_vram_mb(), 1),
            "vram_cap_mb": VRAM_CAP_MB}


@app.post("/synthesize")
def synthesize(req: SynthReq):
    if not req.text or not req.text.strip():
        raise HTTPException(400, "text vide")
    try:
        tts = _get_tts()
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    with _lock:
        if req.speaker_wav and os.path.exists(req.speaker_wav):
            if not tts.extract_voice(req.speaker_wav):
                raise HTTPException(422, "extract_voice a échoué sur "
                                         + req.speaker_wav)
        elif tts.voice_prompt is None:
            raise HTTPException(422, "speaker_wav introuvable et aucune voix "
                                     "en cache — fournissez un wav de référence")
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.close()
        ok = tts.synthesize(req.text.strip(), tmp.name,
                            language=req.language or "ar")
    _maybe_unload()
    if not ok:
        raise HTTPException(500, "synthèse TTS échouée")
    return FileResponse(tmp.name, media_type="audio/wav",
                        filename="genio_tts.wav")
