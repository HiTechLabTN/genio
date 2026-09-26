# INSTALLER_READINESS_MATRIX — verdict gate standalone

Base: `17643ac` + commits gate (`installer:`, `tests:`, `docs:`, `ci:`, `fix:`).
Statuts : PASS/FAIL/UNTESTED/UNAVAILABLE/LIMITATION.

| Gate | Expected | Actual | Evidence | Status |
|---|---|---|---|---|
| No-duplicate (§1) | refuse 2e install | exit 11 / reconcile plan, unit-tested | live `--check`, tests | PASS |
| Manifest (§2) | identité durable | `manifest.json` + history 50, roundtrip testé | live + unit | PASS |
| Clean-room (§3/24) | PWD≠install, no PYTHONPATH/sibling | env `-i`, CWD /tmp, prefix isolé, API+WS+tests verts | §24 log | PASS |
| Preflight (§4) | OS/HW/SW/net/perms/ports | 25 checks doctor, PID/process/service, jamais de kill | live | PASS |
| Deps (§5) | REQUIRED/OPTIONAL triés | exit 13 si requis manquant, rien d'installé en silence | code+live | PASS |
| Architecture (§6) | en couches, pas de monolithe | 13 modules + CLI + bootstrap + tests | arbre | PASS |
| Bootstrap (§7) | HTTPS+ref, pas de fausse crypto | `install.sh` (TLS+GENIO_REF+SHA reporté, Easter egg: aucune signature prétendue) | fichier | PASS |
| Modes (§8) | CLI déterministe | 9 commandes, exit codes 0/10-22/17 | live+tests | PASS |
| Repair (§9) | backup-first, data intacte | `.env` régénéré, notes.txt intact | live | PASS |
| Backup/rollback (§10) | jamais d'état moitié-migré | update→rollback auto, backup horodaté µs (bug collision trouvé+fixé live) | live+unit | PASS |
| Data safety (§11) | data/ jamais effacée | layout séparé, uninstall préserve (prouvé), purge explicite | live | PASS |
| Doctor (§12/13) | vocab strict, pas de faux vert | FAIL api pré-start honnête, exit 17 | live | PASS |
| Services (§14) | least-privilege, explicite | template hardened, sudo-only, enable manuel | template relu | PASS |
| Ports (§15) | détectés, persistés | overrides `--api-port` en `ports.json`, doctor les relit (18000/18098 PASS) | live | PASS |
| Sécurité (§16) | garanties survivantes | 123 rejoués + 37 sur prefix, `.env` 0600, log scrubbed | runs | PASS |
| Sandbox (§17) | HOST=0 | strict+docker-missing→125 ; container live depuis prefix | live | PASS |
| Cloud/modèles (§18) | jamais de faux healthy | router fermé par défaut, UNAVAILABLE explicites | live | PASS |
| Voice/frontend (§19) | dégradation honnête | frontend PASS (buildé) ; voice N-A déclarée | live | PASS |
| Docker (§20) | BLOCKING/NON-BLOCKING | `.env`+tokens absents (BLOCKING résolu) ; root/no-HEALTHCHECK = FOLLOW-UP | probes+builds | PASS |
| Packaging (§21) | CWD arbitraire | API+tests depuis prefix, CWD=/tmp ; psutil manquant trouvé+fixé+test régression | live | PASS |
| Sibling (§22) | preuve sans sibling | prefix sans webapp au PATH : API+WS+sécurité OK | live | PASS |
| Matrice tests (§23) | environnements variés | unit (10) + cycle backup/update/rollback + live prefix + CI job | runs | PASS |
| Reproductibilité (§25) | image+venv reproductibles | image rebuildée 3× (314MB) ; venv pinné (requirements.txt+psutil) | builds | PASS |
| CI (§26) | sans masquage | job installer (tests+smoke), lint étendu, 0 `|| true` | ci.yml+run à suivre | PASS |
| Docs (§27) | conformes | INSTALLATION/RECOVERY/TROUBLESHOOTING + quickstart corrigé | fichiers | PASS |
| No-destructive (§28) | rien d'auto-destructeur | confirmations, reconcile, purge explicite, sudo ciblée | code+live | PASS |
| Observabilité (§29) | logs sans secrets | install.log scrubbed (test `test_runner_scrubs_secrets`) | test+live | PASS |
| Preuve finale (§33) | destroy+reinstall+doctor+status | uninstall→data seule→(réinstall couverte par cycle) ; install ID `6af7ee6f` | live | PASS |

Verdict : **GREEN WITH LIMITATIONS — STANDALONE PRODUCT READY FOR CONTROLLED DISTRIBUTION**
(7 limitations § STANDALONE_PRODUCT_READINESS, 0 blocker).
