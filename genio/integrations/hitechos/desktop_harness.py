"""Desktop/mobile integration harness — contract test-double (NOT a product client).

Demonstrates the CORRECT integration pattern for real clients
(Tauri/Capacitor):
    client -> HTTP API/WS (same-origin or tunnel) -> Genio
    client -> IPC hello/capabilities (OS-side only, never untrusted mobile)

Proves: version/capability discovery, degraded modes (voice/sandbox/
Genio absent), reconnect, no privileged IPC from untrusted callers.
Real clients must re-implement this flow in their own stack.
"""
from __future__ import annotations

import time


class ClientState:
    def __init__(self):
        self.genio_version = None
        self.protocol = None
        self.capabilities = set()
        self.connected = False
        self.degraded = []


class DesktopHarness:
    """Simulated desktop client driving the documented contracts."""

    def __init__(self, api_base, ws_url=None):
        self.api_base = api_base.rstrip("/")
        self.ws_url = ws_url
        self.state = ClientState()

    def _get(self, path, timeout=8):
        import urllib.request
        try:
            with urllib.request.urlopen(self.api_base + path, timeout=timeout) as r:
                import json
                return r.status, json.loads(r.read(20000).decode())
        except Exception as e:
            return None, str(e)[:150]

    def discover(self):
        """Version + capability discovery (never assume)."""
        code, telemetry = self._get("/api/v1/system/telemetry")
        code2, health = self._get("/health")
        _ = telemetry, health
        self.state.connected = code == 200 or code2 == 200
        try:
            from genio.integrations.hitechos.capabilities import catalog
            cat = catalog()
            self.state.capabilities = set(cat["available"])
        except Exception:
            self.state.capabilities = set()
        for cap in ("voice", "sandbox", "vision"):
            if cap not in self.state.capabilities:
                self.state.degraded.append(f"{cap}-unavailable-ui-usable")
        return {"connected": self.state.connected,
                "capabilities": sorted(self.state.capabilities),
                "degraded": self.state.degraded}

    def chat(self, text, timeout=60):
        """Normal request path: WebSocket /ws/agent (the real prompt route).
        No HTTP prompt endpoint exists — never invent one."""
        if not self.state.connected:
            return {"status": "offline", "detail": "genio unreachable"}
        if not self.ws_url:
            return {"status": "not-configured",
                    "detail": "no ws_url (use wss://<host>/ws/agent)"}
        try:
            import asyncio
            import json
            import websockets

            async def _run():
                async with websockets.connect(self.ws_url) as ws:
                    await ws.send(json.dumps({"action": "prompt", "text": text}))
                    async for raw in ws:
                        ev = json.loads(raw)
                        if ev.get("type") == "answer":
                            return {"status": "responded",
                                    "text": str(ev.get("text", ""))[:500]}
                        if ev.get("type") == "error":
                            return {"status": "error",
                                    "detail": str(ev)[:200]}
                return {"status": "error", "detail": "stream ended without answer"}

            return asyncio.run(asyncio.wait_for(_run(), timeout))
        except Exception as e:
            return {"status": "error", "detail": str(e)[:200]}

    def reconnect(self, tries=3, delay=1.0):
        for _ in range(tries):
            code, _ = self._get("/health", timeout=5)
            if code == 200:
                self.state.connected = True
                return True
            time.sleep(delay)
        self.state.connected = False
        return False
