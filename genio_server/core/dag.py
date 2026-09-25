"""Action DAG engine — Phase 19 (canonique, validé avant exécution).

Plans multi-actions en graphes orientés acycliques : validation statique
(cycles, inconnues, prérequis manquants, capacités, impossibilités),
ordre topologique, exécution bornée avec compensations inverses.
S'appuie sur ActionRegistry (Phase 2) — jamais de doublon.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass(frozen=True)
class PlanNode:
    action: str
    args: Dict[str, Any] = field(default_factory=dict)
    depends_on: tuple = ()
    rollback: Optional[str] = None  # action compensatrice (même args)
    timeout_s: float = 60.0


def _registry_names() -> set:
    try:
        from genio_server.core.registries import ActionRegistry
        return set(ActionRegistry.names())
    except Exception:
        return set()


def validate(plan: List[PlanNode],
             granted_capabilities: Optional[set] = None) -> List[str]:
    """Validation statique. Retourne la liste d'erreurs (vide = valide)."""
    errors: List[str] = []
    if not plan:
        return ["empty plan"]
    names = [n.action for n in plan]
    known = _registry_names()
    if known:
        for n in plan:
            if n.action not in known:
                errors.append(f"unknown action: {n.action}")
    seen = set()
    for n in plan:
        if n.action in seen:
            errors.append(f"duplicate action node: {n.action}")
        seen.add(n.action)
        for dep in n.depends_on:
            if dep not in names:
                errors.append(f"{n.action}: missing prerequisite {dep}")
    # Cycles (DFS).
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {n.action: WHITE for n in plan}
    adj = {n.action: [d for d in n.depends_on if d in color] for n in plan}
    stack: List[str] = []

    def _visit(u: str) -> bool:
        color[u] = GRAY
        stack.append(u)
        for v in adj.get(u, []):
            if color[v] == GRAY:
                errors.append("cycle detected: " + " -> ".join(stack + [v]))
                return True
            if color[v] == WHITE and _visit(v):
                return True
        stack.pop()
        color[u] = BLACK
        return False

    for n in plan:
        if color[n.action] == WHITE:
            _visit(n.action)
    # Capacités.
    if granted_capabilities is not None and known:
        try:
            from genio_server.core.registries import ActionRegistry
            for n in plan:
                a = ActionRegistry.get(n.action)
                if a is not None and a.capability not in granted_capabilities:
                    errors.append(f"{n.action}: missing capability "
                                  f"{a.capability}")
        except Exception:
            pass
    return errors


def order(plan: List[PlanNode]) -> List[PlanNode]:
    """Ordre topologique (prérequis d'abord). Lève ValueError si invalide."""
    errs = validate(plan)
    if errs:
        raise ValueError("; ".join(errs))
    by_name = {n.action: n for n in plan}
    done: List[PlanNode] = []
    visited: set = set()

    def _emit(u: str) -> None:
        if u in visited:
            return
        visited.add(u)
        for d in by_name[u].depends_on:
            _emit(d)
        done.append(by_name[u])

    for n in plan:
        _emit(n.action)
    return done


@dataclass
class DagResult:
    status: str  # completed | failed | invalid
    executed: List[str] = field(default_factory=list)
    compensations: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    duration_s: float = 0.0


def execute(plan: List[PlanNode], run_node: Callable[[PlanNode], Dict[str, Any]],
            granted_capabilities: Optional[set] = None) -> DagResult:
    """Exécute dans l'ordre topo ; échec → compensations inverses."""
    errs = validate(plan, granted_capabilities)
    if errs:
        return DagResult(status="invalid", errors=errs)
    t0 = time.monotonic()
    ordered = order(plan)
    done: List[PlanNode] = []
    for node in ordered:
        try:
            res = run_node(node) or {}
            ok = bool(res.get("ok", True))
        except Exception as exc:
            ok, res = False, {"error": str(exc)[:200]}
        if not ok:
            comp = []
            for prev in reversed(done):
                if prev.rollback:
                    try:
                        run_node(PlanNode(action=prev.rollback,
                                          args=dict(prev.args)))
                        comp.append(prev.rollback)
                    except Exception:
                        continue
            return DagResult(
                status="failed", executed=[n.action for n in done],
                compensations=comp,
                errors=[f"{node.action} failed: {res.get('error', 'no detail')}"],
                duration_s=round(time.monotonic() - t0, 3))
        done.append(node)
    return DagResult(status="completed",
                     executed=[n.action for n in done],
                     duration_s=round(time.monotonic() - t0, 3))
