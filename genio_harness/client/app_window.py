"""Genio Client — standalone futuristic PySide6 desktop app.

A decoupled client for the Genio Server daemon. Provides:

* **Server / Node Switcher** header — local Pop!_OS node, TN production
  server, or any custom node (persisted in ``~/.config/genio/nodes.json``).
* **Split view**: left chat / reasoning stream (cyberpunk dark-glass styling),
  right embedded live terminal & execution logs (ANSI via :mod:`pyte`).
* **Multimodal toolbar**: native file picker (📎), vision picker (🖼️),
  push-to-talk voice streaming (🎙️), send (📨) and clear (🧹).
* **Telemetry dock**: live CPU / RAM / GPU stats streamed from the connected
  node over SSE (``/api/v1/telemetry``).

The agent channel uses the ``/ws/agent`` WebSocket: prompts trigger the remote
ReAct loop and stream ``thought`` / ``tool_call`` / ``tool_result`` / ``stats``
/ ``answer`` events back into the chat + terminal panes.
"""
from __future__ import annotations

import asyncio
import base64
import io
import json
import os
import queue
import sys
import threading
import wave
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Callable
from urllib.parse import urlparse

from PySide6.QtCore import QObject, QTimer, Qt, Signal
from PySide6.QtGui import QPixmap, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSplitter,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import httpx
import sounddevice as sd
import websockets

import pyte


DEFAULT_NODES: List[Dict[str, Any]] = [
    {"label": "\U0001f7e2 Local Pop!_OS Node", "api": "http://127.0.0.1:8000", "key": ""},
    {"label": "\U0001f30c TN Production Server", "api": "https://lab.hitech.tn/genio", "key": ""},
]
CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "genio"
NODES_FILE = CONFIG_DIR / "nodes.json"

STYLE = """
QMainWindow, QDialog { background:#0d1117; color:#c9d1d9; }
QLabel { color:#c9d1d9; }
#header { background:#161b22; border-bottom:1px solid #30363d; }
#title { color:#58a6ff; font-weight:bold; font-size:15px; }
QComboBox { background:#21262d; color:#58a6ff; border:1px solid #30363d;
            border-radius:8px; padding:4px 10px; min-width:250px; }
QComboBox QAbstractItemView { background:#161b22; color:#c9d1d9;
    selection-background-color:#21262d; border:1px solid #30363d; }
QPushButton { background:#21262d; color:#c9d1d9; border:1px solid #30363d;
              border-radius:8px; padding:4px 12px; }
QPushButton:hover { background:#30363d; border-color:#58a6ff; }
QPushButton.pill { background:#21262d; color:#58a6ff; border:none; border-radius:12px;
                   padding:5px 14px; font-size:12px; }
QPushButton.pill:hover { background:#30363d; }
QPushButton.send { background:#1f6feb; color:#fff; border:none; border-radius:12px;
                   padding:5px 16px; font-weight:bold; }
QPushButton.send:hover { background:#388bfd; }
QPushButton.recording { background:#f85149; color:#fff; border:none;
                        border-radius:12px; padding:5px 14px; font-weight:bold; }
QLineEdit, QTextEdit, QTextBrowser { background:#161b22; border:1px solid #30363d;
    border-radius:10px; color:#c9d1d9; padding:4px; }
QLineEdit:focus, QTextEdit:focus, QTextBrowser:focus { border-color:#58a6ff; }
#terminal { background:#0d1117; font-family:'JetBrains Mono','Fira Code',
    monospace; font-size:12px; }
#screen { background:#000; border:1px solid #30363d; }
#screenlbl { background:#000; color:#8b949e; }
QTabWidget::pane { border:1px solid #30363d; background:#161b22; }
QTabBar::tab { background:#21262d; color:#8b949e; padding:4px 14px;
               border:1px solid #30363d; border-bottom:none; }
QTabBar::tab:selected { background:#161b22; color:#58a6ff; border-color:#58a6ff; }
#kill { background:#f85149; color:#ffffff; border:none; border-radius:10px;
        padding:8px 18px; font-size:15px; font-weight:bold; }
#kill:hover { background:#ff7b72; }
#kill[halted="true"] { background:#da3633; color:#ffdcd7; }
#arm { background:#1f6feb; color:#fff; border:none; border-radius:10px;
       padding:8px 12px; font-weight:bold; }
#arm[halted="true"] { background:#21262d; color:#3fb950; }
QSplitter::handle { background:#30363d; }
#dock { background:#161b22; border-top:1px solid #30363d; color:#8b949e;
        font-size:11px; }
#chat { background:#0d1117; border:1px solid #30363d; }
"""


def api_to_ws(base: str) -> str:
    u = urlparse(base)
    scheme = "wss" if u.scheme == "https" else "ws"
    host = f"{u.hostname}:{u.port}" if u.port else u.hostname
    return f"{scheme}://{host}{u.path.rstrip('/')}/ws/agent"


def api_to_telemetry(base: str) -> str:
    return f"{base.rstrip('/')}/api/v1/telemetry"


def _hex_escape(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _load_nodes() -> List[Dict[str, Any]]:
    try:
        if NODES_FILE.exists():
            data = json.loads(NODES_FILE.read_text())
            return data if isinstance(data, list) else DEFAULT_NODES
    except Exception:
        pass
    return [dict(n) for n in DEFAULT_NODES]


def _save_nodes(nodes: List[Dict[str, Any]]) -> None:
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        NODES_FILE.write_text(json.dumps(nodes, ensure_ascii=False, indent=2))
    except Exception:
        pass


class VoiceRecorder:
    """Push-to-talk capture to an in-memory WAV buffer (16 kHz mono int16)."""

    def __init__(self) -> None:
        self._frames: List[bytes] = []
        self._stream: Optional[sd.InputStream] = None
        self.error: Optional[str] = None
        self.recording = False

    def start(self) -> bool:
        try:
            self._frames.clear()
            self.error = None
            self._stream = sd.InputStream(
                samplerate=16000, channels=1, dtype="int16", blocksize=1024,
                callback=self._callback,
            )
            self._stream.start()
            self.recording = True
            return True
        except Exception as exc:
            self.error = str(exc)
            self._stream = None
            return False

    def _callback(self, indata, frames, time_info, status) -> None:
        if status:
            pass
        self._frames.append(indata.copy().tobytes())

    def stop(self) -> Tuple[Optional[bytes], float]:
        duration = 0.0
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        self.recording = False
        payload = b"".join(self._frames)
        if self.error is None and payload:
            duration = len(payload) / (16000 * 2)
            return self._to_wav(payload), round(duration, 2)
        return None, 0.0

    def _to_wav(self, pcm: bytes) -> bytes:
        buf = io.BytesIO()
        framed = wave.open(buf, "wb")
        framed.setnchannels(1)
        framed.setsampwidth(2)
        framed.setframerate(16000)
        framed.writeframes(pcm)
        framed.close()
        return buf.getvalue()


class AgentSocketWorker(threading.Thread):
    """WebSocket client to ``/ws/agent``. Runs one asyncio loop per thread."""

    def __init__(self, api_base: str, key: str,
                 on_event: Callable[[dict], None],
                 on_connected: Callable[[], None],
                 on_disconnected: Callable[[], None],
                 on_error: Callable[[str], None]) -> None:
        super().__init__(daemon=True)
        self.url = api_to_ws(api_base)
        self.headers = {"X-API-Key": key} if key else {}
        self._queue: "queue.Queue[Optional[Any]]" = queue.Queue()
        self._loop: Optional[asyncio.BaseEventLoop] = None
        self._connected = threading.Event()
        self.on_event = on_event
        self.on_connected = on_connected
        self.on_disconnected = on_disconnected
        self.on_error = on_error

    def run(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._client())
        except Exception as exc:
            self._loop.close()
            if self.on_error:
                self.on_error(f"agent socket error: {exc}")
            if self.on_disconnected:
                self.on_disconnected()

    async def _client(self) -> None:
        extra = {"additional_headers": self.headers} if self.headers else {}
        async with websockets.connect(self.url, ping_interval=15, **extra) as ws:
            await ws.send(json.dumps({"action": "ping"}))
            if self.on_connected:
                self.on_connected()
            self._connected.set()

            async def writer() -> None:
                while True:
                    item = await self._loop.run_in_executor(None, self._queue.get)
                    if item is None:
                        break
                    if isinstance(item, str):
                        await ws.send(item)
                    else:
                        await ws.send(json.dumps(item))

            async def reader() -> None:
                async for raw in ws:
                    try:
                        event = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    if self.on_event:
                        self.on_event(event)

            await asyncio.gather(writer(), reader())

    def send(self, payload: Any) -> None:
        if not self._connected.is_set():
            self.on_error and self.on_error("not connected to a server node")
            return
        self._queue.put(payload)

    def stop(self) -> None:
        self._queue.put(None)


class TelemetryWorker(threading.Thread):
    """SSE reader for ``/api/v1/telemetry`` — streams JSON snapshots."""

    def __init__(self, api_base: str, key: str, on_update, on_state, on_error) -> None:
        super().__init__(daemon=True)
        self.url = api_to_telemetry(api_base)
        self.headers = {"X-API-Key": key} if key else {}
        self._stop_ev = threading.Event()
        self.on_update = on_update
        self.on_state = on_state
        self.on_error = on_error

    def run(self) -> None:
        try:
            with httpx.Client(timeout=httpx.Timeout(10.0, connect=5.0)) as client:
                with client.stream(
                    "GET", self.url, headers=self.headers,
                    timeout=httpx.Timeout(connect=5.0, read=None, write=None, pool=None),
                ) as resp:
                    if resp.status_code == 401:
                        self.on_state and self.on_state(False)
                        self.on_error and self.on_error("telemetry: unauthorized (bad API key)")
                        return
                    self.on_state and self.on_state(True)
                    for line in resp.iter_lines():
                        if self._stop_ev.is_set():
                            return
                        if line.startswith("data: "):
                            try:
                                snap = json.loads(line[6:])
                            except json.JSONDecodeError:
                                continue
                            self.on_update and self.on_update(snap)
        except Exception as exc:
            self.on_state and self.on_state(False)
            self.on_error and self.on_error(f"telemetry: {exc}")

    def stop(self) -> None:
        self._stop_ev.set()


from PySide6.QtCore import QObject, QTimer, Signal


class _Bridge(QObject):
    """Thread-safe relay: worker-thread callbacks emit these signals into GUI."""

    event = Signal(dict)
    telemetry = Signal(dict)
    conn = Signal(bool)
    err = Signal(str)


class GenioClient(QMainWindow):
    """Standalone futuristic desktop client for the Genio Server daemon."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Genio — Distributed AI Engineer")
        self.resize(1280, 760)
        self._nodes: List[Dict[str, Any]] = _load_nodes()
        self._worker: Optional[AgentSocketWorker] = None
        self._tel_worker: Optional[TelemetryWorker] = None
        self._bridge = _Bridge()
        self._connected = False
        self._busy = False
        self._killed = False
        self._recorder = VoiceRecorder()
        self._term_lines: List[str] = []
        self._last_frame: Optional[bytes] = None

        self._screen = pyte.Screen(100, 30)
        self._stream = pyte.Stream(self._screen)

        self._build_ui()
        self.setStyleSheet(STYLE)
        self._populate_nodes()
        self._connect_bridge()
        self._set_kill_state()
        self._connect_to_node(0)

    # ----- UI construction -------------------------------------------------
    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QWidget()
        header.setObjectName("header")
        hh = QHBoxLayout(header)
        hh.setContentsMargins(12, 6, 12, 6)
        title = QLabel("⬡ GENIO")
        title.setObjectName("title")
        self.node_combo = QComboBox()
        self.conn_label = QLabel("○ no node connected")
        self.conn_label.setObjectName("conn")
        self.reconnect_btn = QPushButton("↻ Reconnect")
        self.reconnect_btn.clicked.connect(self._reconnect)
        hh.addWidget(title)
        hh.addSpacing(16)
        hh.addWidget(QLabel("Server node:"))
        hh.addWidget(self.node_combo, 1)
        hh.addWidget(self.reconnect_btn)
        hh.addWidget(self.conn_label)
        hh.addSpacing(12)
        self.btn_arm = QPushButton("↺ Arm")
        self.btn_arm.setObjectName("arm")
        self.btn_arm.setToolTip("Re-arm the autonomous actuators after a KILL SWITCH halt")
        self.btn_arm.clicked.connect(self._rearm)
        self.btn_kill = QPushButton("🛑 KILL SWITCH")
        self.btn_kill.setObjectName("kill")
        self.btn_kill.setToolTip("Instantly halt the autonomous loop and ALL computer/browser actuators")
        self.btn_kill.setCursor(Qt.PointingHandCursor)
        self.btn_kill.clicked.connect(self._kill)
        hh.addWidget(self.btn_arm)
        hh.addWidget(self.btn_kill)
        root.addWidget(header)

        splitter = QSplitter(Qt.Horizontal)

        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(8, 8, 8, 8)
        lv.setSpacing(6)
        self.chat = QTextBrowser()
        self.chat.setObjectName("chat")
        self.chat.setOpenExternalLinks(True)
        self.chat.setPlaceholderText("Connect to a node, then ask Genio anything…")
        self._toolbar()
        self.input = QLineEdit()
        self.input.setPlaceholderText("Type a message in Darja… (Enter to send)")
        self.input.returnPressed.connect(self._send)
        lv.addWidget(self.chat, 1)
        lv.addLayout(self._toolbar_layout)
        lv.addWidget(self.input)
        splitter.addWidget(left)

        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 8, 8, 8)
        rv.setSpacing(6)
        self.right_tabs = QTabWidget()
        self.right_tabs.setDocumentMode(True)

        term_tab = QWidget()
        tv = QVBoxLayout(term_tab)
        tv.setContentsMargins(4, 4, 4, 4)
        tv.setSpacing(4)
        tbar = QHBoxLayout()
        tbar.addWidget(QLabel("REMOTE PTY / EXECUTION LOGS"))
        sub_lbl = QLabel("ANSI-supported")
        sub_lbl.setObjectName("sub")
        tbar.addWidget(sub_lbl)
        self.terminal = QTextEdit()
        self.terminal.setObjectName("terminal")
        self.terminal.setReadOnly(True)
        self.terminal.setLineWrapMode(QTextEdit.NoWrap)
        self._term_lines.append("─ Genio Remote Terminal ─ waiting for events…")
        self.terminal.setPlainText("\n".join(self._term_lines))
        tv.addLayout(tbar)
        tv.addWidget(self.terminal, 1)
        self.right_tabs.addTab(term_tab, "⌘ Terminal")

        self.screen_tab = QWidget()
        sv = QVBoxLayout(self.screen_tab)
        sv.setContentsMargins(4, 4, 4, 4)
        sv.setSpacing(4)
        sbar = QHBoxLayout()
        sbar.addWidget(QLabel("🖥 LIVE HOST SCREEN (Computer-Use viewport)"))
        self.screen_refresh_lbl = QLabel("paused")
        sbar.addStretch(1)
        sbar.addWidget(self.screen_refresh_lbl)
        self.screen_view = QLabel("Requesting a frame from the node…")
        self.screen_view.setObjectName("screen")
        self.screen_view.setAlignment(Qt.AlignCenter)
        self.screen_view.setMinimumHeight(240)
        sv.addLayout(sbar)
        sv.addWidget(self.screen_view, 1)
        self.right_tabs.addTab(self.screen_tab, "🖥 Screen")

        rv.addWidget(self.right_tabs, 1)
        self.right_tabs.currentChanged.connect(self._on_tab_changed)
        splitter.addWidget(right)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([720, 520])
        root.addWidget(splitter, 1)

        self.dock = QLabel("waiting for telemetry…")
        self.dock.setObjectName("dock")
        root.addWidget(self.dock)

        self.setCentralWidget(central)

    def _toolbar(self) -> None:
        lay = QHBoxLayout()
        lay.setSpacing(6)
        self.btn_file = QPushButton("📎 File")
        self.btn_vision = QPushButton("🖼️ Vision")
        self.btn_voice = QPushButton("🎙️ Voice")
        self.btn_send = QPushButton("📨 Send")
        self.btn_clear = QPushButton("🧹 Clear")
        for b, cls in ((self.btn_file, "pill"), (self.btn_vision, "pill"),
                       (self.btn_voice, "pill"), (self.btn_send, "send"),
                       (self.btn_clear, "pill")):
            b.setProperty("class", cls)
            b.setCursor(Qt.PointingHandCursor)
            b.setFocusPolicy(Qt.NoFocus)
        self.btn_file.setObjectName("btn_file")
        self.btn_vision.setObjectName("btn_vision")
        self.btn_voice.setObjectName("btn_voice")
        self.btn_send.setObjectName("btn_send")
        self.btn_clear.setObjectName("btn_clear")
        self.btn_file.clicked.connect(self._pick_file)
        self.btn_vision.clicked.connect(self._pick_vision)
        self.btn_voice.clicked.connect(self._toggle_voice)
        self.btn_send.clicked.connect(self._send)
        self.btn_clear.clicked.connect(self._clear)
        for b in (self.btn_file, self.btn_vision, self.btn_voice,
                  self.btn_send, self.btn_clear):
            lay.addWidget(b)
        lay.addStretch(1)
        self._toolbar_layout = lay

    def _populate_nodes(self) -> None:
        self.node_combo.blockSignals(True)
        self.node_combo.clear()
        for n in self._nodes:
            self.node_combo.addItem(n["label"], n)
        self.node_combo.addItem("➕ Connect New Server…", None)
        self.node_combo.setCurrentIndex(0)
        self.node_combo.blockSignals(False)
        self.node_combo.currentIndexChanged.connect(self._on_node_selected)

    # ----- node switching --------------------------------------------------
    def _on_node_selected(self, idx: int) -> None:
        data = self.node_combo.currentData()
        if data is None:
            self._prompt_new_node()
            return
        self._connect_to_node(idx)

    def _prompt_new_node(self) -> None:
        api, ok = QInputDialog.getText(
            self, "Connect New Server",
            "API base URL (e.g. http://1.2.3.4:8000 or https://node.example.com/genio):")
        if not ok or not api.strip():
            self.node_combo.setCurrentIndex(0)
            return
        label = api.strip()
        key, ok2 = QInputDialog.getText(
            self, "API Key", "API key (leave empty if the node allows open access):",
            QLineEdit.Password)
        key = key.strip() if ok2 else ""
        node = {"label": f"\U0001f4a1 {label}", "api": api.strip(), "key": key}
        self._nodes.append(node)
        _save_nodes(self._nodes)
        self.node_combo.blockSignals(True)
        self.node_combo.insertItem(len(self._nodes) - 1, node["label"], node)
        idx = self.node_combo.count() - 2
        self.node_combo.setCurrentIndex(idx)
        self.node_combo.blockSignals(False)
        self._connect_to_node(idx)

    def _reconnect(self) -> None:
        self._connect_to_node(self.node_combo.currentIndex())

    def _connect_to_node(self, idx: int) -> None:
        n = self.node_combo.itemData(idx)
        if not n:
            return
        self._killed = False
        self._set_kill_state()
        self._teardown_workers()
        self._conn_label_state(False)
        self._drop("Switching to node: " + n["label"])
        self._worker = AgentSocketWorker(
            n["api"], n.get("key", ""),
            on_event=lambda ev: self._bridge.event.emit(ev),
            on_connected=lambda: self._bridge.conn.emit(True),
            on_disconnected=lambda: self._bridge.conn.emit(False),
            on_error=lambda msg: self._bridge.err.emit(msg),
        )
        self._tel_worker = TelemetryWorker(
            n["api"], n.get("key", ""),
            on_update=lambda s: self._bridge.telemetry.emit(s),
            on_state=lambda ok: self._bridge.conn.emit(ok),
            on_error=lambda msg: self._bridge.err.emit(msg),
        )
        self._worker.start()
        self._tel_worker.start()

    def _teardown_workers(self) -> None:
        if self._worker is not None:
            self._worker.stop()
            self._worker.join(timeout=2)
            self._worker = None
        if self._tel_worker is not None:
            self._tel_worker.stop()
            self._tel_worker = None

    def _conn_label_state(self, ok: bool) -> None:
        self._connected = ok
        self.conn_label.setText(
            "🟢 connected" if ok else "🔴 disconnected")

    # ----- signal wiring ---------------------------------------------------
    def _connect_bridge(self) -> None:
        self._bridge.event.connect(self._on_event)
        self._bridge.telemetry.connect(self._on_telemetry)
        self._bridge.conn.connect(self._on_conn)
        self._bridge.err.connect(self._on_err)

    # ----- event handlers --------------------------------------------------
    def _on_event(self, ev: Dict[str, Any]) -> None:
        t = ev.get("type")
        if t == "thought":
            self._append_chat("🧠", ev.get("text", ""), "#8b949e")
            self._feed_term(f"\x1b[36m› Genio thinks…\x1b[0m\n")
        elif t == "tool_call":
            self._feed_term(
                f"\x1b[33m$ {ev.get('command', '')}\x1b[0m\n")
            self._append_chat("⚙", "$ " + ev.get("command", ""), "#d29922")
        elif t == "tool_result":
            res = ev.get("result", {})
            out = res.get("stdout", "") or ""
            err = res.get("stderr", "") or ""
            code = res.get("returncode", -1)
            if out:
                self._feed_term(out + "\n")
            if err:
                self._feed_term(f"\x1b[31m{err}\x1b[0m\n")
            self._feed_term(
                f"\x1b[2mexit code {code}\x1b[0m\n")
        elif t == "stats":
            self._dock_stats = {
                "tokens": ev.get("tokens", 0),
                "tok_per_s": ev.get("tok_per_s", 0.0),
            }
        elif t == "answer":
            self._append_chat("⬡", ev.get("text", ""), "#58a6ff")
            self._busy = False
            self._update_busy()
        elif t == "error":
            self._append_chat("⚠", ev.get("message", "unknown error"), "#f85149")
            self._busy = False
            self._update_busy()
        elif t == "attached":
            self._append_chat("📎",
                              f"{ev.get('kind', 'file').title()} saved on node: "
                              f"<i>{ev.get('path', '')}</i> ({ev.get('size', 0)} B)",
                              "#3fb950")
        elif t == "voice_ready":
            self._append_chat("🎙",
                              f"voice received — saved as <i>{ev.get('path', '')}</i> "
                              f"({ev.get('duration', 0.0)} s)", "#3fb950")
        elif t == "pong":
            pass
        elif t == "screen":
            self._show_screen_frame(ev.get("data_b64"))
        elif t == "screen_stream":
            if ev.get("active"):
                self.screen_refresh_lbl.setText(f"streaming @ {ev.get('interval', 1.0)}s")
            else:
                self.screen_refresh_lbl.setText("paused")
        elif t in ("killed", "armed"):
            self._killed = not ev.get("armed", False)
            self._set_kill_state()
            self._append_chat("🛑" if not ev.get("armed") else "✅",
                              str(ev.get("reason") or ("killed" if not ev.get("armed")
                                                       else "re-armed")), "#f85149" if not ev.get("armed") else "#3fb950")

    def _on_tab_changed(self, idx: int) -> None:
        want = idx >= 0 and self.right_tabs.widget(idx) is self.screen_tab
        if self._worker is not None and self._connected and want:
            self._worker.send({"action": "screen_stream", "active": True, "interval": 1.0})
        elif self._worker is not None:
            self._worker.send({"action": "screen_stream", "active": False})

    def _show_screen_frame(self, data_b64: Any) -> None:
        if not data_b64:
            return
        try:
            import base64 as _b64
            raw = _b64.b64decode(data_b64)
            self._last_frame = raw
            pm = QPixmap()
            if pm.loadFromData(raw):
                scaled = pm.scaled(
                    self.screen_view.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.screen_view.setPixmap(scaled)
                self.screen_view.setText("")
        except Exception:
            pass

    def _set_kill_state(self) -> None:
        self.btn_kill.setProperty("halted", "true" if self._killed else "false")
        self.btn_kill.setText("🛑 HALTED — RE-ARM" if self._killed else "🛑 KILL SWITCH")
        self.btn_arm.setProperty("halted", "true" if self._killed else "false")
        self.btn_arm.setEnabled(self._killed)
        for w in (self.btn_kill, self.btn_arm):
            w.style().unpolish(w)
            w.style().polish(w)
        self._update_busy()

    def _kill(self) -> None:
        self._killed = True
        self._set_kill_state()
        if self._worker is not None and self._connected:
            self._worker.send({"action": "kill", "reason": "KILL SWITCH pressed by operator"})
        else:
            self._append_chat("🛑", "KILL SWITCH armed locally (no node). "
                                   "Autonomous send disabled until re-arm.", "#f85149")

    def _rearm(self) -> None:
        self._killed = False
        self._set_kill_state()
        if self._worker is not None and self._connected:
            self._worker.send({"action": "rearm"})
        else:
            self._append_chat("✅", "re-armed locally", "#3fb950")

    def _on_telemetry(self, snap: Dict[str, Any]) -> None:
        gpu = snap.get("gpu", {})
        name = gpu.get("name", "GPU")
        used = gpu.get("used_gb", 0.0)
        total = gpu.get("total_gb", 0.0)
        name_short = name.split("NVIDIA ")[-1] if isinstance(name, str) else "GPU"
        tok = snap.get("last_tok_per_s", 0.0)
        cpu = snap.get("cpu_percent", 0)
        ram = snap.get("ram_percent", 0)
        node = snap.get("node", "node")
        armed = snap.get("armed", True)
        if getattr(self, "_dock_stats", None):
            tok = self._dock_stats.get("tok_per_s", tok)
        shield = "🛡 armed" if armed else "🛑 HALTED"
        self.dock.setText(
            f"🎮 {name_short}: {used}/{total}GB   💻 CPU: {cpu:.0f}%   "
            f"🐏 RAM: {ram:.0f}%   ⚡ {tok:.1f} tok/s   🧠 {node}   "
            f"({shield})")
        if not armed and not self._killed:
            self._killed = True
            self._set_kill_state()

    def _on_conn(self, ok: bool) -> None:
        self._conn_label_state(ok)
        if ok:
            self._append_chat("🔗", f"connected to <b>{self._current_node_label()}</b>", "#3fb950")

    def _on_err(self, msg: str) -> None:
        self._append_chat("⚠", msg, "#f85149")

    def _current_node_label(self) -> str:
        n = self.node_combo.currentData()
        return n["label"] if n else "node"

    # ----- chat / terminal helpers -----------------------------------------
    def _append_chat(self, tag: str, text: str, color: str) -> None:
        self.chat.moveCursor(QTextCursor.End)
        html = (f'<div style="margin:6px 0; border-left:3px solid {color};'
                f' padding-left:8px;"><b style="color:{color};">{tag}</b> '
                f'<span style="color:#c9d1d9;">{_esc(text)}</span></div>')
        self.chat.insertHtml(html)
        self.chat.moveCursor(QTextCursor.End)

    def _feed_term(self, ansi: str) -> None:
        if ansi:
            try:
                self._stream.feed(ansi)
            except Exception:
                pass
        snap = "\n".join(self._screen.display).rstrip()
        for ln in snap.split("\n"):
            if not ln:
                continue
            self._term_lines.append(ln)
        if len(self._term_lines) > 400:
            del self._term_lines[:-400]
        self.terminal.setPlainText("\n".join(self._term_lines))
        sb = self.terminal.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _drop(self, text: str) -> None:
        self._busy = False
        self._update_busy()
        self._feed_term("\n")

    def _update_busy(self) -> None:
        self.btn_send.setEnabled(not self._busy and self._connected and not self._killed)
        self.input.setEnabled(self._connected and not self._killed)

    # ----- multimodal actions ----------------------------------------------
    def _pick_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Attach File", str(Path.home()),
            "All files (*);;Code (*.py *.js *.ts *.rs *.go *.yaml *.json *.sh *.md)")
        if not path or not self._worker or not self._connected:
            return
        name = os.path.basename(path)
        data_b64 = base64.b64encode(Path(path).read_bytes()).decode()
        self._worker.send({"action": "attach_file", "name": name, "data_b64": data_b64})

    def _pick_vision(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Attach Image for Vision",
            str(Path.home()),
            "Images (*.png *.jpg *.jpeg *.webp *.gif)")
        if not path or not self._worker or not self._connected:
            return
        name = os.path.basename(path)
        data_b64 = base64.b64encode(Path(path).read_bytes()).decode()
        self._worker.send({"action": "attach_image", "name": name, "data_b64": data_b64})

    def _toggle_voice(self) -> None:
        if not self._recorder.recording:
            if not self._recorder.start():
                self._append_chat("⚠", f"mic error: {self._recorder.error}", "#f85149")
                return
            self.btn_voice.setText("⏹ Stop Voice")
            self.btn_voice.setProperty("class", "recording")
            self.btn_voice.style().unpolish(self.btn_voice)
            self.btn_voice.style().polish(self.btn_voice)
            self._append_chat("🎙", "recording… speak now, click again to send", "#8b949e")
        else:
            self.btn_voice.setText("🎙️ Voice")
            self.btn_voice.setProperty("class", "pill")
            self.btn_voice.style().unpolish(self.btn_voice)
            self.btn_voice.style().polish(self.btn_voice)
            wav, dur = self._recorder.stop()
            if not wav:
                self._append_chat("⚠", "no audio captured", "#f85149")
                return
            if self._worker and self._connected:
                self._worker.send({
                    "action": "voice_wav", "final": True,
                    "data_b64": base64.b64encode(wav).decode(), "duration": dur,
                })

    def _send(self) -> None:
        text = self.input.text().strip()
        if not text or self._busy:
            return
        if self._killed:
            self._append_chat("🛑", "KILL SWITCH is engaged — re-arm before sending.", "#f85149")
            return
        if not self._worker or not self._connected:
            self._append_chat("⚠", "not connected to any node", "#f85149")
            return
        self._append_chat("👤", text, "#3fb950")
        self.input.clear()
        self._busy = True
        self._update_busy()
        self._worker.send({"action": "prompt", "text": text})

    def _clear(self) -> None:
        self.chat.clear()
        self.input.clear()
        self._term_lines.clear()
        self._screen.reset()
        self.terminal.clear()
        self._feed_term("")

    def closeEvent(self, event) -> None:
        self._teardown_workers()
        super().closeEvent(event)


def _esc(text: str) -> str:
    return (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def main() -> int:
    app = QApplication(sys.argv)
    win = GenioClient()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())