"""Resource governance — Phase 26 (plafonds configurables, policy-controlled).

Budgets par tour : iterations, tool_calls, tokens, runtime. Mémoire/CPU/disque
et réseau/download/upload sont des quotas CONTENEUR (sandbox : 512m, cpus,
pids) — voir session_container ; ce module gouverne le tour agent.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Dict, List


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class BudgetConfig:
    max_iterations: int = 5
    max_tool_calls: int = 10
    max_tokens: int = 8000
    max_runtime_s: float = 600.0
    max_parallel_tools: int = 1  # la boucle est séquentielle par design
    max_memory_mb: float = 2048.0
    max_cpu_percent: float = 90.0
    max_disk_mb: float = 512.0
    max_network_kb: float = 10240.0

    @classmethod
    def from_env(cls) -> "BudgetConfig":
        import genio_server.core.agent_loop as _al
        return cls(
            max_iterations=_env_int("GENIO_MAX_ITERATIONS", _al.DEFAULT_MAX_ITERATIONS),
            max_tool_calls=_env_int("GENIO_MAX_TOOL_CALLS", 10),
            max_tokens=_env_int("GENIO_MAX_TOKENS", 8000),
            max_runtime_s=_env_float("GENIO_TURN_BUDGET", _al.TURN_BUDGET_SECONDS),
            max_parallel_tools=1,
            max_memory_mb=_env_float("GENIO_BUDGET_MEMORY_MB", 2048.0),
            max_cpu_percent=_env_float("GENIO_BUDGET_CPU_PCT", 90.0),
            max_disk_mb=_env_float("GENIO_BUDGET_DISK_MB", 512.0),
            max_network_kb=_env_float("GENIO_BUDGET_NET_KB", 10240.0),
        )


@dataclass
class BudgetTracker:
    """Compteurs du tour + vérification. Pur et testable."""
    config: BudgetConfig = field(default_factory=BudgetConfig.from_env)
    started: float = field(default_factory=time.monotonic)
    iterations: int = 0
    tool_calls: int = 0
    tokens: int = 0

    def note_iteration(self) -> None:
        self.iterations += 1

    def note_tool_call(self) -> None:
        self.tool_calls += 1

    def note_tokens(self, n: int) -> None:
        try:
            self.tokens += max(0, int(n or 0))
        except Exception:
            pass

    def elapsed(self) -> float:
        return time.monotonic() - self.started

    def violations(self) -> List[str]:
        out = []
        if self.iterations > self.config.max_iterations:
            out.append(f"iterations {self.iterations}>{self.config.max_iterations}")
        if self.tool_calls > self.config.max_tool_calls:
            out.append(f"tool_calls {self.tool_calls}>{self.config.max_tool_calls}")
        if self.tokens > self.config.max_tokens:
            out.append(f"tokens {self.tokens}>{self.config.max_tokens}")
        if self.elapsed() > self.config.max_runtime_s:
            out.append(f"runtime {self.elapsed():.0f}s>{self.config.max_runtime_s:g}s")
        return out

    def ok(self) -> bool:
        return not self.violations()

    def host_usage(self) -> Dict[str, float]:
        """Lecture hôte réelle (psutil) pour garde-fous mémoire/CPU."""
        try:
            import psutil
            vm = psutil.virtual_memory()
            return {"memory_mb": float(vm.used) / 1e6,
                    "memory_pct": float(vm.percent),
                    "cpu_pct": float(psutil.cpu_percent(interval=0.1))}
        except Exception:
            return {}
