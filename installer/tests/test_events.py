"""Event protocol + error catalog tests (§5/§9 G3).

Schema validity, scrubbing, G1 state mapping, TS mirror lock.
"""
import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from installer.core.events import (  # noqa: E402
    ERRORS, EVENTS, EVENT_STATES, Emitter,
)
from installer.core.states import STATES  # noqa: E402


def test_events_closed_and_mapped():
    assert len(EVENTS) == 18
    assert set(EVENT_STATES) == set(EVENTS)
    for ev, sid in EVENT_STATES.items():
        assert sid in STATES, f"{ev} -> unknown state {sid}"


def test_error_catalog_complete():
    for code, info in ERRORS.items():
        assert info["message"]
        assert set(info) == {"message", "recovery", "docs"}
    assert "INSTALL_CHECKSUM" in ERRORS and "INSTALL_CANCELLED" in ERRORS


def test_unknown_event_and_error_rejected():
    em = Emitter(enabled=False)
    with pytest.raises(AssertionError):
        em.emit("NOPE", {})
    with pytest.raises(AssertionError):
        em.emit("INSTALL_FAILED", {}, error="NOPE")


def test_emitter_disabled_returns_payload():
    em = Emitter(enabled=False, installation_id="abc")
    p = em.emit("INSTALL_STARTED", {"prefix": "/x"})
    assert p["protocol"] == "genio-installer-events/1"
    assert p["state"] == "detecting"
    assert p["installation_id"] == "abc"


def test_emitter_enabled_prints_valid_json():
    em = Emitter(enabled=True)
    buf = io.StringIO()
    with redirect_stdout(buf):
        em.emit("INSTALL_FAILED", {"stage": "x"}, error="INSTALL_CHECKSUM")
    line = json.loads(buf.getvalue().strip())
    assert line["event"] == "INSTALL_FAILED"
    assert line["error"]["code"] == "INSTALL_CHECKSUM"
    assert line["error"]["recovery"]


def test_secrets_scrubbed_from_events():
    em = Emitter(enabled=False)
    p = em.emit("CONFIGURATION_STARTED",
                {"api_key": "GENIO_API_KEY=supersecret123456", "ports": {"api": 8000}})
    assert "supersecret" not in json.dumps(p)
    assert p["data"]["ports"] == {"api": 8000}


def test_ts_mirror_in_sync():
    import re
    text = (REPO / "genio_client" / "src" / "lib" / "installEvents.ts").read_text()
    for ev in EVENTS:
        assert ev in text, f"TS mirror missing {ev}"
    for code in ERRORS:
        assert code in text, f"TS mirror missing {code}"
    m = re.search(r"INSTALL_STARTED:\s*\"(\w+)\"", text)
    assert m and m.group(1) == EVENT_STATES["INSTALL_STARTED"]
