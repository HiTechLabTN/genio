"""Tool Forge — dynamic per-session tool creation (Phase 4, hardened Phase A+B).

Allows the agent (or user) to forge new tools at runtime. Tools are persisted
to `state/tool_forge.json` and auto-loaded into the registry on startup.
Toggle via GENIO_TOOL_FORGE=1 to enable (opt-in, default 0 — fail-safe).

Phase A: default 0, block RCE patterns, remove exec() in-process.
Phase B: route execution to session_container.exec_in_container (never exec()
in server process). Validation via container before registration.
Q1: Docker available local+CI (Oui partout) — if unavailable, refuse (no fallback to insecure local exec).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

FORGE_PATH = Path(__file__).resolve().parents[2] / "state" / "tool_forge.json"
_BUILTIN_TOOLS = {"bash", "social_post", "browser", "computer", "screen", "api", "tool_forge"}


def _enabled() -> bool:
    return os.getenv("GENIO_TOOL_FORGE", "0").strip().lower() not in ("0", "false", "no")


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


def _workdir_for(session_id: Optional[str]) -> Path:
    # Phase C will mount this to /work; for Phase B we also use it as host staging dir
    # Handle permission fallback: if state/ is root-owned, use tempdir
    sid = "".join(c for c in (session_id or "default") if c.isalnum())[:16] or "default"
    try:
        p = Path(__file__).resolve().parents[2] / "state" / "session_workdirs" / sid
        p.mkdir(parents=True, exist_ok=True)
        return p
    except (PermissionError, OSError):
        # Fallback to temp dir for tests/CI where state is not writable
        import tempfile as _tf
        p = Path(_tf.gettempdir()) / f"genio_session_workdirs_{sid}"
        p.mkdir(parents=True, exist_ok=True)
        return p


def _build_wrapper(code: str, payload: Any) -> str:
    payload_json = json.dumps(payload if payload is not None else {})
    # Escape for inclusion in python string
    return (
        "import json, sys\n"
        f"payload = json.loads({payload_json!r})\n"
        "result = None\n"
        + code + "\n"
        "try:\n"
        "    out = str(result) if result is not None else \"ok\"\n"
        "    print(json.dumps({\"result\": out}))\n"
        "except Exception as e:\n"
        "    print(json.dumps({\"error\": str(e)}))\n"
        "    sys.exit(1)\n"
    )


def _exec_via_container(session_id: Optional[str], code: str, payload: Any, timeout: int = 10) -> Dict[str, Any]:
    """Execute code via session_container — never in-process exec()."""
    # Q1 behavior: if Docker unavailable, refuse rather than fallback to insecure local exec
    try:
        from genio_server.tools.session_container import exec_in_container, _docker_available
    except Exception as exc:
        return {"ok": False, "error": f"session_container not available: {exc}"}
    if not _docker_available():
        return {"ok": False, "error": "docker not available — tool not registered (Q1: Oui partout, but fallback is refuse, not local exec)"}
    sid = session_id or "default"
    workdir = _workdir_for(sid)
    # Write wrapper to host workdir for mount (Phase C) and also try inline fallback
    wrapper = _build_wrapper(code, payload)
    # Try mounted path first (Phase C), fallback to inline python3 -c if mount not yet
    try:
        script_path = workdir / f"forge_{re.sub(r'[^a-zA-Z0-9_]', '_', 'tmp')}.py"
        # Use a deterministic temp name per invocation
        import uuid
        script_path = workdir / f"forge_{uuid.uuid4().hex[:8]}.py"
        script_path.write_text(wrapper, encoding="utf-8")
        # Container sees it as /work/<name> after Phase C mount; try that
        container_script = f"/work/{script_path.name}"
        res = exec_in_container(sid, f"python3 {container_script}", timeout=timeout)
        # If file not found (mount not yet), fallback to inline
        if res.get("returncode") != 0 and "No such file" in str(res.get("stderr", "")) + str(res.get("stdout", "")):
            # Fallback inline: python3 -c 'wrapper'
            import shlex
            cmd = f"python3 -c {shlex.quote(wrapper)}"
            res = exec_in_container(sid, cmd, timeout=timeout)
        return res
    except Exception as exc:
        return {"ok": False, "error": f"container exec failed: {exc}", "exception": str(exc)}


class ToolForge:
    """Registry for dynamically forged tools."""

    def create_tool(self, name: str, description: str, code: str = "", session_id: Optional[str] = None) -> Dict[str, Any]:
        if not _enabled():
            return {"ok": False, "error": "tool forge disabled — set GENIO_TOOL_FORGE=1 to enable (opt-in)"}
        err = _valid_name(name)
        if err:
            return {"ok": False, "error": err}
        if not description or len(description.strip()) < 10:
            return {"ok": False, "error": "description must be >=10 chars"}
        # Phase B: validation obligatoire avant enregistrement via container
        if code and code.strip():
            # Block RCE patterns early (defense in depth, even before container)
            forbidden = [
                "__class__", "__bases__", "__subclasses__", "__import__",
                "catch_warnings", "_module", "__builtins__", "popen", "subprocess",
            ]
            low = code.lower()
            if any(p.lower() in low for p in forbidden):
                return {"ok": False, "error": "sandbox exec disabled — code contains forbidden pattern (RCE blocked)"}
            # Smoke-test in container with minimal payload
            sid = session_id or "validation"
            res = _exec_via_container(sid, code, payload={}, timeout=10)
            # exec_in_container returns dict with returncode/stdout/stderr OR ok/error
            rc = res.get("returncode")
            if rc is not None:
                if rc != 0:
                    err_msg = res.get("stderr") or res.get("stdout") or str(res)
                    return {"ok": False, "error": f"validation failed in container (exit {rc}): {err_msg[:500]}"}
            else:
                # _exec_via_container returned ok/error style
                if res.get("ok") is False:
                    return {"ok": False, "error": f"validation failed: {res.get('error')}"}
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

    def invoke(self, name: str, payload: Any, session_id: Optional[str] = None) -> Dict[str, Any]:
        tool = self.get_tool(name)
        if not tool:
            return {"tool": name, "error": f"forged tool '{name}' not found"}
        if not _enabled():
            return {"tool": name, "error": "tool_forge disabled — set GENIO_TOOL_FORGE=1 to enable (opt-in)"}
        code = tool.get("code", "")
        if not code:
            return {"tool": name, "output": f"forged tool '{name}' invoked with {payload!r}", "forged": True}
        # Block RCE patterns (defense in depth)
        forbidden = [
            "__class__", "__bases__", "__subclasses__", "__import__",
            "catch_warnings", "_module", "__builtins__", "popen", "subprocess",
        ]
        low = code.lower()
        if any(p.lower() in low for p in forbidden):
            return {"tool": name, "error": "sandbox exec disabled — code contains forbidden pattern (RCE blocked)"}
        # Route to container — never exec() in-process
        sid = session_id or "default"
        res = _exec_via_container(sid, code, payload, timeout=10)
        rc = res.get("returncode")
        if rc is not None:
            if rc == 0:
                out = res.get("stdout", "")
                try:
                    # wrapper prints json {"result": "..."}
                    data = json.loads(out.strip().splitlines()[-1]) if out.strip() else {}
                    if "result" in data:
                        return {"tool": name, "output": str(data["result"]), "forged": True, "container": res.get("container")}
                    return {"tool": name, "output": out.strip()[:2000], "forged": True, "container": res.get("container")}
                except Exception:
                    return {"tool": name, "output": out.strip()[:2000], "forged": True, "container": res.get("container")}
            else:
                err = res.get("stderr") or res.get("stdout") or "container exec failed"
                return {"tool": name, "error": f"forged tool failed in container (exit {rc}): {err[:500]}"}
        else:
            # _exec_via_container returned ok/error
            if res.get("ok") is False:
                return {"tool": name, "error": res.get("error")}
            return {"tool": name, "error": "forged tool container exec failed"}


_forge_singleton: Optional[ToolForge] = None


def get_forge() -> ToolForge:
    global _forge_singleton
    if _forge_singleton is None:
        _forge_singleton = ToolForge()
    return _forge_singleton


def handle(payload: Any, session_id: Optional[str] = None) -> Dict[str, Any]:
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
        return forge.create_tool(str(data.get("name", "")), str(data.get("description", "")), str(data.get("code", "")), session_id=session_id)
    if action == "list":
        return {"ok": True, "tools": forge.list_tools()}
    if action == "delete":
        return forge.delete_tool(str(data.get("name", "")))
    if action == "invoke":
        return forge.invoke(str(data.get("name", "")), data.get("payload"), session_id=session_id)
    return {"ok": False, "error": f"unknown action '{action}' (create|list|delete|invoke)"}
