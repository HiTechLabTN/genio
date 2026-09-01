"""Phase A — RCE neutralisation proof.

Reproduit LITTÉRALEMENT le payload d'audit via forge.create_tool + forge.invoke,
vérifie PAS de uid= / shell, soit erreur sandbox exec disabled.
Run: pytest test_phase_A_tool_forge_rce.py -v
"""
import tempfile
from pathlib import Path
from unittest import mock

from genio_server.tools.tool_forge import ToolForge

RCE_PAYLOAD = """result = [c for c in ().__class__.__base__.__subclasses__()
               if c.__name__ == "catch_warnings"][0]()._module.__builtins__[
               "__import__"]("os").popen("id").read()"""

def _tmp_forge(tmp_path):
    p = Path(tmp_path) / "forgeA.json"
    with mock.patch("genio_server.tools.tool_forge.FORGE_PATH", p):
        yield ToolForge()

def test_rce_payload_blocked(tmp_path, monkeypatch):
    monkeypatch.setenv("GENIO_TOOL_FORGE", "1")
    forge_path = Path(tmp_path) / "forgeA.json"
    with mock.patch("genio_server.tools.tool_forge.FORGE_PATH", forge_path):
        forge = ToolForge()
        res = forge.create_tool("rce_tool", "RCE test tool with exploit payload here", code=RCE_PAYLOAD)
        # After Phase B, RCE is blocked at create (validation), after Phase A at invoke — accept either
        if res["ok"] is False:
            # Blocked at create — check error
            out = str(res.get("error", ""))
            assert "forbidden" in out.lower() or "sandbox" in out.lower() or "rce" in out.lower()
            assert "uid=" not in out
            return
        # If create succeeded (Phase A), then invoke must be blocked
        inv = forge.invoke("rce_tool", {})
        # Must NOT contain shell output
        out = str(inv.get("output", "")) + str(inv.get("error", ""))
        assert "uid=" not in out, f"RCE succeeded: {out}"
        assert "gid=" not in out
        # Must be explicit sandbox disabled or blocked
        assert "sandbox exec disabled" in out.lower() or "forbidden pattern" in out.lower() or "rce blocked" in out.lower()
        # Ensure no os/sys accessible via error leakage
        assert "os" not in out.lower() or "forbidden" in out.lower()

def test_rce_when_forge_disabled(tmp_path, monkeypatch):
    # GENIO_TOOL_FORGE not set => default 0 => disabled
    monkeypatch.delenv("GENIO_TOOL_FORGE", raising=False)
    # Need to reload? ToolForge reads env each call, so just test
    forge_path = Path(tmp_path) / "forgeA2.json"
    with mock.patch("genio_server.tools.tool_forge.FORGE_PATH", forge_path):
        # create should fail when disabled
        forge = ToolForge()
        res = forge.create_tool("any", "should be disabled because opt-in required here", code="result=1")
        assert res["ok"] is False
        assert "disabled" in res["error"].lower()
        # invoke without create should either not found or disabled
        inv = forge.invoke("any", {})
        assert "not found" in str(inv.get("error", "")).lower() or "disabled" in str(inv.get("error", "")).lower()

def test_legitimate_tool_still_works_when_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv("GENIO_TOOL_FORGE", "1")
    forge_path = Path(tmp_path) / "forgeA3.json"
    with mock.patch("genio_server.tools.tool_forge.FORGE_PATH", forge_path):
        forge = ToolForge()
        benign = "result = payload.get('a', 0) + payload.get('b', 0)"
        res = forge.create_tool("sum_tool", "legitimate sum tool for testing", code=benign)
        assert res["ok"] is True, f"benign create should succeed, got {res}"
        inv = forge.invoke("sum_tool", {"a": 2, "b": 3})
        # Benign should still work via container (Phase B) or temporary exec (Phase A)
        # Check output contains 5 or forged flag, and no forbidden error
        out = str(inv.get("output", "")) + str(inv.get("error", ""))
        assert "5" in out or inv.get("forged") is True or inv.get("output") == "5"
        assert "forbidden" not in out.lower()

def test_tool_forge_via_invoke_disabled_by_default(monkeypatch):
    monkeypatch.delenv("GENIO_TOOL_FORGE", raising=False)
    from genio_server.tools import invoke
    res = invoke("tool_forge", {"action": "list"})
    # When disabled, should not reach exec, should return disabled or empty list?
    # The invoke path checks _enabled before forged lookup, so tool_forge itself should still be callable but create should be disabled
    # For list, it should still work but create should fail
    # Test the gateway: trying to create via invoke should be disabled
    res2 = invoke("tool_forge", {"action": "create", "name": "x", "description": "test disabled via invoke gateway here", "code": "result=1"})
    assert res2.get("ok") is False
    assert "disabled" in str(res2.get("error", "")).lower()
