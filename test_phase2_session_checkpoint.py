"""Phase 2 — SQLite session checkpointing with a bounded rolling context.

Verifies:
  (a) crash/fault tolerance — a "killed" session can be resumed from disk with
      its recent history intact.
  (b) bounded windowing — pushing volume far beyond ``max_history_turns`` never
      rebuilds an unbounded prompt; it compacts older turns into a summary and
      keeps only the last N raw turns under an explicit token budget.

Run:  pytest test_phase2_session_checkpoint.py -v
"""
from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import pytest

from genio_server.core.session_store import (
    SessionStore,
    build_prompt_from_session,
)

# ~4 chars/token heuristic for the budget check (conservative).
CHARS_PER_TOKEN = 4


def approx_tokens(text: str) -> int:
    return len(text) // CHARS_PER_TOKEN


@pytest.mark.asyncio
async def test_crash_tolerance_resume_recent_history():
    tmp = Path(tempfile.mkdtemp()) / "sessions.db"
    store1 = SessionStore(db_path=tmp, max_history_turns=5)

    sid = await store1.create_session(mode="autonomous")
    await store1.append_message(sid, "user", "bonjour")
    await store1.append_message(sid, "assistant", "salut, que faire ?")
    await store1.append_message(sid, "user", "affiche le CWD")

    # Simulate crash: drop the connection/handle, reopen from disk.
    await store1.close()
    store2 = SessionStore(db_path=tmp, max_history_turns=5)
    loaded = await store2.load_session(sid)
    await store2.close()

    assert loaded["exists"] is True
    assert len(loaded["turns"]) == 3
    assert loaded["turns"][-1]["content"] == "affiche le CWD"
    assert loaded["turns"][0]["role"] == "user"


@pytest.mark.asyncio
async def test_prompt_rebuilt_under_budget_with_bounded_window():
    tmp = Path(tempfile.mkdtemp()) / "sessions.db"
    store = SessionStore(db_path=tmp, max_history_turns=8)
    sid = await store.create_session(mode="autonomous")

    # Push 50 turns (each ~1 line) — far more than the window of 8.
    turns = 50
    for i in range(turns):
        await store.append_message(
            sid, "user" if i % 2 == 0 else "assistant",
            f"ligne de conversation numéro {i} pour le stress test",
        )

    session = await store.load_session(sid)
    await store.close()

    # Storage is bounded: only max_history_turns raw rows survive.
    assert len(session["turns"]) == 8, "only the last 8 raw turns survive"

    # Exactly the LAST 8 turns, not the first ones.
    rendered = build_prompt_from_session("SYSTEM", session)
    last_turn_text = f"ligne de conversation numéro {turns - 1}"
    first_turn_text = "ligne de conversation numéro 0"
    assert last_turn_text in rendered
    # The first turn may still appear inside the (compressed) summary, but it
    # must NEVER survive as a raw in-window turn.
    assert session["turns"][0]["content"] != first_turn_text
    assert first_turn_text not in [t["content"] for t in session["turns"]]

    # It carries a summary of the older turns.
    assert "summary" in session and session["summary"].strip() != ""

    # Explicit token budget: < 8k tokens even after 50 turns of input.
    assert approx_tokens(rendered) < 2000


@pytest.mark.asyncio
async def test_load_unknown_session_returns_empty():
    tmp = Path(tempfile.mkdtemp()) / "sessions.db"
    store = SessionStore(db_path=tmp)
    loaded = await store.load_session("does-not-exist")
    await store.close()
    assert loaded["exists"] is False
    assert loaded["turns"] == []
