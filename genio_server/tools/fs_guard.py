"""Filesystem boundary guard — Phase 8.

Toute autorisation AFTER canonicalisation (realpath) : liens symboliques
vicieux et `../` neutralisés AVANT la décision. Périmètres :
- workspace_only : sous le workspace de session désigné uniquement.
- read_only_system : lecture seule, jamais d'écriture, jamais de secrets.
- none : aucun accès fichier.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

_CRED_NAMES = (".ssh", "id_rsa", "id_ed25519", ".pem", ".env", ".vault",
               "credentials", "shadow", "gshadow", "passwd")
_BLOCKED_PREFIXES = ("/etc/", "/root/", "/proc/", "/sys/",
                     "/var/run/", "/run/systemd/", "/run/docker.sock")
_BLOCKED_EXACT = {"/etc", "/root", "/proc", "/sys", "/dev",
                  "/var/run/docker.sock"}
_DEV_OK = {"/dev/null", "/dev/stdout", "/dev/stderr", "/dev/stdin",
           "/dev/zero", "/dev/urandom"}
_SAFE_EXT_RE = re.compile(r"^\.[A-Za-z0-9]{1,10}$")


def canonicalize(path: str | Path) -> str:
    """realpath strict=False : résout ce qui existe, normalise le reste."""
    p = os.path.abspath(os.fspath(path))
    try:
        return os.path.realpath(p, strict=False)
    except TypeError:
        return p
    except Exception:
        return p


def _is_cred(name: str) -> bool:
    low = name.lower()
    return any(pat in low for pat in _CRED_NAMES)


def authorize(path: str | Path, workspace: Optional[str | Path] = None,
              scope: str = "workspace_only",
              for_write: bool = True) -> Optional[str]:
    """Retourne None si autorisé, sinon la raison du refus.

    L'autorisation porte TOUJOURS sur le chemin canonicalisé.
    """
    canon = canonicalize(path)
    base = os.path.basename(canon)
    # Secrets : jamais (lecture comme écriture).
    if _is_cred(base) or _is_cred(canon):
        return f"credential path refused: {base}"
    if scope == "read_only_system":
        # Lecture seule : autorisée sauf secrets/credential ci-dessus.
        if for_write:
            return "read-only scope: write refused"
        return None
    # Sockets/périphériques/système.
    if canon in _BLOCKED_EXACT or canon.startswith(_BLOCKED_PREFIXES):
        return f"system path refused: {canon}"
    if canon.startswith("/dev/") and canon not in _DEV_OK:
        return f"device refused: {canon}"
    if scope == "none":
        return "filesystem scope none: no file access"
    if scope == "read_only_system":
        if for_write:
            return "read-only scope: write refused"
        return None
    # workspace_only (défaut) : sous le workspace après canonicalisation.
    if workspace is None:
        return "workspace_only scope requires a workspace root"
    root = canonicalize(workspace)
    if canon != root and not canon.startswith(root + os.sep):
        return f"outside workspace: {canon} not under {root}"
    return None


def sanitize_ext(name: str) -> str:
    """Extension assainie pour fichiers stagés (nom client non fiable)."""
    ext = os.path.splitext(os.path.basename(name or ""))[1].lower()
    if _SAFE_EXT_RE.match(ext or ""):
        return ext
    return ".bin"


def stage_path(root: str | Path, kind: str, ext: str, token: str) -> str:
    """Chemin stagé server-generated + autorisé (lève ValueError si refus)."""
    import uuid
    safe_ext = sanitize_ext(f"x{ext}")
    cand = os.path.join(canonicalize(root),
                        f"{kind}_{token or uuid.uuid4().hex[:8]}{safe_ext}")
    reason = authorize(cand, workspace=root, for_write=True)
    if reason is not None:
        raise ValueError(reason)
    return cand
