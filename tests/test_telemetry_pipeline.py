"""Phase 16 tests — deterministic telemetry + scrubbing.

Schéma fermé, aucune fuite de secrets/tokens/CoT, ring borné, JSONL valide.
Aucun réseau/modèle.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, "/data/ai_tools/genio")

from genio_server.core.telemetry import Telemetry, get_telemetry, scrub_text


def _tel(tmp_path):
    return Telemetry(log_path=tmp_path / "t.jsonl", ring=10)


def test_schema_valid(tmp_path):
    t = _tel(tmp_path)
    rec = t.emit("agent.started", session_id="s1", actor="agent",
                 capability="READ_ONLY", tool="bash", result="ok",
                 duration_ms=12.5, risk="LOW", decision="ALLOW")
    assert rec is not None
    assert set(rec.keys()) == {"ts", "event", "session_id", "actor",
                               "capability", "tool", "result", "duration_ms",
                               "risk", "decision"}
    assert rec["event"] == "agent.started" and rec["session_id"] == "s1"


def test_unknown_event_rejected(tmp_path):
    assert _tel(tmp_path).emit("agent.hacked") is None


def test_no_secret_leak(tmp_path):
    t = _tel(tmp_path)
    evil = ("Bearer abcdefgh12345678 sk-abcdefgh1234567890 "
            "password: hunter2 ghp_abcdefghij1234567890 "
            "-----BEGIN RSA PRIVATE KEY-----\nXYZ\n-----END RSA PRIVATE KEY-----")
    rec = t.emit("tool.completed", result=evil)
    blob = json.dumps(rec)
    assert "hunter2" not in blob and "abcdefgh12345678" not in blob
    assert "ghp_abcdefghij" not in blob and "PRIVATE KEY-----\nXYZ" not in blob
    assert "[REDACTED:" in blob


def test_no_chain_of_thought_logged(tmp_path):
    t = _tel(tmp_path)
    rec = t.emit("agent.started",
                 result="Thinking: I will now hack\nReal summary here.")
    blob = json.dumps(rec)
    assert "I will now hack" not in blob
    assert "Real summary here." in blob


def test_ring_bounded_and_jsonl_valid(tmp_path):
    t = _tel(tmp_path)
    for i in range(25):
        t.emit("agent.started", result=f"r{i}")
    assert len(t.recent(100)) == 10
    lines = (tmp_path / "t.jsonl").read_text().strip().splitlines()
    assert len(lines) == 25
    for ln in lines:
        d = json.loads(ln)
        assert d["event"] == "agent.started"


def test_singleton_shared():
    assert get_telemetry() is get_telemetry()


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
