# GENIO_INTEGRATION_READINESS — RC Final Release Gate (vérifié empiriquement)

> Rule Zero appliquée : aucun chiffre repris d'un rapport antérieur sans
> re-vérification. Commandes, sondes live et preuves ci-dessous.

## Identité release

- SHA : `7331047962ac0cdcf0e1fb30f2bca8d693e9cf15` (avant commit final —
  voir § Final gate pour le SHA de clôture)
- Branche : `main`
- État : dirty assumé = `feedback_memory.json` + `genio_gestures/gestures.db`
  (données runtime d'apprentissage, exclues volontairement des commits) ;
  `docs/audit/PERFORMANCE_BENCHMARK.md` (re-mesuré, à committer).
- Aucun secret commité : scan `API_KEY|HF_TOKEN|OPENAI|ANTHROPIC|GEMINI|
  PASSWORD|PRIVATE_KEY|SECRET|TOKEN` → 0 token réel (faux positifs :
  lectures `os.environ`, `${{ secrets.* }}` CI, code vendored VODER).
- Aucun poids modèle / dump mémoire / log session commité.

## Commandes de référence

- Tests : `python3 -m pytest tests/ test_phase7_routing_kill.py
  test_bash_tool_safety.py test_phase_motion_memory.py
  test_phase1_memory_agent.py test_phase_E_model_routing.py
  test_registries.py test_genio_core.py -q
  --deselect test_genio_core.py::TestPlanning::test_parse_plan_injects_auditor
  --deselect test_genio_core.py::TestEndToEndDryRun::test_pipeline_dispatch`
- Build front : `npm run build` (dans `genio_client/`)
- Lint CI : `python3 -m ruff check genio_server/ core/ config.py
  tests/test_*.py test_*.py` → `All checks passed!`
- Bench : `python3 scripts/benchmark_phase25.py`

## Matrice finale des tests (29.19)

- Run RC : **269 passed, 0 failed, 1 xfailed, 2 deselected**
  (2026-09-26T01:31:38Z → 01:33:29Z, ~110s).
- Les 2 deselects re-exécutés isolément : échec confirmé pour les raisons
  documentées → **LEGITIMATE**, pas de régression cachée :
  1. `test_parse_plan_injects_auditor` : attend l'ancien nœud
     `planning_audit` (API `genio_executive_core` obsolète ; le DAG
     canonique est couvert par `tests/test_action_dag.py`).
  2. `test_pipeline_dispatch` : exige Ollama `mistral:7b` live
     (`Critical service(s) down`) ; résident = `gemma4:12b`
     (routing couvert par `test_model_router.py` + `test_phase_E`).
- xfail unique : pré-existant documenté (`test_phase_C`).

## Services runtime (sondes live 29.21)

| Service | État | Preuve |
|---|---|---|
| genio :8000 | VERIFIED | `active`, `/health` 200, 14 routes API + 1 WS comptées |
| genio-web :8098 | VERIFIED | `active`, `/app` 200, tunnel `/`+`/app` 200 |
| voder :5050 | VERIFIED | unité `active` (redémarrée), `/health` 200 |
| gestures :8001 | VERIFIED | `/health` 200 |
| ollama :11434 | VERIFIED | `/api/tags` 200, `gemma4:12b` re-warmé après test |
| genio.hitech.tn | VERIFIED | 200 surface + tunnel API/WS ; `/api/v1/models` 404 =
légitime (route inexistante, pas une panne) |
| WS `/ws/agent` | VERIFIED | greeting Darija reçu live |
| UI | VERIFIED | 200 local + tunnel, composants mascotte intacts |
| STT/VAD/pipeline | VERIFIED | endpoint `/voice/transcribe` + VAD 1.5s (chantier) |
| TTS | VERIFIED (après fix RC) | `auto` → 200, wav 3.76s @24kHz ; `ar` → 422 explicite |

## Sécurité / sandbox (29.2–29.18)

- VERIFIED : boot-guard `strict`-sans-clé refuse le démarrage (4 tests RC,
  `GENIO_ENV=prod` déjà couvert) ; `GENIO_ALLOW_CLOUD` fermé par défaut ;
  Bearer TTL + 401/429/413 ; WS sans clé en URL ; sandbox strict fail-closed
  (7 cas, test automatisé) ; bash 20 classes ; FS realpath-avant-autorisation ;
  injection EN/FR/AR × 7 sources ; mémoire isolée/poison-guard ; computer via
  safety centrale (bypass direct refusé) ; browser anti-SSRF ; kill préemptif
  (live : kill→rearm vérifié) ; healing checkpoint→rollback prouvé ;
  uploads magic+quota ; 6 budgets enforced (tests d'épuisement).
- LIMITATION : défaut global `development` (API ouverte sans clé, sandbox
  opt-in) — la production exige `GENIO_ENV=prod` ou `strict` + clé.

## Trouvailles du RC (corrigées, pas masquées)

1. **VODER `language="ar"`** : Qwen3-TTS ne supporte pas `ar` → 500 silencieux.
   Fix : défaut `auto` + 422 explicite. Re-vérifié (wav réel).
2. **Lint CI-scope** : 6 erreurs post-Phase 23 (fichiers ajoutés après la
   session lint). Fix : `All checks passed!`.
3. **Instance VODER orpheline** (processus du 23/09, unité `dead`) : tuée,
   service redémarré via l'unité.
4. **VRAM** : 11/12GB occupés (ollama 6GB) → OOM TTS initial ; résolu par
   `ollama stop` temporaire + re-warm vérifié après test.

## Performance (re-mesuré 29.24)

`scripts/benchmark_phase25.py` : cold 0.19s, fast-path 0.04s, inférence
3.8s @8.0 tok/s (mieux que 10.9s : modèle warmé — pas une régression),
bash 12ms, sandbox 0.35s, mémoire 4ms, WS greeting 0.03s.
Doc `PERFORMANCE_BENCHMARK.md` régénérée par le script.

## Dépendances / CI / docs (29.25–29.27)

- `requirements.lock` (73 pins) + `package-lock.json` ; `pip-audit` : 0 faille.
- CI : aucun `|| true` / bypass ; lint+tests+build bloquants.
- Docs : 14 `docs/*.md` cohérents (14 routes + 1 WS recomptés, défaut dev
  honnêtement déclaré) ; 30 articles THREAT_MODEL traités.

## Contrat HiTech-OS

Protocole v1.0 + UDS + adaptateurs `os.*` (lectures réelles, destructrices
gatées). Pas de fusion, pas de dépendance dure. Plan d'intégration :
`docs/integration/GENIO_HITECHOS_INTEGRATION_PLAN.md` (16 sections).

## Limitations restantes (assumées)

1. Défaut `development` (voir § Sécurité).
2. TTS sans `ar` natif (via `auto` — comportement documenté, 422 sinon).
3. VRAM TTS 4.0GB > cap 3.2GB ; contention GPU avec LLM résident.
4. Modèles `:cloud` = confiance router (pas d'allowlist).
5. noexec stagings = montage hôte ; egress iptables documenté non appliqué.
6. Lane cloud Gemini = token Google opérateur requis.
7. Approbation UI : payload émis, pas de widget dédié.
8. `systemctl` perd ses réponses D-Bus ici (timeout affiché, opération
   exécutée) — vérification par `systemctl show` systématique.

## Risques non résolus

- Compromission opérateur (clé/machine) hors périmètre technique.
- Jailbreak du modèle local par contenu externe : atténué, non éliminable.
- Supply chain dev-toolchain : highs documentés, jamais shippés.

## Verdict final

**READY_WITH_LIMITATIONS** — 0 finding CRITICAL, suite 269 verte, builds OK,
services live OK, limitations 1–8 documentées ci-dessus.
