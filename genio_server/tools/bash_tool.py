"""Safe subprocess wrapper for the Genio harness.

Executes a shell command inside ``bash`` with a hard timeout so a runaway
agent can never hang the harness. Returns a plain dict of ``stdout``,
``stderr`` and ``returncode`` ready to be fed back to the LLM.

Usage::

    from genio_server.tools.bash_tool import run_command
    result = run_command("python3 --version")
    print(result["stdout"])

Phase 1 v2.1: Async migration — run_command now has async counterpart
async_run_command using asyncio.create_subprocess_exec to avoid blocking
the event loop. Sync wrapper retained for backward compat.
"""
from __future__ import annotations

import asyncio
import os
import shlex
import subprocess
import time
from typing import Dict, Optional

DEFAULT_TIMEOUT = 30  # seconds

# Cap any single command's captured output so giant dumps (e.g. ``ls -R``)
# can never overflow the LLM context window.
MAX_OUTPUT = 3000
TRUNCATE_MARKER = "\n... [Output truncated to preserve context window]"


class BashToolError(RuntimeError):
    """Raised when the command could not be run at all (missing, timeout, ...)."""


def _allow_sudo() -> bool:
    """Whether `sudo` is permitted (GENIO_ALLOW_SUDO=1). Off by default."""
    return os.getenv("GENIO_ALLOW_SUDO", "0").strip().lower() in ("1", "true", "yes")


def _tokenize_all(command: str) -> list:
    """Split a command on &&, |, ; and shlex-tokenize each segment.

    Returns a flat list of tokens (preserving each segment's argv order).
    """
    segments = []
    for seg in command.replace("&&", "\n").replace("||", "\n").replace("|", "\n").split("\n"):
        for s in seg.replace(";", "\n").split("\n"):
            s = s.strip()
            if s:
                try:
                    segments.extend(shlex.split(s))
                except ValueError:
                    segments.extend(s.split())
    return [t for t in segments if t]


def is_dangerous(command: str) -> Optional[str]:
    """Return a human-readable refusal reason if ``command`` is unsafe, else None.

    Robust against the obfuscations found in a security audit: ``sudo rm -rf /``,
    ``rm -rf /*``, ``bash -c "rm -rf /"`` and ``cd / && rm -rf .`` are all caught.

    Refusals:
    * ``rm`` with -r/-f/--recursive/--force targeting filesystem roots or paths
      outside the allowed working directory.
    * ``dd`` writing/reading ``/dev/sd*`` block devices.
    * ``mkfs.*`` filesystem creation.
    * shell redirection ``>`` onto ``/dev/sd*``.
    * ``chmod -R 777 /`` (recursive world-writable on root).
    * fork bombs (``:(){ :|:& };:`` and variants).
    * ``sudo`` (refused by default; enable via GENIO_ALLOW_SUDO=1).
    """
    if not command or not command.strip():
        return None
    if not _allow_sudo() and _contains_sudo(command):
        return "sudo is disabled (set GENIO_ALLOW_SUDO=1 to enable)"

    tokens = _tokenize_all(command)
    lowered = command.lower()

    # Fork bomb — a bare function bomb in the raw text.
    if any(fb in lowered for fb in (":(){", ":|:&", "(){ :|:& }")):
        return "potential fork bomb detected"

    # Redirection onto raw block devices: > /dev/sdX
    if _redirects_to_device(lowered):
        return "redirection onto /dev/sd* block device is forbidden"

    # mkfs.* (create filesystem)
    if any(w.startswith("mkfs.") for w in _tokenize_all(lowered)):
        return "mkfs.* (filesystem creation) is forbidden"

    # dd targeting /dev/sd* via of= or if=
    if any(t == "dd" for t in tokens) and _dd_targets_device(lowered):
        return "dd targeting /dev/sd* block device is forbidden"

    # chmod -R 777 / (recursive world-writable on root filesystem)
    if any(t == "chmod" for t in tokens):
        try:
            chmod_idx = tokens.index("chmod")
            rest = tokens[chmod_idx + 1 :]
            flags, targets = _split_flags_targets(rest)
            rec = any(f in ("-r", "-R", "--recursive") for f in flags)
            perms = "777" in rest or any("a+w" in f or "o+w" in f for f in rest)
            if rec and perms and any(t in ("/",) for t in targets):
                return "chmod -R 777 / is forbidden"
        except Exception:
            pass

    # rm with recursive/force whose targets escape the allowed workdir.
    if any(t == "rm" for t in tokens):
        try:
            rm_idx = tokens.index("rm")
            flags, targets = _split_flags_targets(tokens[rm_idx + 1 :])
            if _has_force_recursive(flags):
                for target in targets:
                    reason = _check_rm_target(target)
                    if reason:
                        return reason
        except Exception:
            pass

    # Quoted sub-commands (bash -c "...", sh -c "...") hide tokens inside a
    # single argv element, so tokens above won't see the inner rm/dd/mkfs.
    # Scan the raw command for the classic dangerous substrings as a backstop.
    raw_reason = _scan_raw_danger(command.lower())
    if raw_reason:
        return raw_reason

    return None


def _scan_raw_danger(lowered: str) -> Optional[str]:
    """Regex backstop for shortcuts hidden inside quoted ``-c`` arguments."""
    import re

    # rm -rf <root> (with optional cd / && prefix). Backstop targets absolute
    # roots only; relative ./build etc. are safe and caught by token logic.
    for m in re.finditer(
        r"\brm\s+-(?:[a-z]*[rf][a-z]*)\s+(\/\*?|~\/?)(?:\s|\"|')?",
        lowered,
    ):
        if m.group(1).strip():
            return f"rm-safe: {m.group(0)!r} targets a filesystem root"
    # rm -r < / or /* >
    for m in re.finditer(r"rm\s+-r[a-z]*\s+(/\*?)(?:\s|\"|')?", lowered):
        return f"rm-safe: {m.group(0)!r} targets a filesystem root"
    # dd of=/dev/sdX / if=/dev/sdX
    if re.search(r"dd\b[^\n]*\b(?:of|if)=/dev/sd", lowered):
        return "dd targeting /dev/sd* block device is forbidden"
    # mkfs.*
    if re.search(r"mkfs\.[a-z0-9]+\s+/dev/sd", lowered):
        return "mkfs.* (filesystem creation) is forbidden"
    # > /dev/sdX
    if re.search(r">\s*/dev/sd", lowered):
        return "redirection onto /dev/sd* block device is forbidden"
    # fork bomb
    if re.search(r":\{|:\|:&", lowered):
        return "potential fork bomb detected"
    return None


def _contains_sudo(command: str) -> bool:
    return any(t == "sudo" for t in _tokenize_all(command))


def _redirects_to_device(lowered: str) -> bool:
    return any(m in lowered for m in (">/dev/sd", "> /dev/sd", ">>/dev/sd", ">> /dev/sd"))


def _dd_targets_device(lowered: str) -> bool:
    return any(t.startswith("of=/dev/sd") or t.startswith("if=/dev/sd")
               for t in lowered.split())


def _split_flags_targets(args: list) -> tuple:
    flags, targets = [], []
    for a in args:
        if a.startswith("-"):
            flags.append(a)
        else:
            targets.append(a)
    return flags, targets


def _has_force_recursive(flags: list) -> bool:
    return any(f in ("-f", "--force", "-r", "-R", "--recursive", "-rf", "-fr")
               for f in flags)


def _check_rm_target(target: str) -> Optional[str]:
    if target in ("/", "/*", "*"):
        return f"rm target {target!r} is a filesystem root"
    if target.startswith("/") and target != "/work":
        return f"rm target {target!r} is outside the allowed working directory"
    if target == "~" or target.startswith("~/"):
        return f"rm target {target!r} expands outside the allowed working directory"
    if target in (".", ".."):
        return f"rm target {target!r} is ambiguous at filesystem root"
    return None


def truncate_output(text: str) -> str:
    """Cap captured output to ``MAX_OUTPUT`` chars, appending a marker."""
    text = text or ""
    if len(text) <= MAX_OUTPUT:
        return text
    return text[:MAX_OUTPUT] + TRUNCATE_MARKER


def run_command(command: str, timeout: int = DEFAULT_TIMEOUT,
                session_id: Optional[str] = None) -> Dict[str, object]:
    """Execute ``command`` in bash and return ``{"stdout", "stderr", "returncode"}``.

    Args:
        command:  The shell command string to execute.
        timeout:  Hard wall-clock limit in seconds (defaults to 30s).
        session_id: Optional session id. When set and GENIO_SANDBOX_MODE=container,
            the command is routed through the per-session container instead of a
            local subprocess.

    Returns:
        dict with keys:
            command, stdout, stderr, returncode, duration, timed_out
    """
    command = command.strip()
    if not command:
        return {"command": command, "stdout": "", "stderr": "empty command",
                "returncode": -1, "duration": 0.0, "timed_out": False}

    danger = is_dangerous(command)
    if danger:
        return {"command": command, "stdout": "",
                "stderr": f"refused: {danger}",
                "returncode": 126, "duration": 0.0, "timed_out": False}

    # Container sandboxing (Phase 5) — route per-session when enabled.
    if session_id and os.getenv("GENIO_SANDBOX_MODE", "").strip().lower() == "container":
        try:
            from genio_server.tools.session_container import exec_in_container
            return exec_in_container(session_id, command, timeout)
        except Exception as exc:
            return {"command": command, "stdout": "", "stderr": str(exc),
                    "returncode": 127, "duration": 0.0, "timed_out": False}

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
        return _result(command, proc.stdout, proc.stderr, proc.returncode, started, False)
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


def _result(command: str, stdout: str, stderr: str, returncode: int,
            started: float, timed_out: bool) -> Dict[str, object]:
    """Build the canonical result dict from a completed subprocess outcome."""
    return {
        "command": command,
        "stdout": truncate_output(str(stdout or "")),
        "stderr": truncate_output(str(stderr or "")),
        "returncode": returncode,
        "duration": round(time.monotonic() - started, 3),
        "timed_out": timed_out,
    }


async def async_run_command(command: str, timeout: int = DEFAULT_TIMEOUT,
                            session_id: Optional[str] = None) -> Dict[str, object]:
    """Async non-blocking variant of :func:`run_command` (Phase 1 v2.1).

    Uses ``asyncio.create_subprocess_exec`` so a long-running bash command
    never blocks the harness event loop (WebSocket telemetry, kill handling
    and SSE stay responsive). Semantics otherwise identical to run_command.
    """
    command = command.strip()
    if not command:
        return {"command": command, "stdout": "", "stderr": "empty command",
                "returncode": -1, "duration": 0.0, "timed_out": False}

    danger = is_dangerous(command)
    if danger:
        return {"command": command, "stdout": "",
                "stderr": f"refused: {danger}",
                "returncode": 126, "duration": 0.0, "timed_out": False}

    # Container sandboxing (Phase 5) — route per-session when enabled.
    if session_id and os.getenv("GENIO_SANDBOX_MODE", "").strip().lower() == "container":
        try:
            from genio_server.tools.session_container import async_exec_in_container
            return await async_exec_in_container(session_id, command, timeout)
        except Exception as exc:
            return {"command": command, "stdout": "", "stderr": str(exc),
                    "returncode": 127, "duration": 0.0, "timed_out": False}

    started = time.monotonic()
    cmd = ["/bin/bash", "-lc", command] if os.name == "posix" else ["/bin/sh", "-c", command]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=os.getcwd(),
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=timeout,
        )
        decoded_out = stdout.decode(errors="replace") if stdout else ""
        decoded_err = stderr.decode(errors="replace") if stderr else ""
        return _result(command, decoded_out, decoded_err, proc.returncode, started, False)
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except Exception:
            pass
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
