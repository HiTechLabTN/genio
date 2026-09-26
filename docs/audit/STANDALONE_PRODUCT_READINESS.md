# STANDALONE_PRODUCT_READINESS — clean-room gate (evidence-first)

Repository: HiTechLabTN/genio · Branch: main · Base SHA: `17643ac`
(+ gate commits below). Date: 2026-09-26. Host: Pop!_OS x86_64 (dev
machine also hosting the reference services — port conflicts EXPECTED
and used as detection proof).

## Standalone status — PASS (prouvé, pas déclaré)

- No `/genio`, no PYTHONPATH, arbitrary CWD (`/tmp`, `/tmp/cleanroom/work`),
  env `-i` minimal : CLI + doctor + install + API + WS + tests OK.
- No sibling : installed code never touches `webapp/backend` (guarded
  insert + try/except legacy, grep-proven) ; clean prefix venv boots API.
- CWD independence : `installer/genio` self-locates via `__file__` ;
  product launched with explicit `cwd=repo` (uvicorn) / `cwd=repo`
  (pytest). No installed package (documented LIMITATION) — all launch
  vectors pin CWD (systemd WorkingDirectory, Docker WORKDIR, installer).

## Clean-room result — PASS

Isolated HOME/CWD/env, `git clone file://` (obtain), `install --prefix
/tmp/cleanroom/prefix --api-port 18000 --web-port 18098 --yes` :
manifest `6af7ee6f`, commit `17643ac`, frontend PASS (npm ci+build),
post-install import verify PASS.

## Fresh installation result — PASS

API `:18000` /health 200 (prefix venv, clean env) ; telemetry 200 ;
WS Darija greeting live ; 37 security tests passed on installed code ;
live container sandbox OK (`CLEAN_SANDBOX_OK`, HOST_EXECUTION=0).

## Existing installation discovery — PASS

`install --check` enumerated system services + docker images/containers,
refused to choose, exit 0. Single-healthy rule returns
already-installed (exit 11) ; multi-trace returns reconcile plan.

## Duplicate prevention — PASS

No second installation created in any path (unit-tested + live).

## Repair — PASS (live)

Deleted `.env` → diagnosis DEGRADED → backup → `.env` regenerated,
user `data/notes.txt` preserved byte-for-byte.

## Update — PASS (live)

`update --to HEAD` : fetch → checkout → import-verify → manifest
`17643aced... -> 17643ac`, backup recorded.

## Rollback — PASS (live + unit)

`rollback` restored backup (commit + config) ; unit cycle
backup→mutate→restore green.

## Uninstall — PASS (live)

`uninstall --yes` removed code/venv/config, preserved `data/`
(`notes.txt` intact). `--purge-data` path coded, NOT exercised live
(by design — never delete user data in a proof).

## Doctor — PASS

25 checks, vocabulary PASS/WARN/FAIL/NOT_APPLICABLE, exit 17 on FAIL.
Live: correctly reported occupied dev ports with PID/process/service,
missing API pre-start (FAIL, honest), all-green post-start items.

## Dependency detection — PASS

Required/recommended/optional split ; venv honesty fix (real creation
probe, not `--help`) ; missing required → exit 13, never silent.

## Port detection — PASS

Occupied ports identified (pid/process/systemd unit), never killed ;
overrides persisted to `config/ports.json`.

## Permissions — PASS

euid/sudo/writability reported ; systemd install requires root/sudo
or clean refusal with hint.

## Python packaging — LIMITATION (documentée)

No installable package (no pyproject) ; CWD pinned per launch vector.
Recommandation phase suivante : paquet réel. Pas de RED : tous les
modes supportés pinnent explicitement le CWD (prouvé depuis /tmp).

## sys.path audit — PASS

Product: 2 self-rooted inserts + 1 conditional sibling (guarded,
documented). Tests: self-rooted. PYTHONPATH blocked in sandbox env.

## Sibling dependency audit — LEGACY TEST DEPENDENCY + DEBT

`darija_rewriter/media_steps/llm_utils/ghost_utils` : used ONLY by
legacy `genio_executive_core` (never by runtime — grep-proven) ;
13 legacy tests deselected nominatively ; runtime sovereign unaffected.
Standalone operation WITHOUT sibling PROVEN by this clean-room
(API+WS+security+sandbox on prefix with zero sibling path).

## Docker — PASS (avec LIMITATION)

Image 314MB reproductible ; `.env` + `*token*` case-variants prouvés
absents (`docker run` probes ×3) ; requirements pinnés ; correct
WORKDIR/ENTRYPOINT. LIMITATION : root user, pas de HEALTHCHECK
(recommandations, pas de changement d'archi dans ce gate).

## systemd/service — PASS (limité honnêtement)

Template hardened (NoNewPrivileges, ProtectSystem=strict, chemins
explicites) ; installation sudo-only explicite ; enable/start restent
manuels. Units NON installées en clean-room (hôte partagé — déclaré).

## Security — PASS

123/123 suites rejouées ; boot-guard + cloud-closed + sandbox + API
re-vérifiés sur le code installé (37 tests) ; `.env` 0600 ;
install.log secret-scrubbed (testé).

## Sandbox — PASS

Fail-closed live (rc 125) + container live depuis le prefix.

## Frontend — PASS

Build reproductible (npm ci + tsc + build, dist/index.html+sw.js) ;
tous les assets référencés trackés (3 png latents ajoutés avec
exceptions ciblées) ; composants morts documentés (dette, pas de RED).

## Voice — LIMITATION (honnette, inchangée)

TTS prouvé sur service dev (`auto` 200 wav, `ar` 422) ; non réinstallé
en clean-room (composant optionnel, GPU partagé) → NOT_APPLICABLE
pour le prefix, déclaré (pas de faux vert).

## Model — PASS

Ollama détecté comme service externe partagé ; router : cloud fermé
par défaut, UNAVAILABLE honnêtes. Pas de modèle embarqué (déclaré).

## Persistence — PASS

`data/` survit à repair/update/rollback/uninstall (prouvé live).

## Restart/recovery — PASS (partiel honnête)

API restartée manuellement (setsid) après kill involontaire ;
update-rollback automatique prouvé ; systemd non exercé en clean-room
(déclaré, template relu).

## CI — PASS

Job `installer` ajouté (tests déterministes + smoke CLI CWD=/tmp,
PYTHONPATH vide) ; lint couvre `installer/` ; 0 masking.

## Documentation — PASS

`docs/install/{INSTALLATION,RECOVERY,TROUBLESHOOTING}.md` conformes
aux comportements prouvés (quickstart corrigé + `.env.example`).

## Known limitations (7)

1. Pas de paquet Python installable (CWD pinné par vecteur).
2. Image Docker root + sans HEALTHCHECK.
3. Voice non réinstallée en clean-room (optionnel, GPU partagé).
4. systemd non exercé en clean-room (hôte partagé).
5. `--purge-data` codé mais non exercé live (sécurité).
6. Update exige un checkout git (sources `copy` → réinstall).
7. Réseau requis pour pip/npm (mode offline : WARN, pas de fallback).

## Release blockers — AUCUN

## Final verdict — voir INSTALLER_READINESS_MATRIX.md
