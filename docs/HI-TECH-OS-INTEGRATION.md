# HI-TECH-OS-INTEGRATION — contrat socket IPC (spécification)

`genio/integrations/hitechos/` : protocole JSON **v1.0** strict
(`protocol.py` : InferenceRequest/Response dataclasses frozen + validation),
transport UDS frames préfixées + timeouts (`transport.py`),
adaptateur (`adapter.py` : UNAVAILABLE structuré, jamais de repli silencieux).
Sockets : `/run/hitechos/ai.sock` préféré, `/run/genio/genio.sock` repli
(absents à ce jour — contrat sans daemon).

Adaptateurs `os.*` (`os_tools.py`) : 7 lectures réelles (status/cpu/memory/
storage/gpu/telemetry/logs) ; restart/update/rollback/poweroff DÉCLARÉS,
jamais exécutés sans confirmation (REQUIRE_CONFIRMATION).

Genio possède cognition/orchestration ; HiTech-OS possédera OS/inférence.
Aucune fusion, aucune dépendance dure (cf. THREAT_MODEL #26-27, Phase 29).
Tests : `tests/test_hitechos_contract.py`, `tests/test_native_os_tools.py`.
