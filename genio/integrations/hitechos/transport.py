"""Transport Unix Domain Socket — Phase 14.

Messages JSON v1.0 à longueur préfixée (4 octets big-endian) + timeout dur.
Client : `query(sock_path, request_dict, timeout)`.
Aucune dépendance au daemon réel : le serveur de test vit dans les tests.
"""
from __future__ import annotations

import json
import socket
import struct
from typing import Any, Dict

FRAME = ">I"
MAX_FRAME = 8 * 1024 * 1024


class TransportError(OSError):
    """Socket indisponible, timeout, trame corrompue ou déconnexion."""


def _recv_exact(sock: socket.socket, n: int, timeout: float) -> bytes:
    sock.settimeout(timeout)
    buf = b""
    while len(buf) < n:
        try:
            chunk = sock.recv(n - len(buf))
        except socket.timeout as e:
            raise TransportError(f"recv timeout after {timeout:g}s") from e
        if not chunk:
            raise TransportError("peer disconnected mid-frame")
        buf += chunk
    return buf


def query(sock_path: str, request: Dict[str, Any],
          timeout: float = 30.0) -> Dict[str, Any]:
    """Envoie une requête dict et retourne le dict réponse (lève sinon)."""
    payload = json.dumps(request, ensure_ascii=False).encode("utf-8")
    if len(payload) > MAX_FRAME:
        raise TransportError(f"request too large ({len(payload)} bytes)")
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        try:
            sock.connect(sock_path)
        except (FileNotFoundError, ConnectionRefusedError) as e:
            raise TransportError(f"daemon unavailable at {sock_path}: {e}")
        except OSError as e:
            raise TransportError(f"socket error: {e}")
        sock.sendall(struct.pack(FRAME, len(payload)) + payload)
        (size,) = struct.unpack(FRAME, _recv_exact(sock, 4, timeout))
        if size > MAX_FRAME:
            raise TransportError(f"response too large ({size} bytes)")
        raw = _recv_exact(sock, size, timeout)
    finally:
        try:
            sock.close()
        except Exception:
            pass
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception as e:
        raise TransportError(f"invalid JSON response: {e}")
    if not isinstance(data, dict):
        raise TransportError("response is not an object")
    return data
