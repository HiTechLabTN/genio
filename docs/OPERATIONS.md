# OPERATIONS — démarrage, surveillance, maintenance

## Démarrage
```bash
sudo systemctl start genio.service genio-web.service        # API+UI
sudo systemctl start genio-gestures.service                 # :8001 (optionnel)
# VODER : instance setsid :5050 (unit voder-5050.service enabled, inactive)
./deploy/bootstrap_hitech_os.sh                             # bootstrap souverain
```

## Surveillance
- `GET /health/{liveness,readiness,metrics}` · SSE `/api/v1/telemetry`
- Bar UI (barre top, 3s) · `scripts/genio-probe`
- Logs : journalctl (`genio*`, `cloudflared-wattouna`, `midnight-patrol`)
- Télémétrie JSONL : `state/telemetry.jsonl` (scrubbée)

## Maintenance
- Patrouille 03:00 (`midnight-patrol.timer`, logs `reports/v4/`) — strictement
  cette fenêtre (le script refuse hors 03:00-04:00).
- Sessions DB : `state/sessions.db` (fenêtre 10, auto-compact) ; backup avant
  toute migration manuelle.
- Modèles Ollama : `ollama list` ; timeout tours `GENIO_MODEL_TURN_TIMEOUT=120`.
- Secours : `POST /api/v1/safety {"action":"kill"}` puis `arm` (re-arm explicite).
- Releases stagées : `export/staged_releases/` + `upload_to_drive.py`.

## Variables d'environnement clés
`GENIO_MODEL_TURN_TIMEOUT=120` · `GENIO_MAX_ITERATIONS=5` ·
`GENIO_TURN_BUDGET=600` · `GENIO_TOOL_TIMEOUT=120` ·
`GENIO_SECURITY_MODE=development|strict` · `GENIO_SANDBOX_MODE=container` ·
`GENIO_ALLOW_CLOUD` (défaut fermé) · `GENIO_AUDIO_PIPELINE=1` ·
`GENIO_RATE_LIMIT_RPS/BURST` · `GENIO_MAX_BODY_BYTES` ·
`GENIO_CONFIRM_TIMEOUT=120` · quotas `GENIO_MAX_TOOL_CALLS/TOKENS`,
`GENIO_BUDGET_*` · `GENIO_CLICK_MIN_INTERVAL_S` · `GENIO_SANDBOX_CPUS` ·
`GENIO_UPLOAD_QUOTA_BYTES/TTL` · `GENIO_TOKEN_TTL=900`.
