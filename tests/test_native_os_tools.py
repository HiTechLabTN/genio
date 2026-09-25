"""Phase 15 tests — adaptateurs OS natifs.

Lectures réelles (psutil/nvidia-smi/journalctl), destructrices bloquées
SANS exécution (aucun systemctl/poweroff ne part — prouvé par l'absence
d'effet + payload REQUIRE_CONFIRMATION).
"""
import sys

sys.path.insert(0, "/data/ai_tools/genio")

from genio.integrations.hitechos.os_tools import OS_TOOLS, handle, names


def test_all_declared_with_permissions():
    assert len(names()) == 11
    for n in names():
        s = OS_TOOLS[n]
        assert {"capability", "risk", "confirm", "description"} <= set(s.keys())


def test_reads_are_read_only():
    for n in ("os.status", "os.logs", "os.gpu", "os.telemetry", "os.cpu",
              "os.memory", "os.storage"):
        assert OS_TOOLS[n]["capability"] == "READ_ONLY", n
        assert OS_TOOLS[n]["confirm"] is False


def test_destructive_gated():
    assert OS_TOOLS["os.service.restart"]["capability"] == "SYSTEM_SERVICE_CONTROL"
    assert OS_TOOLS["os.update"]["capability"] == "ADMINISTRATIVE"
    for n in ("os.rollback", "os.poweroff"):
        assert OS_TOOLS[n]["capability"] == "CRITICAL"
        assert OS_TOOLS[n]["confirm"] is True


def test_reads_execute_for_real():
    r = handle("os.status")
    assert r["ok"] and r["uptime_s"] > 0 and r["load_1"] >= 0
    r = handle("os.memory")
    assert r["ok"] and 0 <= r["ram_percent"] <= 100
    r = handle("os.gpu")
    assert r["ok"] and r["status"] in ("ok", "no-gpu")
    if r["status"] == "ok":
        assert r["vram_total_gb"] > 0
    r = handle("os.logs", {"lines": 5})
    assert r["ok"] and isinstance(r["lines"], list)


def test_destructive_never_executes():
    import subprocess
    calls = []
    real_run = subprocess.run
    def spy(*a, **k):
        calls.append(a)
        return real_run(*a, **k)
    import genio.integrations.hitechos.os_tools as m
    orig = m.subprocess
    try:
        for n in ("os.service.restart", "os.update", "os.rollback",
                  "os.poweroff"):
            r = handle(n, {"service": "genio.service"})
            assert r["ok"] is False
            assert r["status"] == "REQUIRE_CONFIRMATION", n
    finally:
        assert m.subprocess is orig
    assert calls == [], "destructive adapter must not spawn anything"


def test_unknown_tool():
    assert handle("os.hack")["status"] == "unknown-tool"


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
