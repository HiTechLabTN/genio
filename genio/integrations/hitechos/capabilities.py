"""Capability advertisement (§19) — ce que Genio expose, avec versions.

Construit depuis le registre de capabilities quand disponible, sinon
depuis la liste statique honnête. Jamais de capability inventée :
chaque entrée provient du registre ou est marquée external/unavailable.
"""
from __future__ import annotations

from typing import Any, Dict, List

from . import PROTOCOL_VERSION

# Capabilities IPC de haut niveau -> sonde de disponibilité.
# sonde: "registry:<tool>" (présent dans ToolRegistry), "service:<host:port>",
# "static:<reason>" (déclaratif honnête, ex. voice/external).
CAPABILITY_PROBES = {
    "agent": "registry:agent.turn",
    "planning": "registry:planner.plan",
    "memory": "registry:memory.recall",
    "tools": "registry:tool.execute",
    "sandbox": "registry:sandbox.exec",
    "browser": "registry:browser.open",
    "computer": "registry:computer.act",
    "voice": "static:external-voder-service",
    "vision": "static:not-configured",
    "models": "registry:model.route",
    "automation": "registry:tool.execute",
    "filesystem": "registry:fs.read",
    "hitechos-integration": "static:ipc-v1",
}


def _registry_tools() -> set:
    try:
        from genio_server.core.registries import ToolRegistry
        reg = ToolRegistry()
        names = set()
        for attr in ("tools", "_tools", "descriptors", "all"):
            if hasattr(reg, attr):
                try:
                    items = getattr(reg, attr)
                    items = items() if callable(items) else items
                    for t in (items or []):
                        n = getattr(t, "name", None) or (t.get("name") if isinstance(t, dict) else None)
                        if n:
                            names.add(str(n))
                except Exception:
                    pass
        return names
    except Exception:
        return set()


def advertise() -> List[Dict[str, Any]]:
    """Catalogue honnête : available=True seulement si prouvé."""
    tools = _registry_tools()
    out = []
    for cap, probe in sorted(CAPABILITY_PROBES.items()):
        kind, _, target = probe.partition(":")
        if kind == "registry":
            available = target in tools
            detail = "tool-registered" if available else "tool-absent"
        else:
            available = kind == "static" and target not in ("not-configured",)
            detail = target
        out.append({"capability": cap, "available": bool(available),
                    "version": "1.0" if available else None,
                    "detail": detail})
    return out


def catalog() -> Dict[str, Any]:
    caps = advertise()
    return {"protocol_version": PROTOCOL_VERSION,
            "capabilities": caps,
            "available": sorted(c["capability"] for c in caps if c["available"]),
            "unavailable": sorted(c["capability"] for c in caps if not c["available"])}
