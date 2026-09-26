# ARCHITECTURE — Genio Sovereign Autonomous Agent Runtime

> Décrit l'implémentation réelle (vérifiée Phases 0-27), pas des intentions.

## Flux de données

```
navigateur ──HTTPS──▶ cloudflared ─┬─▶ :8098 dist statique (genio-web)
                                   ├─▶ :8000 API/WS (genio.service)
                                   │     ├─ AgentLoop (ReAct, ≤5 itérations)
                                   │     ├─ PolicyEngine → registres
                                   │     ├─ sandbox conteneur (optionnel)
                                   │     └─ session_store (SQLite)
                                   └─▶ VODER :5050 (voix, localhost seul)
Ollama :11434 (inférence) · gestures :8001 · timers systemd
```

## Registres canoniques (`genio_server/core/registries.py`)

Tool · Capability (+ToolDescriptor frozen) · Action (12) · Policy (fail-closed)
· Model (vue router) · Skill (20 compilés + 8 patterns) · Memory (descripteurs).

## Boucle agent (`agent_loop.py`)

prompt(TRUSTED_USER) → reflex fast-path → ReAct :
thought → capability.requested → [confirmation?] → tool_call → tool_result →
LoopGuard → feedback(TOOL_OUTPUT) → … → answer. Budgets : 5 itérations,
600s tour, 120s/outil, 10 tools, 8000 tokens. Quota → synthèse Darija.
Kill switch préemptif (Popen registrés, `invoke()` gated).

## Mémoire

Working (éphémère) · Episodic (sessions.db, fenêtre 10) · Semantic
(JSONL + métadonnées + quarantaine) · System (statique). Contexte injecté
étiqueté (SYSTEM/MEMORY/POLICY/USER/TOOL_OUTPUT).

## Intégration HiTech-OS

`genio/integrations/hitechos/` : protocole JSON v1.0 + UDS
(`/run/hitechos/ai.sock`, repli `/run/genio/genio.sock`) + adaptateurs
os.* (lectures réelles, destructrices gatées). Pas de fusion (contrat seul).
