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
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

app = FastAPI(title="VODER audio service")
# Sovereign web UI (genio_client) appelle POST /synthesize depuis le navigateur.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
VRAM_CAP_MB = 3200
UNLOAD_IDLE_S = 300

_lock = threading.Lock()
_tts = None
_last_used = 0.0


class SynthReq(BaseModel):
    text: str
    speaker_wav: str = ""
    # RC-gate : "ar" n'est PAS supporté par Qwen3-TTS (supportés : auto,
    # chinese, english, french, german, italian, japanese, korean,
    # portuguese, russian, spanish). Défaut "auto" (détection multilingue,
    # couvre l'arabe) ; toute autre valeur non supportée -> 422 explicite
    # au lieu d'un 500 après échec.
    language: str = "auto"


SUPPORTED_LANGUAGES = frozenset({
    "auto", "chinese", "english", "french", "german", "italian",
    "japanese", "korean", "portuguese", "russian", "spanish",
})


# Voix masculine souveraine par défaut (145.5Hz médian mesuré — profil grave
# "Jarvis"). Un speaker_wav explicite et existant prime toujours dessus.
DEFAULT_SPEAKER = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "voices", "speaker_male_sovereign.wav")


def _jarvis_filter(wav: "np.ndarray", sr: int) -> "np.ndarray":
    """Post-filtre Jarvis : bass shelf +6dB @120Hz (autorité grave) +
    léger sheen métallique (excitation harmonique douce à 5%).
    Numpy pur — aucune dépendance supplémentaire.
    """
    import numpy as np
    x = wav.astype(np.float64)
    # Bass shelf : one-pole lowpass mixé à +6dB sous ~120Hz.
    alpha = 1.0 - float(np.exp(-2.0 * np.pi * 120.0 / sr))
    y = np.zeros_like(x)
    acc = 0.0
    for i in range(x.shape[0]):
        acc += alpha * (x[i] - acc)
        y[i] = acc
    x = x + y  # +6dB graves
    # Sheen : 5% d'harmonique 2 douce (tanh) pour la brillance métallique.
    x = x + 0.05 * np.tanh(2.0 * x)
    peak = float(np.max(np.abs(x))) or 1.0
    if peak > 0.98:
        x = x * (0.98 / peak)
    return x.astype(np.float32)


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
    lang = (req.language or "auto").strip().lower()
    if lang not in SUPPORTED_LANGUAGES:
        raise HTTPException(
            422, f"langue non supportée: {req.language!r} "
                 f"(supportées: {sorted(SUPPORTED_LANGUAGES)})")
    try:
        tts = _get_tts()
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    with _lock:
        ref = req.speaker_wav if req.speaker_wav and os.path.exists(req.speaker_wav) else ""
        if not ref and os.path.exists(DEFAULT_SPEAKER):
            ref = DEFAULT_SPEAKER  # voix masculine souveraine par défaut
        if ref:
            if not tts.extract_voice(ref):
                raise HTTPException(422, "extract_voice a échoué sur " + ref)
        elif tts.voice_prompt is None:
            raise HTTPException(422, "speaker_wav introuvable et aucune voix "
                                     "en cache — fournissez un wav de référence")
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.close()
        ok = tts.synthesize(req.text.strip(), tmp.name, language=lang)
    _maybe_unload()
    if not ok:
        raise HTTPException(500, "synthèse TTS échouée")
    # Post-filtre Jarvis (grave + sheen) appliqué sur le wav cloné.
    try:
        import soundfile as sf
        import numpy as np
        data, sr = sf.read(tmp.name, dtype="float32")
        mono = data.mean(axis=1) if data.ndim > 1 else data
        sf.write(tmp.name, _jarvis_filter(np.asarray(mono), sr), sr)
    except Exception as e:
        print(f"[voder] jarvis filter skipped: {e}")
    return FileResponse(tmp.name, media_type="audio/wav",
                        filename="genio_tts.wav")
