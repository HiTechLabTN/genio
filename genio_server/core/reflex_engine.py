"""System 1 Reflex Engine — bypass LLM inference for known tasks.

Phase 2 v2.1: deterministic, sub-100ms fast-path execution of high-frequency
system commands and known error resolutions, so the ReAct loop never needs to
call Ollama for repetitive work. Successful multi-step trajectories are
serialized as parameterized *skills* and replayed via the fast path on future
identical/similar prompts.

Design
------
* ``REFLEX_PATTERNS``: an ordered list of high-frequency intent handlers, each
  with a compiled regex + a deterministic sandboxed handler (bash/psutil).
* ``AUTO_FIXES``: known fatal stderr patterns mapped to a container command
  (e.g. ``ModuleNotFoundError`` -> ``pip install <mod>``) resolved before LLM
  reflection.
* Persistence: ``state/skills_library/patterns.json`` holds compiled skills
  whose ``prompt_re`` matches future prompts; a skill is just a reusable
  parameterized command sequence.

Gating: ``GENIO_REFLEX_FASTPATH=1`` enables the fast path. Default on.
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Dict, List, Optional

from genio_server.tools.bash_tool import MAX_OUTPUT, TRUNCATE_MARKER

SKILLS_DIR = Path(__file__).resolve().parents[2] / "state" / "skills_library"
PATTERNS_FILE = SKILLS_DIR / "patterns.json"


def _fastpath_enabled() -> bool:
    return os.getenv("GENIO_REFLEX_FASTPATH", "1").strip().lower() not in ("0", "false", "no")


def _truncate(s: str) -> str:
    s = s or ""
    if len(s) <= MAX_OUTPUT:
        return s
    return s[:MAX_OUTPUT] + TRUNCATE_MARKER


def _invoke_bash(command: str, session_id: Optional[str] = None) -> Dict[str, object]:
    """Route bash through the canonical tool entrypoint so is_dangerous()
    and GENIO_SANDBOX_MODE are always enforced (Phase A fix)."""
    # Local import to avoid circular import at module load time.
    from genio_server.tools import invoke as _invoke
    res = _invoke("bash", command, session_id=session_id)
    # Tag as reflex for downstream accounting; preserve original returncode
    # so the caller sees refuse (126) vs success (0) etc.
    if isinstance(res, dict):
        res = dict(res)  # shallow copy
        res["reflex"] = True
    return res


# --------------------------------------------------------------------------- #
# High-frequency intent handlers (ordered; first regex match wins)
# --------------------------------------------------------------------------- #
_R = re.compile
_REFLEX_PATTERNS: List[Dict[str, object]] = [
    {
        "name": "system_health",
        "prompt_re": _R(r"(system\s*health|check\s*(the\s*)?system|resource\s*usage|"
                        r"how\s*(is|are)\s*(cpu|ram|memory|disk)|uptime|load\s*average)",
                        re.I),
        "handler": "bash",
        "command": "uptime && echo '---' && free -h && echo '---' && df -h / && "
                   "echo '---' && nproc",
    },
    {
        "name": "list_dir",
        "prompt_re": _R(r"(list|show|see).*(files|dir|directory|content).*(in|of)|"
                        r"\bls\b.*\b(in|of)\b|what.*in\s+(the\s+)?(dir|folder)|"
                        r"show\s+(me\s+)?(the\s+)?(files|working\s+dir)|pwd"),
        "handler": "bash",
        "command": "pwd && ls -la",
    },
    {
        "name": "read_file",
        "prompt_re": _R(r"(cat|read|show|print|dump|view).*(file|config|log|code|"
                        r"content|::)|^(cat|read|show)\s+[\\w./_-]+$|show\s+(me\s+)?.*\bfile\b"),
        "handler": "bash",
        "command": "cat <file>",  # <file> substituted by _substitute_file
    },
    {
        "name": "process_status",
        "prompt_re": _R(r"(show|list|check|see).*(process|ps|running\s+process)|"
                        r"\bprocesses?\b|\bps\b"),
        "handler": "bash",
        "command": "ps aux --sort=-%mem | head -20",
    },
    {
        "name": "kill_process",
        "prompt_re": _R(r"(kill|stop|terminate).*(process|pid|service).*[0-9]+|"
                        r"kill\s+-?\d+"),
        "handler": "bash",
        "command": "kill <pid>",  # <pid> substituted by _substitute_pid
    },
    {
        "name": "git_status",
        "prompt_re": _R(r"git\s+status|status\s*(of\s*)?(the\s*)?(repo|git)|"
                        r"what.*(changed|modified)"),
        "handler": "bash",
        "command": "git status --short && git log --oneline -5",
    },
    {
        "name": "python_version",
        "prompt_re": _R(r"(python|py).*(version|--version)|what\s+python\s*", re.I),
        "handler": "bash",
        "command": "python3 --version",
    },
]

# --------------------------------------------------------------------------- #
# Known fatal stderr patterns -> deterministic command (before LLM reflection)
# --------------------------------------------------------------------------- #
_AUTO_FIXES: List[Dict[str, object]] = [
    {
        "name": "module_not_found",
        "fix_re": re.compile(r"ModuleNotFoundError:\s*No module named ['\"]([\w._-]+)['\"]"),
        "command": lambda m: f" pip install {m}",
        "install_cmd": lambda m: f"pip install {m}",
    },
    {
        "name": "command_not_found",
        "fix_re": re.compile(r"/bin/bash:?\s*([\w-]+):\s*command not found"),
        "command": lambda m: f" command '{m}' not found — check available tools",
    },
    {
        "name": "permission_denied",
        "fix_re": re.compile(r"Permission denied"),
        "command": lambda _m: " check file permissions / cannot write there",
    },
]


def _substitute(command: str, placeholders: Dict[str, str]) -> str:
    for key, val in placeholders.items():
        command = command.replace(f"<{key}>", val)
    return command


class ReflexEngine:
    """Deterministic fast-path matcher + skill compiler (System 1)."""

    def __init__(self, skills_dir: Path = SKILLS_DIR):
        self.skills_dir = skills_dir
        self._patterns_file = skills_dir / "patterns.json"
        self._skills: List[Dict[str, object]] = []
        self._load_skills()

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #
    def _load_skills(self) -> None:
        try:
            if self._patterns_file.exists():
                data = json.loads(self._patterns_file.read_text())
                if isinstance(data, list):
                    self._skills = [s for s in data if isinstance(s, dict)]
        except Exception:
            self._skills = []

    def _save_skills(self) -> None:
        try:
            self.skills_dir.mkdir(parents=True, exist_ok=True)
            self._patterns_file.write_text(
                json.dumps(self._skills, ensure_ascii=False, indent=2)
            )
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # Fast-path matching
    # ------------------------------------------------------------------ #
    def match(self, prompt: str, session_id: Optional[str] = None) -> Optional[Dict[str, object]]:
        """Return a fast-path handler dict if ``prompt`` matches a known
        high-frequency intent, else None.  All execution is routed via
        ``invoke("bash", ...)`` so ``is_dangerous()`` + sandbox always apply
        (Phase A — Q1: even read-only patterns are gated).

        ``session_id`` is forwarded to ``invoke`` so per-session container
        isolation (``GENIO_SANDBOX_MODE=container``) is honoured.
        """
        if not _fastpath_enabled() or not prompt or not prompt.strip():
            return None
        started = time.monotonic()
        # 1) compiled skills first (most specific)
        for skill in self._skills:
            pr = skill.get("prompt_re")
            if pr and re.search(pr, prompt, re.I):
                return self._exec_skill(skill, prompt, started, session_id=session_id)
        # 2) built-in high-frequency intents
        for pattern in _REFLEX_PATTERNS:
            if (pattern["prompt_re"]).search(prompt):
                return self._exec_pattern(pattern, prompt, started, session_id=session_id)
        return None

    def _exec_pattern(self, pattern: Dict[str, object], prompt: str,
                      started: float, session_id: Optional[str] = None) -> Dict[str, object]:
        command = str(pattern.get("command") or "")
        placeholders = {}
        if "read_file" in str(pattern.get("name")):
            m = re.search(r"(?:cat|read|show)\s+([\w./_~-]+(?:\.\w+)*)", prompt)
            if m:
                placeholders["file"] = m.group(1)
        if "kill_process" in str(pattern.get("name")):
            m = re.search(r"(?:kill|stop|terminate)[^\d]*(\d+)", prompt)
            if m:
                placeholders["pid"] = m.group(1)
        command = _substitute(command, placeholders)
        return self._finalize(pattern, command, started, session_id=session_id)

    def _exec_skill(self, skill: Dict[str, object], prompt: str,
                    started: float, session_id: Optional[str] = None) -> Dict[str, object]:
        """Executes a compiled skill's parameterized command sequence via
        the canonical bash tool so every step is gated by ``is_dangerous``
        and the configured sandbox."""
        steps = skill.get("steps") or []
        outputs: List[str] = []
        # Track if any step was refused/blocked — propagate worst returncode.
        worst_rc = 0
        worst_err = ""
        for step in steps:
            cmd = str(step.get("command") or "")
            cmd = self._substitute_prompt_params(cmd, prompt, skill)
            res = _invoke_bash(cmd, session_id=session_id)
            rc = int(res.get("returncode", -1)) if isinstance(res.get("returncode"), int) or str(res.get("returncode")).lstrip("-").isdigit() else -1
            # is_dangerous refusal (126) or explicit error must surface
            if rc != 0:
                if worst_rc == 0:
                    worst_rc = rc
                    worst_err = str(res.get("stderr") or res.get("error") or "")
                outputs.append(f"$ {cmd}\n[REFUSED] {worst_err or res.get('stdout','')}")
                # Do NOT continue executing remaining steps after a refusal — fail-safe.
                break
            outputs.append(f"$ {cmd}\n{str(res.get('stdout', '')).rstrip()}")
        body = "\n".join(outputs)
        # If any step was refused, surface that refusal instead of fake success.
        if worst_rc != 0:
            return {
                "type": "tool_result",
                "result": {
                    "command": skill.get("name", "skill"),
                    "stdout": _truncate(body),
                    "stderr": worst_err,
                    "returncode": worst_rc,
                    "duration": round(time.monotonic() - started, 3),
                    "reflex": True,
                    "skill": skill.get("name"),
                },
            }
        return {
            "type": "tool_result",
            "result": {
                "command": skill.get("name", "skill"),
                "stdout": _truncate(body),
                "stderr": "",
                "returncode": 0,
                "duration": round(time.monotonic() - started, 3),
                "reflex": True,
                "skill": skill.get("name"),
            },
        }

    @staticmethod
    def _substitute_prompt_params(cmd: str, prompt: str, skill: Dict[str, object]):
        params = skill.get("params") or []
        for p in params:
            # try to find <p>=<value> in prompt
            m = re.search(rf"{re.escape(str(p))}\s*[:=]\s*([\w./_-]+)", prompt)
            if m:
                cmd = cmd.replace(f"<{p}>", m.group(1))
        return cmd

    @staticmethod
    def _finalize(pattern: Dict[str, object], command: str,
                  started: float, session_id: Optional[str] = None) -> Dict[str, object]:
        res = _invoke_bash(command, session_id=session_id)
        return {
            "type": "tool_result",
            "result": {
                "command": command,
                "stdout": res.get("stdout", ""),
                "stderr": res.get("stderr", ""),
                "returncode": res.get("returncode", -1),
                "duration": round(time.monotonic() - started, 3),
                "reflex": True,
                "handler": pattern.get("name"),
            },
        }

    # ------------------------------------------------------------------ #
    # Deterministic auto-fixes (stderr -> command before LLM reflection)
    # ------------------------------------------------------------------ #
    def auto_fix(self, stderr: str, session_id: Optional[str] = None) -> Optional[str]:
        """Map a known fatal stderr pattern to a deterministic command."""
        if not stderr or not _fastpath_enabled():
            return None
        for fix in _AUTO_FIXES:
            m = (fix["fix_re"]).search(stderr)
            if m:
                installer = fix.get("install_cmd")
                if installer:
                    return installer(m.group(1))
                return fix["command"](m.group(1))
        return None

    # ------------------------------------------------------------------ #
    # Trajectory compiler
    # ------------------------------------------------------------------ #
    def compile_skill(self, name: str, prompt: str, trajectory: List[Dict[str, object]],
                      params: Optional[List[str]] = None) -> bool:
        """Serialize a successful >1 tool-turn trajectory into a reusable skill.

        ``trajectory`` is a list of ``{"command": ..., "result": {...}}`` from a
        completed autonomous run. Stores it in ``state/skills_library/patterns.json``
        keyed by a prompt regex derived from the original prompt.
        """
        if not trajectory or len(trajectory) < 2:
            return False
        steps = []
        for ev in trajectory:
            command = ev.get("command")
            if not command:
                continue
            steps.append({"command": str(command)})
        if not steps:
            return False
        key_tokens = re.findall(r"[\w]{3,}", prompt.lower())
        # Q2 strict: pick 3 most discriminative tokens (longest) and require ALL.
        # Mitigates single-word false positives like "please" triggering any skill.
        # Désactivable via GENIO_REFLEX_STRICT_MATCH=0 (Phase A routing stays fail-safe).
        strict = os.getenv("GENIO_REFLEX_STRICT_MATCH", "1").strip().lower() not in ("0", "false", "no")
        if strict and key_tokens:
            unique = list(dict.fromkeys(key_tokens))
            # Sort by length desc, then alphabetically for determinism
            unique_sorted = sorted(unique, key=lambda w: (-len(w), w))
            # Filter very common stopwords when we have enough candidates
            _stop = {"the","and","for","are","you","please","stp","bonjour","hello","with","this","that","have","from"}
            # Keep stopwords only if they are among the longest? Prefer non-stop.
            candidates = [w for w in unique_sorted if w not in _stop]
            if len(candidates) < 3:
                return False
            top = candidates[:3]
            if len(top) >= 2:
                # Build lookahead regex requiring all top keywords in any order
                parts = "".join(rf"(?=.*\b{re.escape(w)}\b)" for w in top)
                prompt_re = parts + r".*"
        else:
            keyword = " ".join(dict.fromkeys(key_tokens))[:80] if key_tokens else name
            prompt_re = rf"\b{re.escape(keyword.split()[0])}\b" if keyword else None
        skill = {
            "name": name,
            "description": f"compiled from prompt: {prompt[:100]}",
            "prompt_re": prompt_re,
            "params": params or [],
            "steps": steps,
            "compiled_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        self._skills.append(skill)
        self._save_skills()
        return True


# Singleton so the agent loop shares one compiled-skill registry.
_reflex_engine: Optional[ReflexEngine] = None


def get_reflex_engine() -> ReflexEngine:
    global _reflex_engine
    if _reflex_engine is None:
        _reflex_engine = ReflexEngine()
    return _reflex_engine
