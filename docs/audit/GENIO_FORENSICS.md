# GENIO_FORENSICS — Phase 0 Repository Forensics

Date : 2026-09-25 · Host : Pop!_OS local · Méthode : lecture code + commandes live.
Règle : AUCUNE modification du repo pendant cette phase (seule création `docs/audit/` requise).
VS Code branch : `M` = modifié non commité (travail sessions précédentes, listé §12).

## 1. Repository inventory (compté, hors node_modules/.venv/dist)

| Langage | Fichiers |
|---|---|
| Python (.py) | 833 |
| TypeScript React (.tsx) | 49 |
| TypeScript (.ts) | 28 |
| JavaScript (.js) | 20 |
| Shell (.sh) | 5 |
| Tests (`test_*.py` racine) | 21 fichiers |
| CI (`.github/workflows/`) | ci.yml, release.yml, release-binaries.yml |
| Docker | Dockerfile.web, docker-compose.yml, docker-compose.prod.yml |

Répertoires clés : `genio_server/` (serveur+agent), `core/` (router), `genio/`
(adapters/skills compilés), `genio_client/` (React+PWA), `web/` (HUD :8080),
`engines/voder/` (voix, clone depth-1 + venv), `genio_gestures/` (composer+DB),
`genio_harness/` (venv serveur), `state/` (sessions.db), `sandbox/`,
`deploy/` (bootstrap_hitech_os.sh), `scripts/` (dont `genio-probe`),
`export/staged_releases/`, `reports/`, `training/`, `content/`, `electron/`,
`local_workspace/`, `media/`, `docs/` (branding, pas d'ARCHITECTURE/SECURITY).

Git : repo valide (`true`), HEAD `14de430`. Worktree sale (§12).

## 2. Subsystem map

| Sous-système | Localisation | Rôle |
|---|---|---|
| Agent loop ReAct | `genio_server/core/agent_loop.py` (~700 lignes) | boucle thought→tool→result, max 5 itérations, kill switch, trajectory compiler |
| Persona souveraine | `agent_loop.py:SYSTEM_PROMPT` (+ alias `GENIO_SOVEREIGN_SYSTEM_PROMPT`) | source unique ; `adaptive_gateway.py` = alias importés |
| Anti-leak | `sanitize_for_client` branché sur 3 yields | strip Thinking/Genius/HiTech-latin + lexique EN→arabe + drop lignes latines |
| Model router | `core/model_router.py` | ollama-primary/backup (11434), gemini, openrouter ; turn_timeout 120s (env `GENIO_MODEL_TURN_TIMEOUT`) |
| Reflex fast-path | `genio_server/core/reflex_engine.py` | intents (greeting instantané <1s, health, ls, kill…) + skills compilés |
| Tools | `genio_server/tools/` bash/browser/computer/api/social/forge + safety + session_container | exécution outillée, sandbox par conteneur |
| Session store | `genio_server/core/session_store.py` → `state/sessions.db` | fenêtre 10 turns + summary ; fix INSERT OR IGNORE (lignes parent) |
| Gestures | `genio_gestures/` + `gestures.db` (:8001 composer) | plans gestuels, cache, audit 200 lignes |
| Self-improve | `genio_gestures/self_improve.py` | scoring déterministe 0.5/0.3/0.2, skills → `genio/core/compiled_skills/` (20) |
| Voix VODER | `engines/voder/` (QwenTTS + `voder_service.py` :5050) | clone vocal, filtre Jarvis, streaming wav |
| STT | `genio_server/server/voice_pipeline.py` + `POST /api/v1/voice/transcribe` | faster-whisper (fallback CPU), gate `GENIO_AUDIO_PIPELINE=1` |
| Client web | `genio_client/` (React 3D→2.5D, PWA workbox) | chat FAB, accordéons thought/tool, TelemetryBar, CinematicAvatar |
| HUD | `web/server.py` (:8080) | télémétrie + page vitrine |
| Tunnel | cloudflared `a60a1b27` (systemd) | genio.hitech.tn→:8098, /ws+​/api→:8000, store→:8095, wattouna→:8004 |

## 3. Runtime entry points

| Entrée | Commande / unité |
|---|---|
| API+WS | `genio.service` : `uvicorn genio_server.server.main:app :8000` (venv harness) |
| Web UI | `genio-web.service` : `vite preview dist :8098` |
| Voix | `voder-5050.service` (enabled) + instance setsid courante :5050 |
| Gestures | `genio-gestures.service` :8001 |
| Patrouille | `midnight-patrol.timer` → 03:00 (`midnight-patrol.service`, oneshot) |
| CLI probe | `scripts/genio-probe` |
| Bootstrap | `deploy/bootstrap_hitech_os.sh` |

## 4. Services / ports / sockets (mesuré `ss -ltnp`)

`0.0.0.0:8000, 8001, 8004, 8095, 8098, 11435, 4096` · `*:11434` · `127.0.0.1:5050`
· `:9222` (Chrome CDP manuel, audit). Aucun Unix socket applicatif
(`/run/hitechos/ai.sock` et `/run/genio/genio.sock` : NON IMPLÉMENTÉS —
contrat Phase 14 à créer).

## 5. APIs & WebSockets (`genio_server/server/main.py`)

`GET /` · `/health` · `/api/v1/status` · `/api/v1/safety` (GET+POST) ·
`/api/v1/telemetry` (SSE) · `/api/v1/system/telemetry` (JSON scrubbed) ·
`/api/v1/analytics` (POST stub) · `/api/v1/motion/recommend|record` (stubs) ·
`/api/v1/sessions/{sid}` · `/api/v1/voice/transcribe` (×2 définitions —
DUPLICAT à nettoyer Phase 2) · `WS /ws/agent` (prompt/kill/rearm/ping/…)
Auth : `require_key` (ouvert si `API_KEY` vide — état actuel) ; CORS allow-list
explicite (+origines UI). Uploads voix : multipart (transcribe), artifacts
client d'autrui : à auditer Phase 20/21.

## 6. Model providers

Local : Ollama 11434 (`gemma4:12b` + 15 autres tags) + router 11435.
Cloud (conditionnels) : Gemini (clé serveur), OpenRouter (si clé), modèles
`:cloud` via Ollama (minimax/glm/qwen-coder/nemotron). Failover avec cooldown ;
pas d'envoi silencieux documenté côté code (failover explicite, à verrouiller
par policy Phase 5/13).

## 7. Credentials / secrets (classes constatées, AUCUNE valeur reproduite)

- `.env` racine (clés tierces) : NON commité (absent de `git ls-files`) ✓.
- `engines/voder/HF_TOKEN.txt` + `src/HF_TOKEN.txt` : COMMITÉS mais
  placeholders (`# Paste…`, 155/210 octets) — pas de fuite active ; hygiène à
  corriger (gitignore + rotation si un vrai token y a transité).
- `auth.json` opencode + tables `credential/account` : hors repo ✓.
- Règle repo : aucun Bearer/sk-/ghp- en clair dans le code audité (7 784
  redactions appliquées à l'export mémoire historique).

## 8. Filesystem / network / browser / computer-use / shell / containers

- FS : outils bash sans scope codifié (blocklist `is_dangerous` — défense en
  profondeur seule) ; conteneurs par session (`session_container.py`) ;
  workspace `state/session_workdirs/` (Phase C tests) → audit Phases 6/7/8.
- Réseau : sortant libre (curl Cloudflare/Drive OK) ; pas d'allowlist globale
  côté serveur ; tunnel entrant = seul ingress public.
- Browser : `browser_tool.py` (Playwright headless) ; contenu traité comme
  texte DOM (pas de labels de confiance — Phase 10/11).
- Computer-use : `computer_tool.py` (pyautogui/mss) + kill switch ; rate-limits
  à vérifier Phase 9.
- Shell : `bash_tool.py` via `invoke()` + `is_dangerous` ; conteneur si
  `GENIO_SANDBOX_MODE=container` (défaut hôte — Phase 6 P0).
- Skills compilés : `genio/core/compiled_skills/` (20 JSON) +
  `state/skills_library/patterns.json` (non tracké `??`).

## 9. Memory persistence

`state/sessions.db` (sessions+messages, fenêtre 10) · `genio_gestures/gestures.db`
(200 lignes) · `state/skills_library/` · Drive
`/data/hitech_store/storage/agents/{opencode,genio,claude,shared}/`
(export 237 sessions redactées + index). Pas de couches Working/Episodic/
Semantic/Procedural distinguées (Phase 12) ; pas de niveaux de confiance
ni de protection anti-empoisonnement.

## 10. Telemetry / update / deploy

- Télémétrie : SSE + JSON scrubbed + bar UI 3s ; events structurés
  agent.started/completed… PARTIELS (Phase 16 à compléter) ; CoT jamais exposée
  (sanitizer) ✓.
- Update : `lib/updater.ts` (Tauri) + `package_release.sh` ; pas de rollback
  immuable documenté (Phase 18, contrainte HiTech-OS).
- CI : workflows présents (contenu à auditer Phase 23 — vérifier absence de
  `|| echo warnings only`).

## 11. Trust boundaries & attack surface (résumé)

Frontières : navigateur↔tunnel↔:8098 (statique) · :8000 API/WS (clé optionnelle)
· boucle agent↔outils (sandbox conteneur optionnel, hôte par défaut) ·
mémoire SQLite mono-fichier · VODER :5050 localhost (sans auth).
Surface : 14 routes HTTP + 1 WS, uploads (voix/artifacts), computer-use,
browser headless, tool forge (gated `GENIO_TOOL_FORGE`), auto-fix réflexe,
compilation de skills auto, pickup de prompts par env. Détail article par
article : §37 du prompt → traçabilité Phases 6-11.

## 12. Worktree sale au 2026-09-25 (baseline avant phases suivantes)

Modifiés : `README.md`, `core/model_router.py`, `engines/voder/voder_service.py`,
12 skills compilés, + inconnus tronqués (`git status --short` complet à
relever en début de Phase 2). Non trackés : `chat_with_genio.py`,
`CinematicAvatar.tsx`, `TelemetryBar.tsx`, `state/skills_library/`.
Règle : ne committer que par phases, jamais de secrets ni de poids modèles.
