"""Per-session container sandboxing (Phase 5).

Each session gets an isolated container `genio-session-<id>` based on
SandboxConfig.image. When GENIO_SANDBOX_MODE=container, bash_tool routes
commands through exec_in_container; otherwise it runs locally.

Docker is optional: if not available or container start fails, we fall back
to local execution with a `sandbox_fallback` flag so tests/CI never break.
Toggle via:
  GENIO_SANDBOX_MODE=container|local (default local)
  GENIO_SANDBOX_IMAGE (overrides config.sandbox.image)
"""
from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Dict, Optional

from genio_server.tools.bash_tool import MAX_OUTPUT, TRUNCATE_MARKER

CONTAINER_PREFIX = "genio-session-"


def _enabled() -> bool:
    return os.getenv("GENIO_SANDBOX_MODE", "").strip().lower() == "container"


def _image() -> str:
    env_img = os.getenv("GENIO_SANDBOX_IMAGE", "").strip()
    if env_img:
        return env_img
    try:
        from config import get_config
        return get_config().sandbox.image
    except Exception:
        return "ubuntu:22.04"


def _container_name(session_id: str) -> str:
    safe = "".join(c for c in session_id if c.isalnum())[:12]
    return f"{CONTAINER_PREFIX}{safe}"


def _docker_available() -> bool:
    return shutil.which("docker") is not None


def _ensure_container(session_id: str) -> tuple[bool, str]:
    """Ensure container exists and is running. Returns (ok, msg)."""
    name = _container_name(session_id)
    img = _image()
    # check if already running
    try:
        res = subprocess.run(["docker", "inspect", "-f", "{{.State.Running}}", name],
                             capture_output=True, text=True, timeout=5)
        if res.returncode == 0 and "true" in res.stdout.lower():
            return True, ""
    except Exception:
        pass
    # try to run new container detached, keep alive with sleep infinity
    try:
        # Use --rm? No, keep for session reuse. Create if not exists.
        res = subprocess.run(
            ["docker", "run", "-d", "--name", name, "--network", "none",
             "--memory", "512m", "--pids-limit", "256",
             img, "sleep", "infinity"],
            capture_output=True, text=True, timeout=30,
        )
        if res.returncode == 0:
            return True, ""
        # if name already exists but not running, start it
        if "already in use" in res.stderr or "already exists" in res.stderr:
            res2 = subprocess.run(["docker", "start", name], capture_output=True, text=True, timeout=10)
            if res2.returncode == 0:
                return True, ""
        return False, res.stderr.strip() or res.stdout.strip()
    except Exception as exc:
        return False, str(exc)


def _truncate(s: str) -> str:
    if len(s) <= MAX_OUTPUT:
        return s
    return s[:MAX_OUTPUT] + TRUNCATE_MARKER


def exec_in_container(session_id: str, command: str, timeout: int = 30) -> Dict[str, object]:
    """Execute command inside per-session container, fallback to local if needed."""
    started = time.monotonic()
    if not session_id:
        return {"command": command, "stdout": "", "stderr": "missing session_id", "returncode": 127,
                "duration": 0.0, "timed_out": False}

    if not _enabled():
        # Should not be called when disabled, but handle gracefully
        from genio_server.tools.bash_tool import run_command as local_run
        # avoid recursion: call local directly without session_id
        import genio_server.tools.bash_tool as bt
        # Temporarily disable sandbox to avoid loop
        old = os.getenv("GENIO_SANDBOX_MODE")
        os.environ["GENIO_SANDBOX_MODE"] = ""
        try:
            return bt.run_command(command, timeout=timeout)
        finally:
            if old is None:
                os.environ.pop("GENIO_SANDBOX_MODE", None)
            else:
                os.environ["GENIO_SANDBOX_MODE"] = old

    if not _docker_available():
        # Fallback: local execution
        from genio_server.tools.bash_tool import run_command as local_run
        old = os.getenv("GENIO_SANDBOX_MODE")
        os.environ["GENIO_SANDBOX_MODE"] = ""
        try:
            res = local_run(command, timeout=timeout) if False else None
            # Actually call subprocess directly to avoid recursion
            import subprocess as sp
            proc = sp.run(["/bin/bash", "-lc", command], capture_output=True, text=True, timeout=timeout)
            res = {
                "command": command,
                "stdout": _truncate(proc.stdout),
                "stderr": _truncate(proc.stderr),
                "returncode": proc.returncode,
                "duration": round(time.monotonic() - started, 3),
                "timed_out": False,
                "sandbox_fallback": True,
                "sandbox_reason": "docker not available",
            }
            return res
        except subprocess.TimeoutExpired:
            return {"command": command, "stdout": "", "stderr": f"timed out after {timeout}s",
                    "returncode": -9, "duration": round(time.monotonic() - started, 3),
                    "timed_out": True, "sandbox_fallback": True}
        finally:
            if old is None:
                os.environ.pop("GENIO_SANDBOX_MODE", None)
            else:
                os.environ["GENIO_SANDBOX_MODE"] = old

    ok, msg = _ensure_container(session_id)
    if not ok:
        # Fallback to local
        try:
            proc = subprocess.run(["/bin/bash", "-lc", command], capture_output=True, text=True, timeout=timeout)
            return {
                "command": command,
                "stdout": _truncate(proc.stdout),
                "stderr": _truncate(proc.stderr + f"\n[sandbox fallback: {msg}]"),
                "returncode": proc.returncode,
                "duration": round(time.monotonic() - started, 3),
                "timed_out": False,
                "sandbox_fallback": True,
                "sandbox_reason": msg or "container start failed",
            }
        except subprocess.TimeoutExpired:
            return {"command": command, "stdout": "", "stderr": f"timed out after {timeout}s",
                    "returncode": -9, "duration": round(time.monotonic() - started, 3),
                    "timed_out": True, "sandbox_fallback": True}

    name = _container_name(session_id)
    try:
        proc = subprocess.run(
            ["docker", "exec", name, "/bin/bash", "-lc", command],
            capture_output=True, text=True, timeout=timeout,
        )
        return {
            "command": command,
            "stdout": _truncate(proc.stdout),
            "stderr": _truncate(proc.stderr),
            "returncode": proc.returncode,
            "duration": round(time.monotonic() - started, 3),
            "timed_out": False,
            "container": name,
        }
    except subprocess.TimeoutExpired:
        return {"command": command, "stdout": "", "stderr": f"timed out after {timeout}s",
                "returncode": -9, "duration": round(time.monotonic() - started, 3),
                "timed_out": True, "container": name}
    except Exception as exc:
        return {"command": command, "stdout": "", "stderr": str(exc), "returncode": 127,
                "duration": round(time.monotonic() - started, 3), "timed_out": False, "container": name}


def cleanup_container(session_id: str) -> bool:
    name = _container_name(session_id)
    if not _docker_available():
        return False
    try:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=10)
        return True
    except Exception:
        return False
