"""GUI computer-use tool — global mouse, keyboard and screen capture.

Builds on :mod:`pyautogui` (input synthesis) and :mod:`mss` (fast screen
grabs). Every action passes through the KILL SWITCH gate so a halted system
refuses to move / click / type until an operator re-arms it.

All handlers return result dicts (never raise):
``{"ok": bool, ..., "error": "..."}``.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

from genio_server.tools.safety import SAFETY

_SCREEN = None
_PYAUTOGUI = None
TMP_DIR = None


def _get_pyautogui():
    """Lazily import pyautogui (needs X11 + tkinter). Never breaks imports."""
    global _PYAUTOGUI
    if _PYAUTOGUI is None:
        import pyautogui
        pyautogui.FAILSAFE = True  # global failsafe abort
        _PYAUTOGUI = pyautogui
    return _PYAUTOGUI


def _input_unavailable() -> Optional[Dict[str, Any]]:
    try:
        _get_pyautogui()
        return None
    except Exception as exc:
        return {"ok": False, "action": "input",
                "error": f"GUI input unavailable (X11/tkinter missing): {exc}"}


def _get_screen() -> Any:
    """Lazily open the mss screen grabber — keeps imports safe on headless boxes."""
    global _SCREEN
    if _SCREEN is None:
        import mss
        _SCREEN = mss.mss()
    return _SCREEN


def _tmp_shot_dir() -> str:
    global TMP_DIR
    if TMP_DIR is None:
        root = Path(__file__).resolve().parent.parent.parent
        d = root / "tmp"
        d.mkdir(parents=True, exist_ok=True)
        TMP_DIR = str(d)
    return TMP_DIR


def parse(payload: Any) -> Dict[str, Any]:
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return {"ok": False, "error": "malformed computer payload JSON"}
    return payload if isinstance(payload, dict) else {}


def screenshot(path: Optional[str] = None) -> Dict[str, Any]:
    gate = SAFETY.guard("computer", "screenshot")
    if gate:
        return gate
    try:
        scr = _get_screen()
        monitor = scr.monitors[1]
        shot = scr.grab(monitor)
        if path is None:
            path = f"{_tmp_shot_dir()}/screen_{int(time.time() * 1000)}.png"
        from PIL import Image
        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
        img.save(path)
        return {"ok": True, "action": "screenshot", "path": path,
                "width": shot.width, "height": shot.height}
    except Exception as exc:
        return {"ok": False, "action": "screenshot",
                "error": f"screen capture failed (empty display?): {exc}"}


def handle(payload: Any) -> Dict[str, Any]:
    p = parse(payload)
    if p.get("error"):  # malformed payload JSON — surface it, don't guess
        return p
    action = p.get("action")
    gate = SAFETY.guard("computer", str(action))
    if gate:
        return gate

    if action == "screenshot" or action == "screen":
        return screenshot(p.get("path"))
    need = _input_unavailable()
    if need:
        return need
    pg = _PYAUTOGUI
    if action == "position":
        try:
            x, y = pg.position()
            return {"ok": True, "action": "position", "x": x, "y": y}
        except Exception as exc:
            return {"ok": False, "action": "position",
                    "error": f"display unavailable: {exc}"}
    if action == "size":
        return {"ok": True, "action": "size", "width": pg.size().width,
                "height": pg.size().height}
    if action == "move":
        try:
            pg.moveTo(int(p.get("x", 0)), int(p.get("y", 0)), duration=0.1)
            return {"ok": True, "action": "move", "x": int(p.get("x", 0)), "y": int(p.get("y", 0))}
        except Exception as exc:
            return {"ok": False, "action": "move", "error": f"move failed: {exc}"}
    if action == "click":
        try:
            x, y = p.get("x"), p.get("y")
            if x is not None and y is not None:
                pg.click(int(x), int(y), button=p.get("button", "left"),
                         clicks=int(p.get("clicks", 1)))
            else:
                pg.click(button=p.get("button", "left"), clicks=int(p.get("clicks", 1)))
            return {"ok": True, "action": "click", "x": x, "y": y,
                    "button": p.get("button", "left")}
        except Exception as exc:
            return {"ok": False, "action": "click", "error": f"click failed: {exc}"}
    if action == "doubleclick":
        try:
            x, y = p.get("x"), p.get("y")
            if x is not None and y is not None:
                pg.doubleClick(int(x), int(y))
            else:
                pg.doubleClick()
            return {"ok": True, "action": "doubleclick", "x": x, "y": y}
        except Exception as exc:
            return {"ok": False, "action": "doubleclick", "error": f"doubleclick failed: {exc}"}
    if action == "type":
        try:
            text = str(p.get("text") or "")
            interval = min(max(float(p.get("interval", 0.02)), 0.0), 0.5)
            pg.typewrite(text, interval=interval)
            return {"ok": True, "action": "type", "chars": len(text)}
        except Exception as exc:
            return {"ok": False, "action": "type", "error": f"type failed: {exc}"}
    if action == "key":
        try:
            keys = str(p.get("keys") or p.get("key") or "")
            pg.hotkey(*[k.strip() for k in keys.split("+") if k.strip()])
            return {"ok": True, "action": "key", "keys": keys}
        except Exception as exc:
            return {"ok": False, "action": "key", "error": f"key failed: {exc}"}
    if action == "scroll":
        try:
            pg.scroll(int(p.get("clicks", 3)))
            return {"ok": True, "action": "scroll", "clicks": int(p.get("clicks", 3))}
        except Exception as exc:
            return {"ok": False, "action": "scroll", "error": f"scroll failed: {exc}"}

    return {"ok": False,
            "error": f"unknown computer action '{action}' "
                     "(screenshot|position|size|move|click|doubleclick|type|key|scroll)"}