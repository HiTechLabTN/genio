"""Phase 3 — GenericHealer fallback.

Run: pytest test_phase3_generic_healer.py -v
"""
from sandbox.self_healer import GenericHealer, SelfHealer


def test_generic_healer_catches_import():
    g = GenericHealer()
    fix = g.inspect_and_heal("ModuleNotFoundError: No module named 'requests'")
    assert fix and "pip install" in fix
    assert "requests" in fix


def test_generic_healer_catches_syntax():
    g = GenericHealer()
    fix = g.inspect_and_heal("SyntaxError: invalid syntax at line 10")
    assert fix and "syntax" in fix.lower()


def test_generic_healer_catches_name():
    g = GenericHealer()
    fix = g.inspect_and_heal("NameError: name 'foo' is not defined")
    assert fix is not None


def test_self_healer_still_handles_infra():
    s = SelfHealer()
    fix = s.inspect_and_heal("wg handshake failed")
    assert fix and "51820" in fix


def test_self_healer_falls_back_to_generic():
    s = SelfHealer()
    fix = s.inspect_and_heal("Traceback: ValueError: invalid literal")
    assert fix is not None


def test_generic_toggle_off(monkeypatch):
    monkeypatch.setenv("GENIO_GENERIC_HEAL", "0")
    from importlib import reload
    import sandbox.self_healer as m
    reload(m)
    g = m.GenericHealer()
    assert g.inspect_and_heal("ValueError: bad") is None
    # restore
    monkeypatch.setenv("GENIO_GENERIC_HEAL", "1")
    reload(m)
