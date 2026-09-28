# GENIO_PUBLIC_PRODUCT_TRUTH (single source for public messaging)

This document + `docs/releases/PUBLIC_RELEASE.json` +
`genio_client/src/product-data.json` (generated) are the ONLY
authoritative sources for public claims. README, landing, portal and
docs MUST NOT duplicate these facts by hand (validated by
`tests/test_public_truth.py` + `gen-product-data.mjs --check`).

## What Genio IS

Genio is a sovereign Tunisian AI agent runtime: local-first task
execution with policy enforcement, sandboxed tools, model routing,
memory, voice and a web UI. Product 4.1.0, public release v5.0.0.

## What Genio CAN DO (verified categories)

- AI interaction: Darija/French/English chat via app or WS (`/ws/agent`).
- Task execution: multi-step agent runs (≤5 iterations, budgets).
- Tools: structured Bash, bounded filesystem, browser (anti-SSRF),
  computer-use (gated), uploads (magic bytes).
- Sandboxed execution: Docker strict, fail-closed (HOST_EXECUTION=0).
- Browser/computer interaction: as above, capability-gated.
- Memory/state: session recall, audit metadata, poisoning guards.
- Security: policy engine, Bearer TTL, rate limits, telemetry
  scrubbing, kill switch, boot guard.
- Local operation: full runtime on one Linux machine (Ollama).
- Remote operation: same API over tunnel/VPN (operator-secured).
- Developer: OpenAPI (17 paths), IPC v1.x contract, CLI installer,
  JSON event protocol, schemas.
- API: 14 routes + WS, documented in `schemas/openapi-genio.json`.
- IPC: hello/capabilities/infer over UDS (daemon impl. pending OS-side).
- Docker: `ghcr.io/hitechlabtn/genio:5.0.0` (non-root, HEALTHCHECK).
- CLI: install/doctor/status/repair/update/rollback/uninstall.
- Desktop client: Tauri app (Linux AppImage+DEB in v5.0.0 release).

## What Genio CANNOT / DOES NOT YET DO

- Windows/macOS/Android/iOS builds (BLOCKED, toolchains/secrets).
- Production-signed binaries (UNSIGNED/DEVELOPMENT, checksums instead).
- HiTech-OS daemon integration (contract ready, impl pending).
- Native notification rendering verified (protocol proven).
- Offline task execution (offline shell only for cached routes).
- Cloud models without explicit opt-in (closed by default).

## Platform Availability (certified matrix)

PASS: Linux, CLI, Docker, IPC contract.
BLOCKED: Windows, macOS, Android, iOS.
See `docs/audit/GENIO_5_G5E_FINAL_PLATFORM_MATRIX.md`.

## Installation Paths (all real, all verified)

- Linux AppImage / DEB (v5.0.0 release assets).
- Source archive + SHA-256 (v5.0.0 release asset).
- Docker image (ghcr, immutable tag).
- CLI from source/archive (installer, no git required for archives).
- `genio doctor` verifies every path (exit 17 on FAIL).

## Security (factual)

Sandbox fail-closed · boot guard · Bearer TTL · rate limits ·
SSRF/FS/upload/injection guards · telemetry scrubbed · Tauri scopes
($CACHE-only fs, 3 official HTTP origins, shell open-only) · 0
secrets committed. Never "military grade" / "unhackable" / "100%".

## Signing

UNSIGNED / DEVELOPMENT. SHA-256 checksums are the integrity
mechanism. Never hidden.
