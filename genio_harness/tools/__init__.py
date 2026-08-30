"""Genio harness tool set — registry of commands the ReAct loop may call."""
from __future__ import annotations

from pathlib import Path
from typing import Dict

from genio_harness.tools.bash_tool import run_command
from genio_harness.tools.social_tool import invoke_social_post

TOOLS = {
    "bash": "execute a shell command on this Pop!_OS system",
    "social_post": "format a social-media post (LinkedIn/X/Facebook) in TechLab "
                   "darja tone. Payload: JSON {\"content_type\": \"article|rt2r_video\", "
                   "\"raw_text\": \"...\", \"platform\": \"linkedin|twitter|facebook\"}",
}


def invoke(tool: str, payload: object) -> Dict[str, object]:
    """Dispatch a tool call returned by the LLM.

    ``bash`` accepts a command string (or ``{"command": ...}``);
    ``social_post`` accepts a JSON string (or dict) of its args.
    """
    if tool not in TOOLS:
        return {"tool": tool, "error": f"unknown tool '{tool}' (known: {', '.join(sorted(TOOLS))})"}
    if tool == "bash":
        if isinstance(payload, dict):
            command = str(payload.get("command", ""))
        else:
            command = str(payload or "")
        return run_command(command)
    if tool == "social_post":
        return invoke_social_post(payload)
    return {"tool": tool, "error": f"not implemented: {tool}"}


def tool_specs() -> str:
    """Human/LLM-readable description of all available tools."""
    return "\n".join(f"- {name}: {desc}" for name, desc in TOOLS.items())


def safe_cwd() -> Path:
    return Path(__file__).resolve().parent.parent.parent