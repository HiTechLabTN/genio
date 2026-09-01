# Changelog

Toutes les modifications architecturales significatives du repo Genio sont
documentées ici, par phase.

## Phase 0 — Baseline de sécurité

- **`genio_server/tools/bash_tool.py`** : remplacement de `DENIED_PREFIXES`
  (liste de préfixes facilement contournables) par la fonction
  `is_dangerous(command) -> Optional[str]` qui tokenise chaque segment
  (chevron `&&`, pipe `|`, point-virgule `;`) avec `shlex.split` et refuse :
  - `rm -rf` / `-r`/`-f` ciblant `/`, `/*`, `~`, `.`, `..` ou un chemin hors
    du workdir autorisé ;
  - `dd` sur `/dev/sd*` (via `of=`/`if=`) ;
  - `mkfs.*` ;
  - redirection `>` sur `/dev/sd*` ;
  - `chmod -R 777 /` ;
  - fork bombs (`:(){ :|:& };:`) ;
  - `sudo` (refus par défaut, activable via `GENIO_ALLOW_SUDO=1`).
  - Contournements de l'audit couverts : `sudo rm -rf /`, `rm -rf /*`,
    `bash -c "rm -rf /"`, `cd / && rm -rf .`.
- **Nouveau** `test_bash_tool_safety.py` : 37 cas (refus dangereux + commandes
  légitimes + gardes d'environnement).
- **`genio_server/server/main.py`** :
  - garde de démarrage `GENIO_ENV` (`dev` par défaut) : en `prod`, un
    `GENIO_API_KEY` vide fait échouer le démarrage avec un message explicite ;
  - `allow_origins` passé de `*` à une liste lue depuis `GENIO_CORS_ORIGINS`
    (CSV), défaut `["http://localhost:1420"]` (port Tauri dev).

## Phase 1 — Unification mémoire / agent interactif

- **`core/memory_engine.py`** : nouvelle catégorie de données `session_context`
  (liste de faits projet/utilisateur `{ts, category, text}`), distincte des
  `rules` éditoriales de contenu. Méthodes : `add_context(text, category)` et
  `context_text(limit=20)` (bornée, déduplique les faits consécutifs).
  Aucune modification des règles Darija/SVG existantes (pipeline de contenu
  intact).
- **`genio_server/core/agent_loop.py`** : `build_instructions()` injecte
  `get_memory().context_text()` (le contexte de session, PAS les rules
  éditoriales) dans le system prompt. Paramètre optionnel `memory=` pour un
  test propre ; import de `core.memory_engine` en best-effort avec dégradation
  silencieuse si non résolvable.
- **Nouveau** `test_phase1_memory_agent.py` (4 cas).

## Phase 2 — Checkpointing des sessions (tolérance aux pannes)

- **Nouveau** `genio_server/core/session_store.py` (SQLite via `aiosqlite`) :
  schéma `sessions(id, created_at, updated_at, mode, status, summary)` et
  `messages(session_id, seq, role, content, ts)`. Fonctions :
  `create_session()`, `append_message()` (persistance immédiate), `load_session(id,
  max_history_turns=10)` — cette dernière NE retourne JAMAIS l'historique brut
  complet, seulement les `N` derniers tours + un `summary` compacté.
  Politique de fenêtre obligatoire (mandatory) : prompt final =
  `[system_prompt] + [session_context borné déjà dans system_prompt] + [summary si > N] +
  [N derniers tours bruts]`. Dès que `len(messages) > max_history_turns`,
  les plus anciens tours sont résumés par batch en `sessions.summary`
  (via `summarize_session_batch()` — heuristique extractive capée à 600 chars,
  merge capé à 4000 chars) et les lignes `messages` sont renumérotées
  densément pour garder le compactor correct. Stockage borné par construction.
- **`genio_server/core/agent_loop.py`** : ajout du param `session_id` (+ `store`
  injectable), `summarize_session_batch()`, helpers `_session_store()`,
  `_build_initial_messages()` (reconstitue le prompt selon la windowing policy
  via `build_prompt_from_session`), `_save_message()` ; `run(user_input)` charge
  d'abord la fenêtre bornée puis persiste chaque nouveau message (user/assistant/
  feedback) immédiatement — tolérant aux crash serveur.
- **`genio_server/server/main.py`** : nouvelle route `GET /api/v1/sessions/{id}`
  (historique borné + summary) et action WS `resume` (charge la session
  checkpointée sans jamais renvoyer l'historique brut complet) ; l'action WS
  `prompt` accepte désormais `session_id`.
- **Nouveau** `test_phase2_session_checkpoint.py` (3 cas : crash/resume + fenêtre
  sous budget token explicite + unknown session).

## Phase 3 — Self-healing générique

- **`sandbox/self_healer.py`** : extraction de `GenericHealer` (base avec
  `GENERIC_PATTERNS` : ModuleNotFoundError, ImportError, SyntaxError,
  FileNotFound, NameError, AttributeError, TypeError, ValueError, KeyError,
  IndexError, ConnectionError, ZeroDivision, AssertionError + fallback
  générique). `SelfHealer` hérite de `GenericHealer`, conserve ses 4 patterns
  infra et fallback vers le générique. Toggle via `GENIO_GENERIC_HEAL=0`.
- **`genio_server/core/agent_loop.py`** : `_feedback_for()` append une
  `[HEALER SUGGESTION]` via `GenericHealer` quand `GENIO_GENERIC_HEAL` activé.
- **Nouveau** `test_phase3_generic_healer.py` (6 cas).

## Phase 4 — Tool Forge

- **Nouveau** `genio_server/tools/tool_forge.py` : registre dynamique persistant
  `state/tool_forge.json`, validation du nom (alphanum, pas de conflit
  built-in), `create/list/get/delete/invoke`, `handle()` pour le tool
  `tool_forge`. Toggle `GENIO_TOOL_FORGE=0`.
- **`genio_server/tools/__init__.py`** : ajout du tool `tool_forge` à `TOOLS`,
  `invoke(tool, payload, session_id)` vérifie les tools forgés avant
  l'erreur `unknown tool`, gère `session_id` vers `bash`.
- **Nouveau** `test_phase4_tool_forge.py` (4 cas).

## Phase 5 — Per-session container sandboxing

- **Nouveau** `genio_server/tools/session_container.py` : `exec_in_container()`,
  `_ensure_container()`, `cleanup_container()`, nom `genio-session-<id>`,
  image via `SandboxConfig` / `GENIO_SANDBOX_IMAGE`, fallback local si docker
  indisponible (`sandbox_fallback` + reason). Toggle `GENIO_SANDBOX_MODE=container`.
- **`genio_server/tools/bash_tool.py`** : `run_command(..., session_id)` route
  vers `session_container` quand `GENIO_SANDBOX_MODE=container`.
- **`genio_server/tools/__init__.py`** + `genio_server/core/agent_loop.py` +
  `genio_server/server/main.py` : propagation de `session_id` jusqu'à l'exec.
- **Nouveau** `test_phase5_sandbox.py` (4 cas).

## Phase 6 — Rich artifacts + tolerant WS typing

- **Nouveau** `genio_client/src/components/ArtifactPanel.tsx` : rend les
  artifacts (`code|markdown|image|table|file`), export `artifactsFromChat()`.
- **`genio_client/src/lib/types.ts`** : `ChatEvent` + `GenioEvent` étendus avec
  `artifact`/`session` et fallback `type: string` tolérant (index signature).
- **`genio_client/src/lib/ws.ts`** : `CHAT_EVENT_TYPES` élargi, `isChatEvent`
  tolérant (vérifie type string), `onmessage` ne drop plus les frames
  non-JSON ou sans type — les surface en `error` tolérant, coerce manquant.
- **`genio_client/src/hooks/useGenioSocket.ts`** : gère `artifact`/`session`,
  fallback inconnu → `setChat` (UI ne perd jamais un message).
- **Nouveau** `test_phase6_tolerant_ws.py` (4 cas).

## Phase 7 — Model routing + kill propagation

- **`core/model_router.py`** : `ModelRouter.generate(..., cancel_event)` vérifie
  `cancel_event.is_set()` avant chaque endpoint/tentative (`_check_cancelled`),
  lève `asyncio.CancelledError` si tué, toggle `GENIO_ROUTER_KILL=0`. Propagation
  à `_call_endpoint`.
- **`genio_server/core/agent_loop.py`** : `_chat()` vérifie `cancelled()` avant
  et après l'appel HTTP, lève `CancelledError` si tué.
- **`genio_server/server/main.py`** : WS `kill` propage à tous les
  `_KILL_EVENTS` (global halt), pas seulement la connexion courante.
- **Nouveau** `test_phase7_routing_kill.py` (4 cas).

## Phase 8 — CI/CD

- **Nouveau** `.github/workflows/ci.yml` : jobs `backend` (pytest 8 suites),
  `frontend` (tsc + build), `security` (bash safety + prod guard), déclenché
  sur push `main/develop` et PR `main`.

## 2026-09-01 — Remédiation RCE audit (Phases A-F) — faille tool_forge exec

Preuve d'audit ayant motivé l'ensemble du correctif (reprise telle quelle Phase A) :
```
result = [c for c in ().__class__.__base__.__subclasses__()
           if c.__name__ == "catch_warnings"][0]()._module.__builtins__[
           "__import__"]("os").popen("id").read()
→ shell root obtenu, hors de toute liste noire, hors du conteneur bash.
```

| Phase | Faille | Fichier(s) | Correctif | Test |
|-------|--------|------------|-----------|------|
| A | RCE via `exec()` in-process contournable (builtins restreints) | `genio_server/tools/tool_forge.py:77` `ToolForge.invoke()` `exec(code, {"__builtins__": {...}})` + `genio_server/tools/__init__.py:66` `GENIO_TOOL_FORGE` défaut `1` opt-out | Défaut `1`→`0` opt-in (fail-safe), suppression `exec()` in-process, blocage patterns `__class__/__subclasses__/catch_warnings/__builtins__/popen/os.` avant tout exec, retour `sandbox exec disabled` | `test_phase_A_tool_forge_rce.py:13` (4 cas) reproduit littéralement le payload, vérifie pas de `uid=`/`gid=` |
| B | Exécution forgée non sandboxée (même après blocage, pas de container) | `genio_server/tools/tool_forge.py:88` `_exec_via_container`, `genio_server/tools/__init__.py:66` propagation `session_id` | Route via `session_container.exec_in_container(session_id, f"python3 {script}")` jamais `exec()`, validation smoke-test container avant `state/tool_forge.json`, Q1 Docker dispo partout → si docker absent refuse (pas fallback insecure, commenté) | `test_phase_B_tool_forge_container.py` (3 cas) : RCE bloqué à create, sum légitime via container, bad script non listé |
| C | Conteneur inutilisable : pas de volume, réseau `none` fixe, cwd non persistant | `genio_server/tools/session_container.py:95` `_ensure_container` `--network none` sans `-v`, `config.py:55` `SandboxConfig` sans `allowed_registries` | `-v <state/session_workdirs/<sid>>:/work -w /work` isolé par session (Q2), `SandboxConfig.allowed_registries` + `network_policy=allowlist` → `--network bridge` (allow-list via config, Q2), `_CWD_MAP` + `wrapped rc=$?; echo __GENIO_CWD__` + `cd <cwd> &&` | `test_phase_C_session_volume.py` (4 passed+1 xfail) : cwd `cd sub`→`pwd` `/work/sub`, env xfail, fichier `/work/out.txt` visible hôte, urllib pypi.org via bridge, isolation workdir |
| D | Fuite ressources : conteneurs `genio-session-*` jamais nettoyés | `genio_server/tools/session_container.py:188` `cleanup_container`, `genio_server/server/main.py:513` `finally` WS, `genio_server/server/main.py:127` periodic | `finally` WS nettoie `cleanup_container` + `_CWD_MAP/_LAST_USED` pour `_SESSION_IDS[conn]`, tâche périodique `asyncio` 60s `docker ps` + idle `> GENIO_SESSION_CONTAINER_IDLE_TIMEOUT=1800` (Q3 30min), kill-switch détruit immédiatement (Q3) | `test_phase_D_container_lifecycle.py` (4 cas) : WS close mock `docker rm`, idle avance `last_used+2000>1800` nettoyé, kill immediate, env override |
| E | ModelRouter non branché, kill non propagé (double-check avant/après, pas race) | `genio_server/core/agent_loop.py:305` `_chat` direct `httpx.post`, `core/model_router.py:95` `generate` sans `chat`, `genio_server/server/main.py:217` `/api/v1/status` sans router | `AgentLoop._chat` via `ModelRouter.chat(messages, cancel_event)` Q4 endpoints inchangés, race `asyncio.wait(FIRST_COMPLETED)` `chat_task` vs `_wait_cancel` + `chat_task.cancel()` pour fermer HTTP, `/_telemetry` expose `router` health | `test_phase_E_model_routing.py` (3 cas) : `_chat` direct mock sleep 2s, cancel 200ms → `CancelledError` <1s et flag `was_cancelled` True, sans cancel OK, status expose router |
| F | CI incomplet : `test_genio_core` absent, pas de lint, security n'inclut pas Phases A-E | `.github/workflows/ci.yml:26` backend sans `test_genio_core`, sans `ruff`, security sans Phase A-E | Backend `pytest` inclut `test_phase_A-E` + `test_genio_core -k "not 2 flaky"` + `ruff check` (`python -m ruff`), security `pytest test_bash_tool_safety + test_phase_A-E` | CI vert `33478285161` → `backend` 22s, `frontend` 25s, `security` 14s (après fix `-k dangerous` et `pip install` manquant) |

## 2026-09-01 — Genio v2.1 Architecture & Interface Overhaul (Phases 1-4)

### Phase 1 — Backend async non-bloquant + watchdog d'exécution

- **`genio_server/tools/bash_tool.py`** : nouveau `async_run_command()` via
  `asyncio.create_subprocess_exec` (jamais `subprocess.run` sur le event loop) ;
  `run_command()` synchrone conservé pour rétro-compat ; builder `_result()`
  partagé.
- **`genio_server/tools/session_container.py`** : variantes async
  `async_exec_in_container()` / `async_ensure_container()` /
  `async_cleanup_container()` — tout docker (`run/exec/inspect/rm`, bash `-lc`)
  via `create_subprocess_exec`. Fallback docker absent → `async_run_command`
  (comportement identique au chemin sync, gardes Phase C/D intactes).
- **`core/model_router.py`** : watchdog strict `GENIO_MODEL_TURN_TIMEOUT`
  (défaut `30`s) appliqué à `chat()` ET `generate()` via `asyncio.wait_for` :
  dépasse → log `⏱ ${ep} exceeded turn timeout`, `_mark_failure`, failover au
  endpoint suivant — plus jamais de `THINKING…` figé 120s+.
- **`genio_server/core/agent_loop.py`** : `_feedback_for()` injecte une
  directive de continuation automatique quand un outil retourne exit 0 avec
  sortie triviale (`cat`/`touch`/`mkdir`/`pwd`/`echo -n`) → le modèle exécute
  l'étape suivante du plan au lieu de tomber en idle.
- **Benchmark** : commande `sleep 0.3` sous `async_run_command` = event loop
  reste ouvert (un ticker concurrent continue de ticker) ; timeout watchdog
  ​​`0.05s` sur un mock de 5s → failover en <2s (au lieu de 5s).
- **Nouveau** `test_phase_v2_1_watchdog.py` (4 cas). Suite complète :
  `121 passed, 1 xfailed`.

### Phase 2 — System 1 Reflex Engine & compilation de skills autonome

- **Nouveau** `genio_server/core/reflex_engine.py` : `ReflexEngine` avec
  fast-path déterministe <100ms pour les intents haute-fréquence (system
  health `uptime`+`free`+`df`, list dir, read file, process status, kill pid,
  git status, python version) — zéro token Ollama. Auto-fixes déterministes
  connus : `ModuleNotFoundError: No module named 'X'` → `pip install X`,
  `command not found`, `Permission denied` → commande corrective, résolus
  AVANT la réflexion LLM.
- **Compilateur de trajectoires** `compile_skill()` : un ReAct run à >1 tour
  d'outil se terminant par une vraie réponse est sérialisé en skill
  paramétré (`state/skills_library/patterns.json`) ; replayé via fast-path sur
  prompts identiques/similaires.
- **Intégration loop** : `AgentLoop.run()` évalue `ReflexEngine.match(prompt)`
  AVANT `ModelRouter` ; sur match → `tool_result`+`answer` directs (aucun
  appel LLM). Sur outil en échec → `auto_fix()` appliqué avant retour.
- **Feature flag** : `GENIO_REFLEX_FASTPATH=1` (défaut ON).
- **Benchmark** : audit système fast-path mesuré <100ms, `test_reflex_loop_
  never_calls_ollama` prouve zéro `_chat`.
- **Nouveau** `test_phase_v2_2_reflex.py` (5 cas).

### Phase 3 — Pipeline audio natif Android

- **`genio_server/server/voice_pipeline.py`** (nouveau) : transcribe raw audio
  (WAV/WebM/Opus/M4A) via `faster-whisper` > `whisper`, fallback déterministe
  structuré (jamais de raise). Gated `GENIO_AUDIO_PIPELINE=1`.
- **`genio_server/server/main.py`** : `POST /api/v1/voice/transcribe`
  (multipart `audio` + `language`) → `asyncio.to_thread(transcribe_audio)`.
  WS `voice_wav` (final) transcrit et cache le texte dans
  `_PENDING_TRANSCRIPT[conn]` ; l'action `prompt` suivante préfixe le prompt
  avec ce texte → l'audio brut route dans le ReAct proprement. Nettoyage sur
  déconnexion.
- **`genio_client/src/lib/audio.ts`** : `webkitSpeechRecognition` déprécié
  (non fonctionnel sur WebView Android/Tauri) ; capture prima MediaRecorder
  (blobs raw audio/webm·opus / wav) ; nouveau helper `transcribeAudio(blob,
  apiBase?, apiKey?)` → POST multipart avec `X-API-Key`.
- **Nouveau** `test_phase_v2_3_audio.py` (6 cas) : fallback/whisper routing,
  gate 403 quand désactivé / 200 quand activé, injection transcript dans le
  prochain prompt.

### Phase 4 — Cyber-avatar 3D tunisien & HUD holographique

- **Deps** : `@react-three/fiber`, `@react-three/drei`, `three`,
  `@types/three`, `@mediapipe/face_mesh` installés.
- **`genio_client/src/components/avatar/CyberAvatar.tsx`** (nouveau) : tête
  robotique stylisée avec Chachia (شاشية) cybernétique (bandeau + bec néon),
  accents faciaux lumineux, holo-rim ; morphs idle breathing / listening /
  speaking (mâchoire lipsync) ; look-at pointer + FaceMesh webcam opt-in
  (`faceTrack`, import dynamique découpé en chunk séparé, chargement
  `cdn.jsdelivr.net/@mediapipe/face_mesh`) ; fallback 2D néon si WebGL absent.
- **`genio_client/src/components/avatar/HolographicHud.tsx`** (nouveau) :
  HUD double panneau quand `busy` — gauche Task Matrix (checklist tools
  complétés/pending), droite Telemetry gauges (CPU/RAM/GPU/tokens/s).
- **`genio_client/src/components/Dashboard.tsx`** : avatar centré en idle/chat ;
  sur `busy` → translation+cale vers la top widget bar (`scale 0.35`,
  `top 12px`) avec HUD qui se déploie dessous (spring, stiffness 120/damping 18).
- **Build** : `npm run build` exit 0 (tsc + vite). Chunk warning 3D (≈1.3MB)
  bénin ; `face_mesh` codé-split.

## 2026-09-02 — The Ultimate Genio Mobile Overhaul: Adaptive Gemini Cloud, 3D Cyber-Tunisian Avatar & Native Darija Persona

### PHASE 1: Zero-Config Google Auth & Gemini Integration

- **`src/lib/googleAuth.ts`** (nouveau) : `hasGoogleAuth`/`getGoogleToken`/`setGoogleToken` avec `localStorage` + fallback Tauri Store, `signInWithGoogle` via Tauri `plugin-opener` (system browser) ou GIS `google.accounts.id`, mock token pour CI/build, `signOutGoogle`.
- **`src/components/GoogleAuthOnboarding.tsx`** (nouveau) : modal "Sign in with Google" (Globe/Sparkles, Chrome-less via lucide `Globe`), secure token display, bypass logic — si token existe, `shouldShowGoogleAuth()=false` et `App.tsx` saute directement au Dashboard.
- **`src/lib/providers/gemini_provider.ts`** (nouveau) : `GEMINI_MODEL=gemini-2.0-flash`, `GEMINI_API_BASE`, `streamGemini` (SSE via `streamGenerateContent` + `systemInstruction` Darija persona + `functionDeclarations` mapping `bash`/`browser`/`computer`), mock Darija stream si `mock-*` token (CI), `geminiToGenioEvents`.
- **`src/App.tsx`** : double onboarding `GoogleAuth → PermissionOnboarding`, `isGeminiCloud=hasGoogleAuth()` → `geminiChat`/`geminiStatus` state, `sendPrompt` branché `streamGemini` avec `thought`/`tool_call`/`answer` streaming, `connected` bypass — `isGeminiCloud` affiche `Dashboard` avec `node="Gemini Cloud"` sans passer par `ConnectionHub`.

### PHASE 2: Strict Genio Persona

- **`src/lib/persona.ts`** (nouveau) : `GENIO_PERSONA_PROMPT` hardcodé exact (4 règles Tunisian cyber-identity, NEVER Gemini/Google, Darija + Arabizi, multilingual mix, concise warm technical).
- **`src/lib/adaptiveEngine.ts`** + **`genio_server/core/adaptive_gateway.py`** + **`web/server.py`** : tous alignés sur `GENIO_PERSONA_PROMPT` (remplace ancien Darija arabe), `getDarijaPrompt`/`wrap_with_darija` exposés.

### PHASE 3: High-Fidelity Cyborg & Gaze Tracking

- **Overhaul `CyberAvatar.tsx`** : chassis `MeshPhysicalMaterial` white-ceramic (`clearcoat 1.0`) + chrome (`metalness 0.95`), Chachia crimson metallic `#a11a2f` avec micro-texture + neon torus band + tassel, yeux cyan `emissiveIntensity` pulse + eyelid blink mesh, moustache/beard neon capsules/torus, mâchoire articulée `lip-sync` via `audioLevel` (speaking mode fallback sinus 8Hz), breathing bob `sin(1.35)`, `useFaceTrackingContext` lerp.
- **`src/components/avatar/useFaceTracking.ts`** (nouveau) : front camera `facingMode:user 640x480`, `FaceMesh` `locateFile` CDN, `lerp` 0.18 vers `yaw`/`pitch` (landmarks 1,33,263,199), `FaceLookContext` provider.
- **Dashboard** : `faceTrack` passé `!busy`, `audioLevel` 0.45 busy.

### PHASE 4: UI/UX Layout Fixes

- **`src/components/Dashboard.tsx`** : strict viewport — `Idle` avatar `h-[35vh]` dedicated top avec gradient + grid, chat `h-[65vh]` `overflow-y-auto` + bottom padding ; `Busy` avatar absolute `right-3 top-3 w-28 h-28` corner widget (pointer-events none outer, auto inner), HUD expand `HolographicHud` avec `AnimatePresence`, `z-index`/`pointer-events` fixés (avatar `pointer-events-auto` seul, chat scroll jamais bloqué par Canvas).
- **Verification** : `npm run build` 0, layout scale sans overlap (avatar ne couvre jamais chat).

### PHASE 5: Native Android Audio & Permissions

- **`android-overlay/AndroidManifest.xml`** + **`gen/android/...`** : `CAMERA`, `RECORD_AUDIO`, `INTERNET`, `ACCESS_NETWORK_STATE`, `READ_EXTERNAL_STORAGE` (maxSdk 32), `WRITE_EXTERNAL_STORAGE` (29), `READ_MEDIA_IMAGES/VIDEO/AUDIO`, `MODIFY_AUDIO_SETTINGS` + `hardware.camera`/`microphone` features.
- **`src/lib/permissions.ts`** + **`PermissionOnboarding.tsx`** déjà couverts (checklist launch).
- **`src/lib/audio.ts`** : MediaRecorder raw blobs `WebM/WAV` (déprécié WebSpeech), `transcribeAudio` → Gemini/cloud.

**Build** : `npm run build` exit 0 (2826 modules, `gemini_provider` + `face_mesh` codé-split, 380kB gzip). Dépendances ajoutées : `@tauri-apps/plugin-opener` (déjà), `tsx` (dev, vérif).

## 2026-09-02 — Genio v2.2 Hotfix & UI/UX Overhaul: Midjourney-Fidelity Avatar & Loop Resolution

### PHASE 1: Fix Infinite Thinking Loop & Gemini Mock Leak

- **`src/lib/providers/gemini_provider.ts`** : suppression du fallback mock `Ya ahla... (mock Gemini stream)` — désormais `throw "السيرفر طايح توا، ما نجمش نكوّنكتي."` si `!auth` ou `mock-` token, plus de fuite `systemInstruction` dans `contents` (déjà correct via `systemInstruction: {parts: [...]}`), `fetch` wrappé avec `try/catch` → down message sur offline/5xx, `thinkingStreak` compteur `/* thinking */` >3 consécutifs sans tool/answer → `yield {text: "السيرفر طايح توا...", done:true}` + `reader.cancel()` + `return` (loop breaker).
- **`src/App.tsx`** : `catch` branché pour afficher down message en `answer` (pas `error` leak), `streamGemini` streaming `acc` collapse `thought → answer`.

### PHASE 2: Pixar-Style Midjourney Art Direction

- **`src/components/avatar/CyberAvatar.tsx`** : tenue `red hoodie/cape` (`cylinderGeometry` `B91C1C` + gold piping `torus` + `Text G` gold `Orbitron`), barbe/moustache `thick red cartoon` (`capsule` `E53935` fluffy `roughness 0.9`), yeux `big anime` (sclera white `0.11` + iris amber `#8B4513` + red emissive + highlight white + pupil black + glow ring red), matériaux `MeshPhysicalMaterial` `clearcoat` + `envMapIntensity` + `<Environment preset="city" />` pour rendu Pixar glossy.
- **`src/components/Dashboard.tsx`** : fond `bg-[#020B1E]` space + `radial-gradient` + `starfield` + 2 anneaux cyan tournants `spin 28s/42s` + `shadow-[0_0_60px]` derrière avatar (holographic portals).

### PHASE 3: Floating UI & Selfie Mode Polish

- **`src/components/Header.tsx`** : pill `SELFIE MODE` top-right `Camera` + dot pulse, `border-cyan-400/15` `bg-cyan-400/15` active vs `slate-700/40` idle, `selfieActive` state passé à `Dashboard`.
- **`src/components/Dashboard.tsx`** : `selfieActive` `useState`, `CyberAvatar faceTrack={selfieActive}` (idle) vs `false` busy, offline banner `TN VPS hors ligne — السيرفر طايح توا...` (red `border-red-500/30` + pulse) quand `telemetryStale`, chat h-[35vh]/h-[65vh] strict conservé.
- **`src/components/BottomInputBar.tsx`** : pill `ÉCOUTE` rouge `border-red-500` avec waveform 3 bars `equalizer` animée + `Mic`, `PRÊT` pill cyan glowing `border-cyan-400` `shadow-[0_0_16px]` + `✦✦`, footer `• GENIO APP •` `tracking-[0.2em]`, suppression `Send`/`Square` unused.
- **Status Alignment** : `telemetryStale` → banner chat + input reste actif en Gemini Cloud, bloqué visuellement en VPS.

**Verification** : `npm run build` exit 0 (2826 modules → 1514kB, `gemini_provider` + `face_mesh` + `Environment`), plus de mock leak, `/* thinking */` breaker >3 → down message.
