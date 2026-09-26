# TESTING — stratégie et inventaire (implémentation)

## Lancer
```bash
python3 -m pytest tests/ test_*.py -q        # ~300 tests, ~2min (+Ollama pour E2E)
```
CI : `.github/workflows/ci.yml` — lint ruff bloquant → typecheck tsc →
tests → audit prod → build → smoke. Zéro `|| echo`, deselects nominatifs
documentés (2 legacy `test_genio_core`).

## Inventaire `tests/` (phases)
runtime(14) · capabilities(7) · policy(9) · sandbox(4) · bash(7) · fs(8) ·
computer(9) · browser(7) · injection(9) · memory(12) · router(8) ·
hitechos(6) · os-tools(6) · telemetry(6) · kill-hard(4) · healing(6) ·
dag(8) · api-security(8) · upload(7) · deps(4) · adversarial(5) ·
governance(9) · observability(5).

## Conventions
- Réel > mocké : exécutions (echo/sleep/docker/navigateur/socket), horloges
  et timeouts vrais ; subprocess isolé quand un test polluerait la loop.
- Scripted-turns documentés pour la logique de boucle (pas de LLM en CI).
- Aucun test ne mute l'état global sans restaurer (leçon Phase 23 :
  `os.environ` au niveau module banni — fixtures `monkeypatch`).
- Échecs = HALTE + fix racine (gates ci-dessous), jamais de skip silencieux.
