"""Genio ReAct dispatcher — async reasoning/acting loop over local Ollama.

The loop is model-agnostic: it talks to an Ollama instance (``gemma4:12b``)
over HTTP, parses the assistant's reply for a JSON tool-call, runs the tool
through :mod:`genio_server.tools`, then feeds the command output back to the
model for evaluation. Plain-text assistant replies are surfaced as
reasoning/final answers.

Design notes
------------
* Async throughout (``httpx.AsyncClient``) so the Textual TUI can drive the
  loop without blocking its event loop.
* The loop is a generator of structured *events*::

      {"type": "thought",  "text": "..."}        # assistant narration
      {"type": "tool_call","command": "..."}     # parsed JSON tool call
      {"type": "tool_result","result": {...}}    # bash_tool result
      {"type": "answer",   "text": "..."}        # final turn (no tool call)
      {"type": "error",    "message": "..."}

* Bounded iterations (``max_iterations``) so a misbehaving model cannot loop
  forever.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import threading
import time
from typing import TYPE_CHECKING, AsyncIterator, Callable, Dict, List, Optional, Tuple

import httpx

from genio_server.tools import invoke, tool_specs

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from genio_server.core.session_store import SessionStore

DEFAULT_MODEL = os.environ.get("GENIO_MODEL", "gemma4:12b")
OLLAMA_URL = os.environ.get("GENIO_OLLAMA_URL", "http://127.0.0.1:11434")
DEFAULT_MAX_ITERATIONS = int(os.environ.get("GENIO_MAX_ITERATIONS", "5"))
DEFAULT_MODE = os.environ.get("GENIO_MODE", "autonomous")
STEP_TIMEOUT = 120  # seconds per model request

# Phase 3 — budgets d'exécution (plafonds infranchissables, configurables).
# turn_budget_seconds : durée globale max d'un tour utilisateur.
# tool_timeout_seconds : durée max d'UN appel d'outil individuel.
TURN_BUDGET_SECONDS = float(os.environ.get("GENIO_TURN_BUDGET", "600"))
TOOL_TIMEOUT_SECONDS = float(os.environ.get("GENIO_TOOL_TIMEOUT", "120"))
# Loop/stuck detection : même empreinte outil+args >2 fois de suite, ou même
# outil en échec >2 fois → arrêt avec statut explicite (pas de boucle infinie).
MAX_SAME_CALL_REPEATS = 2
MAX_TOOL_ERROR_RETRIES = 2

# Safety: cap any single tool output so giant dumps (e.g. ``ls -R``) can never
# overflow the LLM context window and crash the loop into a premature terminal
# state. When the cap is hit a marker is appended so the model knows the
# result was truncated rather than complete.
MAX_TOOL_OUTPUT = 3000
TRUNCATE_MARKER = "\n... [Output truncated to preserve context window]"


def command_fingerprint(tool: str, command: object) -> str:
    """Empreinte normalisée d'un appel (outil + args canoniques).

    Deux appels identiques → même empreinte (détection de boucle).
    JSON normalisé (clés triées) pour éviter les faux négatifs d'espaces.
    """
    import hashlib
    import json as _json
    if isinstance(command, (dict, list)):
        try:
            body = _json.dumps(command, sort_keys=True, ensure_ascii=False)
        except Exception:
            body = str(command)
    else:
        body = re.sub(r"\s+", " ", str(command or "")).strip()
    return hashlib.sha1(f"{tool}\n{body}".encode("utf-8")).hexdigest()[:16]


class LoopGuard:
    """Détecteur de répétition + budget de retry (pur, testable, sans I/O).

    - même empreinte > MAX_SAME_CALL_REPEATS fois de suite → "LOOP_DETECTED"
    - même outil en échec > MAX_TOOL_ERROR_RETRIES fois (cumulé sur le tour)
      → "RETRY_EXHAUSTED"
    """

    def __init__(self) -> None:
        self._last_fp: Optional[str] = None
        self._run_len = 0
        self._tool_errors: Dict[str, int] = {}

    def would_loop(self, fingerprint: str) -> bool:
        """True si cet appel serait la 3e répétition identique de suite.

        Appelé AVANT l'exécution pour ne jamais lancer le 3e doublon.
        """
        return (fingerprint == self._last_fp
                and self._run_len >= MAX_SAME_CALL_REPEATS)

    def note_call(self, fingerprint: str, tool: str,
                  failed: bool) -> Optional[str]:
        if fingerprint == self._last_fp:
            self._run_len += 1
        else:
            self._last_fp = fingerprint
            self._run_len = 1
        if self._run_len > MAX_SAME_CALL_REPEATS:
            return "LOOP_DETECTED"
        if failed:
            self._tool_errors[tool] = self._tool_errors.get(tool, 0) + 1
            if self._tool_errors[tool] > MAX_TOOL_ERROR_RETRIES:
                return "RETRY_EXHAUSTED"
        return None

    @property
    def repeats(self) -> int:
        return self._run_len

SYSTEM_PROMPT = (
    "أنت جينيو، المهندس المستقل للذكاء الاصطناعي في HiTech Lab. "
    "قاعدة حرجة: يجب أن تتواصل مع المستخدم حصرياً بالدارجة التونسية "
    "بحروف عربية فقط (مثال: عسلامة! أنا جينيو...). ممنوع منعاً باتاً العربيزي/الفرانكو "
    "(mta3, n3awnek, t7eb, 3liha, chnowa) — كل الكلمات تُكتب بحروف عربية. "
    "تستطيع تنفيذ الأوامر، التصفح بلا واجهة، التحكم في سطح المكتب واستدعاء APIs. "
    "أخرج استدعاءات الأدوات بصيغة JSON."
)

# --- Phase 2 v2.1 (Partie C — persona souveraine, source unique de vérité) ---
# GENIO_SOVEREIGN_SYSTEM_PROMPT is THE canonical persona. Every gateway/user
# prompt path imports this and never re-declares the persona (see
# adaptive_gateway.py), so the sovereign Darija rules can't drift.
GENIO_SOVEREIGN_SYSTEM_PROMPT = SYSTEM_PROMPT

# Reasoning / leak markers that MUST never reach the client. The Darija persona
# never labels a step "Thinking…" or "Genius"; its narration is Darija narration
# (type "thought"), not a raw reasoning summary.
THINKING_MARKERS = (
    "thinking", "thought:", "reasoning:", "reason:", "genius:", "genie:",
    "here's my reasoning", "let me think", "rationale:",
)


LATIN_RUN = re.compile(r"[A-Za-z]")
ARAB_RUN = re.compile(r"[\u0600-\u06FF]")

# Lexique déterministe : boilerplate anglais qui fuit parfois du modèle local
# (phrases d'identité/service) → équivalent Darija en script arabe. Appliqué
# AVANT le filtre de dominance latine, dans l'ordre (multi-mots d'abord).
EN_TO_DARIJA = (
    (r"\bat your service\b", "في خدمتك"),
    (r"\bhere(?:'|’)s my reasoning\b", ""),
    (r"\blet me think\b", ""),
    (r"\bchain-of-thought\b", ""),
    (r"\bengineer\b", "مهندس"),
    (r"\bservice\b", "خدمة"),
    (r"\bautonomous\b", "مستقل"),
    (r"\bintelligence\b", "ذكاء"),
    (r"\bartificial\b", "اصطناعي"),
    (r"\btechnolog(?:y|ies)\b", "تكنولوجيا"),
    (r"\bthanks?\b", "يعيشك"),
    (r"\bhello\b", "عسلامة"),
    (r"\bwith\b", "مع"),
    (r"\bfrom\b", "من"),
    (r"\byour\b", "متاعك"),
    (r"\band\b", "و"),
    (r"\bfor\b", "على"),
    (r"\bthe\b", "ال"),
    (r"\bat\b", "في"),
    (r"\ban?\b", ""),
    (r"\bAI\b", "الذكاء الاصطناعي"),
    (r"\bAPIs\b", "الواجهات البرمجية"),
    (r"\bAPI\b", "الواجهة البرمجية"),
    (r"\bJSON\b", "جيسون"),
)


def sanitize_for_client(text: str) -> str:
    """Partie C anti-leak : force Darija arabe 100% + strip tout token de
    raisonnement/identité (Thinking…/Genius) avant émission au client."""
    if not text:
        return text or ""
    kept: List[str] = []
    for ln in (text or "").splitlines():
        s = ln.strip()
        low = s.lower()
        if low.startswith(THINKING_MARKERS):
            continue  # drop raw reasoning headers
        kept.append(ln)
    text = "\n".join(kept)
    # Identity leak : latin "Genius"/"Genie" → جينيو ; "Genio the" → جينيو
    text = re.sub(r"\b(?:Genius|Genie|Genio)\b", "جينيو", text, flags=re.IGNORECASE)
    # HiTech Lab persona token → translittération arabe (jamais latin) :
    # "HiTech Lab"/"HiTechLab"/"HiTech" → هايتيك لاب ; "Genio the" déjà couvert.
    # "عسلامة! أنا جينيو سرك في هايتيك لاب" reste 100% arabe sans fuite latin.
    text = re.sub(r"\bHiTech\s*Lab\b|\bHiTechLab\b|\bHiTech\b", "هايتيك لاب", text,
                  flags=re.IGNORECASE)
    # Boilerplate anglais résiduel → Darija arabe (insensible à la casse).
    for pat, rep in EN_TO_DARIJA:
        text = re.sub(pat, rep, text, flags=re.IGNORECASE)
    # Dernière garde : toute ligne restée à dominante latine (>50% lettres
    # latines) est une fuite de raisonnement/boilerplate, pas du Darija —
    # on la retire au lieu de la laisser fuir au client.
    final: List[str] = []
    for ln in text.splitlines():
        nl = len(LATIN_RUN.findall(ln))
        na = len(ARAB_RUN.findall(ln))
        if nl + na > 0 and nl > na:
            continue
        final.append(ln)
    text = "\n".join(final)
    # Normalise espaces multiples laissés par les suppressions.
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()

AUTONOMY_MODE = (
    "\n"
    "FULLY AUTONOMOUS MODE:\n"
    "- You are an autonomous orchestrator. Take direct action with the tools; "
    "NEVER ask the user for permission or wait for confirmation.\n"
    "- Prefer concrete actions over explanations. Keep narrations short (2-3 "
    "sentences) and always in Tunisian Darja.\n"
    "- Chain as many tool calls as needed (browser, computer, api, bash) to "
    "reach the goal autonomously. Inspect outputs, adapt, and continue.\n"
    "- Stop only when the objective is met; then reply to the user in Darja "
    "with a clear, complete summary of what you did and the result.\n"
)

REACT_INSTRUCTIONS = (
    f"{SYSTEM_PROMPT}\n"
    "\n"
    "Work in a Reason+Act loop:\n"
    "1. Think in plain text — explain your current step.\n"
    "2. When you want to run a command, reply with ONLY a single line of JSON: "
    "{\"tool\": \"<tool>\", \"command\": \"<payload>\"} — nothing else.\n"
    "3. The environment replies with the tool output and status.\n"
    "4. Use that output to decide the next step. When the task is complete, "
    "answer in plain text WITHOUT any JSON.\n"
    "\n"
    "Example of a correct tool turn (nothing before or after the JSON):\n"
    "{\"tool\": \"bash\", \"command\": \"pwd && git status --short\"}\n"
    "\n"
    "Available tools and their payloads:\n"
    + tool_specs()
    + "\n"
    "\n"
    "Rules:\n"
    "- Never invent output you have not observed.\n"
    "- Keep tool calls short and focused; no interactive prompts.\n"
    "- Guard against destructive commands.\n"
    "- Start every tool turn with exactly the JSON object above (no markdown "
    "fences).\n"
    "- For browser extracts, work from the returned DOM text.\n"
    "- For computer use, prefer coordinates/selectors you know exist.\n"
    "\n"
    "LANGUAGE (strict — حروف عربية فقط):\n"
    "- كل رسالة ترسلها للمستخدم — تفكيرك قبل الأداة وجوابك النهائي — يجب أن تُكتب "
    "بالدارجة التونسية بحروف عربية فقط. مثال: عسلامة! أنا جينيو...\n"
    "- ممنوع تماماً Arabizi/Franco-Arabe (mta3, n3awnek, t7eb, 3liha, chnowa) أو حروف لاتينية. "
    "اكتب كل كلمة بالعربية: متاع، نعاونك، تحب، عليها، شنوّا.\n"
    "- ناتج الأدوات قد يصل بأي لغة — انسخه كما هو لكن علّق عليه بالدارجة بحروف عربية."
)


def _session_context_block(memory=None) -> str:
    """Durable project/user facts for the interactive agent (NOT editorial
    rules, which belong to the content pipeline). Best-effort: if the root
    `core.memory_engine` isn't importable, degrade to an empty block."""
    try:
        if memory is None:
            from core.memory_engine import get_memory
            memory = get_memory()
        text = memory.context_text()
    except Exception:
        text = ""
    if not text:
        return ""
    return (
        "\n\nSESSION CONTEXT (durable facts about the project/user, treat as "
        "authoritative ground truth):\n" + text
    )


def build_instructions(mode: str = DEFAULT_MODE, memory=None) -> str:
    # Phase 11 : canaux typés — jamais de contexte indifférencié.
    from genio_server.core.trust import Trust, label_block
    base = label_block(Trust.SYSTEM, REACT_INSTRUCTIONS)
    mem_block = _session_context_block(memory)
    if mem_block:
        base += "\n" + label_block(Trust.MEMORY, mem_block)
    if mode == "autonomous":
        base += "\n" + label_block(Trust.POLICY, AUTONOMY_MODE)
    return base


class OllamaConnectionError(RuntimeError):
    pass


class ToolCallParseError(ValueError):
    pass


def _extract_tool_call(text: str) -> Optional[Dict[str, object]]:
    """Return ``{"tool": ..., "command": ...}`` if the text asks for a tool."""
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?\s*|\s*```$", "", candidate)
    pattern = re.compile(r"\{.*\}", re.S)
    match = pattern.search(candidate)
    if not match:
        return None
    try:
        obj = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict) or "tool" not in obj:
        return None
    if "command" not in obj and "payload" not in obj:
        return None
    command = obj.get("command") or obj.get("payload") or ""
    if isinstance(command, str):
        command = command.strip()
    # Keep dict/list commands as-is (nested JSON) so payloads are not mangled
    # into Python reprs ("{'action': 'x'}") that tools can't JSON-parse.
    return {"tool": str(obj["tool"]).strip(), "command": command}


def _split_narration(text: str) -> Tuple[str, Optional[Dict[str, object]]]:
    """Split an assistant reply into narration text and an optional tool call."""
    text = (text or "").strip()
    if not text:
        return "", None
    if text.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
        call = _extract_tool_call(stripped)
        if call:
            return "", call
    call = _extract_tool_call(text)
    if call:
        idx = text.find("{")
        before = text[:idx].strip()
        return before, call
    return text, None


def _last_json(text: str) -> Optional[Dict[str, object]]:
    """Extract a JSON object that may contain a tool call (lenient)."""
    for candidate in (text, re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())):
        call = _extract_tool_call(candidate)
        if call:
            return call
    return None


def truncate_output(text: str, limit: int = MAX_TOOL_OUTPUT) -> str:
    """Cap tool output to ``limit`` chars, appending a truncation marker.

    Prevents oversized command output (e.g. ``ls -R``, huge logs) from
    overflowing the model's context window and corrupting the ReAct loop.
    """
    text = text or ""
    if len(text) <= limit:
        return text
    return text[:limit] + TRUNCATE_MARKER


async def summarize_session_batch(conversation_text: str,
                                  max_chars: int = 600) -> str:
    """Compress an overflow batch of old turns into a short extractive summary.

    Pure local heuristic (first/last lines + a count) so the store has no hard
    dependency on the model being reachable. A model-written summarizer can
    replace the body later without changing the call signature.
    """
    lines = [ln for ln in (conversation_text or "").splitlines() if ln.strip()]
    if not lines:
        return ""
    snippet = "\n".join(lines[:3] + ["…"] + lines[-3:])
    summary = (f"[conversation summary — {len(lines)} turns] "
               f"earlier: {lines[0][:140]} … later: {lines[-1][:140]}")
    return summary[:max_chars]


# Phase 1 v2.1: no-op exit-0 commands (file/touch/mkdir/cat style) that yield no
# meaningful content and should never terminate the loop into idle.
_NOOP_CMDS = ("cat", "touch", "mkdir", "pwd", "cd", "ls", "true", "echo -n", ":")


def _is_noop_command(command: str) -> bool:
    """Return True if the command is a known no-op (file/touch/mkdir/cat style)
    that completes instantly with no observable output worth acting on."""
    cmd = (command or "").strip().lower()
    first = cmd.split()[0] if cmd.split() else ""
    if first in ("cat", "touch", "mkdir", "pwd", "cd", "ls", "true", ":"):
        return True
    return any(cmd.startswith(n) for n in ("echo -n", "printf ''"))


def _is_trivial_success(assistant: str, output: str) -> bool:
    """Return True when the model's narration is short AND the tool body is
    empty or trivial, indicating a step finished without meaningful output."""
    narration = (assistant or "").strip()
    narration_is_short = not narration or len(narration) < 120
    out = (output or "").strip()
    trivial_body = not out or len(out) < 40
    return narration_is_short and trivial_body


def _feedback_for(result: Dict[str, object], assistant: str) -> str:
    """Human/LLM-readable tool feedback for the next model turn.

    Truncates long output and, on a non-zero exit code or tool error, injects
    an explicit self-correction directive so the model retries/repairs instead
    of collapsing the loop into a premature terminal state.
    When GENIO_GENERIC_HEAL is enabled, appends a GenericHealer suggestion.
    """
    def _heal_hint(text: str) -> str:
        if os.getenv("GENIO_GENERIC_HEAL", "1").lower() in ("0", "false", "no"):
            return ""
        try:
            from sandbox.self_healer import GenericHealer
            hint = GenericHealer().inspect_and_heal(text)
            return f"\n\n[HEALER SUGGESTION]: {hint}" if hint else ""
        except Exception:
            return ""

    if not isinstance(result, dict):
        flat = str(result or "(no output)")
        return f"Tool output:\n{truncate_output(flat)}"
    if "returncode" in result:  # bash-style result
        out = truncate_output(str(result.get("stdout") or ""))
        err = truncate_output(str(result.get("stderr") or ""))
        code = result.get("returncode")
        code = int(code) if code is not None else -1
        body = out or err or "(no output)"
        if code == 0:
            # Phase 1 v2.1: loop-chaining enforcement. Exit-0 with trivial
            # file/touch/mkdir/cat output means the step is done — instruct the
            # model to PROCEED to its next pending step rather than terminating
            # prematurely into idle.
            if _is_trivial_success(assistant, out) and _is_noop_command(str(result.get("command") or "")):
                return (
                    f"Tool output (exit code 0):\n{body}\n\n"
                    "This step completed successfully with no meaningful output. "
                    "If your plan has more pending steps, execute the NEXT step "
                    "immediately with another tool call — do not stop or go idle "
                    "until the entire objective is met. Only give a final answer "
                    "once all plan steps are complete."
                )
            return f"Tool output (exit code 0):\n{body}"
        # Self-correction: surface the failure and ask the model to adapt.
        return (
            f"TOOL FAILED (exit code {code}):\n{body}\n\n"
            "The command above did not succeed. Diagnose the error, adjust your "
            "approach and retry until it works — do not give up and do not report "
            "success prematurely. If it is genuinely impossible, explain that in "
            "your final answer." + _heal_hint(body)
        )
    if result.get("error"):
        return (
            f"TOOL FAILED (ERROR): {result['error']}\n\n"
            "The tool raised an error. Inspect it, correct your call and retry; "
            "only stop with a final answer once the task is actually resolved." + _heal_hint(str(result['error']))
        )
    flat = json.dumps(result, ensure_ascii=False)
    return f"Tool output:\n{truncate_output(flat)}"


class AgentLoop:
    """Async ReAct dispatcher bound to a local Ollama instance."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        ollama_url: str = OLLAMA_URL,
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
        step_timeout: float = STEP_TIMEOUT,
        mode: str = DEFAULT_MODE,
        cancel_event: Optional[threading.Event] = None,
        system_prompt: Optional[str] = None,
        session_id: Optional[str] = None,
        store: Optional["SessionStore"] = None,
    ) -> None:
        self.model = model
        self.ollama_url = ollama_url.rstrip("/")
        self.max_iterations = max_iterations
        self.step_timeout = step_timeout
        self.mode = mode
        self.cancel_event = cancel_event
        self.session_id = session_id
        self._store = store
        self.system_prompt = system_prompt or build_instructions(mode)

    def cancelled(self) -> bool:
        return bool(self.cancel_event is not None and self.cancel_event.is_set())

    # -- Phase 3 helpers (synchrones, testables) -------------------------- #
    @staticmethod
    def _known_tools() -> List[str]:
        try:
            from genio_server.core.registries import ToolRegistry
            return ToolRegistry.names()
        except Exception:
            try:
                from genio_server.tools import TOOLS
                return sorted(TOOLS.keys())
            except Exception:
                return []

    @classmethod
    def _tool_known(cls, tool: str) -> bool:
        return bool(tool) and tool in cls._known_tools()

    @staticmethod
    def _sandbox_available() -> bool:
        return os.getenv("GENIO_SANDBOX_MODE", "").strip().lower() == "container"

    @classmethod
    def _capability_check(cls, tool: str) -> Dict[str, str]:
        """Phase 4 : descripteur + décision policy (pur, testable).

        Lookup par NOM seul (le payload du LLM est ignoré) ; hook prêt pour
        le PolicyEngine Phase 5 (REQUIRE_CONFIRMATION → interrupteur à venir).
        """
        try:
            from genio_server.core.registries import (
                CapabilityRegistry, PolicyRegistry)
            desc = CapabilityRegistry.descriptor_of(tool)
            if desc is None:
                return {"tool": tool, "capability": "UNKNOWN",
                        "risk": "CRITICAL", "decision": "DENY",
                        "reason": "DENIED_UNKNOWN_CAPABILITY"}
            decision = PolicyRegistry.decide_tool(
                tool, sandbox_available=cls._sandbox_available())
            return {"tool": tool, "capability": desc.capability,
                    "risk": desc.risk_level, "decision": decision,
                    "requires_confirmation": str(desc.requires_confirmation)}
        except Exception:
            return {"tool": tool, "capability": "UNKNOWN",
                    "risk": "CRITICAL", "decision": "DENY",
                    "reason": "registry-unavailable"}

    @staticmethod
    def _quota_synthesis(
            trajectory: List[Dict[str, object]],
            prefix: str = "[تلخيص مرحلي — quota atteint] ") -> str:
        """Synthèse intermédiaire propre à l'atteinte d'un quota.

        Résume les étapes exécutées (jamais de contenu brut tronqué) pour que
        l'utilisateur voie la progression au lieu d'un mur vide.
        """
        steps = []
        for t in trajectory[-5:]:
            # Ligne à dominante arabe (le sanitizer anti-leak retire les
            # lignes latines) — commandes et sorties restent verbatim.
            cmd = str(t.get("command", ""))[:120]
            res = t.get("result") if isinstance(t.get("result"), dict) else {}
            rc = res.get("returncode", "?")
            out = str(res.get("stdout") or res.get("stderr") or "").strip()
            steps.append(f"• الأمر المنفذ: {cmd} — النتيجة (رمز الخروج {rc}): "
                         f"{out[:160]}".strip())
        body = "\n".join(steps) if steps else "ما بديت حتى خطوة بعد."
        return sanitize_for_client(
            f"{prefix}وقفت بعد {len(trajectory)} خطوات باش ما ندورش في حلقة. "
            f"آخر الخطوات:\n{body}\nقولي كيفاش نكمل.")

    async def _wait_cancel(self):
        """Wait until cancel_event is set — for race with chat."""
        while not self.cancelled():
            await asyncio.sleep(0.05)
        raise asyncio.CancelledError("killed")

    async def _chat(self, client: httpx.AsyncClient,
                    messages: List[Dict[str, str]]) -> Tuple[str, int, float]:
        """POST via ModelRouter with true cancellation race (Phase E).

        Q4: endpoints from core/model_router.py kept as-is (Ollama backups + OpenRouter).
        Uses asyncio.wait FIRST_COMPLETED to race chat vs cancel, and cancels the
        HTTP task explicitly so the connection is closed immediately, not just ignored.
        """
        # Use ModelRouter (shared failover) instead of direct httpx post
        try:
            from core.model_router import ModelRouter
            router = ModelRouter()
        except Exception:
            # Fallback to direct httpx if router not available (should not happen)
            router = None

        if router is not None:
            chat_task = asyncio.create_task(router.chat(messages, cancel_event=self.cancel_event))
            cancel_task = asyncio.create_task(self._wait_cancel())
            # If already cancelled, cancel_task will complete immediately
            if self.cancelled():
                cancel_task.cancel()
                chat_task.cancel()
                raise asyncio.CancelledError("killed before chat")
            done, pending = await asyncio.wait(
                [chat_task, cancel_task], return_when=asyncio.FIRST_COMPLETED
            )
            if cancel_task in done:
                # Kill won — cancel the HTTP request explicitly
                chat_task.cancel()
                try:
                    await chat_task
                except asyncio.CancelledError:
                    pass
                # Also try to cancel the underlying httpx via router's cancellation
                # The mock in tests sets a flag when cancelled
                for t in pending:
                    t.cancel()
                raise asyncio.CancelledError("killed during chat")
            else:
                # Chat won — cancel the waiter
                cancel_task.cancel()
                try:
                    await cancel_task
                except asyncio.CancelledError:
                    pass
                try:
                    return await chat_task
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    # Map router errors to OllamaConnectionError for compatibility
                    if "All chat" in str(exc) or "All LLM" in str(exc):
                        raise OllamaConnectionError(str(exc)) from exc
                    raise
        # Fallback direct (should not be used, but keep for compat)
        if self.cancelled():
            raise asyncio.CancelledError("killed before chat")
        try:
            resp = await client.post(
                f"{self.ollama_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": 0.3},
                },
                timeout=self.step_timeout,
            )
            resp.raise_for_status()
        except httpx.ConnectError as exc:
            raise OllamaConnectionError(
                f"cannot reach Ollama at {self.ollama_url} — is `ollama serve` "
                f"running and is the model '{self.model}' pulled?"
            ) from exc
        # Check kill immediately after network IO
        if self.cancelled():
            raise asyncio.CancelledError("killed after chat response")
        data = resp.json()
        if not isinstance(data, dict):
            return "", 0, 0.0
        content = str(data.get("message", {}).get("content", ""))
        eval_count = int(data.get("eval_count") or 0)
        eval_ns = int(data.get("eval_duration") or 0)
        tok_per_s = (eval_count / (eval_ns / 1e9)) if eval_ns > 0 else 0.0
        return content, eval_count, round(tok_per_s, 1)

    async def _session_store(self) -> "Optional[SessionStore]":
        if not self.session_id:
            return None
        if self._store is not None:
            return self._store
        try:
            from genio_server.core.session_store import get_session_store
            return get_session_store()
        except Exception:
            return None

    async def _build_initial_messages(self) -> Optional[List[Dict[str, str]]]:
        """Resume a prior session from its bounded rolling window + summary.

        Returns the full message list to seed the loop (system + resumed
        turns), or ``None`` to fall back to a fresh single-turn conversation.
        Never loads unbounded raw history.
        """
        store = await self._session_store()
        if store is None:
            return None
        session = await store.load_session(self.session_id)
        if not session.get("exists"):
            return None
        # Assemble per mandatory windowing policy, then unpack to messages.
        try:
            from genio_server.core.session_store import build_prompt_from_session
        except Exception:
            return [{"role": "system", "content": self.system_prompt}]
        prompt = build_prompt_from_session(self.system_prompt, session)
        messages: List[Dict[str, str]] = [{"role": "system", "content": prompt}]
        for t in session.get("turns") or []:
            messages.append({"role": t["role"], "content": t["content"]})
        # If a summary exists but no raw turns are in the window, the system
        # prompt already carries it; add nothing extra here.
        return messages

    async def _save_message(self, role: str, content: str) -> None:
        if self.session_id:
            store = await self._session_store()
            if store is not None:
                try:
                    await store.append_message(self.session_id, role, content)
                except Exception:
                    logger.exception("failed to persist message")

    async def run(self, user_input: str) -> AsyncIterator[Dict[str, str]]:
        """Execute the ReAct loop for ``user_input`` and yield events.

        In autonomous mode the loop chains tool calls without confirmation.
        If ``cancel_event`` is set (KILL SWITCH) the loop halts immediately.
        When ``session_id`` is set, prior turns (bounded window + summary) are
        resumed and every new message is persisted immediately (crash-tolerant).
        """
        # Load the bounded window FIRST (otherwise we'd double-count the new
        # user turn if we saved before the load — it would appear both in the
        # stored history and as the new turn).
        resumed = await self._build_initial_messages()
        # Phase 11 : requête opérateur étiquetée TRUSTED_USER (jamais brute).
        from genio_server.core.trust import Trust, guard_block, label_block
        trusted_user = label_block(Trust.USER, user_input)
        if resumed is not None:
            messages = resumed + [{"role": "user", "content": trusted_user}]
            self.system_prompt = messages[0]["content"]
        else:
            messages: List[Dict[str, str]] = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": trusted_user},
            ]
        await self._save_message("user", user_input)
        final_answer = ""

        # Phase 2 v2.1: System 1 Reflex fast-path — resolve deterministic
        # high-frequency intents without any Ollama tokens.
        # Phase A fix: verify kill-switch BEFORE any reflex match so a halted
        # session cannot still trigger host execution; route via invoke with
        # session_id so is_dangerous + sandbox always apply.
        if self.cancelled():
            yield {
                "type": "error",
                "message": "HALTED — kill switch engaged. Re-arm the system "
                           "before running another autonomous task.",
            }
            return
        if os.getenv("GENIO_REFLEX_FASTPATH", "1").strip().lower() not in ("0", "false", "no"):
            try:
                from genio_server.core.reflex_engine import get_reflex_engine
                fast = get_reflex_engine().match(user_input, session_id=self.session_id)
                if fast is not None:
                    # Re-check cancelled after match computation in case kill fired concurrently
                    if self.cancelled():
                        yield {
                            "type": "error",
                            "message": "HALTED — kill switch engaged. Re-arm the system "
                                       "before running another autonomous task.",
                        }
                        return
                    res = fast.get("result") or fast
                    yield {"type": "tool_call", "command": res.get("command", "")}
                    yield {"type": "tool_result", "result": res}
                    final_answer = f"[ردّ سريع من جينيو] {res.get('stdout', '').strip()}"
                    await self._save_message("assistant", final_answer)
                    yield {"type": "answer", "text": final_answer}
                    return
            except Exception:
                logger.exception("reflex fast-path failed; falling through to LLM")

        # Phase 2 v2.1: trajectory tracking for skill compilation.
        trajectory: List[Dict[str, object]] = []
        # Phase 3: loop guard (répétition + retry budget) + deadline du tour.
        guard = LoopGuard()
        turn_deadline = time.monotonic() + TURN_BUDGET_SECONDS

        async with httpx.AsyncClient(base_url=self.ollama_url) as client:
            for _ in range(self.max_iterations):
                # Yield to the event loop each iteration so surrounding tasks
                # (WebSocket telemetry, SSE stream, kill handling) can run.
                await asyncio.sleep(0)
                if self.cancelled():
                    yield {
                        "type": "error",
                        "message": "HALTED — kill switch engaged. Re-arm the system "
                                    "before running another autonomous task.",
                    }
                    return
                if time.monotonic() >= turn_deadline:
                    final_answer = self._quota_synthesis(trajectory)
                    await self._save_message("assistant", final_answer)
                    yield {"type": "answer", "text": final_answer}
                    return
                assistant, eval_count, tok_per_s = await self._chat(client, messages)
                if eval_count:
                    yield {"type": "stats", "tokens": eval_count, "tok_per_s": tok_per_s}
                narration, call = await asyncio.to_thread(_split_narration, assistant)
                if narration:
                    yield {"type": "thought", "text": sanitize_for_client(narration)}

                if call is None:
                    final_answer = await asyncio.to_thread(
                        sanitize_for_client, assistant.strip())
                    await self._save_message("assistant", final_answer)
                    yield {"type": "answer", "text": final_answer}
                    # Phase 2 v2.1: trajectory compiler — a >1 tool-turn run that
                    # ends with a real answer is serialized as a reusable skill.
                    if len(trajectory) > 1 \
                            and os.getenv("GENIO_REFLEX_FASTPATH", "1").strip().lower() \
                            not in ("0", "false", "no"):
                        try:
                            from genio_server.core.reflex_engine import get_reflex_engine
                            get_reflex_engine().compile_skill(
                                f"auto-{int(time.time())}", user_input, trajectory)
                        except Exception:
                            logger.exception("skill compilation failed")
                    return

                command = call["command"]
                if not command:
                    yield {"type": "error", "message": "tool call had empty command"}
                    return
                # Phase 3: assainit les arguments (dict/list JSON → canonique).
                if isinstance(command, (dict, list)):
                    try:
                        command = json.dumps(command, sort_keys=True,
                                             ensure_ascii=False)
                    except Exception:
                        command = str(command)
                else:
                    command = str(command)
                tool_name = str(call.get("tool", "")).strip()
                # Phase 3: outils hallucinés — gate ToolRegistry (Phase 2) :
                # erreur structurée renvoyée au LLM, jamais d'exception.
                if not self._tool_known(tool_name):
                    msg = (f"unknown tool '{tool_name}' — known: "
                           f"{', '.join(self._known_tools())}. "
                           "Reply with ONLY one JSON tool call using a known "
                           "tool, or a final plain-text answer.")
                    yield {"type": "error", "message": msg}
                    feedback = ("TOOL REJECTED (unknown tool): " + msg)
                    messages.append({"role": "assistant", "content": assistant})
                    messages.append({"role": "user", "content": feedback})
                    await self._save_message("assistant", assistant)
                    await self._save_message("user", feedback)
                    continue
                yield {"type": "tool_call", "command": command}

                # Phase 4: interception capability — le LLM ne s'autorise plus
                # lui-même. Descripteur extrait (nom seul), event télémétrique
                # structuré, décision PolicyRegistry ; DENY = erreur structurée
                # renvoyée au modèle (jamais d'exécution, jamais d'exception).
                cap_info = self._capability_check(tool_name)
                yield {"type": "capability.requested", **cap_info}
                if cap_info["decision"] == "DENY":
                    msg = (f"POLICY DENY [{cap_info['capability']}/"
                           f"{cap_info['risk']}]: tool '{tool_name}' refused "
                           f"({cap_info.get('reason', 'policy')}). "
                           "Use a permitted tool or answer directly.")
                    yield {"type": "error", "message": msg}
                    feedback = ("POLICY DENIED: " + msg)
                    messages.append({"role": "assistant", "content": assistant})
                    messages.append({"role": "user", "content": feedback})
                    await self._save_message("assistant", assistant)
                    await self._save_message("user", feedback)
                    continue
                # Phase 5: interrupteur de confirmation — REQUIRE_CONFIRMATION
                # suspend le tour et attend l'opérateur (timeout = refus).
                if cap_info["decision"] == "REQUIRE_CONFIRMATION":
                    try:
                        from core.policy_engine import get_policy_engine
                    except Exception:
                        logger.exception("policy engine import failed")
                        msg = ("POLICY ERROR: confirmation gate unavailable — "
                               "refused fail-closed.")
                        yield {"type": "error", "message": msg}
                        feedback = ("POLICY DENIED: " + msg)
                        messages.append({"role": "assistant",
                                         "content": assistant})
                        messages.append({"role": "user", "content": feedback})
                        await self._save_message("assistant", assistant)
                        await self._save_message("user", feedback)
                        continue
                    engine = get_policy_engine()
                    pend = engine.request_confirmation(tool_name, command)
                    yield {"type": "action_confirmation_required",
                           "tool": tool_name,
                           "capability": cap_info["capability"],
                           "risk": cap_info["risk"],
                           "command": str(command)[:500],
                           "nonce": pend.nonce,
                           "expires_in_s": float(os.getenv(
                               "GENIO_CONFIRM_TIMEOUT", "120"))}
                    approved = await asyncio.to_thread(
                        engine.await_decision, pend.nonce)
                    if not approved:
                        msg = (f"POLICY REQUIRE_CONFIRMATION unapproved for "
                               f"'{tool_name}' (timeout/refus) — refused.")
                        yield {"type": "error", "message": msg}
                        feedback = ("POLICY DENIED: " + msg)
                        messages.append({"role": "assistant",
                                         "content": assistant})
                        messages.append({"role": "user", "content": feedback})
                        await self._save_message("assistant", assistant)
                        await self._save_message("user", feedback)
                        continue
                # Phase 3: pré-check boucle AVANT exécution — le 3e doublon
                # ne part jamais (2 exécutions max).
                _fp = command_fingerprint(tool_name, command)
                if guard.would_loop(_fp):
                    msg = ("LOOP_DETECTED: same tool call repeated "
                           "without progress — stopping to avoid an "
                           "infinite loop.")
                    yield {"type": "error", "message": msg}
                    final_answer = self._quota_synthesis(
                        trajectory, prefix="[توقّف ضدّ التكرار] ")
                    await self._save_message("assistant", final_answer)
                    yield {"type": "answer", "text": final_answer}
                    return
                # Tools (playwright / pyautogui / mss) are blocking — run them
                # in a worker thread so the async loop stays responsive.
                # Phase 3: budget individuel par outil (timeout dur).
                try:
                    result = await asyncio.wait_for(
                        asyncio.to_thread(invoke, tool_name, command,
                                          self.session_id),
                        timeout=TOOL_TIMEOUT_SECONDS,
                    )
                except asyncio.TimeoutError:
                    result = {"tool": tool_name, "command": command,
                              "stdout": "", "stderr": "",
                              "returncode": 124,
                              "error": f"tool timeout after "
                                       f"{TOOL_TIMEOUT_SECONDS:g}s — aborted"}
                # Phase 2 v2.1: deterministic auto-fix — map a known fatal
                # stderr pattern (e.g. ModuleNotFoundError) to an immediate
                # corrective command, before feeding it back for LLM reflection.
                if isinstance(result, dict) and result.get("returncode") not in (0, None) \
                        and os.getenv("GENIO_REFLEX_FASTPATH", "1").strip().lower() \
                        not in ("0", "false", "no"):
                    try:
                        from genio_server.core.reflex_engine import get_reflex_engine
                        fix_cmd = get_reflex_engine().auto_fix(
                            str(result.get("stderr") or result.get("stdout") or ""),
                            session_id=self.session_id,
                        )
                        if fix_cmd:
                            yield {
                                "type": "thought",
                                "text": sanitize_for_client(
                                    f"[تصليح تلقائي من جينيو] {fix_cmd}"),
                            }
                            fix_result = await asyncio.to_thread(
                                invoke, "bash", fix_cmd, self.session_id)
                            if isinstance(fix_result, dict):
                                for k in ("stdout", "stderr"):
                                    if isinstance(fix_result.get(k), str):
                                        fix_result[k] = truncate_output(fix_result[k])
                                fix_result["reflex_fix"] = True
                            result = fix_result
                    except Exception:
                        logger.exception("reflex auto-fix failed")
                # Bound the stored result fields too so the client transcript
                # and any persisted state stay within a sane size.
                if isinstance(result, dict):
                    for k in ("stdout", "stderr"):
                        if isinstance(result.get(k), str):
                            result[k] = truncate_output(result[k])
                trajectory.append({"command": command, "result": result})
                yield {"type": "tool_result", "result": result}

                # Phase 3: détecteur de boucle + budget de retry.
                failed = bool(isinstance(result, dict) and (
                    result.get("error") or
                    result.get("returncode") not in (0, None)))
                verdict = guard.note_call(
                    command_fingerprint(tool_name, command), tool_name, failed)
                if verdict in ("LOOP_DETECTED", "RETRY_EXHAUSTED"):
                    msg = ("LOOP_DETECTED: same tool call repeated "
                           if verdict == "LOOP_DETECTED" else
                           "RETRY_EXHAUSTED: same tool failing repeatedly ") + \
                        "without progress — stopping to avoid an infinite loop."
                    yield {"type": "error", "message": msg}
                    final_answer = self._quota_synthesis(
                        trajectory, prefix="[توقّف ضدّ التكرار] ")
                    await self._save_message("assistant", final_answer)
                    yield {"type": "answer", "text": final_answer}
                    return

                feedback = _feedback_for(result, assistant)
                # Phase 11 : sortie d'outil = UNTRUSTED (garde anti-élévation
                # si détournement détecté dans le contenu).
                try:
                    from genio_server.core.trust import Trust as _T
                    from genio_server.core.trust import guard_block as _gb
                    feedback = _gb(_T.TOOL_OUTPUT, feedback)
                except Exception:
                    pass
                messages.append({"role": "assistant", "content": assistant})
                messages.append({"role": "user", "content": feedback})
                await self._save_message("assistant", assistant)
                await self._save_message("user", feedback)

            yield {
                "type": "answer",
                "text": final_answer or self._quota_synthesis(trajectory),
            }
            # Phase 2 v2.1: Trajectory compiler — a >1 tool-turn run that ended
            # with a final answer qualifies for skill serialization.
            if final_answer and len(trajectory) > 1 \
                    and os.getenv("GENIO_REFLEX_FASTPATH", "1").strip().lower() \
                    not in ("0", "false", "no"):
                try:
                    from genio_server.core.reflex_engine import get_reflex_engine
                    get_reflex_engine().compile_skill(
                        f"auto-{int(time.time())}", user_input, trajectory)
                except Exception:
                    logger.exception("skill compilation failed")


async def run_repl_default_prompt() -> None:
    """Small test: send a prompt and print the event stream."""
    loop = AgentLoop()
    async for event in loop.run("Show the current working directory and git status."):
        print(json.dumps(event, ensure_ascii=False))


if __name__ == "__main__":
    import asyncio

    asyncio.run(run_repl_default_prompt())