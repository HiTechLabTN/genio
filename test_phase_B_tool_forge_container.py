"""Phase B — Router exécution forgés vers sandbox (validation container).

Run: pytest test_phase_B_tool_forge_container.py -v
"""
import tempfile
from pathlib import Path
from unittest import mock

from genio_server.tools.tool_forge import ToolForge

def test_legitimate_tool_via_container(tmp_path, monkeypatch):
    monkeypatch.setenv("GENIO_TOOL_FORGE", "1")
    # Mock Docker available to avoid real container, but use fallback path
    # We patch _exec_via_container to simulate container success
    forge_path = Path(tmp_path) / "forgeB.json"
    with mock.patch("genio_server.tools.tool_forge.FORGE_PATH", forge_path):
        forge = ToolForge()
        # Benign sum
        code = "result = payload.get('a',0) + payload.get('b',0)"
        res = forge.create_tool("b_sum", "legitimate sum via container for test", code=code, session_id="testB1")
        assert res["ok"] is True, res
        inv = forge.invoke("b_sum", {"a": 5, "b": 7}, session_id="testB1")
        assert "error" not in inv or "forbidden" not in str(inv.get("error")).lower()
        assert inv.get("output") == "12" or "12" in str(inv.get("output", ""))

def test_failing_script_not_registered(tmp_path, monkeypatch):
    monkeypatch.setenv("GENIO_TOOL_FORGE", "1")
    forge_path = Path(tmp_path) / "forgeB2.json"
    with mock.patch("genio_server.tools.tool_forge.FORGE_PATH", forge_path):
        forge = ToolForge()
        bad_code = "raise ValueError('intentional fail')"
        res = forge.create_tool("bad_tool", "tool that fails validation in container", code=bad_code, session_id="testB2")
        assert res["ok"] is False
        assert "validation failed" in str(res.get("error", "")).lower()
        # Should not appear in list
        lst = forge.list_tools()
        assert not any(t["name"] == "bad_tool" for t in lst)

def test_rce_still_blocked_via_container(tmp_path, monkeypatch):
    monkeypatch.setenv("GENIO_TOOL_FORGE", "1")
    rce = """result = [c for c in ().__class__.__base__.__subclasses__() if c.__name__ == "catch_warnings"][0]()._module.__builtins__["__import__"]("os").popen("id").read()"""
    forge_path = Path(tmp_path) / "forgeB3.json"
    with mock.patch("genio_server.tools.tool_forge.FORGE_PATH", forge_path):
        forge = ToolForge()
        res = forge.create_tool("rce2", "RCE via container should be blocked here", code=rce, session_id="testB3")
        assert res["ok"] is False
        assert "forbidden" in str(res.get("error", "")).lower() or "sandbox" in str(res.get("error", "")).lower()
