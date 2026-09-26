# Release notes — Genio 4.1.0 (standalone + IPC platform)

Product version 4.1.0 (next minor after platform v4.0.0).
Components: genio-client 4.3.0 · installer 1.0.0 · IPC v1.0 · API app 1.0.0.

## New

- Smart installer (`installer/genio`): install/doctor/status/repair/
  update/rollback/uninstall, manifests, backups, port detection.
- Release archives `.tar.gz` + SHA-256 + release manifest (no-git updates).
- IPC v1.x server (hello/capabilities/infer), error codes, events,
  capability catalog, same-UID auth, nonce + rate-limit + audit.
- Hardened Docker image (non-root, HEALTHCHECK).
- Machine-readable schemas (`schemas/`, OpenAPI + IPC JSON Schema).
- SBOM (CycloneDX-lite) from lockfiles.

## Changed

- `requirements.txt`: +psutil (was missing for API boot).
- `Dockerfile.web`: non-root `genio` user, HEALTHCHECK on `/health`.
- `web/server.py`: additive `/health` endpoint.
- Legacy `test_genio_core`: 15 nominative deselects (sibling deps).

## Fixed

- VODER `language="ar"` 500 → default `auto` + explicit 422.
- Strict-mode keyless boot refused (boot guard + tests).
- CI: pinned ruff, portable test paths, Playwright browsers, missing
  PWA asset, sibling-path guard.
- Docker context: secrets/weights excluded (proven).

## Security

- Sandbox fail-closed re-proven; boot guard; cloud closed by default;
  Bearer TTL; telemetry scrubbed; 0 secrets committed.

## Breaking changes — NONE (API: 14 routes + 1 WS stables).

## Deprecated

- `genio_executive_core` legacy paths (kept, tested via sovereign suite).

## Known limitations

See `KNOWN_LIMITATIONS_4.1.0.md`.
