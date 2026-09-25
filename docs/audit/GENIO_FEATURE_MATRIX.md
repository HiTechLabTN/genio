# GENIO_FEATURE_MATRIX — Phase 1 (statuts réels, vérifiés ou marqués honnêtement)

Date : 2026-09-25 · Statuts autorisés uniquement :
`VERIFIED | PARTIALLY_VERIFIED | IMPLEMENTED_UNTESTED | BROKEN | STUB | MOCK | NOT_IMPLEMENTED`.
Règle : VERIFIED = exécuté sur cet hôte dans cette phase ou traçé à une preuve datée.

## Conversation & persona

| Feature | Localisation | API | Statut | Preuve / limite |
|---|---|---|---|---|
| Chat Darija souverain | `agent_loop.py:SYSTEM_PROMPT` | `WS /ws/agent` action=prompt | VERIFIED | 10 cycles live 0.00% latin ; réponses live « أنا جينيو… » |
| Accordéon Reasoning | `App.tsx` details.thought-container | events `thought` | VERIFIED | smoke Playwright 1 bloc + toggle OK, 0 JS err |
| Blocs tool_call/result | `App.tsx` details.tool-call | events `tool_call/result` | VERIFIED | smoke 2 blocs ; streaming WS live vu en E2E publique |
| Réponse RTL + bouton voix | `App.tsx` + `speakViaVoder` | `POST :5050/synthesize` | VERIFIED | RTL + bouton rendus ; CORS `*` vérifié ; synthèses 200 réelles |
| Fast-path salutations | `reflex_engine.py:greeting` | interne AgentLoop | VERIFIED | « عسلامة » → 0.02s, 100% Darija ; pas de hijack (tâches→LLM) |
| Boucle multi-step (≤5) | `agent_loop.py` | interne | VERIFIED | 2 tool-turns chaînés live (47s) ; cap `GENIO_MAX_ITERATIONS=5` |
| Mémoire de turn | `session_store.py` + backfill | `session_id` | VERIFIED | bug ligne parent FIXÉ ; retest « وين وصلت » = rappel exact |
| Kill switch | `SAFETY` + `_KILL_EVENTS` | `WS kill/rearm`, `POST /api/v1/safety` | PARTIALLY_VERIFIED | `test_phase7_routing_kill.py` : 41 passed (avec bash_safety) ; halt live non rejoué ici |

## Voix & avatar

| Feature | Localisation | API | Statut | Preuve / limite |
|---|---|---|---|---|
| VODER TTS masculin | `engines/voder/` + `:5050` | `POST /synthesize` | VERIFIED | 200, 2.88s RMS 0.203 **F0 140Hz** (réf 145Hz vs 205Hz féminin) ; filtre Jarvis actif |
| STT microphone | `voice_pipeline.py` + `/api/v1/voice/transcribe` | multipart | VERIFIED | faster-whisper live : « أسلامة أنا جينيو » ; gate `GENIO_AUDIO_PIPELINE=1` ; fallback CPU |
| Touch handlers micro | `App.tsx` onPointerUp/onTouchEnd + VAD 1.5s | client | IMPLEMENTED_UNTESTED | code + `tsc` OK ; PAS de device mobile physique pour tester |
| Avatar 2.5D | `CinematicAvatar.tsx` + webm states | — | VERIFIED | rendu (4 vidéos), follow-focus codé ; **0 req .glb/three/rapier** en technique |
| Mascotte 3D (verrouillée P.A) | `MascotStage/RiggedMascot` (lazy) | — | PARTIALLY_VERIFIED | chunk isolé, charge seulement en mode mascotte ; non rejoué visuellement ici |

## Système & ops

| Feature | Localisation | API | Statut | Preuve / limite |
|---|---|---|---|---|
| Telemetry bar + endpoint | `TelemetryBar.tsx` + `/api/v1/system/telemetry` | GET JSON | VERIFIED | 200 en 24ms ; valeurs live publiques ; scrubbed (pas de marque/host) |
| Self-improve déterministe | `genio_gestures/self_improve.py` | `midnight-patrol.timer` 03:00 | VERIFIED | ranking identique 2 runs ; 20 skills ; timer `waiting` |
| Site public + tunnel | cloudflared `a60a1b27` + `genio-web.service` | https://genio.hitech.tn | VERIFIED | `/` et `/app` 200 ; `/ws`+`/api` routés :8000 ; E2E MCP complète 0 erreur |
| Sandbox conteneurs | `tools/session_container.py` | `GENIO_SANDBOX_MODE` | IMPLEMENTED_UNTESTED | tests Phase 5/B/C/D existants, non exécutés dans cette phase ; défaut = hôte |
| Lane cloud Gemini | `gemini_provider.ts` + gateway | OAuth Google | IMPLEMENTED_UNTESTED | code présent ; sans token Google ici → repli « سجّل بـ Google » vu en E2E |
| Uploads sécurisés | `main.py` (transcribe, attachments) | multipart | BROKEN→à traiter Ph.20/21 | **AUCUNE limite taille/MIME/magic-bytes codifiée** (grep vide) |
| Auth API | `require_key` | headerclé | PARTIALLY_VERIFIED | ouverte si `API_KEY` vide (état actuel assumé, à durcir Ph.20) |
| Contrat HiTech-OS | — | — | NOT_IMPLEMENTED | pas de `genio/integrations/hitechos/`, pas de `/run/*.sock`, pas de protocole v1 |
| Docs d'archi/sécu | `docs/` | — | NOT_IMPLEMENTED | que branding/guides ; ARCHITECTURE/SECURITY/etc. = Phase 28 |

## Sécurité — points durs déjà visibles (sans attendre)

1. Sandbox défaut hôte (fail-open) → Phase 6 P0.
2. Pas de limites d'upload → Phases 20/21.
3. `HF_TOKEN.txt` commités (placeholders, pas de fuite) → hygiène Phase 2.
4. Double définition `POST /api/v1/voice/transcribe` → dédupliquer Phase 2.
5. Worktree sale (README, router, voder_service, skills, untracked) → baseline git Phase 2.
