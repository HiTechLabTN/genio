"""Adaptateurs d'outils natifs HiTech-OS — Phase 15 (contrats d'avenir).

Lectures système RÉELLES (psutil/nvidia-smi) : os.status, os.logs, os.gpu,
os.telemetry, os.cpu, os.memory, os.storage → READ_ONLY.
Contrôle/critique DÉCLARÉS mais NON EXÉCUTÉS sans gate de confirmation
opérateur (os.service.restart, os.update, os.rollback, os.poweroff) :
le handler retourne REQUIRE_CONFIRMATION et ne touche jamais au système.
"""
from __future__ import annotations

import subprocess
import time
from typing import Any, Dict, List

OS_TOOLS: Dict[str, Dict[str, Any]] = {
    "os.status": {"capability": "READ_ONLY", "risk": "LOW",
                  "confirm": False,
                  "description": "uptime + charge système"},
    "os.logs": {"capability": "READ_ONLY", "risk": "LOW",
                "confirm": False,
                "description": "50 dernières lignes journal système"},
    "os.gpu": {"capability": "READ_ONLY", "risk": "LOW",
               "confirm": False,
               "description": "utilisation GPU/VRAM"},
    "os.telemetry": {"capability": "READ_ONLY", "risk": "LOW",
                     "confirm": False,
                     "description": "snapshot vitals"},
    "os.cpu": {"capability": "READ_ONLY", "risk": "LOW",
               "confirm": False,
               "description": "CPU percent"},
    "os.memory": {"capability": "READ_ONLY", "risk": "LOW",
                  "confirm": False,
                  "description": "RAM utilisée/totale"},
    "os.storage": {"capability": "READ_ONLY", "risk": "LOW",
                   "confirm": False,
                   "description": "disques"},
    "os.service.restart": {"capability": "SYSTEM_SERVICE_CONTROL",
                           "risk": "HIGH", "confirm": True,
                           "description": "redémarrage service (gate)"},
    "os.update": {"capability": "ADMINISTRATIVE", "risk": "CRITICAL",
                  "confirm": True,
                  "description": "mise à jour (gate)"},
    "os.rollback": {"capability": "CRITICAL", "risk": "CRITICAL",
                    "confirm": True,
                    "description": "rollback (gate)"},
    "os.poweroff": {"capability": "CRITICAL", "risk": "CRITICAL",
                    "confirm": True,
                    "description": "extinction (gate)"},
}


def _psutil():
    import psutil
    return psutil


def handle(name: str, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Exécute un adaptateur OS. Destructif = REQUIRE_CONFIRMATION, jamais
    d'exécution (le flux d'approbation Phase 5 s'appliquera plus tard)."""
    params = params or {}
    spec = OS_TOOLS.get(name)
    if spec is None:
        return {"ok": False, "tool": name, "status": "unknown-tool"}
    if spec["confirm"]:
        return {"ok": False, "tool": name, "status": "REQUIRE_CONFIRMATION",
                "capability": spec["capability"], "risk": spec["risk"],
                "message": f"'{name}' exige une confirmation opérateur "
                           f"explicite [{spec['capability']}] — non exécuté."}
    try:
        psutil = _psutil()
    except Exception as exc:
        return {"ok": False, "tool": name, "status": "error",
                "error": f"psutil unavailable: {exc}"}
    try:
        if name == "os.status":
            return {"ok": True, "tool": name, "status": "ok",
                    "uptime_s": int(time.time() - psutil.boot_time()),
                    "load_1": round(__import__("os").getloadavg()[0], 2)}
        if name == "os.cpu":
            return {"ok": True, "tool": name, "status": "ok",
                    "cpu_percent": float(psutil.cpu_percent(interval=0.1))}
        if name in ("os.memory", "os.telemetry"):
            vm = psutil.virtual_memory()
            return {"ok": True, "tool": name, "status": "ok",
                    "ram_percent": float(vm.percent),
                    "ram_used_gb": round(vm.used / 1e9, 1),
                    "ram_total_gb": round(vm.total / 1e9, 1)}
        if name == "os.storage":
            du = psutil.disk_usage("/")
            return {"ok": True, "tool": name, "status": "ok",
                    "disk_percent": float(du.percent),
                    "disk_free_gb": round(du.free / 1e9, 1)}
        if name == "os.gpu":
            try:
                out = subprocess.run(
                    ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,"
                     "memory.total", "--format=csv,noheader,nounits"],
                    capture_output=True, text=True, timeout=5)
                if out.returncode != 0:
                    return {"ok": True, "tool": name, "status": "no-gpu"}
                u, used, total = [x.strip() for x in
                                  out.stdout.strip().splitlines()[0].split(",")]
                return {"ok": True, "tool": name, "status": "ok",
                        "gpu_percent": float(u),
                        "vram_used_gb": round(int(used) / 1024, 1),
                        "vram_total_gb": round(int(total) / 1024, 1)}
            except Exception:
                return {"ok": True, "tool": name, "status": "no-gpu"}
        if name == "os.logs":
            n = min(int(params.get("lines", 50)), 200)
            try:
                out = subprocess.run(
                    ["journalctl", "--no-pager", "-n", str(n)],
                    capture_output=True, text=True, timeout=10)
                lines = out.stdout.strip().splitlines()[-n:]
            except Exception:
                lines = []
            return {"ok": True, "tool": name, "status": "ok", "lines": lines}
    except Exception as exc:
        return {"ok": False, "tool": name, "status": "error",
                "error": str(exc)[:200]}
    return {"ok": False, "tool": name, "status": "unknown-tool"}


def names() -> List[str]:
    return sorted(OS_TOOLS.keys())
