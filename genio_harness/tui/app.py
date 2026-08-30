"""Genio Harness Textual TUI — next-gen command center.

Features
--------
* Draggable split between the chat pane and the live-execution log pane.
* Multimodal toolbar (📎 File / 🖼️ Vision / 🎙️ Voice) + action buttons
  (📨 Send / 🧹 Clear) beside the prompt input.
* Loading feedback (LoadingIndicator) while the model generates.
* Live telemetry bar docked above the footer: status (Idle/Thinking/Executing),
  CPU %, RAM %, RTX VRAM (nvidia-smi), Tok/s from the agent loop.
* Clipboard synced with the OS clipboard (xclip/xsel/wl-clipboard via
  pyperclip) so copy/paste work across Pop!_OS windows.
* All agent work runs inside a Textual worker on the app's event loop, so the
  UI never blocks.

Run from the repo root::

    python3 genio.py
"""
from __future__ import annotations

import subprocess
import time
from typing import List, Optional

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.events import MouseDown, MouseMove, MouseUp
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    LoadingIndicator,
    Markdown,
    RichLog,
    Static,
)

from genio_harness.core.agent_loop import AgentLoop, OllamaConnectionError

APP_TITLE = "Genio Harness v0.1 — HiTech Lab (Pop!_OS)"

MIN_PANE = 320  # min px width of chat/logs panes


def _nvidia_vram() -> str:
    """Live RTX VRAM usage from ``nvidia-smi`` (best-effort)."""
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total",
             "--format=csv,noheader,nounits"],
            stderr=subprocess.DEVNULL, text=True, timeout=3,
        )
        used, total = out.strip().split(",")[:2]
        return f"{used.strip()}MiB/{total.strip()}MiB"
    except Exception:
        return "n/a"


def sys_metrics() -> str:
    """Cheap CPU/RAM/load metrics via psutil + /proc fallback."""
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=None)
        ram = psutil.virtual_memory().percent
        return f"{cpu:.0f}%", f"{ram:.0f}%"
    except Exception:
        pass
    try:
        with open("/proc/loadavg") as fh:
            load_1 = fh.read().split()[0]
        return load_1, "?"
    except OSError:
        return "?", "?"


class SplitterBar(Static):
    """Thin draggable divider between the chat and logs panes."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__("⣿", *args, **kwargs)
        self._dragging = False
        self._sx = 0
        self._start_w = 0

    def on_mouse_down(self, event: MouseDown) -> None:
        self._dragging = True
        self._sx = event.screen_x
        self._start_w = int(self.app.chat_pane_width())
        event.stop()

    def on_mouse_move(self, event: MouseMove) -> None:
        if not self._dragging:
            return
        self.app.resize_chat_pane(self._start_w + int(event.screen_x - self._sx))
        event.stop()

    def on_mouse_up(self, event: MouseUp) -> None:
        self._dragging = False
        event.stop()


class GenioHarnessApp(App[None]):
    """Next-gen Genio command center."""

    TITLE = APP_TITLE
    SUB_TITLE = "Autonomous engineering loop @ Ollama gemma4:12b"

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", priority=True),
        Binding("ctrl+l", "clear", "Clear"),
        Binding("ctrl+c", "cancel_agent", "Cancel", priority=True),
    ]

    CSS = """
    Screen { layout: vertical; }
    #split { width: 1fr; height: 1fr; }
    #chat-col { width: 58%; height: 1fr; }
    #splitter { width: 3; height: 1fr; color: #22d3ee; background: #0e1626;
                text-align: center; }
    #splitter:hover { background: #14303f; }
    #logs-col { width: 1fr; height: 1fr; border: round #22d3ee; padding: 1; }
    #chat-col { border: round #334155; padding: 0 1; }
    #mm-toolbar { height: auto; padding: 0 0 0 1; }
    #mm-toolbar Button { margin: 0 0 0 1; }
    #chat-md { height: 1fr; }
    #loading { height: 3; color: #22d3ee; text-style: bold; }
    #input-row { height: 3; margin: 0 0 1 0; }
    #prompt { height: 3; }
    #btn_send { width: 12; height: 3; margin: 0 1; }
    #btn_clear { width: 12; height: 3; }
    #telemetry { height: 1; width: 1fr; background: #0b1220; color: #9fb9e8;
                 padding: 0 2; border-top: solid #22334d; }
    Markdown { background: #0b1220; }
    """

    def __init__(self) -> None:
        super().__init__()
        self._agent_loop = AgentLoop()
        self._chat_lines: List[str] = []
        self._worker: Optional[object] = None
        self.is_thinking = False
        self._agent_status = "idle"          # idle | thinking | executing
        self._tokps = 0.0
        self._last_vram = "", 0.0
        try:
            import psutil  # noqa: F401
            psutil.cpu_percent(interval=None)  # warm up sample
        except Exception:
            pass

    # ------------------------------------------------------------- compose

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="split"):
            with Vertical(id="chat-col"):
                with Horizontal(id="mm-toolbar"):
                    yield Button("📎 File", id="btn_file", variant="primary")
                    yield Button("🖼️ Vision", id="btn_vision", variant="warning")
                    yield Button("🎙️ Voice", id="btn_voice", variant="success")
                yield Markdown("# Genio — autonomous engineer", id="chat-md")
                yield LoadingIndicator(id="loading")
                with Horizontal(id="input-row"):
                    yield Input(placeholder="أمّر Genio باش يعمل…", id="prompt")
                    yield Button("📨 إرسل", id="btn_send", variant="primary")
                    yield Button("🧹 مسح", id="btn_clear", variant="error")
            yield SplitterBar(id="splitter")
            with Vertical(id="logs-col"):
                yield RichLog(id="logs", highlight=True, markup=True, wrap=False)
        yield Static(id="telemetry", markup=True)
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#loading", LoadingIndicator).display = False
        self.query_one("#logs", RichLog).write(self._sys_header())
        self.set_interval(1.0, self.update_telemetry)

    # ------------------------------------------------------------- clipboard

    @property
    def clipboard(self) -> str:
        """OS clipboard (pyperclip) fallback to the local one."""
        try:
            import pyperclip
            value = pyperclip.paste()
            if value:
                self._clipboard = value
                return value
        except Exception:
            pass
        return self._clipboard

    def copy_to_clipboard(self, text: str) -> None:
        super().copy_to_clipboard(text)
        try:
            import pyperclip
            pyperclip.copy(text)
        except Exception:
            pass

    # ------------------------------------------------------------- telemetry

    def _sys_header(self) -> str:
        return f"[bold cyan]{sys_metrics()}[/] — model [b]{self._agent_loop.model}[/b]"

    def _status_line(self) -> str:
        state = {
            "idle": "🧠 Status: Idle 🟢",
            "thinking": "🧠 Status: Thinking 🟡",
            "executing": "🧠 Status: Executing 🟠",
        }[self._agent_status]
        cpu, ram = sys_metrics()
        now = time.monotonic()
        if now - self._last_vram[1] > 2.0:
            self._last_vram = _nvidia_vram(), now
        vram = self._last_vram[0]
        return (f"{state} | 💻 CPU: {cpu} | 🐏 RAM: {ram} | "
                f"🎮 VRAM: {vram} | ⚡ {self._tokps:.1f} tok/s")

    def update_telemetry(self) -> None:
        self.query_one("#telemetry", Static).update(self._status_line())

    # ------------------------------------------------------------- helpers

    def chat_pane_width(self) -> int:
        return max(MIN_PANE, int(self.query_one("#chat-col").size.width))

    def resize_chat_pane(self, width: int) -> None:
        split_w = int(self.query_one("#split").size.width)
        width = max(MIN_PANE, min(width, split_w - MIN_PANE - 3))
        self.query_one("#chat-col").styles.width = width

    def _append_chat(self, text: str) -> None:
        md = self.query_one("#chat-md", Markdown)
        self._chat_lines.append(text)
        md.update("\n\n".join(self._chat_lines))
        try:
            md.scroll_end(animate=False)
        except AttributeError:
            pass

    def _log(self, line: str) -> None:
        self.query_one("#logs", RichLog).write(line)

    def _set_status(self, status: str) -> None:
        self._agent_status = status
        self.update_telemetry()

    def _set_thinking(self, on: bool) -> None:
        self.is_thinking = on
        loader = self.query_one("#loading", LoadingIndicator)
        loader.display = on
        self._set_status("thinking" if on else "idle")

    def _set_busy(self, busy: bool) -> None:
        prompt = self.query_one("#prompt", Input)
        prompt.disabled = busy if not busy else True
        prompt.placeholder = "Genio khaddem… (ctrl+c yahbad)" if busy \
            else "أمّر Genio باش يعمل…"
        self._set_thinking(busy)

    # ------------------------------------------------------------- actions

    def action_clear(self) -> None:
        self._chat_lines.clear()
        self.query_one("#chat-md", Markdown).update("# Genio — autonomous engineer")
        logs = self.query_one("#logs", RichLog)
        logs.clear()
        logs.write(self._sys_header())

    def action_cancel_agent(self) -> None:
        if self._worker is not None and not self._worker.is_cancelled:
            self._worker.cancel()
            self._log("[yellow]agent task cancelled by user[/]")
            self._set_busy(False)
            self._set_status("idle")

    # ------------------------------------------------------------- chat input

    def _submit(self, text: str) -> None:
        text = (text or "").strip()
        if not text or self.is_thinking:
            return
        self.query_one("#prompt", Input).value = ""
        self._append_chat(f"**You:** {text}")
        self._log(f"[bold]» new task[/] {text!r}")
        self._set_busy(True)
        self._launch_agent(text)

    @on(Input.Submitted)
    def _on_input_submitted(self, event: Input.Submitted) -> None:
        prompt = event.value or ""
        event.input.value = ""
        self._submit(prompt)

    @on(Button.Pressed, "#btn_send")
    def _on_btn_send(self, event: Button.Pressed) -> None:
        self._submit(self.query_one("#prompt", Input).value or "")

    @on(Button.Pressed, "#btn_clear")
    def _on_btn_clear(self, event: Button.Pressed) -> None:
        self.action_clear()

    def _launch_agent(self, prompt: str) -> None:
        async def _run() -> None:
            try:
                async for event in self._agent_loop.run(prompt):
                    self._handle_agent_event(event)
            except OllamaConnectionError as exc:
                self._log(f"[bold red]Ollama error[/] {exc}")
                self._append_chat(f"**System:** {exc}")
            except Exception as exc:  # noqa: BLE001 - surface to user
                self._log(f"[bold red]agent error[/] {exc!r}")
                self._append_chat(f"**System:** internal agent error: {exc}")
            finally:
                self._set_busy(False)
                self._set_status("idle")

        self._worker = self.run_worker(_run(), name=f"react-{time.time():.0f}")

    def _handle_agent_event(self, event: dict) -> None:
        kind = event.get("type")
        if kind == "stats":
            self._tokps = float(event.get("tok_per_s", 0.0))
            self.update_telemetry()
        elif kind == "thought":
            self._append_chat(f"> {event['text'].strip()}")
            self._log(f"[#7d8899]reason:[/] {event['text'].strip()[:200]}")
            self._set_status("thinking")
        elif kind == "tool_call":
            self._append_chat(f"```bash\n{event['command']}\n```")
            self._log(f"[bold cyan]$ {event['command']}[/]")
            self._set_status("executing")
        elif kind == "tool_result":
            res = event["result"]
            code = res.get("returncode", "?")
            secs = res.get("duration", "?")
            col = "green" if code == 0 else "red"
            out = (res.get("stdout") or "").strip() or (res.get("stderr") or "").strip() or "(no output)"
            lines = out.splitlines()
            snippet = lines[0] if lines else out
            if len(lines) > 1:
                snippet += f" … (+{len(lines) - 1} lines)"
            self._log(f"[{col}]exit={code}[/] [#7d8899]{secs}s[/] {snippet[:200]}")
            self._set_status("thinking")
        elif kind == "answer":
            self._append_chat(f"**Genio:** {event['text'].strip()}")
            self._log(f"[bold]{event['text'].strip()[:200]}[/]")
            self._set_status("idle")
        elif kind == "error":
            self._log(f"[bold red]{event.get('message', 'error')}[/]")
            self._append_chat(f"**System:** {event.get('message', 'error')}")
            self._set_status("idle")

    # -------------------------------------------------- multimodal toolbar

    @on(Button.Pressed, "#btn_file")
    def _on_btn_file(self, event: Button.Pressed) -> None:
        self._log("[bold #22d3ee]📎 File attach[/] scaffolding — file picker UI coming online next.")

    @on(Button.Pressed, "#btn_vision")
    def _on_btn_vision(self, event: Button.Pressed) -> None:
        self._log("[bold #f0b429]🖼️ Vision[/] scaffolding — image input banner will hook a vision model here.")

    @on(Button.Pressed, "#btn_voice")
    def _on_btn_voice(self, event: Button.Pressed) -> None:
        self._log("[bold #27c93f]🎙️ Voice (Push-to-Talk)[/] scaffolding — sounddevice recording will bind here.")


if __name__ == "__main__":
    GenioHarnessApp().run()