# POLICY_ENGINE — décisions centralisées (implémentation)

`core/policy_engine.py` : `evaluate()` pure et déterministe (outil, sandbox,
mode) → ALLOW / DENY / REQUIRE_CONFIRMATION / SANDBOX_ONLY (+ RATE_LIMIT,
RESOURCE_LIMIT, NETWORK_RESTRICTED disponibles). Fail-closed : inconnu,
registre HS et strict-sans-sandbox = DENY.

Interrupteur : `request_confirmation()` (nonce hex unique, TTL 120s défaut),
payload WS `action_confirmation_required`, `await_decision()` bloquant
(timeout = refus), `resolve(nonce, bool)` via WS `approve`, `purge_expired()`.

La boucle suspend le tour en attente d'approbation ; sans gate disponible,
refus fermé. LLM jamais autorité. Tests : `tests/test_policy_engine.py`.
