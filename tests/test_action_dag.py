"""Phase 19 tests — moteur DAG (validation statique + exécution ordonnée).

Cycles rejetés, inconnues rejetées, prérequis manquants rejetés, ordre
topologique respecté, compensations inverses en cas d'échec, gate capacités.
Exécuteur injecté (pur), aucun I/O réel.
"""
import sys

sys.path.insert(0, "/data/ai_tools/genio")

from genio_server.core.dag import DagResult, PlanNode, execute, order, validate


def _ok_plan():
    return [PlanNode(action="screenshot"),
            PlanNode(action="telemetry", depends_on=("screenshot",))]


def test_valid_plan_passes():
    assert validate(_ok_plan()) == []


def test_cycle_rejected():
    plan = [PlanNode(action="screenshot", depends_on=("telemetry",)),
            PlanNode(action="telemetry", depends_on=("screenshot",))]
    errs = validate(plan)
    assert any("cycle" in e for e in errs)
    try:
        order(plan)
        raise SystemExit("order should have raised")
    except ValueError:
        pass


def test_unknown_action_rejected():
    errs = validate([PlanNode(action="teleport")])
    assert any("unknown action" in e for e in errs)
    r = execute([PlanNode(action="teleport")], lambda n: {"ok": True})
    assert r.status == "invalid"


def test_missing_prerequisite_rejected():
    errs = validate([PlanNode(action="telemetry", depends_on=("nope",))])
    assert any("missing prerequisite" in e for e in errs)


def test_empty_plan_invalid():
    assert validate([]) == ["empty plan"]


def test_capability_gate():
    errs = validate(_ok_plan(), granted_capabilities={"READ_ONLY"})
    assert errs == []
    errs = validate([PlanNode(action="prompt")],
                    granted_capabilities={"READ_ONLY"})
    assert any("missing capability" in e for e in errs)


def test_ordered_execution():
    seen = []

    def run(n):
        seen.append(n.action)
        return {"ok": True}

    r = execute(_ok_plan(), run)
    assert r.status == "completed"
    assert seen == ["screenshot", "telemetry"]
    assert r.executed == ["screenshot", "telemetry"]


def test_failure_runs_compensations_reverse():
    log = []

    def run(n):
        log.append(n.action)
        if n.action == "telemetry":
            return {"ok": False, "error": "boom"}
        return {"ok": True}

    plan = [PlanNode(action="screenshot", rollback="telemetry"),
            PlanNode(action="telemetry", depends_on=("screenshot",))]
    r = execute(plan, run)
    assert r.status == "failed"
    assert r.executed == ["screenshot"]
    assert r.compensations == ["telemetry"]
    assert any("boom" in e for e in r.errors)


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
