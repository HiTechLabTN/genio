"""Genio Harness Textual TUI — futuristic developer command center.

Next-gen design pass:
* Compact mini-pill toolbar (📎 File / 🖼️ Vision / 🎙️ Voice) + live status
  badge with an animated neural/status orb.
* Native file pickers via ``zenity`` on Pop!_OS, transparently falling back
  to a Textual ``DirectoryTree`` modal screen when zenity is unavailable.
* Push-to-talk voice capture via ``sounddevice`` with a REAL live pulsing
  waveform banner driven by the microphone input level.
* Cyberpunk / dark-glass palette: ``#0d1117``/``#161b22`` surfaces,
  ``#30363d`` hairline borders, electric-cyan ``#58a6ff`` and emerald
  ``#3fb950`` accents, tight typography.
* Single-line telemetry dock: [🎮 RTX 3060: x/yGB] [💻 CPU] [🐏 RAM]
  [⚡ tok/s] [🧠 HiTech-Node].

All agent work + pickers run inside Textual workers so the UI never blocks;
voice capture runs on a daemon thread owned by ``VoiceRecorder`` and only a
peak level is brought back onto the app's event loop.
"""
from __future__ import annotations

import asyncio
import math
import os
import shutil
import threading
import time
import wave
from pathlib import Path
from typing import List, Optional

import numpy as np

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.events import MouseDown, MouseMove, MouseUp
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    DirectoryTree,
    Footer,
    Header,
    Input,
    Markdown,
    RichLog,
    Static,
)

from genio_harness.core.agent_loop import AgentLoop, OllamaConnectionError

APP_TITLE = "Genio Harness v0.2 — HiTech Lab / HiTech-Node"

MIN_PANE = 320  # min cell width of chat/logs panes

ORB_FRAMES = "◐◓◑◒"
BAR_LEVELS = "▁▂▃▄▅▆▇█"
WAVE_LEN = 16

_BG_DARK, _BG_PANEL = "#0d1117", "#161b22"
_BG_ELEV, _BG_HOVER = "#21262d", "#30363d"
_CYAN, _EMERALD, _EMERALD_OK, _AMBER = "#58a6ff", "#3fb950", "#3fb950", "#d29922"
_RED, _MUTED = "#f85149", "#8b949e"


def _gpu_line() -> str:
    """Live RTX summary, e.g. ``RTX 3060: 8.6/12GB`` (best-effort)."""
    try:
        out = subprocess_check(["nvidia-smi",
                                "--query-gpu=name,memory.used,memory.total",
                                "--format=csv,noheader,nounits"])
        name, used_mib, total_mib = [x.strip() for x in out.strip().split(",")[:3]]
        return f"{name}: {int(used_mib) / 1024:.1f}/{int(total_mib) / 1024:.0f}GB"
    except Exception:
        return "GPU: n/a"


def subprocess_check(args: List[str], timeout: int = 3) -> str:
    import subprocess
    return subprocess.check_output(args, stderr=subprocess.DEVNULL,
                                   text=True, timeout=timeout)


def sys_cpu_ram() -> str:
    """``"cpu%|ram%"`` via psutil with a /proc fallback."""
    try:
        import psutil
        return f"{psutil.cpu_percent(interval=None):.0f}", f"{psutil.virtual_memory().percent:.0f}"
    except Exception:
        pass
    try:
        load = Path("/proc/loadavg").read_text().split()[0]
        return load, "?"
    except OSError:
        return "?", "?"


# ----------------------------------------------------------------------------
# Voice capture thread (sounddevice) -----------------------------------------
# ----------------------------------------------------------------------------

class VoiceRecorder:
    """Microphone capture on a daemon thread; exposes a live ``peak`` level.

    The PortAudio callback only computes the peak of each 16 kHz int16 chunk
    and accumulates raw samples; the UI polls ``peak`` via its own timer, so
    no lock contention or cross-thread widget access happens.
    """

    SAMPLE_RATE = 16000

    def __init__(self, path: str = "/tmp/genio_voice.wav") -> None:
        self.path = path
        self.peak = 0.0
        self.error: Optional[str] = None
        self.duration: float = 0.0
        self._chunks: List[np.ndarray] = []
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self._chunks = []
        self.peak = 0.0
        self.error = None
        self.duration = 0.0
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True,
                                        name="genio-voice")
        self._thread.start()

    def _run(self) -> None:
        try:
            import sounddevice as sd
        except ImportError as exc:
            self.error = f"sounddevice unavailable: {exc}"
            return
        try:

            def _cb(indata, _frames, _time, _status) -> None:
                arr = np.frombuffer(indata, dtype=np.int16).astype(np.float32) / 32768.0
                self._chunks.append(arr.copy())
                level = float(np.max(np.abs(arr))) if arr.size else 0.0
                self.peak = self.peak * 0.6 + level * 0.4

            with sd.InputStream(samplerate=self.SAMPLE_RATE, channels=1,
                                dtype="int16", blocksize=512, callback=_cb):
                while not self._stop.wait(0.1):
                    pass
        except Exception as exc:  # PortAudio errors (no device, busy, ...)
            self.error = f"{type(exc).__name__}: {exc}"

    def stop(self) -> None:
        """Stop capture and persist ``/tmp/genio_voice.wav``.

        Returns ``None`` on failure/nothing captured; returns duration of the
        audio in seconds otherwise.
        """
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
        if self.error:
            return None
        if not self._chunks:
            return None
        audio = np.concatenate(self._chunks)
        self.duration = float(audio.shape[0]) / self.SAMPLE_RATE
        with wave.open(self.path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.SAMPLE_RATE)
            wf.writeframes((np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16).tobytes())
        return self.duration

    def wav_size(self) -> int:
        try:
            return Path(self.path).stat().st_size
        except OSError:
            return 0


# ----------------------------------------------------------------------------
# Native file picker fallback (DirectoryTree modal) --------------------------
# ----------------------------------------------------------------------------

class FilePickerScreen(ModalScreen[str]):
    """Fallback graphical file tree when ``zenity`` is missing/failed."""

    CSS = """
    FilePickerScreen { align: center middle; background: #0d1117 80%; }
    #fp-box { width: 74; height: 27; border: thick #30363d; background: #161b22;
              padding: 1; }
    #fp-title { height: 1; color: #58a6ff; text-style: bold; }
    #fp-tree { height: 19; border: round #30363d; background: #0d1117; }
    #fp-path { height: 1; padding: 0 1; color: #3fb950; }
    #fp-buttons { height: 3; margin-top: 1; align-horizontal: right; }
    """

    BINDINGS = [Binding("escape", "cancel_picker", "Cancel")]

    def action_cancel_picker(self) -> None:
        self.dismiss(None)

    def __init__(self, title: str = "Select a file",
                 root: Optional[str] = None) -> None:
        super().__init__()
        self._title = title
        self._root = root or os.getcwd()
        self._current: Optional[str] = None

    def compose(self) -> ComposeResult:
        with Vertical(id="fp-box"):
            yield Static(f"🗂 {self._title}", id="fp-title")
            yield DirectoryTree(self._root, id="fp-tree")
            yield Static("Select a file…", id="fp-path")
            with Horizontal(id="fp-buttons"):
                yield Button("Cancel", id="fp-cancel")
                yield Button("Select", id="fp-select", variant="primary")

    @on(DirectoryTree.FileSelected)
    def _on_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        self._current = str(event.path)
        self.query_one("#fp-path", Static).update(f"[b]{self._current}[/b]")

    @on(Button.Pressed, "#fp-cancel")
    def _on_cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#fp-select")
    def _on_select(self) -> None:
        self.dismiss(self._current)


# ----------------------------------------------------------------------------
# Draggable splitter ---------------------------------------------------------
# ----------------------------------------------------------------------------

class SplitterBar(Static):
    """Thin draggable divider between the chat and the execution-log panes."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__("⋮", *args, **kwargs)
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


# ----------------------------------------------------------------------------
# Main app -------------------------------------------------------------------
# ----------------------------------------------------------------------------

class GenioHarnessApp(App[None]):
    """Futuristic Genio command center."""

    TITLE = APP_TITLE
    SUB_TITLE = "ReAct loop @ Ollama gemma4:12b — HiTech-Node"

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", priority=True),
        Binding("ctrl+l", "clear", "Clear"),
        Binding("ctrl+c", "cancel_agent", "Cancel", priority=True),
    ]

    CSS = """
    Screen { background: #0d1117; }

    #split { width: 1fr; height: 1fr; }
    #chat-col { width: 58%; height: 1fr; }
    #splitter { width: 3; height: 1fr; color: #30363d; background: #161b22;
                text-align: center; }
    #splitter:hover { background: #21262d; color: #58a6ff; }

    #toolbar { height: 3; padding: 1 1; align-horizontal: left; margin-bottom: 1; }
    .mini-btn { height: 1; padding: 0 2; margin: 0 1; border: none;
                background: #21262d; color: #58a6ff; text-style: bold; }
    .mini-btn:hover { background: #30363d; color: #79c0ff; }
    #status_badge { height: 1; margin: 0 2; padding: 0 2; text-style: bold; }

    #chat-scroll { height: 1fr; background: #0d1117; padding: 0 1;
                   scrollbar-color: #30363d; }
    .bubble-genio { background: #1c2128; border: none; border-left: solid #58a6ff;
                    padding: 1 2; margin: 1 0; color: #c9d1d9; }
    .bubble-user { background: #11161d; border: none; border-left: solid #3fb950;
                   padding: 1 2; margin: 1 0; color: #9da7b3; }

    #voice-banner { height: 2; background: #160d0d; color: #f85149;
                    text-style: bold; padding: 0 2; }
    #voice-banner.muted { color: #8b949e; }

    #input-row { height: 3; margin: 1 0 1 1; }
    #prompt { height: 3; background: #161b22; border: tall #30363d; color: #c9d1d9;
              padding: 0 2; }
    #btn_send, #btn_clear { height: 3; margin: 0 1; background: #21262d;
                            border: none; color: #58a6ff; }
    #btn_send:hover, #btn_clear:hover { background: #30363d; color: #79c0ff; }

    #logs-col { width: 1fr; height: 1fr; border: round #30363d; background: #161b22;
                padding: 1; }
    #logs { background: #161b22; color: #c9d1d9; }

    #telemetry { height: 1; width: 1fr; background: #161b22; color: #8b949e;
                 padding: 0 2; border-top: hkey #30363d; }

    Header { background: #161b22; color: #58a6ff; }
    Header .header-title { color: #58a6ff; text-style: bold; }
    Footer { background: #161b22; }
    """

    def __init__(self) -> None:
        super().__init__()
        self._agent_loop = AgentLoop()
        self._worker: Optional[object] = None
        self._chat_lines: List[str] = []
        self.is_thinking = False
        self.is_recording = False
        self._agent_status = "idle"        # idle | thinking | executing | recording
        self._tokps = 0.0
        self._last_gpu = "", 0.0
        self._orb_char = "◐"
        self._orb_timer: Optional[object] = None
        self._voice_timer: Optional[object] = None
        self._recorder = VoiceRecorder()
        self._wave_phase = 0.0
        self._wave_hist: List[float] = []
        self._pending_image: Optional[str] = None
        try:
            import psutil  # noqa: F401
            psutil.cpu_percent(interval=None)  # warm the sample
        except Exception:
            pass

    # ------------------------------------------------------------- compose

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="split"):
            with Vertical(id="chat-col"):
                with Horizontal(id="toolbar"):
                    yield Button("📎 File", id="btn_file", classes="mini-btn")
                    yield Button("🖼️ Vision", id="btn_vision", classes="mini-btn")
                    yield Button("🎙️ Voice", id="btn_voice", classes="mini-btn")
                    yield Static("[#3fb950]●[/] READY", id="status_badge")
                yield VerticalScroll(id="chat-scroll")
                yield Static("", id="voice-banner")
                with Horizontal(id="input-row"):
                    yield Input(placeholder="أمّر Genio باش يعمل…", id="prompt")
                    yield Button("📨", id="btn_send")
                    yield Button("🧹", id="btn_clear")
            yield SplitterBar(id="splitter")
            with Vertical(id="logs-col"):
                yield RichLog(id="logs", highlight=True, markup=True, wrap=False)
        yield Static(id="telemetry", markup=True)
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#logs", RichLog).write(self._sys_header())
        self.query_one("#voice-banner", Static).display = False
        self.set_interval(1.0, self.update_telemetry)

    def on_unmount(self) -> None:
        self._stop_voice()

    # ------------------------------------------------------------- clipboard

    @property
    def clipboard(self) -> str:
        """OS clipboard (pyperclip) with local fallback."""
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
            import asyncio as _aio
            # pyperclip blocks; run on a worker to keep the loop responsive
            self.run_worker(self._copy_safe(text), name="clip")
        except Exception:
            pass

    async def _copy_safe(self, text: str) -> None:
        await asyncio.to_thread(lambda: _clip_paste(text))

    # ------------------------------------------------------------- telemetry

    def _sys_header(self) -> str:
        cpu, ram = sys_cpu_ram()
        return (f"[bold {_CYAN}]Genio node[/] [b]HiTech-Node[/] — "
                f"popOS | cpu {cpu}% | ram {ram}% | model [b]{self._agent_loop.model}[/b]")

    def _status_line(self) -> str:
        state = {
            "idle": "🧠 Ready",
            "thinking": "🧠 Thinking",
            "executing": "🧠 Executing",
            "recording": "🎙 Recording",
        }[self._agent_status]
        cpu, ram = sys_cpu_ram()
        now = time.monotonic()
        if now - self._last_gpu[1] > 2.0:
            self._last_gpu = _gpu_line(), now
        gpu = self._last_gpu[0]
        return (f"[{_EMERALD_OK}🎮 {gpu}[/]] "
                f"[💻 CPU: {cpu}%] [🐏 RAM: {ram}%] "
                f"[⚡ {self._tokps:.1f} tok/s] [{_CYAN}🧠 HiTech-Node[/]]  {state}")

    def update_telemetry(self) -> None:
        self.query_one("#telemetry", Static).update(self._status_line())

    # ------------------------------------------------------------- pane split

    def chat_pane_width(self) -> int:
        return max(MIN_PANE, int(self.query_one("#chat-col").size.width))

    def resize_chat_pane(self, width: int) -> None:
        split_w = int(self.query_one("#split").size.width)
        width = max(MIN_PANE, min(width, split_w - MIN_PANE - 3))
        self.query_one("#chat-col").styles.width = width

    # ------------------------------------------------------------- bubbles

    def _append_chat(self, text: str, who: str = "user") -> None:
        self._chat_lines.append(text)
        bubble = Markdown(text, classes=f"bubble-{who}")
        self.query_one("#chat-scroll").mount(bubble)
        self.query_one("#chat-scroll", VerticalScroll).scroll_end(
            animate=not self._agent_status == "idle")

    def _log(self, line: str) -> None:
        self.query_one("#logs", RichLog).write(line)

    # ------------------------------------------------------------- status/orb

    def _set_status(self, status: str) -> None:
        self._agent_status = status
        if self._orb_timer is not None:
            self._orb_timer.stop()
            self._orb_timer = None
        badge = self.query_one("#status_badge", Static)
        badge.update(self._orb_text())
        if status in ("thinking", "executing"):
            self._orb_timer = self.set_interval(0.2, self._orb_tick)
        self.update_telemetry()

    def _orb_text(self) -> str:
        st = self._agent_status
        if st == "idle":
            return f"[{_EMERALD_OK}]●[/] READY"
        if st == "recording":
            return f"[{_RED}]🔴[/] RECORDING"
        if st == "executing":
            return f"[{_AMBER}]{self._orb_char}[/] EXECUTING"
        return f"[{_CYAN}]{self._orb_char}[/] THINKING"

    def _orb_tick(self) -> None:
        idx = ORB_FRAMES.index(self._orb_char) if self._orb_char in ORB_FRAMES else 0
        self._orb_char = ORB_FRAMES[(idx + 1) % len(ORB_FRAMES)]
        self.query_one("#status_badge", Static).update(self._orb_text())

    def _set_thinking(self, on: bool) -> None:
        self.is_thinking = on
        self._set_status("thinking" if on else "idle")

    def _set_busy(self, busy: bool) -> None:
        prompt = self.query_one("#prompt", Input)
        prompt.disabled = busy
        prompt.placeholder = "Genio khaddem… (ctrl+c yahbad)" if busy \
            else "أمّر Genio باش يعمل…"

    # ------------------------------------------------------------- actions

    def action_clear(self) -> None:
        self._chat_lines = []
        for child in list(self.query_one("#chat-scroll").children):
            child.remove()
        logs = self.query_one("#logs", RichLog)
        logs.clear()
        logs.write(self._sys_header())

    def action_cancel_agent(self) -> None:
        if self._worker is not None and not self._worker.is_cancelled:
            self._worker.cancel()
        self._log(f"[{_AMBER}]agent task cancelled by user[/]")
        self._set_busy(False)
        self._set_thinking(False)

    def action_quit(self) -> None:
        self._stop_voice()
        super().action_quit()

    # ------------------------------------------------------------- chat input

    def _submit(self, text: str) -> None:
        text = (text or "").strip()
        if not text or self.is_thinking:
            return
        if self._pending_image:
            text = (f"Attached image for analysis: {self._pending_image} — "
                    f"use bash tools to inspect it.\n{text}")
        self._pending_image = None
        self.query_one("#prompt", Input).value = ""
        self._append_chat(f"**You:** {text}", "user")
        self._log(f"[bold {_CYAN}]» new task[/] {text[:120]}…")
        self._set_busy(True)
        self._set_thinking(True)
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

    # ------------------------------------------------------------- agent loop

    def _launch_agent(self, prompt: str) -> None:
        async def _run() -> None:
            try:
                async for event in self._agent_loop.run(prompt):
                    self._handle_agent_event(event)
            except OllamaConnectionError as exc:
                self._log(f"[{_RED}]Ollama error[/] {exc}")
                self._append_chat(f"**System:** {exc}", "genio")
            except Exception as exc:
                self._log(f"[{_RED}]agent error[/] {exc!r}")
                self._append_chat(f"**System:** internal agent error: {exc}", "genio")
            finally:
                self._set_busy(False)
                self._set_thinking(False)

        self._worker = self.run_worker(_run(), name=f"react-{time.monotonic():.0f}")

    def _handle_agent_event(self, event: dict) -> None:
        kind = event.get("type")
        if kind == "stats":
            self._tokps = float(event.get("tok_per_s", 0.0))
            self.update_telemetry()
        elif kind == "thought":
            self._append_chat(f"> {event['text'].strip()}", "genio")
            self._log(f"[{_MUTED}]reason:[/] {event['text'].strip()[:200]}")
            self._set_status("thinking")
        elif kind == "tool_call":
            self._append_chat(f"```bash\n{event['command']}\n```", "genio")
            self._log(f"[bold {_CYAN}]{event['command']}[/]")
            self._set_status("executing")
        elif kind == "tool_result":
            res = event["result"]
            code = res.get("returncode", "?")
            secs = res.get("duration", "?")
            col = _EMERALD_OK if code == 0 else _RED
            out = (res.get("stdout") or res.get("stderr") or "").strip() or "(no output)"
            lines = out.splitlines()
            snippet = lines[0] if lines else out
            if len(lines) > 1:
                snippet += f" … (+{len(lines) - 1} lines)"
            self._log(f"[{col}]exit={code}[/] [{_MUTED}]{secs}s[/] {snippet[:200]}")
            self._set_status("thinking")
        elif kind == "answer":
            self._append_chat(f"**Genio:** {event['text'].strip()}", "genio")
            self._log(f"[bold]{event['text'].strip()[:200]}[/]")
            self._set_status("idle")
        elif kind == "error":
            self._log(f"[{_RED}]{event.get('message', 'error')}[/]")
            self._append_chat(f"**System:** {event.get('message', 'error')}", "genio")
            self._set_status("idle")

    # ------------------------------------------------------------- native pickers

    @staticmethod
    async def _zenity(args: List[str]) -> Optional[str]:
        """Run zenity; return the selected path or ``None`` on cancel."""
        if shutil.which("zenity") is None:
            return None
        proc = await asyncio.create_subprocess_exec(
            "zenity", *args, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL)
        stdout, _ = await proc.communicate()
        if proc.returncode != 0:
            return None
        path = stdout.decode("utf-8", "replace").strip()
        return path if path and os.path.exists(path) else None

    async def _launch_file_picker(self) -> Optional[str]:
        path = await self._zenity(
            ["--file-selection", "--title=Select Code/Log File"])
        if path is not None:
            return path
        return await self.push_screen_wait(
            FilePickerScreen("Select Code/Log File", os.getcwd()))

    async def _launch_image_picker(self) -> Optional[str]:
        path = await self._zenity(
            ["--file-selection", "--title=Select an image",
             "--file-filter=Images | *.png *.jpg *.jpeg *.webp"])
        if path is not None:
            return path
        return await self.push_screen_wait(
            FilePickerScreen("Select an image", os.getcwd()))

    @on(Button.Pressed, "#btn_file")
    def _on_btn_file(self, event: Button.Pressed) -> None:
        self.run_worker(self._attach_file())

    @on(Button.Pressed, "#btn_vision")
    def _on_btn_vision(self, event: Button.Pressed) -> None:
        self.run_worker(self._attach_image())

    async def _attach_file(self) -> None:
        path = await self._launch_file_picker()
        if not path:
            self._log(f"[{_MUTED}]file picker cancelled[/]")
            return
        try:
            size = Path(path).stat().st_size
            preview = ""
            if size <= 200_000:
                preview = " ".join(Path(path).read_text(
                    errors="replace").splitlines()[:2])[:160]
        except OSError:
            size, preview = 0, ""
        self.query_one("#prompt", Input).value = path
        self._log(f"[{_CYAN}]📎 attached file[/] {path} [{_MUTED}]{size} B[/]")
        if preview:
            self._log(f"[{_MUTED}]preview:[/] {preview}…")

    async def _attach_image(self) -> None:
        path = await self._launch_image_picker()
        if not path:
            self._log(f"[{_MUTED}]image picker cancelled[/]")
            return
        self._pending_image = path
        self.query_one("#prompt", Input).value = f"wanh essoura: {Path(path).name}"
        self._log(f"[{_CYAN}]🖼 vision[/] queued image {path} "
                  f"[{_MUTED}]gemma4:12b (send prompt to inspect)[/]")

    # ------------------------------------------------------------- push-to-talk

    @on(Button.Pressed, "#btn_voice")
    def _on_btn_voice(self, event: Button.Pressed) -> None:
        if self.is_recording:
            self._stop_voice()
        else:
            self._start_voice()

    def _start_voice(self) -> None:
        if self.is_recording:
            return
        self.is_recording = True
        self._recorder.start()
        self._wave_phase = 0.0
        self._wave_hist = []
        banner = self.query_one("#voice-banner", Static)
        banner.update(self._waveframe())
        banner.display = True
        banner.remove_class("muted")
        self._set_status("recording")
        self._voice_timer = self.set_interval(0.12, self._voice_tick)
        self._log(f"[{_RED}]🎙 recording[/] → {self._recorder.path} — click again to stop")

    def _voice_tick(self) -> None:
        if not self.is_recording:
            return
        if self._recorder.error:
            self._stop_voice()
            self._append_chat(
                f"**System:** voice input unavailable ({self._recorder.error})", "genio")
            return
        self.query_one("#voice-banner", Static).update(self._waveframe())

    def _waveframe(self) -> str:
        peak = float(getattr(self._recorder, "peak", 0.0))
        if self._agent_status == "recording" and peak <= 0.003:
            peak = 0.035  # keep the visual alive under silence
        self._wave_hist.append(peak)
        if len(self._wave_hist) > WAVE_LEN:
            self._wave_hist.pop(0)
        self._wave_phase += 0.22
        amp = min(1.0, max(peak * 2.6, 0.02))
        bars = ""
        for i in range(WAVE_LEN):
            pos = i / (WAVE_LEN - 1)
            v = amp * (0.5 + 0.5 * math.sin(pos * math.pi * 2 - self._wave_phase))
            bars += BAR_LEVELS[min(7, max(0, int(round(v * 7))))]
        return f"🎙️ [{_RED}]🔴[/] [ {bars} ] RECORDING… click again to process"

    def _stop_voice(self) -> None:
        if self._voice_timer is not None:
            self._voice_timer.stop()
            self._voice_timer = None
        if not self.is_recording:
            return
        self.is_recording = False
        duration = self._recorder.stop()
        if self._recorder.error:
            self._log(f"[{_RED}]voice error[/] {self._recorder.error}")
        elif duration:
            self._log(f"[{_EMERALD_OK}]✓ audio captured[/] {duration:.1f}s → "
                      f"{self._recorder.path} ({self._recorder.wav_size()} B) — "
                      f"ready for STT")
        else:
            self._log(f"[{_MUTED}]no voice captured[/]")
        banner = self.query_one("#voice-banner", Static)
        banner.display = False
        self._set_status("idle")


def _clip_paste(text: str) -> None:
    import pyperclip
    pyperclip.copy(text)


if __name__ == "__main__":
    GenioHarnessApp().run()