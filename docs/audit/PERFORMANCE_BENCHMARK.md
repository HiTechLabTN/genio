# PERFORMANCE_BENCHMARK — Phase 25 (mesuré, non estimé)

Date : 2026-09-26 02:46 CET · hôte Pop!_OS local.

| Métrique | Résultat |
|---|---|
| cold_start | 0.19s — import+init in 0.2s model=gemma4:12b |
| fast_path_reflex | 0.04s — miss 0.001s / greeting-hit 0.015s |
| routing_inference | 3.839s — 3.7s total, 8.0 tok/s (eval 20 tok) |
| tool_exec_bash | 0.012s — 12ms |
| sandbox_startup | 0.353s — 0.2s (create+exec, conteneur réel) |
| memory_retrieval | 0.004s — 1ms turns=10 |
| ws_greeting_turn | 0.029s — 0.03s greeting turn |
| footprints | 0.11s — server-rss=0.11GB host-ram=32.2% vram=11052, 12288 |

Notes : le fast-path salutations répond en millisecondes (pas de LLM) ;
l'inférence locale domine tout tour LLM ; le sandbox inclut create+exec.
Aucune optimisation appliquée — mesure d'abord (règle master).
