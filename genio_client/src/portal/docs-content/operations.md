# Operations runbook — Genio standalone

## Layout

Prefix per `docs/install/INSTALLATION.md`. Logs: `<prefix>/logs/`
(app), journald (services), `<prefix>/.genio/install.log`
(installer, secret-scrubbed).

## Start / stop / restart

- Manual: `uvicorn genio_server.server.main:app` with `cwd=<prefix>/repo`,
  env from `<prefix>/config/.env`.
- systemd: `systemctl {start,stop,restart,status} genio-standalone`
  (only if installed `--with-services`).

## Health

`genio doctor --prefix <P> --deep` (exit 17 on FAIL) ;
`GET /health` (API), `/health` (web image), IPC `hello`.

## Backup / restore

Automatic pre-repair/update backups in `.genio/backups/`.
`genio rollback --prefix <P> [--backup NAME]`. `data/` excluded by
design — back it up with your own tooling for off-host copies.

## Monitoring

Watch: process alive ≠ healthy. Check API `/health`, IPC hello,
sandbox denials in telemetry (`security.event`), disk (`data/` growth),
VRAM contention (LLM vs TTS — evict, don't share).

## Upgrade

`RELEASE_PROCESS.md` gates. Never skip the post-update verify;
rollback is automatic on failure — confirm with `doctor`.
