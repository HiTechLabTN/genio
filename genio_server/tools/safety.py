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
        # Phase 17 : processus enfants actifs (Popen/asyncio) pour kill préemptif.
        self._procs: Dict[int, Any] = {}

    def register_proc(self, proc: Any) -> int:
        """Enregistre un subprocess actif (retourne id, à unregister après)."""
        with self._lock:
            key = id(proc)
            self._procs[key] = proc
            return key

    def unregister_proc(self, key: int) -> None:
        with self._lock:
            self._procs.pop(key, None)

    def kill_all_active(self) -> int:
        """Termine tous les processus enfants enregistrés (then kill)."""
        with self._lock:
            procs = list(self._procs.items())
        killed = 0
        for key, proc in procs:
            try:
                proc.terminate()
                killed += 1
            except Exception:
                pass
        # Seconde passe : kill dur pour les récalcitrants.
        import time as _t
        _t.sleep(0.5)
        with self._lock:
            rest = list(self._procs.items())
        for key, proc in rest:
            try:
                proc.kill()
                killed += 1
            except Exception:
                pass
        return killed

    @property
    def armed(self) -> bool:
        with self._lock:
            return self._armed

    def halt(self, reason: str = "KILL SWITCH engaged by operator") -> None:
        # Phase 17 : préemptif — tue les enfants actifs AVANT de verrouiller.
        try:
            self.kill_all_active()
        except Exception:
            pass
        with self._lock:
            self._armed = False
            self._reason = reason
            self._killed_at = time.time()
        # Audit (best-effort, jamais bloquant).
        try:
            from genio_server.core.telemetry import get_telemetry
            get_telemetry().emit("kill_switch.triggered", actor="operator",
                                 result=reason[:200])
        except Exception:
            pass

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