"""Phase 9 tests — computer-use safety.

Validateurs purs (coordonnées, rate, bornes) + kill-switch d'urgence sur
handle() réel. Aucun display requis (pas d'actuation physique en test).
"""
import sys
import time

sys.path.insert(0, "/data/ai_tools/genio")

from genio_server.tools import computer_tool as ct
from genio_server.tools.safety import SAFETY


def setup_function(_):
    ct.clear_rate_state()
    if not SAFETY.armed:
        SAFETY.arm()


def test_coords_in_frame():
    assert ct.validate_coords(100, 200, 1920, 1080) is None
    assert ct.validate_coords(0, 0, 1920, 1080) is None


def test_coords_out_of_frame_rejected():
    assert ct.validate_coords(-5, 100, 1920, 1080) is not None
    assert ct.validate_coords(1920, 100, 1920, 1080) is not None
    assert ct.validate_coords(100, 1080, 1920, 1080) is not None
    assert ct.validate_coords(99999, 99999, 1920, 1080) is not None
    assert ct.validate_coords("x", 10, 1920, 1080) is not None


def test_press_bounds():
    assert ct.validate_press("left", 1) is None
    assert ct.validate_press("middle", 5) is None
    assert ct.validate_press("hyper", 1) is not None
    assert ct.validate_press("left", 0) is not None
    assert ct.validate_press("left", 99) is not None


def test_rate_limit_clicks():
    ct.clear_rate_state()
    assert ct.check_rate("click") is None
    assert ct.check_rate("click") is not None  # trop rapproché
    time.sleep(ct.CLICK_MIN_INTERVAL_S + 0.1)
    assert ct.check_rate("click") is None


def test_type_length_cap():
    assert ct.MAX_TYPE_CHARS == 2000
    r = ct.handle({"action": "type", "text": "x" * 2001})
    assert r["ok"] is False and "too long" in r["error"]


def test_key_combo_cap():
    r = ct.handle({"action": "key", "keys": "a+b+c+d+e+f"})
    assert r["ok"] is False and "too many keys" in r["error"]
    r = ct.handle({"action": "key", "keys": ""})
    assert r["ok"] is False


def test_scroll_bound():
    r = ct.handle({"action": "scroll", "clicks": 999})
    assert r["ok"] is False and "out of range" in r["error"]


def test_kill_switch_blocks_instantly():
    SAFETY.halt("phase9 test")
    try:
        r = ct.handle({"action": "screenshot"})
        assert r.get("error") and "KILL SWITCH" in r["error"]
        r = ct.handle({"action": "click", "x": 10, "y": 10})
        assert r.get("error") and "KILL SWITCH" in r["error"]
    finally:
        SAFETY.arm()
    assert SAFETY.armed is True


def test_unknown_action_structured():
    r = ct.handle({"action": "teleport"})
    assert r["ok"] is False and "unknown computer action" in r["error"]


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
