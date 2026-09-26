# THREAT_MODEL — Genio (30 articles §37, synthèse opposable)

Acteurs : opérateur (TRUSTED_USER), modèle local (non-autorité), contenu
externe (UNTRUSTED : web, docs, tool outputs, API), réseau local, cloud
conditionnel, hôte physique.

| # | Article | Statut |
|---|---|---|
| 1 | Sandbox fallback hôte | FERMÉ en strict (SANDBOX_UNAVAILABLE) |
| 2 | Limites blocklist bash | Couche structurée primaire + blocklist profondeur |
| 3 | Interpréteurs arbitraires | -c avec payload dangereux bloqué ; reste = risque accepté documenté |
| 4 | Socket Docker | Bloqué (args + volumes + privileged/pid-host) |
| 5 | FS hôte | Boundary realpath + scopes |
| 6 | Egress réseau | Libre en dev ; conteneur `none`/allowlist ; pas de allowlist globale serveur (limite) |
| 7 | Auth WS | Clé/Bearer (query `token` préféré, `key` legacy) ; nonces 32hex |
| 8 | Clés API | Env uniquement ; jamais en URL (sauf legacy `?key=`, à déprécier) ; Bearer 15min |
| 9 | Uploads | Magic + quota + TTL + 0o600 ; pas de limites MIME illusoires |
| 10 | Fuite secrets | Sanitizers (client, telemetry, logs) + 7 784 redactions historiques |
| 11 | Injection prompt | Labels + détecteur EN/FR/AR + garde anti-élévation |
| 12 | Poisoning mémoire | Quarantaine externe + confiance + provenance + expiration |
| 13 | Actions destructrices | Capabilities CRITICAL + confirmation (moteur) ; os.* non exécutés sans gate |
| 14 | Computer-use | Kill + rate + coords + caps |
| 15 | Browser | SSRF + isolation + UNTRUSTED |
| 16 | Self-healing privesc | Transactions workspace-scopées + policy ALLOW explicite |
| 17 | Tool Forge RCE | Gated `GENIO_TOOL_FORGE` + capability ADMINISTRATIVE + tests RCE existants |
| 18-19 | Sessions | Isolation par session_id (store + contextes browser) ; pas de cross-read |
| 20 | Épuisement ressources | Budgets tour + quotas conteneur + timeouts |
| 21 | Supply chain | Lockfiles + audit prod 0 high/critical ; dev highs documentés |
| 22 | CI masking | Banni (pipeline réécrit, 0 `|| echo`) |
| 23 | Artefacts générés | Staging + scans ; SW precache sans three/GLB |
| 24 | Legacy | `genio_executive_core` isolé (2 tests en échec documentés, hors runtime) |
| 25 | Registres dupliqués | 7 registres canoniques, sources uniques |
| 26 | Fallback modèle | Cooldown + gate cloud explicite |
| 27 | Fuite cloud | `GENIO_ALLOW_CLOUD` défaut fermé |
| 28 | Bypass kill-switch | Registre Popen + gate `invoke()` + re-arm explicite requis |
| 29 | Intégrité audit | JSONL append-only + ring borné + scrub |
| 30 | Rollback | Prouvé par comparaison d'octets (tests) |

Limites résiduelles : voir SECURITY.md + GENIO_INTEGRATION_READINESS.md.
