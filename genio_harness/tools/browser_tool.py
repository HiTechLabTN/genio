"""Headless browser tool — Playwright wrapper for autonomous web browsing.

Genio can open URLs, read the rendered DOM text, click elements, type into
fields and take screenshots. A single persistent headless Chromium session is
reused across calls (serialised by a lock — Playwright is not thread-safe).

All handlers return a result dict (never raise), the same shape the ReAct loop
feeds back to the model:
``{"ok": bool, "status"...|"text"..., "error": "..."}``.
"""
from __future__ import annotations

import json
import threading
import time
from typing import Any, Dict, Optional

from genio_harness.tools.safety import SAFETY

MAX_TEXT = 8000  # keep DOM text digest-sized for the LLM context
DEFAULT_TIMEOUT_MS = 15_000
BROWSER_SHUTDOWN_BUDGET_S = 4.0


class BrowserSession:
    """One lazy headless Chromium + a single landing page, serially accessed."""

    def __init__(self) -> None:
        self._pw: Optional[Any] = None
        self._browser: Optional[Any] = None
        self._page: Optional[Any] = None
        self._lock = threading.Lock()

    def _ensure(self) -> Any:
        if self._page is None:
            from playwright.sync_api import sync_playwright
            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.launch(headless=True)
            self._page = self._browser.new_page()
            self._page.set_default_timeout(DEFAULT_TIMEOUT_MS)
            self._page.set_default_navigation_timeout(DEFAULT_TIMEOUT_MS)
        return self._page

    def close(self) -> None:
        # NOTE: callers (BrowserSession handlers) already hold ``_lock``;
        # do NOT re-acquire it here (it is a non-reentrant Lock).
        if self._pw is None:
            return
        # Watchdog-bounded teardown: a wedged Node driver must never block
        # the daemon. If a step exceeds its budget we abandon it (the
        # driver/chromium are daemon children and die with the process).
        def _teardown() -> None:
            for ob in (self._page, self._browser, self._pw):
                try:
                    if ob is self._pw:
                        ob.stop()
                    else:
                        ob.close()
                except Exception:
                    pass
        thread = threading.Thread(target=_teardown, daemon=True)
        thread.start()
        thread.join(BROWSER_SHUTDOWN_BUDGET_S)
        self._page = self._browser = self._pw = None


_SESSION = BrowserSession()


def _snap(text: str) -> str:
    text = (text or "").strip()
    return text if len(text) <= MAX_TEXT else text[:MAX_TEXT] + "\n…[truncated]"


def handle(payload: Any) -> Dict[str, Any]:
    """Dispatch a browser command; ``payload`` may be a dict or a JSON string."""
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return {"ok": False, "error": "malformed browser payload JSON"}
    if not isinstance(payload, dict):
        return {"ok": False, "error": "browser payload must be an object"}

    gate = SAFETY.guard("browser", str(payload.get("action", "")))
    if gate:
        return gate

    action = payload.get("action")
    with _SESSION._lock:
        try:
            if action == "open":
                return _open(payload)
            if action == "extract":
                return _extract(payload)
            if action == "click":
                return _click(payload)
            if action == "type":
                return _type(payload)
            if action == "screenshot":
                return _screenshot(payload)
            if action == "url":
                return _url()
            if action == "close":
                _SESSION.close()
                return {"ok": True, "closed": True}
            return {"ok": False, "error": f"unknown browser action '{action}' "
                                          "(open|extract|click|type|screenshot|url|close)"}
        except Exception as exc:
            return {"ok": False, "error": f"browser {action} failed: {exc}"}


def _open(payload: Dict[str, Any]) -> Dict[str, Any]:
    url = str(payload.get("url", "")).strip()
    if not url:
        return {"ok": False, "error": "open requires a 'url'"}
    if not url.startswith(("http://", "https://", "file://", "data:")):
        url = "https://" + url
    page = _SESSION._ensure()
    t0 = time.time()
    page.goto(url, wait_until="domcontentloaded")
    return {
        "ok": True,
        "action": "open",
        "url": page.url,
        "title": page.title(),
        "elapsed_ms": int((time.time() - t0) * 1000),
    }


def _extract(payload: Dict[str, Any]) -> Dict[str, Any]:
    page = _SESSION._ensure()
    selector = (payload.get("selector") or "").strip()
    if selector:
        page.wait_for_selector(selector, timeout=8000)
        text = page.inner_text(selector)
        sample = f"[matched selector: {selector}]\n{text}"
        return {"ok": True, "action": "extract", "text": _snap(sample)}
    text = page.inner_text("body")
    return {"ok": True, "action": "extract", "url": page.url,
            "title": page.title(), "text": _snap(text)}


def _click(payload: Dict[str, Any]) -> Dict[str, Any]:
    selector = str(payload.get("selector", "")).strip()
    if not selector:
        return {"ok": False, "error": "click requires a 'selector'"}
    page = _SESSION._ensure()
    page.click(selector)
    return {"ok": True, "action": "click", "selector": selector, "url": page.url}


def _type(payload: Dict[str, Any]) -> Dict[str, Any]:
    page = _SESSION._ensure()
    selector = (payload.get("selector") or "").strip()
    text = str(payload.get("text") or "")
    if selector:
        page.fill(selector, text)
        return {"ok": True, "action": "type", "selector": selector, "into": text[:200]}
    page.keyboard.type(text, delay=5)
    return {"ok": True, "action": "type", "target": "page keyboard", "into": text[:200]}


def _screenshot(payload: Dict[str, Any]) -> Dict[str, Any]:
    page = _SESSION._ensure()
    full_page = bool(payload.get("full_page", False))
    buf = page.screenshot(full_page=full_page)
    return {"ok": True, "action": "screenshot", "bytes": len(buf), "png": True}


def _url() -> Dict[str, Any]:
    if _SESSION._page is None:
        return {"ok": False, "error": "browser not started yet"}
    return {"ok": True, "action": "url", "url": _SESSION._page.url,
            "title": _SESSION._page.title()}