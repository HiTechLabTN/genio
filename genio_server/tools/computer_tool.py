"""GUI computer-use tool — global mouse, keyboard and screen capture.

Builds on :mod:`pyautogui` (input synthesis) and :mod:`mss` (fast screen
grabs). Every action passes through the KILL SWITCH gate so a halted system
refuses to move / click / type until an operator re-arms it.

All handlers return result dicts (never raise):
``{"ok": bool, ..., "error": "..."}``.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

from genio_server.tools.safety import SAFETY

# Phase 9 — bornes actionneurs (constantes configurables par env).
CLICK_MIN_INTERVAL_S = float(os.getenv("GENIO_CLICK_MIN_INTERVAL_S", "0.5"))
MAX_TYPE_CHARS = int(os.getenv("GENIO_MAX_TYPE_CHARS", "2000"))
MAX_CLICKS = 5
MAX_SCROLL = 20
MAX_KEYS = 5
_ALLOWED_BUTTONS = ("left", "right", "middle")

# Rate-limit : dernier timestamp par classe d'action (testable via clear).
_RATE_STATE: Dict[str, float] = {}


def check_rate(action: str, now: Optional[float] = None) -> Optional[str]:
    """Retourne None si autorisé, sinon la raison du refus (rate-limit)."""
    if action not in ("click", "doubleclick", "key", "type", "move", "scroll"):
        return None
    t = time.monotonic() if now is None else now
    last = _RATE_STATE.get(action, 0.0)
    if t - last < CLICK_MIN_INTERVAL_S:
        return (f"rate-limited: '{action}' trop rapproché "
                f"(min {CLICK_MIN_INTERVAL_S:g}s entre actions)")
    _RATE_STATE[action] = t
    return None


def clear_rate_state() -> None:
    _RATE_STATE.clear()


def validate_coords(x: Any, y: Any, width: int, height: int) -> Optional[str]:
    """Coordonnées entières dans le cadre [0,w]x[0,h], sinon raison du refus."""
    try:
        xi, yi = int(x), int(y)
    except (TypeError, ValueError):
        return "coordinates must be integers"
    if not (0 <= xi < width and 0 <= yi < height):
        return (f"coordinates out of frame: ({xi},{yi}) "
                f"not in [0,{width})x[0,{height})")
    return None


def validate_press(button: Any, clicks: Any) -> Optional[str]:
    if str(button or "left").lower() not in _ALLOWED_BUTTONS:
        return f"button refused: {button!r}"
    try:
        n = int(clicks if clicks is not None else 1)
    except (TypeError, ValueError):
        return "clicks must be an integer"
    if not 1 <= n <= MAX_CLICKS:
        return f"clicks out of range 1..{MAX_CLICKS}: {n}"
    return None

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


def _screen_size(pg: Any) -> Optional[tuple]:
    """Dimensions d'écran, ou None si indisponibles (fail-closed appelant)."""
    try:
        sz = pg.size()
        return int(sz.width), int(sz.height)
    except Exception:
        return None


def _refuse(action: str, reason: str) -> Dict[str, Any]:
    return {"ok": False, "action": action, "error": reason}


def _validate_static(action: Any, p: Dict[str, Any]) -> Optional[str]:
    """Validation sans display (bornes/combos/longueurs/inconnu)."""
    if action == "type":
        if len(str(p.get("text") or "")) > MAX_TYPE_CHARS:
            return (f"text too long ({len(str(p.get('text') or ''))} > "
                    f"{MAX_TYPE_CHARS} chars)")
        return None
    if action == "key":
        parts = [k.strip() for k in str(p.get("keys") or p.get("key") or "").split("+")
                 if k.strip()]
        if not parts:
            return "empty key combo"
        if len(parts) > MAX_KEYS:
            return f"too many keys ({len(parts)} > {MAX_KEYS})"
        return None
    if action == "scroll":
        try:
            n = int(p.get("clicks", 3))
        except (TypeError, ValueError):
            return "scroll clicks must be an integer"
        if abs(n) > MAX_SCROLL:
            return f"scroll out of range ±{MAX_SCROLL}: {n}"
        return None
    if action in ("click", "doubleclick"):
        err = validate_press(p.get("button", "left"), p.get("clicks", 1))
        if err:
            return err
        return None
    if action in ("screenshot", "screen", "position", "size", "move",
                  "click", "doubleclick", "type", "key", "scroll"):
        return None
    return f"unknown computer action '{action}'"


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
    # Phase 9: validation statique AVANT le check display (fail-fast même
    # headless : bornes, combos, type-length, action inconnue).
    static_err = _validate_static(action, p)
    if static_err:
        return _refuse(action, static_err)
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
        dim = _screen_size(pg)
        if dim is None:
            return _refuse("move", "display unavailable: cannot validate coordinates")
        err = validate_coords(p.get("x", 0), p.get("y", 0), *dim)
        if err:
            return _refuse("move", err)
        err = check_rate("move")
        if err:
            return _refuse("move", err)
        try:
            pg.moveTo(int(p.get("x", 0)), int(p.get("y", 0)), duration=0.1)
            return {"ok": True, "action": "move", "x": int(p.get("x", 0)), "y": int(p.get("y", 0))}
        except Exception as exc:
            return {"ok": False, "action": "move", "error": f"move failed: {exc}"}
    if action == "click":
        try:
            x, y = p.get("x"), p.get("y")
            if x is not None and y is not None:
                dim = _screen_size(pg)
                if dim is None:
                    return _refuse("click", "display unavailable: cannot validate coordinates")
                err = validate_coords(x, y, *dim)
                if err:
                    return _refuse("click", err)
                err = validate_press(p.get("button", "left"), p.get("clicks", 1))
                if err:
                    return _refuse("click", err)
                err = check_rate("click")
                if err:
                    return _refuse("click", err)
                pg.click(int(x), int(y), button=p.get("button", "left"),
                         clicks=int(p.get("clicks", 1)))
            else:
                err = validate_press(p.get("button", "left"), p.get("clicks", 1))
                if err:
                    return _refuse("click", err)
                err = check_rate("click")
                if err:
                    return _refuse("click", err)
                pg.click(button=p.get("button", "left"), clicks=int(p.get("clicks", 1)))
            return {"ok": True, "action": "click", "x": x, "y": y,
                    "button": p.get("button", "left")}
        except Exception as exc:
            return {"ok": False, "action": "click", "error": f"click failed: {exc}"}
    if action == "doubleclick":
        try:
            x, y = p.get("x"), p.get("y")
            if x is not None and y is not None:
                dim = _screen_size(pg)
                if dim is None:
                    return _refuse("doubleclick", "display unavailable: cannot validate coordinates")
                err = validate_coords(x, y, *dim)
                if err:
                    return _refuse("doubleclick", err)
            err = check_rate("doubleclick")
            if err:
                return _refuse("doubleclick", err)
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
            if len(text) > MAX_TYPE_CHARS:
                return _refuse("type", f"text too long ({len(text)} > {MAX_TYPE_CHARS} chars)")
            err = check_rate("type")
            if err:
                return _refuse("type", err)
            interval = min(max(float(p.get("interval", 0.02)), 0.0), 0.5)
            pg.typewrite(text, interval=interval)
            return {"ok": True, "action": "type", "chars": len(text)}
        except Exception as exc:
            return {"ok": False, "action": "type", "error": f"type failed: {exc}"}
    if action == "key":
        try:
            keys = str(p.get("keys") or p.get("key") or "")
            parts = [k.strip() for k in keys.split("+") if k.strip()]
            if not parts:
                return _refuse("key", "empty key combo")
            if len(parts) > MAX_KEYS:
                return _refuse("key", f"too many keys ({len(parts)} > {MAX_KEYS})")
            err = check_rate("key")
            if err:
                return _refuse("key", err)
            pg.hotkey(*parts)
            return {"ok": True, "action": "key", "keys": keys}
        except Exception as exc:
            return {"ok": False, "action": "key", "error": f"key failed: {exc}"}
    if action == "scroll":
        try:
            n = int(p.get("clicks", 3))
            if abs(n) > MAX_SCROLL:
                return _refuse("scroll", f"scroll out of range ±{MAX_SCROLL}: {n}")
            err = check_rate("scroll")
            if err:
                return _refuse("scroll", err)
            pg.scroll(n)
            return {"ok": True, "action": "scroll", "clicks": n}
        except Exception as exc:
            return {"ok": False, "action": "scroll", "error": f"scroll failed: {exc}"}

    return {"ok": False,
            "error": f"unknown computer action '{action}' "
                     "(screenshot|position|size|move|click|doubleclick|type|key|scroll)"}