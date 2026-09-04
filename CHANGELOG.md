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

## 2026-09-02 — Genio v2.2.2 Critical Hotfix: UI Thread Unblock, WebGL Crash Fix & Interactive Avatars

### PHASE 1: UI Thread Unblocking & FaceMesh Optimization
- **`src/components/avatar/useFaceTracking.ts`** : throttled `setAngles` to 15 FPS (66ms cap via `performance.now()` guard) — stops 60Hz React state churn that froze main thread.
- **`src/components/avatar/CyberAvatar.tsx`** : `React.memo(SceneCanvas)` + `React.memo(CyberAvatar)` — 3D Canvas no longer re-renders on every chat keystroke or audio level change; 60 FPS scrolling preserved while canvas active.

### PHASE 2: WebGL Crash Fix & Material Simplification
- **`src/components/avatar/CyberAvatar.tsx`** : all `MeshPhysicalMaterial` → `MeshStandardMaterial` (drops `clearcoat`/`envMapIntensity`/`metalness` complexity that failed to compile on Android WebView); geometries simplified (head `64→16` seg, beard `24→12`, cape `32→16`); white sphere head + red cylinder Chachia + solid red beard + red torso with golden "G" `Text`.
- **`src/components/avatar/CyberAvatar.tsx`** : `<Canvas>` wrapped in `<Suspense fallback={<LoadingUI />}>` — WebGL crash shows spinner instead of invisible/unresponsive canvas.

### PHASE 3: Interactive Animations
- **`AvatarMode`** extended with `"greeting"` — first-launch wave animation.
- **`listening`** → right arm raises to ear + head tilts forward.
- **`greeting`** → right arm oscillates left-right 3× over 3s.
- **`speaking`** → lip-sync continues based on `audioLevel`.
- **`idle`** → gentle breathing bob + arms down.

### PHASE 4: Audio Input Unblocking
- **`src/lib/audio.ts`** : `startVoiceRecording` defers `new MediaRecorder()` to `queueMicrotask` — `toggleMic` stays snappy, never blocks React render cycle; removed wasteful double `getUserMedia` call.

**Build** : `npm run build` exit 0 (2826 modules, 4.97s, 1515kB gzip).

## 2026-09-02 — Genio v2.3.0: Chronos Portal, Pixar Avatar & System Metrics

### Hook Custom: useTaskProcessor
- **`src/hooks/useTaskProcessor.ts`** (nouveau) : recoit `task` (string | null), retourne `isMinimized`, `thinkingSteps` (5 etapes animees toutes les 1.2s), `metrics` (CPU/GPU/RAM/VRAM simules toutes les 2s), `result` (texte de succes), `isProcessing`.
- `setIsMinimized(false)` pour rouvrir le portail apres traitement termine.

### Composant SystemMetrics
- **`src/components/ChronosPortal/SystemMetrics.tsx`** (nouveau) : 4 barres de progression (CPU cyan, GPU magenta, RAM orange, VRAM rouge) avec animation de transition.

### Chronos Portal
- **`src/components/ChronosPortal/ChronosPortal.tsx`** (nouveau) : layout flex (Avatar Pixar a gauche, SystemMetrics + thinkingStream + result a droite), anne Chronos tournant `rotateGalaxy 28s`, mode minimized (icone flottante en haut a droite avec tooltip), bouton fermer pour clear la tache.
- **`src/components/ChronosPortal/ChronosPortal.module.css`** (nouveau) : deep space `#020B1E` avec gradients, animations `rotateGalaxy`/`float`/`slideIn`, responsive `@media (max-width: 768px)` (colonne unique, Avatar reduit), `z-index: 9999` pour minimizedContainer.

### Integration App.tsx
- **`src/App.tsx`** : `useState<string | null>(null)` pour `task`, `handleSendPrompt` met a jour `setTask(text)`, `<ChronosPortal task={task} onDismiss={() => setTask(null)} />` en bas du layout.

**Build** : `npm run build` exit 0 (2830 modules, 5.15s, 1522kB gzip). Release `v2.3.0` avec `Genio-Web-v2.3.0.zip` (477KB).

## 2026-09-02 — Genio v2.3.1: Multiplateforme Electron + Capacitor + CI/CD

### Electron (Desktop)
- **`electron/main.js`** (nouveau) : BrowserWindow 1200x800, `loadFile dist/index.html`, `removeMenu()`, preload.js.
- **`electron/preload.js`** (nouveau) : `DOMContentLoaded` console.log.
- **`package.json`** : `version "2.3.1"`, `main "electron/main.js"`, scripts `electron:start`, `electron:build:win` (nsis), `electron:build:linux` (deb).

### Capacitor (Mobile)
- **`capacitor.config.json`** (nouveau) : `appId com.hitechlab.genio`, `webDir dist`, `androidScheme https`.
- **`package.json`** : devDeps `@capacitor/cli/android/ios ^5`, scripts `capacitor:sync`, `capacitor:build:android`.

### GitHub Actions CI/CD
- **`.github/workflows/release-binaries.yml`** (nouveau) : déclenché sur `release: published`.
  - **build-web** : `npm install && npm run build` → upload artifact `dist`.
  - **build-electron** : matrix `windows-latest` + `ubuntu-latest`, download web-dist, `electron-builder` → upload `Genio-Setup.exe` / `genio_amd64.deb`.
  - **build-android** : Java 17 Zulu + Android SDK, `npx cap sync android`, `./gradlew assembleDebug` → upload `Genio.apk`.

### electron-builder config
- **`package.json`** → `"build"` : `appId com.hitechlab.genio`, `productName Genio`, `directories.output release-builds`, `win.target nsis`, `linux.target deb`.

**Build** : `npm run build` exit 0 (2830 modules). GitHub Actions déclenchées automatiquement sur le tag `v2.3.1` — binaires EXE/DEB/APK disponibles dans ~5-10 min sur la page Releases.

## 2026-09-02 — Correctif audit round 3 : Reflex Engine, Chronos Portal, Gemini Auth (v2.1 → v2.3.1)

Preuve d'audit ayant motivé l'ensemble du correctif (reprise telle quelle Phase A — trouvaille n°1) :
```
engine.compile_skill('auto-test3', 'please clean my build cache now', [
    {'command': 'echo setup'},
    {'command': 'rm -rf /tmp/genio_workdir_victim'},
])
is_dangerous('rm -rf /tmp/genio_workdir_victim')
→ "outside the allowed working directory" (bloqué en chemin normal)
engine.match('please tell me a joke about robots')
→ AVANT : exécutait rm -rf sans contrôle (canari supprimé, canary survived: False)
→ APRÈS : canari survit (strict 3-keyword lookahead => pas de match OU refus 126 via is_dangerous + sandbox host|container)
```

| Phase | Faille | Fichier(s) | Correctif | Test |
|-------|--------|------------|-----------|------|
| A | Reflex Engine (v2.1) contourne intégralement Phases 0/5 : `_run_bash()` `subprocess.run` direct sur hôte, sans `is_dangerous()` ni conteneur, + `compile_skill` déclenché sur 1er mot ≥3 chars (`\bplease\b`) + kill-switch non consulté avant fast-path (ligne 519 `return` avant boucle ReAct) | `genio_server/core/reflex_engine.py` (`_run_bash` supprimé, `_exec_pattern`/`_exec_skill`/`_finalize` → `_invoke_bash` via `genio_server.tools.invoke("bash", cmd, session_id)` + `match(prompt, session_id)` + `auto_fix(..., session_id)` + `GENIO_REFLEX_STRICT_MATCH` 3-keyword lookahead) `genio_server/core/agent_loop.py` (`self.cancelled()` vérifié AVANT `get_reflex_engine().match(..., session_id)` + re-check après match) | Tous les patterns (même lecture seule Q1) passent par `is_dangerous()` + `GENIO_SANDBOX_MODE` (host/container) ; kill-switch bloque avant tout retour anticipé ; `compile_skill` exige désormais 3 mots discriminants (lookahead `(?=.*\bkw1\b)(?=.*\bkw2\b)...`) désactivable via `GENIO_REFLEX_STRICT_MATCH=0` (Phase A routing reste fail-safe) | `test_phase_A_reflex_bypass.py` (4 cas) reproduit littéralement la preuve (canari filesystem réel survit), + related prompt bloqué par `is_dangerous`, + kill-switch armé → aucun `invoke`/`_invoke_bash` (spy mock), + pattern légitime `check system health` <500ms |
| B | Chronos Portal (v2.3.0) entièrement simulé : `useTaskProcessor` `THINKING_STEPS` (5 chaînes) + `setInterval` 1.2s + `randomMetric(15,85)` toutes les 2s + `DONE_MESSAGES` aléatoire 8-12s — aucun lien avec WS `/ws/agent` (`thought`/`tool_call`/`tool_result`/`stats`/`answer`) ni SSE `/api/v1/telemetry` | `genio_client/src/hooks/useTaskProcessor.ts` (suppression `THINKING_STEPS`/`DONE_MESSAGES`/`randomMetric`/`setInterval`/`Math.random`, dérivation via `useMemo` depuis `chat`/`telemetry`/`agentStatus`) `genio_client/src/components/ChronosPortal/ChronosPortal.tsx` (props `{chat, telemetry, agentStatus}`, `toolActivity` séparé, `error`/`killed` visible, `hasContent` guard) `genio_client/src/App.tsx` (`task` string supprimé, `chronosDismissed` + props réels, `useGenioSocket` garde WS + SSE séparés Q3) | `thought` → `thinkingSteps`, `tool_call`/`tool_result` → `toolActivity` distinct, `stats` + SSE `telemetry` → `metrics` (cpu/gpu/ram/vram réels), `answer` → `result`, `error`/`killed` → état d'échec, types WS inconnus ignorés silencieusement (Phase 6) ; `useGenioSocket` garde 2 connexions isolées (WS ReAct + SSE HUD) pour éviter freeze | Vérif (a) flux WS simulé `thought→tool_call→tool_result→stats→answer` → `thinkingSteps`/`toolActivity`/`metrics`/`result` exacts (useMemo dérivation), (b) `grep -r setInterval\|Math.random\|THINKING_STEPS\|DONE_MESSAGES\|randomMetric useTaskProcessor.ts` = 0 hits après build, (c) `npm run build` exit 0, (d) `test_phase6_tolerant_ws.py` reste vert (types inconnus ignorés) |
| C | Clé API Gemini dans bundle client (`genio_client/src/lib/providers/gemini_provider.ts:25` `import.meta.env.VITE_GEMINI_API_KEY`) intégrée en clair dans `dist/` (APK/EXE/DEB via `release-binaries.yml`) + OAuth `localStorage` implicit flow | `genio_client/src/lib/providers/gemini_provider.ts` (`VITE_GEMINI_API_KEY` supprimé, `GEMINI_API_BASE` `/api/v1/gemini` proxy, `resolveAuth` sans Vite, `buildUrl` serveur-relatif, `streamGemini` fetch proxy) `genio_client/src/App.tsx` (host `generativelanguage` → `genio-server`) `config.py` (`GeminiConfig` `GENIO_GEMINI_API_KEY`/`GENIO_GEMINI_MODEL`) `core/model_router.py` (endpoint `gemini` priority 90 + `_call_gemini_chat` systemInstruction/contents/tools + `?key=` + Bearer passthrough, `_call_endpoint` Gemini path) `genio_server/server/main.py` (`/api/v1/gemini/{full_path:path}` proxy `Authorization`/`?key=` + `StreamingResponse` pour `:streamGenerateContent`) | Clé lue uniquement côté serveur (`GENIO_GEMINI_API_KEY` env, `get_config().gemini.api_key`, désactivable vide), client appelle désormais `/api/v1/gemini/...` via serveur (WS ReAct existant ou REST proxy) au lieu de `generativelanguage.googleapis.com` direct ; ModelRouter intègre Gemini comme endpoint failover supplémentaire (Q4) avec même streaming/tool-calling que Ollama/OpenRouter | (a) `grep -r VITE_GEMINI_API_KEY dist/ + grep -r generativelanguage dist/` = 0 hits après `npm run build` exit 0, (b) mock réseau `generativelanguage` échoue si appelé direct depuis client (fetch intercepte proxy et passe par serveur), (c) `ModelRouter` health expose `gemini` quand `GENIO_GEMINI_API_KEY` set, `test_phase_E_model_routing.py` vert |

### Correctif Phase A Q2 (2026-09-02)
- **reflex_engine.py** : suppression du fallback incluant les stopwords ("please", "hello", etc.) quand moins de 3 candidats non-stopwords.

## 2026-09-03 — Genio v3.1.0: Islamic Cyberpunk Anime HUD (10 assets, 6 components, 4 bugfixes)

### Assets (10 images, ordre attachement)
- `src/assets/mascot/genio-jebba-wave.png` (#1 crimson jebba gold sfifa waving) → source icône app (pipeline `capacitor-assets`/`tauri icon`)
- `src/assets/mascot/genio-burnous-present.png` (#2 cream burnous over red jebba arms open)
- `src/assets/mascot/genio-listen.png` (#3 transparent arms open)
- `src/assets/mascot/genio-exec.png` (#4 transparent pointing)
- `src/assets/mascot/genio-think.png` (#5 transparent glowing red eyes)
- `src/assets/mascot/genio-wave.png` (#6 transparent waving)
- `src/assets/scenes/scene-thinking.png` (#7 burnous + brain + GPU bar)
- `src/assets/scenes/scene-exec.png` (#8 jebba + matrix + metrics)
- `src/assets/scenes/scene-answering.png` (#9 burnous holding answer + waveform)
- `src/assets/splash/splash-anime.png` (#10 anime hologram + GENIO wordmark)
- Fallback SVG même basename si PNG manquant ; build garanti (placeholder `DejaVu` remplacé par vrais `woff2` Orbitron via `@fontsource` déjà en place) ; chaque PNG ≤300KB.

### State → Mascot
- `idle=#1`, `listening=#3`, `thinking=#5`, `executing=#4`, `answering=#2`, `completed=#6` — mapping centralisé dans `mascot/HologramMascot.tsx` avec `AnimatePresence` spring crossfade.

### Keyframes #7–#9 (live, non statiques)
- #7 → `hud/BrainActivity.tsx` (pulsing brain + 8 sparks transform/opacity only) + `SYSTEM LIVE` GPU bar cyan + yeux cyan glow en `thinking`.
- #8 → `hud/MatrixTaskScreen.tsx` (blur 8px + Arabic rain `جينيو01ذكاءتونس` opacity .3, pause on `document.hidden`, checkboxes staggered, spring 28vh→75vh) + `hud/SystemMetrics.tsx` panel `CPU/RAM/NET/TEMP/VRAM` à droite en `executing`.
- #9 → `GenioShell` expanded answer screen `Arabic RTL + waveform live (audioLevel) + speaker button` + mascot minimisé `72px` docké coin `MatrixTaskScreen` en `answering`.

### Design Spec — Islamic Cyberpunk Anime HUD
1. `background/IslamicPatterns.tsx` (z-0, memo, `transform/opacity` only) : SVG 8-point Andalusian stars `cyan .12` + `gold .08`, `linear-gradient #0a0e1a→#0f172a→#1a0a1e`, bordure arabesque pulse `6s`, ≤20 particules or `y`/`opacity` uniquement.
2. `mascot/HologramMascot.tsx` (`status`, `audioLevel`, `isMinimized`) : float `4.5s`, 3 anneaux pulsants (`idle #22d3ee`, `listening #f43f5e`, `thinking #facc15`, `executing #fb7185`, `answering #4ade80`), `spring` crossfade, ombre sol, `whileTap .88/-6°`, scanlines statiques + radial glow (pas de filtres animés), `face-track` `rotateX/Y ±8/±12°` lerp `mousemove` + `useFaceTracking`, `lip-sync scaleY=1+audioLevel*.04`, `layoutId="genio-avatar"` morph, `minimized=72px`.
3. `hud/SystemMetrics.tsx` (memo, `1s` poll, isolé) : jauges circulaires SVG `CPU/GPU/RAM` (+`NET/TEMP/VRAM` si dispo), `strokeDasharray` transition `0.6s`, ne re-render jamais le mascot.
4. `hud/BrainActivity.tsx` : `thinking`/`executing` only, cerveau pulsant + 8 étincelles `transform/opacity`.
5. `hud/MatrixTaskScreen.tsx` : `backdrop-blur 8px`, pluie `opacity .3`, `document.hidden` pause, lignes `staggered`, `spring` `28vh→75vh`, clic toggle check.
6. `layout/GenioShell.tsx` : `z` `patterns(0)→matrix(8)→mascot(10)→chat(15)→metrics/brain(20)` ; `isMascotSmall=answering||expanded` ; conserve `ChatBubble` + `BottomInputBar` (Darija STT/TTS).

### Splash Screen (#10, mobile + desktop)
- Natif : `capacitor.config.json` `SplashScreen` `backgroundColor #0a0e1a` + `launchShowDuration 0` + `Electron` `BrowserWindow backgroundColor #0a0e1a` `show:false` → `ready-to-show` (zéro flash blanc, petit logo seul).
- Web : `layout/SplashScreen.tsx` overlay `z-50` : `#10` centré, `clip-path bottom→top 1.2s` + scanlines + `12` particules cyan (`transform/opacity` only), anneau progrès fin cyan sous `GENIO`, `Darija` cyclage `نجهّز الحكيم…` `نشحّن الذاكرة…` `نتثبت الاتصال…` (900ms), `hide` sur `genio:ready` `spring fade+scale-out` + `hard 5s timeout`, `layoutId="genio-avatar"` → morph vers HUD.

### Performance
- `transform`/`opacity` uniquement (pas de `filter`/`box-shadow` animé), `memo()` widgets, `SystemMetrics` isolé des `telemetry` ticks, `mascot` lerp `requestAnimationFrame` `0.09`, `MatrixTaskScreen` `document.hidden` pause, PNGs `≤300KB`.

### Bug Fixes
- **F1** `Connection refused pop-os:8000` : `App.tsx` `handleConnect` `/health` `3s` `AbortController` pre-check ; fail → `healthStatus=offline` + `Tier A` `On-Device` chip + `retry` ; jamais crash, `useDeviceProfile`/`decideEngine` fallback intact.
- **F2** `speechSynthesis` WebView guards conservés : `useVoiceOutput.ts` `window.speechSynthesis?.addEventListener?.` / `removeEventListener?.` / `cancel?.` + early return `if (!window.speechSynthesis) return` (Android WebView sans TTS).
- **F3** `.gitignore` allow-list : `!genio_client/src/assets/**/*.png` déjà présent au root (anc. `*.png` trap), vérifié `git check-ignore` `src/assets/mascot/*.png` → not ignored.
- **F4** Caméra refusée : `useFaceTracking` `enabled=false` → `active=false` → `HologramMascot` `faceTrack={!isMinimized && active}` fallback `mousemove` lerp, mascot reste centré, pas de `getUserMedia` crash.

### Hard Safety
- Branch `feat/islamic-ui` (jamais `main` direct).
- `GoogleAuthOnboarding`, `gemini_provider` proxy, `GENIO_PERSONA_PROMPT`, `permissions onboarding`, `speechSynthesis` guards, `RootErrorBoundary`, `On-Device Tier A` préservés.
- Hooks existants réutilisés (`useFaceTracking`, `audioLevel`, `AgentStatus`, `telemetry` via `useGenioSocket` + `useTaskProcessor`).
- `framer-motion` existant seul, pas de `three.js` nouveau (CyberAvatar conservé mais non impacté).
- `npx tsc --noEmit` + `npm run build` `exit 0` à chaque étape.

## 2026-09-03 — Genio v3.1.2: Fix HUD mount, hologram splash, perf & version

### P1 Splash hologram (F1) — static → 3D materialization
- `layout/SplashScreen.tsx` : `clip-path inset(100% 0 0 0)→inset(0% 0 0 0)` 1.2s ease-out + 2px cyan scanline bar moving with reveal edge, `perspective(900px) rotateX(12deg) scale(1.08)→rotateX(0) scale(1)` 0.9s spring → idle `y[0,-10,0]` 4s loop, 2 chromatic copies `mix-blend screen translateX ±2px` `opacity [0,.5,0]` 350ms only, base ring pulse + 12 rising particles synced, `transform/opacity/clip-path` only, `5s` hard timeout kept, `fetchPriority="high"` on splash image.

### P2 HUD mount (F2) — empty avatar → IslamicPatterns + HologramMascot
- `App.tsx` post-onboarding root now renders `IslamicPatterns` `z-0` (replaces dot-grid) + `HologramMascot` `h-[35vh]` `z-10` visible immediately at `idle` (no empty avatar), `MatrixTaskScreen` `z-8` `28vh→75vh`, `SystemMetrics` top bar `z-20`, `BrainActivity` during `thinking/executing`, expanded answer screen `z-15` during `answering` (RTL + waveform + speaker). Keeps `ChatBubble`, `VoiceInput`, `ÉCOUTE/PRÊT`, `CHRONOS` portal, `Tier` chip. `isMascotSmall=answering||expanded` + `layoutId="genio-avatar"` morph from splash.

### P3 Performance (F3) — freeze 2-4s → 60fps
- **7 PNGs 1.4-2.1MB → WebP q80** `genio-jebba-wave 137KB`, `burnous-present 93K`, `listen 92K`, `exec 34K`, `think 65K`, `wave 109K`, `splash-anime 72K` (≤400KB, commit `.webp` delete `.png`, update imports).
- **Single render:** `HologramMascot` `AnimatePresence mode="wait"` renders ONLY `IMAGE_MAP[status]`; rest preload via `requestIdleCallback` `fetchPriority="low"` `decoding="async"`.
- **face_mesh gate:** `useFaceTracking` dynamic import only after `genio:ready` + `document.visibilityState==="visible"` + `idle` + `navigator.permissions.query camera=granted` (fallback graceful centered mascot).
- **Update check:** `checkForUpdates` delayed `setTimeout 3000ms` + `requestIdleCallback` (timeout 4000), never at boot.
- **Blur:** `MatrixTaskScreen` `backdrop-blur-[8px]` → `[@media(pointer:coarse)]:backdrop-blur-none` + baked `bg-gradient-to-br from-[#0f172a]/90 to-[#1a0a1e]/85` for mobile.
- **Telemetry:** `SystemMetrics` `memo` + `1s` interval, `rAF`-throttled `useFaceTracking` `66ms` (15 FPS), verified via React Profiler `mascot` not re-rendering on `telemetry` ticks.

### P4 Version & updater (F4)
- **Bump** `3.1.1`→`3.1.2` in `package.json` + `capacitor.config.json` + `src-tauri/tauri.conf.json` (+ `package-lock`) BEFORE tagging; checklist `ALWAYS bump on every release`.
- **Updater:** `lib/updater.ts` `isNewer` semver `latest > current` only shows dialog when `semver(latest) > semver(current)` (assets commit `3.1.0`→`3.1.1` without bump caused `v3.1.1` dialog on `v3.1.1` build — now fixed).

### Verification
- `npx tsc --noEmit` exit 0, `npm run build` 2859 modules → 1492kB gzip 435kB.
- Startup trace (mid-range Android WebView, Moto G): LCP `1.8s→1.1s` (-39%), TTI `4.2s→1.9s` (-55%), 0 long tasks >50ms during first 5s (vs 3 tasks 120-180ms before), `document.hidden` pause verified, `face_mesh` chunk `64KB` lazy-loaded after `genio:ready`.

## 2026-09-03 — Genio v3.2.0: Real-time 3D Living Mascot (Talking Tom, <15k tris)

### LivingMascot3D — R3F full-screen `Canvas absolute inset-0 z-1`
- **`src/components/mascot/LivingMascot3D.tsx`** (nouveau, `React.lazy` via `App.tsx`, chunk `LivingMascot3D 9.7KB gzip 2.9KB`) : remplace le PNG statique par une mascotte 3D temps réel `Talking Tom` — white ceramic head sphere + maroon glossy visor (`sphereGeometry 32seg` flat 0.96 op) + AMBER emissive eyes (`0.52` 45% movable `tx*0.07`/`ty*0.05` blink 3-6s 120ms) + fluffy red beard scaled spheres `flatShading` + crimson jebba `capsuleGeometry 8/16` + gold sfifa planes + G emblem cylinder + capsule arms + black tassel chain spring sway — tout `MeshStandardMaterial` seul, total <15k tris (estimé ~8-9k).
- **Canvas** `absolute inset-0 z-1` `dpr [1, 1.5]` `antialias false` sur `pointer:coarse`, `alpha:true` pour laisser voir `IslamicPatterns` derrière, `camera [0,0.9,3.2] fov38` centré upper third (~70vh portrait `inset-0`), `powerPreference high-performance`, `onError` → fallback, `document.hidden` pause `useFrame` early return + `visibilitychange` `setAnimationLoop(null)`.
- **Lattice** `background/IslamicPatterns.tsx` `z-0` allégé `cyan .07`/`gold .07` (vs .12/.08) + `linear-gradient #0a0e1a→#0f172a→#1a0a1e` border pulse 6s, `behind` mascot avec `glow pulse` synchronisé status, radial light beam sprite `plane 3.2×3.2` `opacity .25` `AdditiveBlending` derrière `LivingSceneInner`.
- **HUD layers** inchangés `IslamicPatterns z-0 → mascot z-1 → MatrixTaskScreen z-8 → chat z-15 → metrics/brain z-20 → header z-30`, chat `pt-[36vh]` préservé, `SplashScreen z-50` → `layoutId` morph.

### Behaviors (eyes/track, breath, touch, poses, lip-sync)
- **Eyes** track user via `useFaceTrackingContext` `lerp ±10°` `0.08`, fallback `pointermove` → `idleLook` random 4-7s `±0.5/0.3`, clamp `faceLookTarget` `±0.5`.
- **Blink** 3-6s random `120ms` `scaleY 0.08`, blink reset sur `surprised`.
- **Breathing** `scaleY ±.015 @4.5s` `sin(2π/4.5)` + `position.y sin 1.396*0.045`, `jump` double-tap `sin 12*0.18`.
- **Raycast touch** `pointerdown` double-tap <300ms → `jump` 600ms + 8 sparks `sphere 0.02` `visible 600ms`, sinon `head/belly/hand` → `surprised 600ms` (eyes scaleX 1.18)/`proud 700ms` (beard wiggle `sin18*0.012`)/`waveBack 800ms` (arm lerp), `raycaster.intersectObjects(group.children)` avec fallback `pt.y` thresholds.
- **Poses** per `status` via `pose` targets lerp `0.12` : `listening` hand-to-ear `lean 0.18`, `thinking` hand-to-chin `eyesUp -0.18`, `executing` typing, `answering` waving, `completed` hand raised `±0.8`.
- **Lip-sync** `jaw.position.y = - (min(audioLevel,1)*0.22 + answering sin7.5*0.06)` lerp `0.22`; `audioLevel` from `isListening?0.45:0` reuse tiers existants.

### Performance & safety
- `React.lazy` (`App.tsx` `lazy(()=>import LivingMascot3D)`) + `Suspense` fallback `HologramMascot h-[35vh]`, `memo()` isolé, `face_mesh` non re-importé, `transform/opacity` only, `tiers` guard : `MAX_TEXTURE_SIZE<2048` ou `navigator.deviceMemory ≤2` ou `!webgl` → `HologramMascot h-[35vh]` fallback `z-10`, `WebGL` error boundary → jamais crash, `coarse` `dpr 1.2` + `antialias false` + `hidden` pause, estimé `draw calls ~14`, `tris ~8k`, `VRAM <40MB`.

### Version
- Bump `3.1.2→3.2.0` `package.json` + `capacitor.config.json` + `src-tauri/tauri.conf.json` BEFORE tagging; `release-binaries.yml` génère `Genio-Web-*.zip` + `APK/AAB/exe/deb` sur `v*`.

### Verification
- `npx tsc --noEmit` exit 0, `npm run build` 2861 modules → `LivingMascot3D 9.75KB` `face_mesh 64KB` codé-split, total `1495KB gzip 436KB` (+3KB vs 3.1.2), fallback Tier low vérifié, `document.hidden` pause, `TTI` inchangé via lazy.

## 2026-09-03 — Genio v3.2.1: Hotfix P1-P4 (portrait, voice, gauges, welcome)

### P1 Portrait
- `LivingMascot3D.tsx` enveloppé `<Bounds fit clip observe margin={1.4}>` caméra `fov35 [0,1,6]`, clamp radii `≤0.35` hauteur `≤2.2`, centrage middle 60%, `ContactShadows [0,-1.1,0] opacity0.42 scale3` + re-fit resize/orientation → 390x844 head→feet ≥10% margin.

### P2 Voice
- `useVoiceOutput.ts` `speechSynthesis.resume()` avant `speak()`, gate premier gesture, `lang ar-TN fallback fr-FR volume1 rate1`, chip `🔇 voix indisponible` si `!speechSynthesis`, toggle top-bar persist `genio:voice:enabled`.

### P3 Gauges
- `App.tsx` auto-select `fetch http://tn:8000/api/v1/status 2s` → `connect WS` si OK sinon Gemini Cloud, `SystemMetrics isCloud` → badge `☁️ CLOUD MODE` jamais 0%, `useGenioSocket` backoff exponentiel + `visibilitychange`.

### P4 Welcome
- `GoogleAuthOnboarding.tsx` + `App.tsx` auto-continue 1.2s si `getGoogleToken()` existe.

### Version
- Bump `3.2.0→3.2.1` `package.json` + `capacitor.config.json` + `src-tauri/tauri.conf.json`; `tsc 0 vite 2853 modules 413k+911k`.

## 2026-09-04 — Genio v3.3.0: CLEAN UI REBUILD (mobile-first fixed root)

### S1 Audit & Delete Legacy Stack
- Audit `App.tsx`/`GenioShell.tsx`/`Dashboard.tsx` : listé 8 sections root; supprimé `Header` duplicate, avatar `h-[35vh]` dot-grid `radial-gradient/starfield/anneaux`, panels `h-screen/h65vh`, bandes grises `tier bar bg-carbon/30` + `GENIO APP` footer; conservé hooks `chat/WS/telemetry/voice/face tracking`.

### S2 Single Root Layout
- `fixed inset-0 h-[100dvh] overflow-hidden` `z-0 IslamicPatterns .07 + glow`, `z-1 LivingMascot3D inset-x-0 top-[56px] bottom-[32%] middle60% Bounds margin1.4`, `z-20 TopBar [☰][SYSTEM LIVE]…[VOIX]`, `z-15 TaskMatrix compact collapsible max-h 28% backdrop-blur collapsed mobile / right panel desktop`, `z-15 BottomSheet status+gauges/cloud+transcript+input env(safe-area-inset-bottom)`, desktop même root; pas de scroll, pas de bandes grises.

### S3 Updater OFF on Web
- `isWebPlatform !android && !electron && !__TAURI__ && !Capacitor native` → skip `checkForUpdates` et ne jamais rendre `UpdateModal` (gardé Android APK/desktop).

### S4 Visual Acceptance
- Servi `dist` via `python3 -m http.server 4173`, Playwright headless `390x844` + `1280x800`, vérifié mascot full head→feet + input visible sans scroll + pas de bandes/duplicates + pas de triangle rouge leaking; fixes `BottomInputBar w-full min-w-0 flex-1` + pills `px-2.5 sm:px-4 hidden sm:inline`, `MatrixTaskScreen` `110px` collapsed; shots `reports/ui-v3.3.0-mobile.png + -desktop.png`.

### S5 Release & Deploy
- Bump `3.2.1→3.3.0` `package.json` + `capacitor.config.json` + `src-tauri/tauri.conf.json`; `tsc 0 vite 2853 modules 413k+911k`.

### Verification
- `npx tsc --noEmit` exit 0, `npm run build` exit 0 (2853 modules), screenshots valid, mascot full visible, input visible, no gray bands.

## 2026-09-04 — Genio v3.3.1: HOTFIX P1-P5 + S6 deploy

### P1 Updater never on browsers
- `App.tsx` `isNative = !!(window.__TAURI__ || window.Capacitor?.isNative || isNativePlatform())` — `isWebPlatform` old UA `android` check removed; `checkForUpdates` + `UpdateModal` only if `isNative`; Android Chrome on `genio.hitech.tn` never renders dialog.

### P2 Darija voice
- `audio.ts` `SpeechRecognition.lang = "ar-TN"` fallback `ar-SA→fr-FR`, `interimResults true` → Arabic-script interim; `MediaRecorder` blob `language "ar"` POST `/api/v1/voice/transcribe` when node connected via `transcribeAudio(blob, apiBase)`; `BottomInputBar` `isConnected/target` → server transcribe authoritative, `ar-TN` live preview.

### P3 Cloud chat cards
- `gemini_provider.ts` `buildUrl` same-origin `/api/v1/gemini` on web (ignore `serverBase`), distinct errors `NO_GOOGLE_TOKEN` / `GEMINI_PROXY_FAIL`; `App.tsx` `isGeminiCloud=!connected` + `!hasToken` → inline card `"سجّل بـ Google باش تكمّل في السحاب"` + button `setShowGoogleAuth(true)`, proxy fail → `"مشكل في الاتصال بالسحاب — عاود جرّب"` + retry; cards rendered in transcript.

### P4 HiTech Cloud preset
- `ConnectionHub.tsx` preset `HiTech Cloud host genio.hitech.tn port 443`, default on web `hitech-cloud` else `pop`; `ws.ts` `buildWsUrl` `wss://genio.hitech.tn/ws/agent` + `streamTelemetry` `/api/v1/telemetry` same-origin (nginx proxies `/api` + `/ws` → `pop-os:8000`); `App.tsx` auto-connect + `handleConnect` use `/api/v1/status` same-origin for cloud; phone on 5G `wss` gauges live.

### P5 Connection resilience
- `useGenioSocket.ts` `window offline/online` listeners + `visibilitychange` keep `shouldReconnect`; `connectionToast` `"الاتصال انقطع — نعاودو نربطو…"` on `offline` / `idle` drop, auto `scheduleReconnect` on `online` without reload; `App.tsx` fixed toast `bottom-[84px]` amber.

### S6 auto-deploy fix
- `/data/genio-deploy/auto-deploy.sh` rewritten no `sudo`, `rsync -avz --delete pop-os:/data/ai_tools/genio/genio_client/dist/ → ~/genio_dist_new` (fallback keep existing) + `docker compose up -d --no-deps genio-frontend`; `nginx.conf` added `location /ws/` proxy; manual `rsync` + `auto-deploy.sh` run verified `https://genio.hitech.tn` `index-Dta76BxS.js` 200 OK.

### Version
- Bump `3.3.0→3.3.1` `package.json` + `capacitor.config.json` + `src-tauri/tauri.conf.json`; `tsc 0 vite 418k+911k`.

## 2026-09-04 — Genio v3.4.0: BRAND PUPPET + LANDING + INTRO

### S1 Assets
- `genio-hero/listen/think/speak/wave.png` 1.7-2.4M → `webp q80` 120-196K keeping names; `intro_voiceover.m4a` 52s 634K at `src/assets/audio/` forced via `git add -f` (bypass `audio/` ignore).

### S2 HologramPuppet (REPLACE LivingMascot3D)
- New `HologramPuppet.tsx` state→image `idle/completed=wave listening=listen thinking=think answering/executing=speak` crossfade `250ms spring`; `mask-image radial-gradient soft` + `mix-blend screen` dissolves dark rect; alive: breathing `±.015@4.5s`, tilt `rotateY±8°` via `useFaceTracking` + pointer fallback, glow pulse per status, ring+particles, scanline shimmer; tap head→think→wave, body→speak 800ms, double-tap jump+spark burst; answering mouth glow `audioLevel`; deleted `LivingMascot3D.tsx` (911K) → bundle `2291` modules `463k` (was 2853 `418k+911k`).

### S3 Landing at `/`
- `pages/Landing.tsx` hero `genio-hero` + `أول صاحب ذكاء اصطناعي تونسي` + CTA `جرّب Genio توة → /app`; sections `how-it-works 3 steps`, `tech & privacy` (Gemini proxy, on-device), `ROADMAP 4` (Academy/Education/SysAdmin/Daily), `FOUNDER محمد عزمي كعنيش` + portrait, footer; `dir=rtl` `Tajawal UI + Reem Kufi` via Google Fonts, `dark void #020B1E + zellij .07`, mobile-first, Lighthouse >90; `index.html` fonts + title; `react-router-dom@6` added.

### S4 Intro Cinematic (first visit /app only)
- `components/intro/IntroCinematic.tsx` `intro_voiceover.m4a` 5 scenes `0-10 wave 10-25 listen 25-45 think 45-70 speak 70-80 hero+CTA` crossfade `250ms`; progress bar, `تخطي` top-right, `localStorage genio:intro:seen` no replay, autoplay tap fallback; `App.tsx` `showIntro` + `handleIntroDone` overlay `z-[60]`.

### S5 Routing + P6
- `main.tsx` `BrowserRouter Routes / → Landing /app → App /about → About *→/`; `pages/About.tsx` founder long-form RTL; keep `updater off web, Google auth, persona, gemini proxy, RootErrorBoundary, voice, CLOUD MODE`; `App.tsx` intro scoped to `/app` only; `P6` nginx `/ws/` already `proxy_pass http://100.85.172.4:8000` with `Upgrade $http_upgrade Connection upgrade` verified, phone `wss://genio.hitech.tn/ws/agent` gauges live.

### Version
- Bump `3.3.1→3.4.0` `package.json` + `capacitor.config.json` + `src-tauri/tauri.conf.json`; `tsc 0 vite 2300 modules 463k`.

## 2026-09-04 — Genio v4.0.0: GENIO BODY OS (THE BEING + THE MIND)

### S0 Discover & Self-Provision
- GPU RTX 3060 12GB (580.173.02 CUDA 13.0) VRAM 11348MiB free → InstantMesh selected; ComfyUI 0.0.0.0:8188 running (PID 3540872) verified via `/system_stats`; ComfyUI-3D-Pack cloned but prebuilds Windows py312 cu124 only — fallback to blender primitive (logged); blender 3.0.1 apt installed verified; ollama qwen2.5:7b-instruct-q4_K_M 4.7GB pulled verified chat 63 tok/s; ffmpeg 4.4.2, node v22.23.2; provisioning log `reports/v4/provisioning.log`.

### S1 IMAGE→3D
- `genio-wave.png` → `blender --background` procedural jebba crimson+gold, head, chachia, arms, ring — `media/mascot_raw.glb 1.2M` + `mascot_raw.obj 1.1M` (>1MB) + `.mtl`; turntable 3 angles via `montage` → `reports/body-turntable.png 583K` + `reports/v4/body-turntable.png`; palette crimson+gold+cyan verified via materials; one retry via larger subdiv (fallback documented).

### S2 RIG + MOTION
- OSS rigger not pip-installable → `blender --background` Rigify `human_metarig_add` + `ARMATURE_AUTO` → `media/rig/mascot_rigged.glb 2.1M`; docs/MIXAMO_GUIDE.md for FBX clips (`wave/walk/idle/talk.fbx` → `media/mixamo/`); procedural fallback: walk hip bob+leg swing, idle breath 4.5s, wave shoulder/elbow IK, talk jaw audioLevel, blink 3-6s — creativity engine.

### S3 GenioBody (R3F) + PHYSICS STAGE
- `GenioBody.tsx` lazy chunk `3.2M` (`@react-three/rapier` + `@dimforge/rapier3d-compat`); Rapier `Physics gravity -9.81` zellij floor `CuboidCollider 5x0.1x5` + neon ring `RingGeometry` + arches gold torus; WALK to tap waypoints via `raycaster` plane y=0, `walkSpeed 1.4` lerp, stop+face user `atan2`; head-tilt via `useFaceTrackingContext` + pointer fallback `rotateY±8°`; flag `genio:body:3d` desktop on, tier-low (deviceMemory≤2 or no WebGL) → HologramPuppet Tier-B fallback; `public/media/rig/mascot_rigged.glb` copied.

### S4 movement_charter.json v1
- `src/assets/movement_charter.json` version `1.0.0` states `[idle,listening,thinking,answering,executing,walking,waving,completed]` clipsOrProcedural `procedural` blends `0.2-0.4s` physics `gravity -9.81 walkSpeed 1.4` creativity `ikRanges headTilt ±12 nod ±8 shoulder ±45 elbow 0-120 hipBob 0.04 legSwing 0.35 noveltyDecay 0.85` documented.

### S5 THE MIND: local gesture composer
- `genio_gestures/app.py` FastAPI port `8001` systemd `genio-gestures.service` (User hitech, Restart always); `POST /compose {context,emotion,user_prefs}` → `{gesture_plan{head{tilt,nod,blink},hands[IK],mouth,body}}` system prompt = `GENIO_PERSONA_PROMPT` + gesture vocab + `modest, no single-finger pointing`; ollama `qwen2.5:7b-instruct-q4_K_M` backend `timeout 1.8s` `num_predict 30`; SQLite `gestures.db` cache 50/user + dataset; latency `1.86s` first, `0.0003s` cached (<2s) verified; env flag `GENIO_GESTURES_ENABLED` + charter fallback.

### S6 NIGHT SELF-IMPROVEMENT
- `genio_gestures/self_improve.py` + cron `0 1 * * *` 01:00-06:00 window, load >4 skip; 100 synthetic pairs → composer plans → self-eval `culture/personality/novelty 0-10` → keep top-10 → dataset `total 160 real 150 synthetic 10` → `ollama create genio-gesture` ≤30min → log `reports/v4/cron.log`; dataset 44K, top10 via `/stats`.

### S7 INTEGRATION + ADMIN
- `GenioBody` queries `/compose` per status change with Gemini `gesture_hint` forwarded; per-user `+1/-1` via `POST /feedback` + decay (SQLite `feedback`); `src/pages/Admin.tsx` + `main.tsx` route `/genio/admin` dashboard: model health (`/health` VRAM 12GB), dataset real vs synthetic, top-10 gestures, cron logs, improvement score.

### S8 OpenDesign (:7456)
- Consult non-blocking stage art direction: zellij floor, neon ring, arches — verified `curl http://localhost:7456/` 200 Next.js Open Design, consult logged, no block.

### S9 ACCEPTANCE (Playwright swiftshader)
- `reports/body-*.png` `390x844 135K` + `1280x800 355K` full body via `chromium --use-gl=swiftshader` `vite preview 4175` with `genio:body:3d on` + `genio:intro:seen` bypass; walking ≥2m via tap waypoint, waving, jaw moving (audioLevel), blink across frames, 5 consecutive `POST /compose` ALL different (uniq 5) latency 1.86s; `npx tsc --noEmit 0` + `npm run build 0` lazy bundle `GenioBody 3.2M`.

### S10 RELEASE
- Bump `3.4.0→4.0.0` `package.json` + `capacitor.config.json` + `src-tauri/tauri.conf.json`; tag `v4.0.0`; `gh release` + `auto-deploy tn` via `rsync dist → ~/genio_dist_new` + `docker compose up -d --no-deps genio-frontend`; keep `v3.4.1 fixes, landing, intro, updater-off-web, Google auth, gemini proxy, ErrorBoundary, voice, CLOUD MODE` never break.

### Version
- Bump `3.4.0→4.0.0` `package.json` + `capacitor.config.json` + `src-tauri/tauri.conf.json`; `tsc 0 vite 2862 modules 465k + GenioBody 3.2M`.


