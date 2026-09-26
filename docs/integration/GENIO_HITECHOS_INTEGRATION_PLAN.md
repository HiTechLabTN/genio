# GENIO × HI-TECH-OS — Integration Plan (cible, pas d'exécution)

> Statut : PLAN. Aucune intégration exécutée (décision release : ne pas
> fusionner après le gate). Ce document définit les frontières pour que
> l'intégration future ne duplique aucune responsabilité.

Cible :

```text
HiTech-OS
|-- OS / NixOS
|-- Hardware
|-- System services
|-- Telemetry
|-- AI inference daemon
|-- Genio Runtime
|   |-- cognition
|   |-- memory
|   |-- planner
|   |-- tools
|   |-- capabilities
|   |-- policy
|   |-- sandbox
|   |-- skills
|   |-- orchestration
```

## 1. Process boundaries

- Genio tourne comme **runtime utilisateur isolé** (UID dédié, jamais root,
  jamais PID 1). HiTech-OS ne `fork()` jamais Genio dans un service système ;
  Genio ne gère jamais le cycle de vie d'un service OS directement (voir §8).
- Communication exclusive via IPC (§2). Aucun import croisé de code interne :
  l'intégration est **adapter-based** (`genio/integrations/hitechos/`,
  protocole v1.0 vérifié).

## 2. IPC

- Transport : Unix Domain Socket `/run/hitechos/ai.sock` (datagrammes JSON
  versionnés `hitechos/1.0`, `request_id` corrélé, timeouts + reconnect +
  file de requêtes concurrentes — contrat déjà testé).
- L'OS expose : inference, telemetry-bus, lifecycle, policy-push.
  Genio expose : prompt-turn, tool-result, health, telemetry-scrubbed.
- Aucune donnée non scrubbed ne traverse (§7).

## 3. Authentication

- Socket UDS : credential-passing (SO_PEERCRED) — seul l'UID Genio parle au
  daemon ; pas de Bearer sur UDS.
- HTTP/WS Genio (s'il reste exposé) : `GENIO_ENV=prod` + `GENIO_API_KEY`
  obligatoire au boot (garde vérifiée RC 29.2), Bearer TTL 15min.
- Rotation : clés via variables d'environnement, jamais en repo.

## 4. Capability model

- Référence : `genio_server/core/registries.py` (ToolDescriptor frozen).
- L'OS peut **demander** une capability (`capability.requested`) ; Genio
  l'**accorde** après policy (§5). L'OS ne s'auto-attribue jamais de droit.
- Les capabilities `os.*` destructrices restent gatées confirmation
  (`GENIO_CONFIRM_TIMEOUT=120`).

## 5. Policy model

- Référence : `core/policy_engine.py` (binaire ALLOW/DENY/ESCALATE).
- HiTech-OS peut pousser une **policy d'entreprise** (JSON signé) qui ne peut
  que **restreindre** (jamais élargir) la policy Genio.
- Conflit = DENY + audit (fail-closed).

## 6. Inference API

- Backends : LOCAL → OLLAMA → HI-TECH-OS → CLOUD(opt-in `GENIO_ALLOW_CLOUD=1`).
- Le daemon d'inférence OS devient le backend `HITECH-OS` (même taxonomie,
  mêmes gates de confidentialité : pas de fuite cloud silencieuse).
- Timeouts/annulation hérités du router (`GENIO_MODEL_TURN_TIMEOUT`).

## 7. Telemetry

- Seule la télémétrie **scrubbed** (clés, tokens, cookies, secrets FS/env
  supprimés — scrubber testé) remonte au bus OS.
- Métriques utiles conservées (latences, budgets, décisions policy).

## 8. System tools

- Adaptateurs `os.*` : lectures réelles libres ; `restart/update/rollback/
  poweroff/network/device` = lectures proposées → **l'OS décide et exécute**,
  Genio ne fait que recommander via DAG validé + compensations.
- Principe : Genio orchestre, l'OS opère. Aucune opération destructive
  sur simple demande LLM.

## 9. Lifecycle

- États Genio : `boot → ready → halted (kill) → rearmed`.
- L'OS peut ordonner `halt` (kill-switch préemptif, enfants tués) ;
  `rearm` toujours **explicite** (jamais auto).
- Genio signale `ready/health` sur IPC au démarrage.

## 10. Startup ordering

1. OS/NixOS → hardware → services système.
2. Daemon d'inférence (+ modèle warmé).
3. Socket `/run/hitechos/ai.sock` disponible.
4. Genio Runtime (attend le socket avec timeout, dégrade en LOCAL seul
   si absent — jamais de crash boot).

## 11. Failure handling

- Panne daemon inférence → fallback LOCAL/OLLAMA, turn dégradé signalé.
- Panne socket → file locale + retry exponentiel, pas de perte de turn.
- Kill pendant opération → arrêt préemptif vérifié (RC 29.14), état
  transactionnel restauré (§12).

## 12. Rollback

- Référence : `genio_server/core/healing.py` (checkpoint → diagnostic →
  policy → réparation → tests → health → commit, rollback prouvé).
- Mise à jour Genio ratée → l'OS restaure le snapshot précédent
  (NixOS generation ou snapshot FS) ; Genio revalide `health` avant `ready`.

## 13. Update strategy

- Genio : releases taggées + lockfiles (`requirements.lock`,
  `package-lock.json`) ; staging `export/staged_releases/` + checklist Drive.
- Modèles : versionnés par digest (pas `latest` flottant en prod).
- Fenêtre de maintenance OS ; pas d'auto-update silencieux du runtime.

## 14. Resource governance

- Budgets Genio enforced : `MAX_ITERATIONS=5`, `TURN_BUDGET=600s`,
  `TOOL_TIMEOUT=120s`, `MODEL_TURN_TIMEOUT=120s`, `MAX_TOOL_CALLS=10`,
  `MAX_TOKENS=8000` (tests d'épuisement RC 29.18).
- OS : cgroup (512m/pids/CPU/RO équivalent systemd) + quota VRAM partagée
  LLM/TTS (contention documentée RC : planifier l'éviction, pas le partage).

## 15. Hardware permissions

- GPU : arbitrage OS (un seul résident lourd à la fois ou partition) ;
  Genio déclare ses besoins (LLM ~6GB, TTS ~4GB, cap 3.2GB).
- Micro/caméra/écran (computer-use/STT) : permission explicite par session,
  révocable (kill), auditée.

## 16. Security boundaries

- Synthèse : sandbox strict sans exécution hôte en échec (RC 29.3) ;
  FS realpath-avant-autorisation ; anti-SSRF ; uploads magic+quota ;
  mémoire isolée par session ; injection neutralisée (labels+sanitizer) ;
  secrets hors repo (scan RC propre) ; boot strict exige clé.
- L'OS ne contourne jamais ces frontières « pour le confort » : toute
  exception = finding CRITICAL → NOT_READY.
