"""Short-lived Bearer tokens — Phase 20 (zéro clé API dans les URLs).

Format : ``gsk_<exp_ts>_<hmac>`` où hmac = HMAC-SHA256(API_KEY, exp_ts),
comparaison constant-time. TTL 900s par défaut. Sans API_KEY configurée,
aucun token n'est émis (le serveur est en mode ouvert dev, documenté).
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import time

TOKEN_TTL_SECONDS = int(os.getenv("GENIO_TOKEN_TTL", "900"))
_TOKEN_RE = re.compile(r"^gsk_(\d+)_([0-9a-f]{64})$")


def _secret() -> str:
    return os.getenv("GENIO_API_KEY", "")


def mint_token(now: float | None = None) -> tuple[str, int]:
    """Émet (token, expires_in_s). Lève RuntimeError si pas de API_KEY."""
    secret = _secret()
    if not secret:
        raise RuntimeError("no API_KEY configured — token issuance disabled")
    exp = int(now or time.time()) + TOKEN_TTL_SECONDS
    mac = hmac.new(secret.encode(), str(exp).encode(),
                   hashlib.sha256).hexdigest()
    return f"gsk_{exp}_{mac}", TOKEN_TTL_SECONDS


def verify_token(token: str, now: float | None = None) -> bool:
    """True si signature valide ET non expiré (constant-time)."""
    secret = _secret()
    if not secret or not token:
        return False
    m = _TOKEN_RE.match(token.strip())
    if not m:
        return False
    exp = int(m.group(1))
    if exp < int(now or time.time()):
        return False
    want = hmac.new(secret.encode(), str(exp).encode(),
                    hashlib.sha256).hexdigest()
    return hmac.compare_digest(want, m.group(2))
