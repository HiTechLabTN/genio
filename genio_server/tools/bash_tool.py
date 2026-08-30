"""Safe subprocess wrapper for the Genio harness.

Executes a shell command inside ``bash`` with a hard timeout so a runaway
agent can never hang the harness. Returns a plain dict of ``stdout``,
``stderr`` and ``returncode`` ready to be fed back to the LLM.

Usage::

    from genio_server.tools.bash_tool import run_command
    result = run_command("python3 --version")
    print(result["stdout"])
"""
from __future__ import annotations

import os
import shlex
import subprocess
import time
from typing import Dict

DEFAULT_TIMEOUT = 30  # seconds

# Commands we never allow the agent to run from the harness.
DENIED_PREFIXES = (
    "rm -rf /",
    "sudo dd ",
    ":(){",
    "mkfs.",
    "> /dev/sd",
)


class BashToolError(RuntimeError):
    """Raised when the command could not be run at all (missing, timeout, ...)."""


def run_command(command: str, timeout: int = DEFAULT_TIMEOUT) -> Dict[str, object]:
    """Execute ``command`` in bash and return ``{"stdout", "stderr", "returncode"}``.

    Args:
        command:  The shell command string to execute.
        timeout:  Hard wall-clock limit in seconds (defaults to 30s).

    Returns:
        dict with keys:
            command, stdout, stderr, returncode, duration, timed_out
    """
    command = command.strip()
    if not command:
        return {"command": command, "stdout": "", "stderr": "empty command",
                "returncode": -1, "duration": 0.0, "timed_out": False}

    for denied in DENIED_PREFIXES:
        if command.startswith(denied):
            return {"command": command, "stdout": "",
                    "stderr": f"refused: command matches denied prefix '{denied}'",
                    "returncode": 126, "duration": 0.0, "timed_out": False}

    started = time.monotonic()
    cmd = ["/bin/bash", "-lc", command] if os.name == "posix" else command
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=os.getcwd(),
        )
        return {
            "command": command,
            "stdout": proc.stdout or "",
            "stderr": proc.stderr or "",
            "returncode": proc.returncode,
            "duration": round(time.monotonic() - started, 3),
            "timed_out": False,
        }
    except subprocess.TimeoutExpired:
        return {
            "command": command,
            "stdout": "",
            "stderr": f"timed out after {timeout}s",
            "returncode": -9,
            "duration": round(time.monotonic() - started, 3),
            "timed_out": True,
        }
    except FileNotFoundError:
        raise BashToolError(f"binary not found for command: {command!r}")