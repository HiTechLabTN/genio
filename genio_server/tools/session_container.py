"""Per-session container sandboxing (Phase 5, hardened Phase C).

Each session gets an isolated container `genio-session-<id>` based on
SandboxConfig.image. When GENIO_SANDBOX_MODE=container, bash_tool routes
commands through exec_in_container; otherwise it runs locally.

Docker is optional: if not available or container start fails, we fall back
to local execution with a `sandbox_fallback` flag so tests/CI never break.
Toggle via:
  GENIO_SANDBOX_MODE=container|local (default local)
  GENIO_SANDBOX_IMAGE (overrides config.sandbox.image)
  GENIO_CONTAINER_NETWORK (none|allowlist|bridge, default allowlist per Q2)

Phase C: montage volume -v <workdir hôte>:/work -w /work où workdir =
state/session_workdirs/<session_id>/ (isolé par session, évite collision).
Network policy: allowlist (bridge + egress filter via SandboxConfig.allowed_registries)
Cwd persistence: Dict[session_id, str] mis à jour via pwd après chaque exec, préfixe cd <cwd> &&
"""
from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Dict, Optional

from genio_server.tools.bash_tool import MAX_OUTPUT, TRUNCATE_MARKER

CONTAINER_PREFIX = "genio-session-"

# Phase C: cwd persistence per session
_CWD_MAP: Dict[str, str] = {}
_LAST_USED: Dict[str, float] = {}


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


def _host_workdir(session_id: str) -> Path:
    """Isolated host workdir per session — Q2: state/session_workdirs/<session_id>/"""
    sid = "".join(c for c in session_id if c.isalnum())[:16] or "default"
    # Try primary state, fallback to temp if permission denied (as in tool_forge)
    try:
        p = Path(__file__).resolve().parents[2] / "state" / "session_workdirs" / sid
        p.mkdir(parents=True, exist_ok=True)
        return p
    except (PermissionError, OSError):
        import tempfile as _tf
        p = Path(_tf.gettempdir()) / f"genio_session_workdirs_{sid}"
        p.mkdir(parents=True, exist_ok=True)
        return p


def _network_args() -> list:
    """Phase C: Q2 allow-list — reuse SandboxConfig instead of hard-coding."""
    try:
        from config import get_config
        cfg = get_config().sandbox
        policy = os.getenv("GENIO_CONTAINER_NETWORK", cfg.network_policy).lower()
        # For allowlist we use bridge (egress to allowed_registries) — documented
        # For none we isolate completely
        if policy == "none":
            return ["--network", "none"]
        if policy == "allowlist":
            # Bridge with egress filter is enforced at host iptables level in prod;
            # for now we use bridge and document allowed_registries
            return ["--network", "bridge"]
        return ["--network", "bridge"]
    except Exception:
        return ["--network", "none"]


def _docker_available() -> bool:
    return shutil.which("docker") is not None


def _ensure_container(session_id: str) -> tuple[bool, str]:
    """Ensure container exists and is running. Returns (ok, msg)."""
    name = _container_name(session_id)
    img = _image()
    workdir = _host_workdir(session_id)
    net_args = _network_args()
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
        # Phase C: montage volume isolé par session
        cmd = ["docker", "run", "-d", "--name", name] + net_args + [
              "-v", f"{workdir}:/work", "-w", "/work",
              "--memory", "512m", "--pids-limit", "256",
              img, "sleep", "infinity"]
        res = subprocess.run(
            cmd,
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

    # Phase C: cwd persistence — prefix with known cwd
    cwd = _CWD_MAP.get(session_id)
    if cwd and cwd != "/work":
        import shlex
        command = f"cd {shlex.quote(cwd)} && {command}"

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
        # Phase C: wrap command to capture cwd in same shell while preserving exit code
        # Use rc capture so validation correctly detects failures
        wrapped = f"{command}\nrc=$?\necho __GENIO_CWD__$(pwd)\nexit $rc"
        proc = subprocess.run(
            ["docker", "exec", name, "/bin/bash", "-lc", wrapped],
            capture_output=True, text=True, timeout=timeout,
        )
        # Parse cwd from stdout
        stdout = proc.stdout
        cwd_captured = None
        if "__GENIO_CWD__" in stdout:
            # Split on marker
            if stdout.count("__GENIO_CWD__") >= 1:
                actual, cwd_part = stdout.rsplit("__GENIO_CWD__", 1)
                cwd_captured = cwd_part.strip().splitlines()[0].strip()
                stdout = actual
        # Update cwd map and last used if success
        if proc.returncode == 0:
            _LAST_USED[session_id] = time.time()
            if cwd_captured:
                _CWD_MAP[session_id] = cwd_captured
        return {
            "command": command,
            "stdout": _truncate(stdout),
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


async def async_cleanup_container(session_id: str) -> bool:
    """Async non-blocking variant of :func:`cleanup_container` (Phase 1 v2.1)."""
    name = _container_name(session_id)
    if not _docker_available():
        return False
    try:
        proc = await asyncio.create_subprocess_exec(
            "docker", "rm", "-f", name,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.wait_for(proc.wait(), timeout=10)
        return proc.returncode == 0
    except Exception:
        return False


async def async_ensure_container(session_id: str) -> tuple[bool, str]:
    """Async variant of :func:`_ensure_container` using create_subprocess_exec."""
    name = _container_name(session_id)
    img = _image()
    workdir = _host_workdir(session_id)
    net_args = _network_args()
    try:
        proc = await asyncio.create_subprocess_exec(
            "docker", "inspect", "-f", "{{.State.Running}}", name,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
        )
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
        if proc.returncode == 0 and b"true" in (out or b"").lower():
            return True, ""
    except Exception:
        pass
    try:
        cmd = ["docker", "run", "-d", "--name", name] + net_args + [
            "-v", f"{workdir}:/work", "-w", "/work",
            "--memory", "512m", "--pids-limit", "256",
            img, "sleep", "infinity"]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        out, err = await asyncio.wait_for(proc.communicate(), timeout=30)
        if proc.returncode == 0:
            return True, ""
        errtext = (err or out or b"").decode(errors="replace")
        if "already in use" in errtext or "already exists" in errtext:
            proc2 = await asyncio.create_subprocess_exec(
                "docker", "start", name,
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
            )
            _, err2 = await asyncio.wait_for(proc2.communicate(), timeout=10)
            if proc2.returncode == 0:
                return True, ""
            return False, err2.decode(errors="replace").strip() or errtext.strip()
        return False, errtext.strip()
    except Exception as exc:
        return False, str(exc)


async def async_exec_in_container(session_id: str, command: str,
                                  timeout: int = 30) -> Dict[str, object]:
    """Async non-blocking variant of :func:`exec_in_container` (Phase 1 v2.1).

    All docker exec/run/inspect/ps calls use ``asyncio.create_subprocess_exec``
    so slow container operations never block the harness event loop. Fallback
    to ``async_run_command`` when docker is unavailable or container start
    fails, exactly as the sync path does.
    """
    if not session_id:
        return {"command": command, "stdout": "", "stderr": "missing session_id",
                "returncode": 127, "duration": 0.0, "timed_out": False}
    return await _async_exec_in_container(session_id, command, timeout)


async def _async_exec_in_container(session_id: str, command: str,
                                   timeout: int) -> Dict[str, object]:
    started = time.monotonic()

    def _t(s: str) -> str:
        if len(s) <= MAX_OUTPUT:
            return s
        return s[:MAX_OUTPUT] + TRUNCATE_MARKER

    cwd = _CWD_MAP.get(session_id)
    if cwd and cwd != "/work":
        import shlex
        command = f"cd {shlex.quote(cwd)} && {command}"

    if not _enabled():
        from genio_server.tools.bash_tool import async_run_command
        old = os.getenv("GENIO_SANDBOX_MODE")
        os.environ["GENIO_SANDBOX_MODE"] = ""
        try:
            return await async_run_command(command, timeout=timeout)
        finally:
            if old is None:
                os.environ.pop("GENIO_SANDBOX_MODE", None)
            else:
                os.environ["GENIO_SANDBOX_MODE"] = old

    if not _docker_available():
        old = os.getenv("GENIO_SANDBOX_MODE")
        os.environ["GENIO_SANDBOX_MODE"] = ""
        try:
            try:
                proc = await asyncio.create_subprocess_exec(
                    "/bin/bash", "-lc", command,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                )
                out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
                return {
                    "command": command,
                    "stdout": _t(out.decode(errors="replace")),
                    "stderr": _t(err.decode(errors="replace")),
                    "returncode": proc.returncode,
                    "duration": round(time.monotonic() - started, 3),
                    "timed_out": False,
                    "sandbox_fallback": True,
                    "sandbox_reason": "docker not available",
                }
            except asyncio.TimeoutError:
                return {"command": command, "stdout": "", "stderr": f"timed out after {timeout}s",
                        "returncode": -9, "duration": round(time.monotonic() - started, 3),
                        "timed_out": True, "sandbox_fallback": True}
        finally:
            if old is None:
                os.environ.pop("GENIO_SANDBOX_MODE", None)
            else:
                os.environ["GENIO_SANDBOX_MODE"] = old

    ok, msg = await async_ensure_container(session_id)
    if not ok:
        old = os.getenv("GENIO_SANDBOX_MODE")
        os.environ["GENIO_SANDBOX_MODE"] = ""
        try:
            try:
                proc = await asyncio.create_subprocess_exec(
                    "/bin/bash", "-lc", command,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                )
                out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
                return {
                    "command": command,
                    "stdout": _t(out.decode(errors="replace")),
                    "stderr": _t(err.decode(errors="replace") + f"\n[sandbox fallback: {msg}]"),
                    "returncode": proc.returncode,
                    "duration": round(time.monotonic() - started, 3),
                    "timed_out": False,
                    "sandbox_fallback": True,
                    "sandbox_reason": msg or "container start failed",
                }
            except asyncio.TimeoutError:
                return {"command": command, "stdout": "", "stderr": f"timed out after {timeout}s",
                        "returncode": -9, "duration": round(time.monotonic() - started, 3),
                        "timed_out": True, "sandbox_fallback": True}
        finally:
            if old is None:
                os.environ.pop("GENIO_SANDBOX_MODE", None)
            else:
                os.environ["GENIO_SANDBOX_MODE"] = old

    name = _container_name(session_id)
    try:
        wrapped = f"{command}\nrc=$?\necho __GENIO_CWD__$(pwd)\nexit $rc"
        proc = await asyncio.create_subprocess_exec(
            "docker", "exec", name, "/bin/bash", "-lc", wrapped,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        stdout = out.decode(errors="replace")
        cwd_captured = None
        if "__GENIO_CWD__" in stdout:
            actual, cwd_part = stdout.rsplit("__GENIO_CWD__", 1)
            cwd_captured = cwd_part.strip().splitlines()[0].strip()
            stdout = actual
        if proc.returncode == 0:
            _LAST_USED[session_id] = time.time()
            if cwd_captured:
                _CWD_MAP[session_id] = cwd_captured
        return {
            "command": command,
            "stdout": _t(stdout),
            "stderr": _t(err.decode(errors="replace")),
            "returncode": proc.returncode,
            "duration": round(time.monotonic() - started, 3),
            "timed_out": False,
            "container": name,
        }
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except Exception:
            pass
        return {"command": command, "stdout": "", "stderr": f"timed out after {timeout}s",
                "returncode": -9, "duration": round(time.monotonic() - started, 3),
                "timed_out": True, "container": name}
    except Exception as exc:
        return {"command": command, "stdout": "", "stderr": str(exc), "returncode": 127,
                "duration": round(time.monotonic() - started, 3), "timed_out": False, "container": name}
