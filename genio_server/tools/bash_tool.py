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
import logging
import os
import shlex
import subprocess
import time
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

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


def _effective_workspace() -> Tuple[str, bool, str]:
    """Resolve the execution workspace.

    Returns (path, explicit, note) where explicit=True only when
    GENIO_WORKSPACE names an existing directory (operator-designated
    disposable scope). A GENIO_WORKSPACE that is set but invalid is
    NEVER silently replaced: note carries the warning and callers treat
    destructive commands as refused (fail-closed, loud).
    """
    configured = os.getenv("GENIO_WORKSPACE", "").strip()
    if configured:
        if os.path.isdir(configured):
            return configured, True, ""
        note = (f"GENIO_WORKSPACE={configured!r} invalid (missing/not-a-dir)")
        logger.warning("bash_tool: %s — destructive commands refused", note)
        return os.getcwd(), False, note
    return os.getcwd(), False, ""


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


def is_dangerous(command: str, workspace: Optional[str] = None) -> Optional[str]:
    """Return a human-readable refusal reason if ``command`` is unsafe, else None.

    Static string predicate PLUS workspace-canonicalized rm scoping (the
    closure gate): ``workspace`` defaults to the effective workspace
    (GENIO_WORKSPACE when valid, else server cwd); run_command passes the
    already-resolved value. Refusal classes: HARD (roots, system, devices,
    privesc, fork, mkfs — never overridable) vs "scoped: ..."/workspace
    messages (fresh single-use approval bound to the exact command may
    override; see refusal_overridable + verify_approval).

    Robust against the obfuscations found in a security audit: ``sudo rm -rf /``,
    ``rm -rf /*``, ``bash -c "rm -rf /"`` and ``cd / && rm -rf .`` are all caught.

    Refusals:
    * ``rm`` with -r/-f/--recursive/--force: roots always; any other
      target must resolve under the workspace AND the workspace must be
      an explicit disposable one, else approval is required. Relative
      paths, ``..`` traversal and symlink escapes are resolved
      canonically (realpath) — there is no relative-path exemption.
    * bare ``rm`` keeps the historic root/outside rules (single-file
      semantics; the interactive policy gate still escalates it).
    * ``dd`` writing/reading block devices (hard); ``dd of=<file>``,
      ``shred``/``wipefs``, ``mv … /dev/null`` (scoped).
    * ``mkfs.*`` filesystem creation.
    * shell redirection ``>`` onto ``/dev/sd*``.
    * ``chmod -R 777 /`` (recursive world-writable on root).
    * fork bombs (``:(){ :|:& };:`` and variants).
    * ``sudo`` (refused by default; enable via GENIO_ALLOW_SUDO=1).
    """
    if not command or not command.strip():
        return None
    # Phase 7 : validation structurée D'ABORD (couche primaire) — les regex
    # historiques ci-dessous restent en défense en profondeur.
    try:
        from genio_server.tools.bash_ast import denial_reason
        structured = denial_reason(command)
        if structured:
            return structured
    except Exception:
        pass
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

    # rm — workspace-canonicalized scoping (closure gate, no
    # relative-path exemption). Historic absolute messages kept.
    rm_reason = _rm_workspace_reason(command, tokens, workspace)
    if rm_reason:
        return rm_reason

    # Other destroyers (scoped, approval-overridable).
    other = _scoped_other_reason(command)
    if other:
        return other

    # Quoted sub-commands (bash -c "...", sh -c "...") hide tokens inside a
    # single argv element, so tokens above won't see the inner rm/dd/mkfs.
    # Scan the raw command for the classic dangerous substrings as a backstop.
    raw_reason = _scan_raw_danger(command.lower())
    if raw_reason:
        return raw_reason

    return None


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


def _rm_workspace_reason(command: str, tokens: list,
                         workspace=None) -> Optional[str]:
    """Canonical rm scoping for ONE command string. See is_dangerous.

    ``workspace``: None → effective workspace; str path → (path,
    isdir(path), ""); (path, explicit, note) tuple → used as-is (lets
    run_command resolve once and share the exact context, including the
    invalid-workspace warning).
    """
    from genio_server.tools.fs_guard import canonicalize
    if workspace is None:
        ws_path, explicit, ws_note = _effective_workspace()
    elif isinstance(workspace, tuple):
        ws_path, explicit, ws_note = workspace
    else:
        ws_path, explicit, ws_note = workspace, os.path.isdir(workspace), ""
    root = canonicalize(ws_path)
    suffix = f" [{ws_note}]" if ws_note else ""
    for flags, targets, _src in _iter_rm_commands(command):
        if not _has_force_recursive(flags):
            # Bare rm: historic rules for roots/home/ambiguous + absolute
            # paths outside the workspace; explicit single-file targets
            # under the workspace stay allowed (ordinary file work — the
            # interactive policy gate still escalates every rm).
            for t in targets:
                if t in ("/", "/*", "*"):
                    return f"rm target {t!r} is a filesystem root"
                if t in (".", "..") or t.startswith("~"):
                    reason = _check_rm_target(t)
                    if reason:
                        return reason
                    continue
                if t.startswith("/"):
                    if not _under(_resolve_against(root, t), root):
                        return (f"rm target {t!r} is outside the allowed "
                                f"working directory")
                    continue
            continue
        # Recursive/force rm: every target must resolve under the
        # workspace; under-workspace further requires an explicit
        # disposable workspace, else approval.
        if not targets:
            return (f"scoped: recursive/force rm without explicit target "
                    f"in {root}{suffix} — approval required")
        for t in targets:
            if t in ("/", "/*"):
                return f"rm target {t!r} is a filesystem root"
            canon = _resolve_against(root, t)
            if not _under(canon, root):
                if t.startswith("/") or t.startswith("~"):
                    legacy = _check_rm_target(t)
                    if legacy:
                        return legacy
                return (f"scoped: rm target {t!r} resolves to {canon!r}, "
                        f"outside workspace {root}{suffix} — approval required")
            if not explicit:
                return (f"scoped: recursive/force rm under server cwd "
                        f"{root}{suffix} — approval required")
    # NOTE: no legacy token-level fallback here on purpose — the canonical
    # scan above (token segments + raw backstop) plus the AST primary layer
    # plus _scan_raw_danger already triple-cover rm; a legacy fallback
    # would re-impose the stale /work-only absolute rule and undo
    # workspace-aware decisions (closure gate).
    return None


def _scan_raw_danger(lowered: str) -> Optional[str]:
    """Regex backstop for shortcuts hidden inside quoted ``-c`` arguments."""
    import re

    # rm -rf <root> (with optional cd / && prefix). Backstop targets TRUE
    # roots only (/ /* ~ ~/) — longer absolute paths (/tmp/x) are NOT
    # roots; the canonical workspace layer owns them (closure gate).
    for m in re.finditer(
        r"\brm\s+-(?:[a-z]*[rf][a-z]*)\s+(\/|/\*|~|~/)(?=\s|\"|'|$)",
        lowered,
    ):
        if m.group(1).strip():
            return f"rm-safe: {m.group(0)!r} targets a filesystem root"
    # rm -r < / or /* > (true roots only, same rationale).
    for m in re.finditer(r"rm\s+-r[a-z]*\s+(\/|/\*)(?=\s|\"|'|$)", lowered):
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
    import re as _re
    for f in flags:
        if f in ("-f", "--force", "-r", "-R", "--recursive", "-rf", "-fr"):
            return True
        # clusters: -rfv, -frv, -Rfv, --recursive=... etc.
        if _re.fullmatch(r"-[a-zA-Z]+", f or "") and (
                "r" in f or "R" in f or "f" in f):
            return True
        if (f or "").startswith("--recursive") or (f or "") == "--force":
            return True
    return False


def _resolve_against(cwd: str, target: str) -> str:
    """Canonicalize a shell target the way the shell would see it.

    realpath(strict=False): existing symlinks fully resolved (escape
    detection), dangling paths normalized via their existing parents.
    """
    from genio_server.tools.fs_guard import canonicalize
    t = (target or "").strip()
    if t.startswith("~"):
        t = os.path.expanduser(t)
    if not os.path.isabs(t):
        t = os.path.join(cwd, t)
    return canonicalize(t)


def _under(canon: str, root: str) -> bool:
    return canon == root or canon.startswith(root + os.sep)


def _iter_rm_commands(command: str):
    """Yield (flags, targets) for each rm/unlink invocation found.

    Token parse first (shlex per && / || / | / ; segment); raw-regex
    fallback catches rm hidden in quoted -c payloads / $(...) where the
    tokenizer sees a single opaque argv element.
    """
    import re as _re
    seen = []
    for seg in (command or "").replace("&&", "\n").replace("||", "\n").replace(
            "|", "\n").split("\n"):
        for s in seg.replace(";", "\n").split("\n"):
            s = s.strip()
            if not s:
                continue
            try:
                toks = shlex.split(s)
            except ValueError:
                toks = s.split()
            for i, t in enumerate(toks):
                if t in ("rm", "unlink"):
                    flags, targets = [], []
                    for a in toks[i + 1:]:
                        if a == "--":
                            continue
                        (flags if a.startswith("-") and a != "-" else targets).append(a)
                    # stop targets at shell operators that survived quoting
                    targets = [x for x in targets
                               if x not in ("&&", "||", "|", ";")]
                    seen.append((flags, targets, f"tokens:{t}"))
    for m in _re.finditer(
            r"\brm\s+((?:-[a-zA-Z]+\s+|--\w[\w-]*\s+)*)(\S+)", command or ""):
        flags = (m.group(1) or "").split()
        target = m.group(2).rstrip(";|&")
        if target:
            seen.append((flags, [target], "raw"))
    return seen


def _scoped_other_reason(command: str) -> Optional[str]:
    """Scoped (approval-overridable) refusals for non-rm destroyers.

    - `mv X /dev/null` (deletion by redirection into the void).
    - `shred` / `wipefs` on any target (deliberate unrecoverable wipe).
    - `dd … of=<regular-file>` (block overwrite of a named file;
      device targets stay HARD via the existing device rules).
    """
    import re as _re
    text = command or ""
    if _re.search(r"\bmv\s+\S[\s\S]*?\s+/dev/null(\s|$|[;|&])", text):
        return ("scoped: mv to /dev/null destroys data — approval required")
    for m in _re.finditer(r"\b(shred|wipefs)\b([^;|&\n]*)", text):
        if (m.group(2) or "").strip():
            return (f"scoped: {m.group(1)} destroys data — approval required")
    for m in _re.finditer(r"\bdd\s+([^;|&\n]*)", text, flags=_re.IGNORECASE):
        args = m.group(1) or ""
        om = _re.search(r"\bof=(\S+)", args)
        if om:
            dest = om.group(1)
            dl = dest.lower()
            if dl in ("/dev/null", "/dev/stdout", "/dev/stderr"):
                continue
            if dl.startswith("/dev/"):
                continue  # hard device rules own these
            return (f"scoped: dd overwrites {dest!r} — approval required")
    return None


def refusal_overridable(reason: str) -> bool:
    """True iff a refusal reason may be overridden by a fresh single-use
    approval bound to the exact command (policy-engine consume).

    HARD (never — even approved, run it in your own terminal):
    filesystem roots `/` and `/*`, system/credential/device paths,
    kernel-FS writes, privesc, fork bombs, mkfs, container escapes,
    setuid games, sudo-when-disabled.
    SCOPED (operator sees the exact command and decides): everything
    workspace-scoping — "scoped:" reasons, absolute-outside-workspace,
    ~-expansion, ambiguous ./.., and non-root destructive-rm targets
    (including bare `*` globs).
    """
    r = (reason or "")
    if r.startswith("scoped:"):
        return True
    # Roots stay hard; every other destructive-rm target is scoped.
    # (AST formats as "destructive rm target: /"; token check quotes it.)
    if "destructive rm target" in r or "filesystem root" in r:
        return not (r.rstrip().endswith((": /", ": /*"))
                    or "'/'" in r or "'/*'" in r)
    if "outside the allowed working directory" in r:
        return True
    if "expands outside" in r:
        return True
    if "ambiguous at filesystem root" in r:
        return True
    return False


def _resolve_cwd() -> Tuple[str, bool, str]:
    """Shared cwd resolution for run_command/async (cwd, explicit, note)."""
    return _effective_workspace()


def verify_approval(approval: object, command: str) -> bool:
    """Check a fresh single-use approval bound to the exact command.

    ``approval`` is {"nonce": ..., "command": ...} as threaded by the
    agent loop after an explicit operator approve. Verification consumes
    the nonce (replay fails) and requires exact command equality
    (changed targets after approval fail). Any failure → False, and the
    caller must refuse (fail-closed). Never raises.
    """
    try:
        if not isinstance(approval, dict):
            return False
        nonce = str(approval.get("nonce") or "")
        if not nonce:
            return False
        from core.policy_engine import get_policy_engine
        return bool(get_policy_engine().consume(nonce, str(command or "")))
    except Exception:
        logger.exception("bash_tool: approval verification failed")
        return False


def _refused(command: str, reason: str, started: float) -> Dict[str, object]:
    return {"command": command, "stdout": "",
            "stderr": f"refused: {reason}",
            "returncode": 126, "duration": round(time.monotonic() - started, 3),
            "timed_out": False}


def truncate_output(text: str) -> str:
    """Cap captured output to ``MAX_OUTPUT`` chars, appending a marker."""
    text = text or ""
    if len(text) <= MAX_OUTPUT:
        return text
    return text[:MAX_OUTPUT] + TRUNCATE_MARKER


def run_command(command: str, timeout: int = DEFAULT_TIMEOUT,
                session_id: Optional[str] = None,
                approval: Optional[Dict[str, object]] = None
                ) -> Dict[str, object]:
    """Execute ``command`` in bash and return ``{"stdout", "stderr", "returncode"}``.

    Args:
        command:  The shell command string to execute.
        timeout:  Hard wall-clock limit in seconds (defaults to 30s).
        session_id: Optional session id. When set and GENIO_SANDBOX_MODE=container,
            the command is routed through the per-session container instead of a
            local subprocess.
        approval: Optional {"nonce": ..., "command": ...} from an explicit
            operator approve. Overrides SCOPED refusals only (workspace
            scoping); HARD refusals stand. Verified single-use against the
            exact command (policy-engine consume) — replay or altered
            command fails closed.

    Returns:
        dict with keys:
            command, stdout, stderr, returncode, duration, timed_out
    """
    command = command.strip()
    if not command:
        return {"command": command, "stdout": "", "stderr": "empty command",
                "returncode": -1, "duration": 0.0, "timed_out": False}

    started = time.monotonic()
    cwd, explicit, ws_note = _resolve_cwd()

    def _overridden(reason: str) -> bool:
        # Presenting a valid approval retires the nonce even when the
        # underlying refusal is HARD (use-it-or-lose-it: no replay, no
        # orphaned live approvals). Only SCOPED refusals may execute.
        verified = verify_approval(approval, command)
        if verified and refusal_overridable(reason):
            logger.info("bash_tool: scoped refusal overridden by approval "
                        "(%.8s…): %s", (approval or {}).get("nonce", "")
                        if isinstance(approval, dict) else "", reason)
            return True
        return False

    danger = is_dangerous(command, (cwd, explicit, ws_note))
    if danger and not _overridden(danger):
        return _refused(command, danger, started)

    # Container sandboxing (Phase 5) — route per-session when enabled.
    # Phase 6 : en strict, exec_in_container refuse fermé (SANDBOX_UNAVAILABLE)
    # si le conteneur manque — jamais de repli hôte (voir session_container).
    if session_id and os.getenv("GENIO_SANDBOX_MODE", "").strip().lower() == "container":
        try:
            from genio_server.tools.session_container import exec_in_container
            return exec_in_container(session_id, command, timeout, approval=approval)
        except Exception as exc:
            return {"command": command, "stdout": "", "stderr": str(exc),
                    "returncode": 127, "duration": 0.0, "timed_out": False}

    cmd = ["/bin/bash", "-lc", command] if os.name == "posix" else command
    # Execution cwd = resolved workspace (GENIO_WORKSPACE when valid,
    # else server cwd). Invalid GENIO_WORKSPACE never silently broadens:
    # destructive commands were already refused above with the warning.
    _cwd = cwd
    # Phase 17 : Popen enregistré → halt() préemptif le termine en vol.
    from genio_server.tools.safety import SAFETY as _SAFETY17
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=_cwd,
        )
        key = _SAFETY17.register_proc(proc)
        try:
            out, err = proc.communicate(timeout=timeout)
        finally:
            _SAFETY17.unregister_proc(key)
        return _result(command, out, err, proc.returncode, started, False)
    except subprocess.TimeoutExpired:
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
                            session_id: Optional[str] = None,
                            approval: Optional[Dict[str, object]] = None
                            ) -> Dict[str, object]:
    """Async non-blocking variant of :func:`run_command` (Phase 1 v2.1).

    Uses ``asyncio.create_subprocess_exec`` so a long-running bash command
    never blocks the harness event loop (WebSocket telemetry, kill handling
    and SSE stay responsive). Semantics otherwise identical to run_command,
    including workspace scoping and approval override.
    """
    command = command.strip()
    if not command:
        return {"command": command, "stdout": "", "stderr": "empty command",
                "returncode": -1, "duration": 0.0, "timed_out": False}

    started = time.monotonic()
    cwd, explicit, ws_note = _resolve_cwd()

    def _overridden(reason: str) -> bool:
        verified = verify_approval(approval, command)
        return bool(verified and refusal_overridable(reason))

    danger = is_dangerous(command, (cwd, explicit, ws_note))
    if danger and not _overridden(danger):
        return _refused(command, danger, started)

    # Container sandboxing (Phase 5) — route per-session when enabled.
    # Phase 6 : idem async (fail-closed dans session_container).
    if session_id and os.getenv("GENIO_SANDBOX_MODE", "").strip().lower() == "container":
        try:
            from genio_server.tools.session_container import async_exec_in_container
            return await async_exec_in_container(session_id, command, timeout, approval=approval)
        except Exception as exc:
            return {"command": command, "stdout": "", "stderr": str(exc),
                    "returncode": 127, "duration": 0.0, "timed_out": False}

    cmd = ["/bin/bash", "-lc", command] if os.name == "posix" else ["/bin/sh", "-c", command]
    # Phase 17 : enregistré → halt() préemptif le termine en vol.
    # cwd = resolved workspace (parité avec run_command).
    from genio_server.tools.safety import SAFETY as _SAFETY17A
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        key = _SAFETY17A.register_proc(proc)
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout,
            )
        finally:
            _SAFETY17A.unregister_proc(key)
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
