"""User identity + login sessions — OAuth foundation (voice/identity mission).

Storage reuses the existing sessions.db (aiosqlite, same file as the agent
session store) with two NEW tables (CREATE IF NOT EXISTS — never touches
existing tables):

- users: one row per (provider, provider_sub) — the STABLE internal id.
  Email is informational only, NEVER a linking key (no auto-linking two
  providers by matching email).
- login_sessions: server-side sessions keyed by SHA-256 of the raw token
  (raw tokens never stored). Cookie carries the raw token; the DB only
  ever sees its hash.

Memory foundation: agent session ownership is recorded in
session_owners(session_id → user_id) so a later memory layer can scope
and delete per-user data. No personal content beyond what OAuth
providers return (sub/email/name/picture) is stored; no access/refresh
tokens are stored anywhere.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import aiosqlite
except ImportError:  # pragma: no cover
    aiosqlite = None  # type: ignore

DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "state" / "sessions.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    provider_sub TEXT NOT NULL,
    email TEXT,
    email_verified INTEGER NOT NULL DEFAULT 0,
    name TEXT,
    picture TEXT,
    created_at REAL NOT NULL,
    last_login_at REAL NOT NULL,
    UNIQUE(provider, provider_sub)
);
CREATE TABLE IF NOT EXISTS login_sessions (
    token_hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at REAL NOT NULL,
    expires_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_login_sessions_user ON login_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_login_sessions_exp ON login_sessions(expires_at);
CREATE TABLE IF NOT EXISTS session_owners (
    session_id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at REAL NOT NULL
);
"""


def hash_token(raw: str) -> str:
    return hashlib.sha256((raw or "").encode()).hexdigest()


class UserStore:
    """Async identity store. One shared connection per instance."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        if aiosqlite is None:
            raise RuntimeError("aiosqlite unavailable — user store disabled")
        self.db_path = Path(db_path or DEFAULT_DB_PATH)
        self._conn = None

    async def _db(self):
        if self._conn is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = await aiosqlite.connect(str(self.db_path))
            self._conn.row_factory = aiosqlite.Row
            await self._conn.executescript(SCHEMA)
            await self._conn.commit()
        return self._conn

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    async def get_or_create_user(self, provider: str, provider_sub: str,
                                 email: Optional[str] = None,
                                 email_verified: bool = False,
                                 name: Optional[str] = None,
                                 picture: Optional[str] = None) -> Dict[str, Any]:
        """Identity keyed by (provider, provider_sub) ONLY. Email never
        links providers: same email on Google and GitHub = two users."""
        db = await self._db()
        now = time.time()
        async with db.execute(
                "SELECT * FROM users WHERE provider=? AND provider_sub=?",
                (provider, provider_sub)) as cur:
            row = await cur.fetchone()
        if row is None:
            async with db.execute(
                    "INSERT INTO users (provider, provider_sub, email, "
                    "email_verified, name, picture, created_at, "
                    "last_login_at) VALUES (?,?,?,?,?,?,?,?)",
                    (provider, provider_sub, email,
                     1 if email_verified else 0, name, picture, now, now)) as cur:
                uid = cur.lastrowid
            await db.commit()
        else:
            uid = row["id"]
            await db.execute(
                "UPDATE users SET email=?, email_verified=?, name=?, "
                "picture=?, last_login_at=? WHERE id=?",
                (email, 1 if email_verified else 0, name, picture, now, uid))
            await db.commit()
        return await self.get_user(uid)

    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        db = await self._db()
        async with db.execute("SELECT * FROM users WHERE id=?",
                              (user_id,)) as cur:
            row = await cur.fetchone()
        return dict(row) if row else None

    async def create_session(self, user_id: int, raw_token: str,
                             ttl_s: float) -> Dict[str, Any]:
        db = await self._db()
        now = time.time()
        await db.execute(
            "INSERT INTO login_sessions (token_hash, user_id, created_at, "
            "expires_at) VALUES (?,?,?,?)",
            (hash_token(raw_token), user_id, now, now + ttl_s))
        await db.commit()
        return {"user_id": user_id, "expires_at": now + ttl_s}

    async def get_session_user(self, raw_token: str,
                               now: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """Resolve a presented session token to its user (None if unknown
        or expired). Expired rows are reaped opportunistically."""
        if not raw_token:
            return None
        now = now if now is not None else time.time()
        db = await self._db()
        digest = hash_token(raw_token)
        async with db.execute(
                "SELECT * FROM login_sessions WHERE token_hash=?",
                (digest,)) as cur:
            row = await cur.fetchone()
        if row is None:
            return None
        if float(row["expires_at"]) <= now:
            await db.execute("DELETE FROM login_sessions WHERE token_hash=?",
                             (digest,))
            await db.commit()
            return None
        user = await self.get_user(int(row["user_id"]))
        if user is None:
            return None
        if not hmac.compare_digest(digest, hash_token(raw_token)):
            return None
        user["session_expires_at"] = float(row["expires_at"])
        return user

    async def revoke_session(self, raw_token: str) -> bool:
        db = await self._db()
        cur = await db.execute("DELETE FROM login_sessions WHERE token_hash=?",
                               (hash_token(raw_token),))
        await db.commit()
        return (cur.rowcount or 0) > 0

    async def revoke_user_sessions(self, user_id: int) -> int:
        db = await self._db()
        cur = await db.execute("DELETE FROM login_sessions WHERE user_id=?",
                               (user_id,))
        await db.commit()
        return cur.rowcount or 0

    async def delete_user(self, user_id: int) -> bool:
        """Full identity + sessions + ownership removal (memory-deletion
        foundation: per-user data lifetime ends here)."""
        db = await self._db()
        await db.execute("DELETE FROM login_sessions WHERE user_id=?",
                         (user_id,))
        await db.execute("DELETE FROM session_owners WHERE user_id=?",
                         (user_id,))
        cur = await db.execute("DELETE FROM users WHERE id=?", (user_id,))
        await db.commit()
        return (cur.rowcount or 0) > 0

    async def set_session_owner(self, session_id: str,
                                user_id: int) -> None:
        """Bind an agent session to its owner (first writer wins — a
        session never changes hands silently)."""
        if not session_id:
            return
        db = await self._db()
        await db.execute(
            "INSERT OR IGNORE INTO session_owners (session_id, user_id, "
            "created_at) VALUES (?,?,?)", (session_id, user_id, time.time()))
        await db.commit()

    async def get_session_owner(self, session_id: str) -> Optional[int]:
        if not session_id:
            return None
        db = await self._db()
        async with db.execute(
                "SELECT user_id FROM session_owners WHERE session_id=?",
                (session_id,)) as cur:
            row = await cur.fetchone()
        return int(row["user_id"]) if row else None


_STORE: Optional[UserStore] = None


def get_user_store(db_path: Optional[Path] = None) -> UserStore:
    global _STORE
    if _STORE is None or (db_path is not None and _STORE.db_path != Path(db_path)):
        _STORE = UserStore(db_path)
    return _STORE


SESSION_TTL_SECONDS = float(os.getenv("GENIO_SESSION_TTL", "604800"))  # 7d
