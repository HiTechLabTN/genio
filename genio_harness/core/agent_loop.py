"""Genio ReAct dispatcher — async reasoning/acting loop over local Ollama.

The loop is model-agnostic: it talks to an Ollama instance (``gemma4:12b``)
over HTTP, parses the assistant's reply for a JSON tool-call, runs the tool
through :mod:`genio_harness.tools`, then feeds the command output back to the
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

import json
import os
import re
from typing import AsyncIterator, Dict, List, Optional, Tuple

import httpx

from genio_harness.tools import invoke, tool_specs

DEFAULT_MODEL = os.environ.get("GENIO_MODEL", "gemma4:12b")
OLLAMA_URL = os.environ.get("GENIO_OLLAMA_URL", "http://127.0.0.1:11434")
DEFAULT_MAX_ITERATIONS = int(os.environ.get("GENIO_MAX_ITERATIONS", "10"))
STEP_TIMEOUT = 120  # seconds per model request

SYSTEM_PROMPT = (
    "You are Genio, the autonomous AI engineer for HiTech Lab. "
    "CRITICAL RULE: You MUST communicate with the user EXCLUSIVELY in "
    "Tunisian Darja (Tunisian Arabic naturally mixed with technical "
    "English/French terms). NEVER reply in standard French or standard "
    "Arabic. You can execute commands on this Linux system. Output tool "
    "calls in JSON format."
)

REACT_INSTRUCTIONS = (
    f"{SYSTEM_PROMPT}\n"
    "\n"
    "Work in a Reason+Act loop:\n"
    "1. Think in plain text — explain your current step.\n"
    "2. When you want to run a command, reply with ONLY a single line of JSON: "
    "{\"tool\": \"bash\", \"command\": \"<shell command>\"} — nothing else.\n"
    "3. The environment replies with the command output and exit code.\n"
    "4. Use that output to decide the next step. When the task is complete, "
    "answer in plain text WITHOUT any JSON.\n"
    "\n"
    "Example of a correct tool turn (nothing before or after the JSON):\n"
    "{\"tool\": \"bash\", \"command\": \"pwd && git status --short\"}\n"
    "\n"
    "Rules:\n"
    "- Never invent output you have not observed.\n"
    "- Keep tool calls short and focused; no interactive prompts.\n"
    "- Guard against destructive commands.\n"
    "- Start every tool turn with exactly the JSON object above (no markdown "
    "fences).\n"
    "\n"
    "LANGUAGE (strict):\n"
    "- Every message you send to the user — reasoning BEFORE a tool call and "
    "your final answer — MUST be written in Tunisian Darja. Use Latin-script "
    "terms (English/French) naturally as a Tunisian engineer would.\n"
    "- Never write standard French or standard Modern Standard Arabic.\n"
    "- Command output may arrive in any language (for example French, if the "
    "system locale is French). That output is not yours — quote it and "
    "report the result back in Darja.\n"
    "\n"
    + tool_specs()
)


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
    return {"tool": str(obj["tool"]).strip(), "command": str(command).strip()}


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


class AgentLoop:
    """Async ReAct dispatcher bound to a local Ollama instance."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        ollama_url: str = OLLAMA_URL,
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
        step_timeout: float = STEP_TIMEOUT,
        system_prompt: Optional[str] = None,
    ) -> None:
        self.model = model
        self.ollama_url = ollama_url.rstrip("/")
        self.max_iterations = max_iterations
        self.step_timeout = step_timeout
        self.system_prompt = system_prompt or REACT_INSTRUCTIONS

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

    async def run(self, user_input: str) -> AsyncIterator[Dict[str, str]]:
        """Execute the ReAct loop for ``user_input`` and yield events."""
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_input},
        ]
        final_answer = ""

        async with httpx.AsyncClient(base_url=self.ollama_url) as client:
            for _ in range(self.max_iterations):
                assistant, eval_count, tok_per_s = await self._chat(client, messages)
                if eval_count:
                    yield {"type": "stats", "tokens": eval_count, "tok_per_s": tok_per_s}
                narration, call = _split_narration(assistant)
                if narration:
                    yield {"type": "thought", "text": narration}

                if call is None:
                    final_answer = assistant.strip()
                    yield {"type": "answer", "text": final_answer}
                    return

                command = call["command"]
                if not command:
                    yield {"type": "error", "message": "tool call had empty command"}
                    return
                yield {"type": "tool_call", "command": command}

                result = invoke(call["tool"], command)
                yield {"type": "tool_result", "result": result}

                output = result.get("stdout", "") or ""
                err = result.get("stderr", "") or ""
                code = result.get("returncode", -1)
                feedback = f"Tool output (exit code {code}):\n{output or err or '(no output)'}"
                messages.append({"role": "assistant", "content": assistant})
                messages.append({"role": "user", "content": feedback})

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