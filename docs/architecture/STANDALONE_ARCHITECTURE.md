# Standalone architecture — Genio as a product

Genio ships as: git checkout OR versioned release archive, installed
by the stdlib-only smart installer (`installer/genio`) into an
isolated prefix (code/config/data separated). No Python package, no
sibling repo, no CWD assumption, no PYTHONPATH.

```
source (git | tar.gz+sha256)
   ↓  verify (ref / checksum, fail closed)
prefix/
  repo/      application code (git or archive)
  venv/      runtime env (pinned requirements.txt)
  config/    .env 0600 + ports.json
  data/      user data (never deleted except --purge-data)
  .genio/    manifest.json + backups/ + install.log (scrubbed)
services (optional, explicit) : hardened systemd unit (non-root user,
  ProtectSystem=strict, explicit paths) — enable/start stays manual.
runtime  : uvicorn genio_server (API/WS) + optional VODER/gestures/web.
ipc      : Genio UDS server (hello/capabilities/infer) for HiTech-OS,
  same-uid auth, nonce+rate-limit, audited. Absent OS = full standalone.
```

HiTech-OS integration is an additional capability (IPC v1.x contract),
never a requirement: with no OS socket, Genio is complete; with no
Genio, the OS must keep working (its side, documented in
`docs/integration/GENIO_HITECHOS_INTEGRATION_PLAN.md`).
