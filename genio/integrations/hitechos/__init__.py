"""HiTech-OS integration contract — Phase 14 (adaptateur, PAS de fusion).

Couche d'adaptation propre : Genio ne dépend NI n'importe du code interne
de HiTech-OS. Protocole JSON v1.0 versionné sur Unix Domain Socket.
Transport préféré : /run/hitechos/ai.sock, repli /run/genio/genio.sock.
"""
from __future__ import annotations

PROTOCOL_VERSION = "1.0"
DEFAULT_SOCK_HITECHOS = "/run/hitechos/ai.sock"
DEFAULT_SOCK_GENIO = "/run/genio/genio.sock"
