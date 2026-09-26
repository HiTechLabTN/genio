# AGENT_RUNTIME — cycle de vie (implémentation)

`AgentLoop.run(prompt)` : instructions étiquetées → fast-path réflexe
(<1s salutations) → boucle ReAct bornée (5 itérations, 600s, 120s/outil,
10 tools, 8000 tokens) → answer ou synthèse de quota.

Par itération : narration (sanitizée) → tool_call → gate capability →
[confirmation] → LoopGuard pré-check → invoke (timeout) → auto-fix →
tool_result → LoopGuard post → feedback étiqueté → modèle.

Terminaisons : answer LLM · quota (synthèse) · LOOP_DETECTED/RETRY_EXHAUSTED ·
quota budgets · HALTED (kill) · modèle injoignable (réponse gracieuse) ·
DENY répétés (le modèle conclut).

Mémoire : fenêtre 10 + summary + faits sémantiques (additif).
Persistance immédiate (crash-tolerant) ; ligne parent auto-créée.
Compilation de skills si trajectoire >1 (réflexe activé).

Tests : `tests/test_agent_runtime.py` (14) + `test_adversarial_suite.py` (5).
