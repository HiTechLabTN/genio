"""Global kill-switch gate for autonomous actuators.

Every actuator (mouse control, typing, screenshots, browser automation) consults
:data:`SAFETY` before acting. When the operator trips the KILL SWITCH the gate
is opened and the actuators refuse to run until it is explicitly re-armed.

The gate is process-wide so a halt issued through any channel (WebSocket, HTTP,
client button) immediately affects every other code path.
"""
from __future__ import annotations

import threading
import time
from typing import Any, Dict, Optional


class KillSwitch:
    """Thread-safe arming state shared across tool invocations."""

    def __init__(self) -> None:
        self._armed = True
        self._reason: Optional[str] = None
        self._killed_at: Optional[float] = None
        self._lock = threading.Lock()

    @property
    def armed(self) -> bool:
        with self._lock:
            return self._armed

    def halt(self, reason: str = "KILL SWITCH engaged by operator") -> None:
        with self._lock:
            self._armed = False
            self._reason = reason
            self._killed_at = time.time()

    def arm(self) -> None:
        with self._lock:
            self._armed = True
            self._reason = None
            self._killed_at = None

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "armed": self._armed,
                "reason": self._reason,
                "killed_at": self._killed_at,
            }

    def guard(self, tool: str, action: str) -> Optional[Dict[str, Any]]:
        """Return an error payload if halted; ``None`` means allowed to act."""
        with self._lock:
            if not self._armed:
                return {
                    "tool": tool,
                    "action": action,
                    "error": "KILL SWITCH engaged — autonomous actions are halted. "
                             "An operator must re-arm before this actuator runs again.",
                    "killed_at": self._killed_at,
                }
            return None


SAFETY = KillSwitch()