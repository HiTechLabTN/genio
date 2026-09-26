"""Desktop/mobile harness tests — contract flows against live dev services.

NOT_APPLICABLE-safe: skips only when the local Genio API is unreachable
(CI without services). Never asserts fake capabilities.
"""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from genio.integrations.hitechos.desktop_harness import DesktopHarness  # noqa: E402

API = os.environ.get("GENIO_TEST_API", "http://127.0.0.1:8000")
WS = os.environ.get("GENIO_TEST_WS", "ws://127.0.0.1:8000/ws/agent")


def _api_up():
    try:
        import urllib.request
        with urllib.request.urlopen(API + "/health", timeout=5) as r:
            return r.status == 200
    except Exception:
        return False


needs_live_api = pytest.mark.skipif(
    not _api_up(), reason="live Genio API absent (CI sans services)")


@needs_live_api
def test_discover_reports_honest_state():
    h = DesktopHarness(API, WS)
    d = h.discover()
    assert d["connected"] is True
    assert isinstance(d["capabilities"], list)
    assert "vision" not in d["capabilities"]
    assert any("unavailable-ui-usable" in x for x in d["degraded"])


@needs_live_api
def test_chat_end_to_end():
    h = DesktopHarness(API, WS)
    h.discover()
    r = h.chat("عسلامة")
    assert r["status"] == "responded" and r["text"]


@needs_live_api
def test_offline_and_reconnect():
    h = DesktopHarness("http://127.0.0.1:9", "ws://127.0.0.1:9/ws/agent")
    d = h.discover()
    assert d["connected"] is False
    assert h.chat("hi")["status"] == "offline"
    assert h.reconnect(tries=1, delay=0.1) is False
    h2 = DesktopHarness(API, WS)
    assert h2.reconnect(tries=3, delay=0.5) is True
