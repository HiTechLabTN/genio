# PERFORMANCE_BENCHMARK — Phase 25 (mesuré, non estimé)

Date : 2026-09-26 01:32 CET · hôte Pop!_OS local.

| Métrique | Résultat |
|---|---|
| cold_start | 0.19s — import+init in 0.2s model=gemma4:12b |
| fast_path_reflex | 0.039s — miss 0.000s / greeting-hit 0.014s |
| routing_inference | 10.965s — 10.9s total, 8.5 tok/s (eval 20 tok) |
| tool_exec_bash | 0.013s — 13ms |
| sandbox_startup | 0.2s — create+exec, conteneur réel (GENIO_SANDBOX_MODE=container) |
| memory_retrieval | 0.004s — 1ms turns=10 |
| ws_greeting_turn | 0.045s — 0.04s greeting turn |
| footprints | 0.074s — server-rss=0.11GB host-ram=31.1% vram=11007, 12288 |

Notes : le fast-path salutations répond en millisecondes (pas de LLM) ;
l'inférence locale domine tout tour LLM ; le sandbox inclut create+exec.
Aucune optimisation appliquée — mesure d'abord (règle master).
