"""Genio — Durable session store with bounded rolling context window.

SQLite (via ``aiosqlite``) persistence for interactive agent sessions.
Guarantees:

* ``load_session`` NEVER returns the full unbounded history — only the last
  ``max_history_turns`` raw turns, plus any compressed ``summary`` of the
  older turns that have slid out of that window.
* ``append_message`` persists each message immediately (crash-tolerant) and
  transparently compacts the oldest turns into ``sessions.summary`` once the
  stored history exceeds ``max_history_turns``, so the table never grows
  without bound either.

The compressed ``summary`` is distinct from Phase 1's durable ``session_context``
(project facts): here we compress the *conversational* history that grows
without bound.
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import aiosqlite

DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "state" / "sessions.db"
DEFAULT_MAX_HISTORY_TURNS = 10
_MAX_SUMMARY_CHARS = 4000

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    created_at REAL,
    updated_at REAL,
    mode TEXT,
    status TEXT,
    summary TEXT
);
CREATE TABLE IF NOT EXISTS messages (
    session_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    role TEXT,
    content TEXT,
    ts REAL,
    PRIMARY KEY (session_id, seq)
);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, seq);
"""


def _now() -> float:
    return time.time()


class SessionStore:
    """Async SQLite-backed store enforcing a bounded rolling context window."""

    def __init__(self, db_path: Optional[Path] = None,
                 max_history_turns: int = DEFAULT_MAX_HISTORY_TURNS):
        self.db_path = Path(db_path or DEFAULT_DB_PATH)
        self.max_history_turns = max(1, int(max_history_turns))
        self._conn: Optional[aiosqlite.Connection] = None

    async def _db(self) -> aiosqlite.Connection:
        if self._conn is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = await aiosqlite.connect(str(self.db_path))
            self._conn.row_factory = aiosqlite.Row
            await self._conn.executescript(_SCHEMA)
            await self._conn.commit()
        return self._conn

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    # ------------------------------------------------------------------ #
    async def create_session(self, mode: str = "autonomous") -> str:
        db = await self._db()
        sid = uuid.uuid4().hex
        now = _now()
        await db.execute(
            "INSERT INTO sessions(id, created_at, updated_at, mode, status, summary) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (sid, now, now, mode, "active", ""),
        )
        await db.commit()
        return sid

    async def append_message(self, session_id: str, role: str,
                             content: str) -> None:
        """Persist a message and, if the window is exceeded, compact the oldest
        turns into ``sessions.summary``. Bounded storage by construction."""
        db = await self._db()
        seq = await self._next_seq(session_id)
        await db.execute(
            "INSERT INTO messages(session_id, seq, role, content, ts) VALUES (?,?,?,?,?)",
            (session_id, seq, role, content, _now()),
        )
        await db.execute(
            "UPDATE sessions SET updated_at=? WHERE id=?",
            (_now(), session_id),
        )
        await db.commit()
        await self._maybe_compact(db, session_id)

    async def set_status(self, session_id: str, status: str) -> None:
        db = await self._db()
        await db.execute(
            "UPDATE sessions SET status=?, updated_at=? WHERE id=?", (
                status, _now(), session_id))
        await db.commit()

    async def set_summary(self, session_id: str, summary: str) -> None:
        db = await self._db()
        await db.execute(
            "UPDATE sessions SET summary=?, updated_at=? WHERE id=?", (
                summary, _now(), session_id))
        await db.commit()

    async def _next_seq(self, session_id: str) -> int:
        db = await self._db()
        cur = await db.execute(
            "SELECT COALESCE(MAX(seq), -1) AS m FROM messages WHERE session_id=?",
            (session_id,),
        )
        row = await cur.fetchone()
        return int(row["m"]) + 1

    async def _maybe_compact(self, db: aiosqlite.Connection,
                             session_id: str) -> None:
        cur = await db.execute(
            "SELECT COUNT(*) AS c FROM messages WHERE session_id=?", (session_id,))
        row = await cur.fetchone()
        count = int(row["c"])
        if count <= self.max_history_turns:
            return
        # Oldest `count - max_history_turns` turns slide out of the raw window
        # and get folded into the summary.
        n_old = count - self.max_history_turns
        cur = await db.execute(
            "SELECT role, content FROM messages WHERE session_id=? ORDER BY seq LIMIT ?",
            (session_id, n_old),
        )
        old = await cur.fetchall()
        old_text = "\n".join(f"{r['role']}: {r['content']}" for r in old)
        batch_summary = await self._summarize_batch(old_text)

        prev = await self._get_summary(db, session_id)
        merged = (prev + "\n" + batch_summary).strip() if prev else batch_summary
        # Cap the persisted summary so it cannot grow without bound either.
        merged = merged[:_MAX_SUMMARY_CHARS]

        # Delete the oldest rows.
        cur = await db.execute(
            "SELECT seq FROM messages WHERE session_id=? ORDER BY seq LIMIT ?",
            (session_id, n_old),
        )
        del_seqs = [r["seq"] for r in await cur.fetchall()]
        for s in del_seqs:
            await db.execute(
                "DELETE FROM messages WHERE session_id=? AND seq=?", (session_id, s))

        # Renumber the survivors densely (0..k-1) so MAX(seq) grows monotonically
        # and the next compaction predicate stays correct.
        cur = await db.execute(
            "SELECT seq FROM messages WHERE session_id=? ORDER BY seq", (session_id,))
        survivors = [r["seq"] for r in await cur.fetchall()]
        for new_seq, old_seq in enumerate(survivors):
            await db.execute(
                "UPDATE messages SET seq=? WHERE session_id=? AND seq=?",
                (new_seq, session_id, old_seq))

        await db.execute(
            "UPDATE sessions SET summary=?, updated_at=? WHERE id=?",
            (merged, _now(), session_id),
        )
        await db.commit()

    async def _get_summary(self, db: aiosqlite.Connection,
                           session_id: str) -> str:
        cur = await db.execute(
            "SELECT summary FROM sessions WHERE id=?", (session_id,))
        row = await cur.fetchone()
        return row["summary"] if row else ""

    async def _summarize_batch(self, old_text: str) -> str:
        """Compress a batch of old turns into a short summary. Uses a compact
        local summarizer hook so the store has no hard dependency on the LLM;
        the summarizer can be swapped for a model call by the agent loop."""
        try:
            from genio_server.core.agent_loop import summarize_session_batch
            return await summarize_session_batch(old_text)
        except Exception:
            # Fallback: heuristic extractive summary (first/last lines).
            lines = [l for l in old_text.splitlines() if l.strip()]
            snippet = "\n".join(lines[:2] + ["…"] + lines[-2:])
            return f"[truncated conversation, {len(lines)} lines]: {snippet[:400]}"

    async def load_session(self, session_id: str,
                           max_history_turns: Optional[int] = None) -> Dict[str, Any]:
        """Return the bounded rolling context for a session.

        Never returns unbounded raw history: only the last ``max_history_turns``
        turns plus any persisted ``summary`` of older compressed turns.

        Returns:
            {session_id, mode, status, summary, turns: [ {role, content}, ... ]}
        """
        db = await self._db()
        window = max_history_turns or self.max_history_turns
        cur = await db.execute(
            "SELECT id, mode, status, summary FROM sessions WHERE id=?",
            (session_id,),
        )
        row = await cur.fetchone()
        if row is None:
            return {"session_id": session_id, "exists": False, "mode": "autonomous",
                    "status": "", "summary": "", "turns": []}

        cur = await db.execute(
            "SELECT role, content FROM messages WHERE session_id=? "
            "ORDER BY seq DESC LIMIT ?",
            (session_id, window),
        )
        rows = await cur.fetchall()
        turns = [{"role": r["role"], "content": r["content"]}
                 for r in reversed(rows)]
        return {
            "session_id": session_id,
            "exists": True,
            "mode": row["mode"],
            "status": row["status"],
            "summary": row["summary"],
            "turns": turns,
        }

    async def session_count(self, session_id: str) -> int:
        db = await self._db()
        cur = await db.execute(
            "SELECT COUNT(*) AS c FROM messages WHERE session_id=?", (session_id,))
        row = await cur.fetchone()
        return int(row["c"])


_store_singleton: Optional[SessionStore] = None


def get_session_store() -> SessionStore:
    """Process-wide shared store (single SQLite connection)."""
    global _store_singleton
    if _store_singleton is None:
        _store_singleton = SessionStore()
    return _store_singleton


def build_prompt_from_session(system_prompt: str,
                              session: Dict[str, Any],
                              max_history_turns: Optional[int] = None) -> str:
    """Assemble the final model prompt per the mandatory windowing policy:

        [system_prompt]
        [session_context, bounded]          (already inside system_prompt)
        [session summary if > max_history_turns]
        [N last raw turns]

    Never injects unbounded raw history.
    """
    window = max_history_turns or DEFAULT_MAX_HISTORY_TURNS
    turns = session.get("turns") or []
    parts = [system_prompt]

    summary = (session.get("summary") or "").strip()
    if summary:
        parts.append("\n\n[SESSION SUMMARY — condensed earlier turns]:\n" + summary)

    # Only include turns within the window (defensive).
    bound_turns = turns[-window:]
    if bound_turns:
        parts.append(
            "\n\n[RECENT CONVERSATION — latest turns]:\n"
            + "\n".join(f"{t['role']}: {t['content']}" for t in bound_turns)
        )
    elif summary:
        # Everything summarized, nothing raw left in window.
        parts.append("\n(RECENT RAW TURNS: none — all prior turns are in the summary above)")

    return "\n".join(parts)
