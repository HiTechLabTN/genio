# API — référence (implémentation)

Base : `http://127.0.0.1:8000` (+ tunnel même-origine en prod).
Auth : `X-API-Key` ou `Authorization: Bearer <15min>` (`POST /api/v1/auth/token`
avec clé) ; ouvert si `API_KEY` vide (dev assumé). WS `/ws/agent` : header,
`?token=` (Bearer, préféré), `?key=` legacy. Rate-limit IP (20rps/40burst,
429), corps 10MB max (413), erreurs assainies (pas de traceback/chemins).

Routes : `GET /` `/health` `/health/{liveness,readiness,metrics}`
`GET /api/v1/status|safety|telemetry(SSE)|system/telemetry|sessions/{sid}`
`POST /api/v1/safety|auth/token|analytics|motion/record|voice/transcribe`
`GET /api/v1/motion/recommend` `GET /api/v1/executions/{sid}`
`WS /ws/agent` (prompt/kill/rearm/resume/approve/screenshot/screen_stream/
attach/voice_wav). Voix : `:5050/synthesize|health` (localhost, sans auth).

Conventions : JSON partout, `request_id` écho `X-Request-ID`, events WS
`{type, ...}` (`thought/answer/tool_call/tool_result/capability.requested/
action_confirmation_required/error/stats`).
Tests : `tests/test_api_security.py`, `tests/test_observability.py`.
