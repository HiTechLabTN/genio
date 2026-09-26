# GENIO_INTEGRATION_READINESS — Phase 29 (constat vérifié)

## Feature status (20/20 Phase 1, re-vérifiées)

Conversation Darija, accordéons thought/tool, RTL+voix, fast-path <1s,
boucle multi-step ≤5, mémoire session, kill-switch, VODER masculin (F0
140Hz), STT faster-whisper, telemetry bar, self-improve déterministe,
site public 200, avatar 2.5D (0 asset lourd) : toutes VERIFIED live au
cours du chantier (preuves : frames, metrics, wav, logs de runs).

## Security status

30 articles THREAT_MODEL traités (voir `docs/THREAT_MODEL.md`) : sandbox
fail-closed strict, bash structuré, FS boundary, computer/browser/upload/API
durcis, secrets hors repo, injection/contre-mesures, kill préemptif,
rollback prouvé. Suites sécurité : 100+ tests verts.

## Test status

~300 tests : `pytest tests/ test_*.py` = 295 passed + 2 legacy désélectionnés
nominativement (`test_genio_core` : module legacy + services down).
CI réécrite sans masquage (lint bloquant, tsc, vitest, audit, build, smoke).

## Known limitations (explicites, non cachées)

1. Défaut `development` : sandbox opt-in, API ouverte sans clé — durcir
   (`strict` + clé) pour toute exposition au-delà du tunnel actuel.
2. Backend TTS sans `ar` natif (synthèse via `auto`, audio réel vérifié).
3. VRAM TTS résident 4.0GB > cap 3.2GB (unload idle 300s).
4. Modèles `:cloud` via router local = confiance router (pas d'allowlist).
5. noexec stagings = montage hôte ; egress iptables documenté non appliqué.
6. Lane cloud Gemini = token Google opérateur requis.
7. Bouton d'approbation UI (confirmation) : payload émis, pas de widget dédié.

## Unresolved risks

- Compromission opérateur (clé API / accès machine) hors périmètre technique.
- Modèle local jailbreaké par contenu externe : atténué (labels + sanitizer),
  pas d'élimination formelle possible.
- Supply chain : dev-toolchain highs documentés (jamais shippés).

## Dependency / sandbox / performance

Lockfiles : `requirements.lock` (78 pins), `package-lock.json` ; audit prod
0 high/critical ; 7 paquets morts purgés du venv live (serveur 200 OK).
Sandbox : quotas vérifiés live (512m/pids/CPU/RO). Benchmarks :
`docs/audit/PERFORMANCE_BENCHMARK.md` (fast-path 14ms, inférence 8.5tok/s…).

## API compatibility

14 routes + 1 WS stables ; ajouts additifs uniquement (telemetry, auth/token,
stubs motion, probes, executions) ; alias `GENIO_PERSONA_PROMPT` conservé ;
aucune rupture.

## HiTech-OS compatibility

Contrat seul : protocole v1.0 + UDS + adaptateurs os.* (lectures réelles,
destructrices gatées). Pas de fusion, pas de dépendance dure.
Migration future : exposer le daemon sur `/run/hitechos/ai.sock`,
`GENIO_ALLOW_CLOUD` selon politique OS, monter `strict` + sandbox.

## Final readiness

**READY_WITH_LIMITATIONS** — pas READY : les limitations 1-7 ci-dessus
imposent une revue opérateur avant production exposée. Pas NOT_READY :
aucun finding CRITICAL non traité (sandbox fail-open corrigé en strict,
uploads/API/WS/injection verrouillés et testés).
