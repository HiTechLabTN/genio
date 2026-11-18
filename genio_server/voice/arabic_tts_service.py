#!/usr/bin/env python3
"""Genio Arabic TTS sidecar — Partie voix arabe (port 5051, localhost only).

POST /synthesize {"text": "...", "language": "ar"} → audio/wav (FileResponse).
GET /health → {"status", "backend", "model", "device"}.

Backend: facebook/mms-tts-ara (VITS, CPU) — license CC-BY-NC-4.0,
one-time download ~150MB into the HF hub cache (disclosed, never silent).
Speaks Modern Standard Arabic phonetics; Tunisian-dialect text written in
Arabic script is intelligible but NOT dialect-authentic — documented limit.

Design notes (closure-grade honesty, mirrors voder_service style):
- Arabic ONLY: language must be "ar" (422 otherwise). French/English keep
  their existing paths (browser SpeechSynthesis + Qwen3-TTS) untouched.
- Never fake audio: 503 if the model is absent/unloadable, 500 on real
  synthesis failure, 400 on empty text. No silent fallbacks.
- Lazy-load on first request under a lock (one synthesis at a time);
  CPU-only by default (GENIO_AR_TTS_DEVICE=cpu) to avoid GPU contention
  with Ollama/Qwen. No VRAM used.
- No downloads at import: weights fetch on first /synthesize (or via an
  explicit pre-warm), always logged with size + license.
"""
from __future__ import annotations

import io
import logging
import os
import threading

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

logger = logging.getLogger("arabic_tts")

app = FastAPI(title="Genio Arabic TTS sidecar")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

MODEL_ID = os.getenv("GENIO_AR_TTS_MODEL", "facebook/mms-tts-ara")
DEVICE = os.getenv("GENIO_AR_TTS_DEVICE", "cpu").strip().lower() or "cpu"
MAX_CHARS = int(os.getenv("GENIO_AR_TTS_MAX_CHARS", "2000"))

_lock = threading.Lock()
_bundle = None  # (tokenizer, model, sampling_rate)


class SynthReq(BaseModel):
    text: str
    language: str = "ar"


def _load_bundle():
    """Lazy-load tokenizer+model once. Raises RuntimeError (→ 503)."""
    global _bundle
    with _lock:
        if _bundle is not None:
            return _bundle
        try:
            from transformers import VitsModel, VitsTokenizer
        except Exception as exc:
            raise RuntimeError(f"transformers VITS unavailable: {exc}")
        logger.warning(
            "arabic-tts: loading %s (one-time download ~150MB, "
            "license CC-BY-NC-4.0, device=%s)", MODEL_ID, DEVICE)
        try:
            tokenizer = VitsTokenizer.from_pretrained(MODEL_ID)
            model = VitsModel.from_pretrained(MODEL_ID).to(DEVICE)
            model.eval()
        except Exception as exc:
            raise RuntimeError(f"arabic TTS weights unavailable "
                               f"({MODEL_ID}): {exc}")
        sr = int(getattr(model.config, "sampling_rate", 22050) or 22050)
        _bundle = (tokenizer, model, sr)
        logger.warning("arabic-tts: model ready (sr=%d)", sr)
        return _bundle


@app.get("/health")
def health():
    import torch
    return {"status": "ok" if _bundle is not None else "idle",
            "backend": "mms-tts-ara",
            "model": MODEL_ID,
            "device": DEVICE,
            "torch": getattr(torch, "__version__", "?")}


@app.post("/synthesize")
def synthesize(req: SynthReq):
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(400, "text vide")
    if len(text) > MAX_CHARS:
        raise HTTPException(422, f"text too long ({len(text)} > {MAX_CHARS})")
    lang = (req.language or "ar").strip().lower()
    if lang != "ar":
        raise HTTPException(
            422, f"this service speaks Arabic only (got {req.language!r}); "
                 f"use the French/English voice paths for other languages")
    # At least some Arabic script required — Latin-only text would produce
    # misleading phonetics from an Arabic acoustic model.
    if not any("\u0600" <= ch <= "\u06FF" for ch in text):
        raise HTTPException(
            422, "no Arabic script in text — this voice reads Arabic script")
    try:
        tokenizer, model, sr = _load_bundle()
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))
    try:
        import torch
        with _lock:
            inputs = tokenizer(text, return_tensors="pt")
            with torch.no_grad():
                out = model(**{k: v.to(DEVICE) for k, v in inputs.items()}).waveform
        wav = out.squeeze().cpu().float().numpy()
    except Exception as exc:
        logger.exception("arabic-tts synthesis failed")
        raise HTTPException(500, f"synthèse TTS arabe échouée: {exc}")
    import soundfile as sf
    buf = io.BytesIO()
    sf.write(buf, wav, sr, format="WAV", subtype="PCM_16")
    return Response(content=buf.getvalue(), media_type="audio/wav",
                    headers={"Content-Disposition":
                             'attachment; filename="genio_ar_tts.wav"'})
