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
from typing import TYPE_CHECKING, AsyncIterator, Callable, Dict, List, Optional, Tuple

import httpx

from genio_server.tools import invoke, tool_specs

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from genio_server.core.session_store import SessionStore

DEFAULT_MODEL = os.environ.get("GENIO_MODEL", "gemma4:12b")
OLLAMA_URL = os.environ.get("GENIO_OLLAMA_URL", "http://127.0.0.1:11434")
DEFAULT_MAX_ITERATIONS = int(os.environ.get("GENIO_MAX_ITERATIONS", "15"))
DEFAULT_MODE = os.environ.get("GENIO_MODE", "autonomous")
STEP_TIMEOUT = 120  # seconds per model request

# Safety: cap any single tool output so giant dumps (e.g. ``ls -R``) can never
# overflow the LLM context window and crash the loop into a premature terminal
# state. When the cap is hit a marker is appended so the model knows the
# result was truncated rather than complete.
MAX_TOOL_OUTPUT = 3000
TRUNCATE_MARKER = "\n... [Output truncated to preserve context window]"

SYSTEM_PROMPT = (
    "You are Genio, the fully autonomous AI engineer for HiTech Lab. "
    "CRITICAL RULE: You MUST communicate with the user EXCLUSIVELY in "
    "Tunisian Darja (Tunisian Arabic naturally mixed with technical "
    "English/French terms). NEVER reply in standard French or standard "
    "Arabic. You can execute commands, browse the web headlessly, control "
    "the desktop GUI and call third-party REST APIs on this Linux system. "
    "Output tool calls in JSON format."
)

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
    "LANGUAGE (strict):\n"
    "- Every message you send to the user — reasoning BEFORE a tool call and "
    "your final answer — MUST be written in Tunisian Darja. Use Latin-script "
    "terms (English/French) naturally as a Tunisian engineer would.\n"
    "- Never write standard French or standard Modern Standard Arabic.\n"
    "- Command/tool output may arrive in any language (for example French, if "
    "the system locale is French). That output is not yours — quote it and "
    "report the result back in Darja."
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
    base = REACT_INSTRUCTIONS + _session_context_block(memory)
    return base + (AUTONOMY_MODE if mode == "autonomous" else "")


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


def _feedback_for(result: Dict[str, object], assistant: str) -> str:
    """Human/LLM-readable tool feedback for the next model turn.

    Truncates long output and, on a non-zero exit code or tool error, injects
    an explicit self-correction directive so the model retries/repairs instead
    of collapsing the loop into a premature terminal state.
    """
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
            return f"Tool output (exit code 0):\n{body}"
        # Self-correction: surface the failure and ask the model to adapt.
        return (
            f"TOOL FAILED (exit code {code}):\n{body}\n\n"
            "The command above did not succeed. Diagnose the error, adjust your "
            "approach and retry until it works — do not give up and do not report "
            "success prematurely. If it is genuinely impossible, explain that in "
            "your final answer."
        )
    if result.get("error"):
        return (
            f"TOOL FAILED (ERROR): {result['error']}\n\n"
            "The tool raised an error. Inspect it, correct your call and retry; "
            "only stop with a final answer once the task is actually resolved."
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

    async def _chat(self, client: httpx.AsyncClient,
                    messages: List[Dict[str, str]]) -> Tuple[str, int, float]:
        """POST to Ollama; return ``(content, eval_count, tokens_per_second)``."""
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
        if resumed is not None:
            messages = resumed + [{"role": "user", "content": user_input}]
            self.system_prompt = messages[0]["content"]
        else:
            messages: List[Dict[str, str]] = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_input},
            ]
        await self._save_message("user", user_input)
        final_answer = ""

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
                assistant, eval_count, tok_per_s = await self._chat(client, messages)
                if eval_count:
                    yield {"type": "stats", "tokens": eval_count, "tok_per_s": tok_per_s}
                narration, call = _split_narration(assistant)
                if narration:
                    yield {"type": "thought", "text": narration}

                if call is None:
                    final_answer = assistant.strip()
                    await self._save_message("assistant", final_answer)
                    yield {"type": "answer", "text": final_answer}
                    return

                command = call["command"]
                if not command:
                    yield {"type": "error", "message": "tool call had empty command"}
                    return
                yield {"type": "tool_call", "command": command}

                # Tools (playwright / pyautogui / mss) are blocking — run them
                # in a worker thread so the async loop stays responsive.
                result = await asyncio.to_thread(invoke, call["tool"], command)
                # Bound the stored result fields too so the client transcript
                # and any persisted state stay within a sane size.
                if isinstance(result, dict):
                    for k in ("stdout", "stderr"):
                        if isinstance(result.get(k), str):
                            result[k] = truncate_output(result[k])
                yield {"type": "tool_result", "result": result}

                feedback = _feedback_for(result, assistant)
                messages.append({"role": "assistant", "content": assistant})
                messages.append({"role": "user", "content": feedback})
                await self._save_message("assistant", assistant)
                await self._save_message("user", feedback)

            yield {
                "type": "answer",
                "text": final_answer or "Max iterations reached without a final answer.",
            }


async def run_repl_default_prompt() -> None:
    """Small test: send a prompt and print the event stream."""
    loop = AgentLoop()
    async for event in loop.run("Show the current working directory and git status."):
        print(json.dumps(event, ensure_ascii=False))


if __name__ == "__main__":
    import asyncio

    asyncio.run(run_repl_default_prompt())