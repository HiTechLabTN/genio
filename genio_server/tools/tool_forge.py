"""Tool Forge — dynamic per-session tool creation (Phase 4).

Allows the agent (or user) to forge new tools at runtime. Tools are persisted
to `state/tool_forge.json` and auto-loaded into the registry on startup.
Toggle via GENIO_TOOL_FORGE=0 to disable.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

FORGE_PATH = Path(__file__).resolve().parents[2] / "state" / "tool_forge.json"
_BUILTIN_TOOLS = {"bash", "social_post", "browser", "computer", "screen", "api", "tool_forge"}


def _enabled() -> bool:
    return os.getenv("GENIO_TOOL_FORGE", "1").strip().lower() not in ("0", "false", "no")


def _load() -> Dict[str, Dict[str, str]]:
    if FORGE_PATH.exists():
        try:
            return json.loads(FORGE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save(data: Dict[str, Dict[str, str]]) -> None:
    FORGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = FORGE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(FORGE_PATH)


def _valid_name(name: str) -> Optional[str]:
    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]{2,31}$", name):
        return "name must be 3-32 chars, start with letter/_ , alphanumeric/_ only"
    if name in _BUILTIN_TOOLS:
        return f"name '{name}' conflicts with built-in tool"
    return None


class ToolForge:
    """Registry for dynamically forged tools."""

    def create_tool(self, name: str, description: str, code: str = "") -> Dict[str, Any]:
        if not _enabled():
            return {"ok": False, "error": "tool forge disabled (GENIO_TOOL_FORGE=0)"}
        err = _valid_name(name)
        if err:
            return {"ok": False, "error": err}
        if not description or len(description.strip()) < 10:
            return {"ok": False, "error": "description must be >=10 chars"}
        data = _load()
        data[name] = {"description": description.strip(), "code": code or ""}
        _save(data)
        return {"ok": True, "name": name, "description": description.strip()}

    def list_tools(self) -> List[Dict[str, str]]:
        return [{"name": k, "description": v["description"]} for k, v in _load().items()]

    def get_tool(self, name: str) -> Optional[Dict[str, str]]:
        return _load().get(name)

    def delete_tool(self, name: str) -> Dict[str, Any]:
        data = _load()
        if name not in data:
            return {"ok": False, "error": f"tool '{name}' not found"}
        del data[name]
        _save(data)
        return {"ok": True, "deleted": name}

    def invoke(self, name: str, payload: Any) -> Dict[str, Any]:
        tool = self.get_tool(name)
        if not tool:
            return {"tool": name, "error": f"forged tool '{name}' not found"}
        code = tool.get("code", "")
        if not code:
            return {"tool": name, "output": f"forged tool '{name}' invoked with {payload!r}", "forged": True}
        # Execute code in restricted context (no dangerous ops)
        try:
            # Provide payload as variable, capture output
            local = {"payload": payload, "result": None}
            exec(code, {"__builtins__": {"str": str, "len": len, "dict": dict, "list": list}}, local)
            return {"tool": name, "output": str(local.get("result") or "ok"), "forged": True}
        except Exception as exc:
            return {"tool": name, "error": f"forged tool failed: {exc}"}


_forge_singleton: Optional[ToolForge] = None


def get_forge() -> ToolForge:
    global _forge_singleton
    if _forge_singleton is None:
        _forge_singleton = ToolForge()
    return _forge_singleton


def handle(payload: Any) -> Dict[str, Any]:
    """Entry point for `tool: tool_forge`."""
    data = payload if isinstance(payload, dict) else {}
    if isinstance(payload, str):
        try:
            data = json.loads(payload)
        except Exception:
            data = {"action": payload}
    action = str(data.get("action", "list")).lower()
    forge = get_forge()
    if action == "create":
        return forge.create_tool(str(data.get("name", "")), str(data.get("description", "")), str(data.get("code", "")))
    if action == "list":
        return {"ok": True, "tools": forge.list_tools()}
    if action == "delete":
        return forge.delete_tool(str(data.get("name", "")))
    if action == "invoke":
        return forge.invoke(str(data.get("name", "")), data.get("payload"))
    return {"ok": False, "error": f"unknown action '{action}' (create|list|delete|invoke)"}
