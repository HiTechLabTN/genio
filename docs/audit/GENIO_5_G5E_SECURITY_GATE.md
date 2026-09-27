# GENIO_5_G5E_SECURITY_GATE (2026-09-27, commit 09af3d5)

Suites (all green, this audit): capabilities, policy, sandbox,
bash, filesystem, computer-use, browser/SSRF, prompt-injection,
memory, API auth, uploads, telemetry, kill-switch, governance,
adversarial, boot-guard, model-router, IPC v1.x (18), desktop
harness, Tauri capabilities, updater (7) — 156 passed §L alone,
plus installer 35 and backend halves in CI.

Scans (this audit): 0 token patterns in product paths (1 synthetic
fixture excluded by pattern) · 0 weights/caches tracked · 0 private
keys/keystores tracked · `.env` + `HF_TOKEN.txt` untracked (verified
placeholder content) · Docker image proven free of `.env`/tokens
(3 `docker run` probes across gates).

Boundaries re-verified: boot-guard strict, Bearer TTL, cloud closed,
sandbox fail-closed (live 125), no shell in browser code (test),
admin Bearer gate, Tauri scopes ($CACHE-only fs, 3-URL http).
