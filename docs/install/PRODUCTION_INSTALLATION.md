# Production installation checklist

Canonical procedure: `INSTALLATION.md`. Production adds:

1. `GENIO_ENV=prod` + strong `GENIO_API_KEY` in `config/.env`
   (boot refuses keyless prod — tested).
2. Or `GENIO_SECURITY_MODE=strict` + `GENIO_SANDBOX_MODE=container`.
3. `GENIO_ALLOW_CLOUD` stays empty unless cloud explicitly approved.
4. Install with `--with-services`, then `systemctl enable --now`.
5. Verify: `genio doctor --deep` → 0 FAIL; `GET /health` 200.
6. Backups live in `.genio/backups/` — replicate off-host yourself
   (installer never exfiltrates).
