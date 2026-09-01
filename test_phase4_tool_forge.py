"""Phase 4 — Tool Forge.

Run: pytest test_phase4_tool_forge.py -v
"""
import tempfile
from pathlib import Path
from unittest import mock

from genio_server.tools.tool_forge import ToolForge
from genio_server.tools import invoke


def _tmp_forge(tmp_path):
    return ToolForge()


def test_create_and_invoke_forged_tool(tmp_path, monkeypatch):
    monkeypatch.setenv("GENIO_TOOL_FORGE", "1")
    # isolate state
    forge_path = Path(tmp_path) / "tool_forge.json"
    with mock.patch("genio_server.tools.tool_forge.FORGE_PATH", forge_path):
        forge = ToolForge()
        res = forge.create_tool("my_tool", "does something useful for testing")
        assert res["ok"] is True
        listed = forge.list_tools()
        assert any(t["name"] == "my_tool" for t in listed)
        inv = forge.invoke("my_tool", {"x": 1})
        assert inv.get("forged") is True or "output" in inv


def test_invalid_name_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("GENIO_TOOL_FORGE", "1")
    forge_path = Path(tmp_path) / "forge.json"
    with mock.patch("genio_server.tools.tool_forge.FORGE_PATH", forge_path):
        forge = ToolForge()
        res = forge.create_tool("bash", "conflicts with built-in tool name here")
        assert res["ok"] is False
        assert "conflicts" in res["error"]


def test_invoke_via_registry(tmp_path, monkeypatch):
    monkeypatch.setenv("GENIO_TOOL_FORGE", "1")
    forge_path = Path(tmp_path) / "tool_forge2.json"
    with mock.patch("genio_server.tools.tool_forge.FORGE_PATH", forge_path):
        # need to patch both forge module and tools __init__ import path
        import genio_server.tools.tool_forge as tf
        orig_path = tf.FORGE_PATH
        tf.FORGE_PATH = forge_path
        try:
            tf.get_forge().create_tool("hello_tool", "says hello world tool")
            result = invoke("hello_tool", {"msg": "hi"})
            assert result.get("forged") is True or "hello_tool" in str(result)
        finally:
            tf.FORGE_PATH = orig_path


def test_forge_disabled(monkeypatch, tmp_path):
    monkeypatch.setenv("GENIO_TOOL_FORGE", "0")
    forge_path = Path(tmp_path) / "f.json"
    with mock.patch("genio_server.tools.tool_forge.FORGE_PATH", forge_path):
        forge = ToolForge()
        res = forge.create_tool("disabled_tool", "should not be created because disabled")
        assert res["ok"] is False
        assert "disabled" in res["error"].lower()
