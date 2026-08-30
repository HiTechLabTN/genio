"""Genio harness tool set — registry of commands the ReAct loop may call.

Includes the classic local tools (bash, social_post) plus the autonomous
actuators: headless browsing (:mod:`~.browser_tool`), GUI computer use
(:mod:`~.computer_tool`) and dynamic third-party API calls
(:mod:`genio_server.server.api_engine`). Every actuator is gated by the
process-wide KILL SWITCH (:mod:`~.safety`).
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict

from genio_server.tools.bash_tool import run_command
from genio_server.tools.social_tool import invoke_social_post
from genio_server.tools import browser_tool, computer_tool

TOOLS = {
    "bash": "execute a shell command on this Pop!_OS system",
    "social_post": "format a social-media post (LinkedIn/X/Facebook) in TechLab "
                   "darja tone. Payload: JSON {\"content_type\": \"article|rt2r_video\", "
                   "\"raw_text\": \"...\", \"platform\": \"linkedin|twitter|facebook\"}",
    "browser": "autonomous headless web browsing. Payload: JSON {\"action\": "
               "\"open|extract|click|type|screenshot|url|close\", \"url\": ..., "
               "\"selector\": ..., \"text\": ...}",
    "computer": "autonomous GUI control of the host desktop. Payload: JSON "
                "{\"action\": \"screenshot|position|move|click|doubleclick|type|key|scroll\", "
                "\"x\": ..., \"y\": ..., \"text\": ..., \"keys\": ...}",
    "screen": "capture a screenshot of the host display and return its path "
              "(alias of computer screenshot). Payload optional.",
    "api": "call third-party REST APIs through dynamically loaded OpenAPI skills. "
           "Payload: JSON {\"action\": \"list|search|execute|load\", "
           "\"name\": <skill name>, \"query\": ..., \"method\": ..., \"path\": ..., "
           "\"params\": {...}, \"body\": {...}, \"source\": <url or file>}",
}


def mkdir_tmp() -> Path:
    root = Path(__file__).resolve().parent.parent.parent
    d = root / "tmp"
    d.mkdir(parents=True, exist_ok=True)
    return d


def parse_payload(payload: Any) -> Any:
    if isinstance(payload, str):
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            return payload
    return payload


def invoke(tool: str, payload: Any) -> Dict[str, object]:
    """Dispatch a tool call returned by the LLM.

    ``bash`` accepts a command string (or ``{"command": ...}``);
    ``social_post`` accepts a JSON string (or dict) of its arguments.
    """
    if tool not in TOOLS:
        return {"tool": tool, "error": f"unknown tool '{tool}' (known: {', '.join(sorted(TOOLS))})"}
    try:
        if tool == "bash":
            if isinstance(payload, dict):
                command = str(payload.get("command", ""))
            else:
                command = str(payload or "")
            return run_command(command)
        if tool == "social_post":
            return invoke_social_post(payload)
        if tool == "browser":
            return browser_tool.handle(payload)
        if tool == "computer":
            return computer_tool.handle(payload)
        if tool == "screen":
            return computer_tool.screenshot()
        if tool == "api":
            from genio_server.server.api_engine import handle as api_handle
            return api_handle(payload)
    except Exception as exc:
        return {"tool": tool, "error": f"{tool} raised: {exc}"}
    return {"tool": tool, "error": f"not implemented: {tool}"}


def tool_specs() -> str:
    """Human/LLM-readable description of all available tools."""
    return "\n".join(f"- {name}: {desc}" for name, desc in TOOLS.items())


def safe_cwd() -> Path:
    return Path(__file__).resolve().parent.parent.parent