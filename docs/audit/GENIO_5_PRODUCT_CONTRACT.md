# GENIO_5_PRODUCT_CONTRACT (source of truth index)

## Identity

| Slot | Value | Source file |
|---|---|---|
| product name | genio | `VERSION` + manifests |
| product version | **4.1.0** | `VERSION` (single truth) |
| frontend component | 4.3.0 | `genio_client/package.json` (+ tauri.conf, aligned) |
| installer component | 1.0.0 | `installer/__init__.py` |
| IPC contract | 1.0 | `genio/integrations/hitechos/__init__.py` |
| API app | 1.0.0 | `genio_server/server/main.py` (FastAPI version) |
| desktop id | tn.hitechlab.genio | `src-tauri/tauri.conf.json` |
| mobile id | com.hitechlab.genio | `capacitor.config.json` |
| Docker | ghcr.io/hitechlabtn/genio:4.1.0@sha256:61d4b42… | immutable tag only |
| API identity | 14 routes + `/ws/agent` | `schemas/openapi-genio.json` (17 paths incl. probes) |

Component versions evolve independently; product version is the only
release version. `Cargo.toml` 0.1.0 is scaffold debt (noted, harmless:
Tauri version comes from tauri.conf).

## Experience

Canonical UX = G4.3 unified (`/app` unified mode + portal). Semantic
states: G1 18 installer states + 18 presence states (locked mirrors).
Presence contract: `resolvePresence` → same object for dot/3D/panels.
Hierarchy: simple/detailed/advanced (persisted). a11y: keyboard,
focus, skip-link, landmarks, reduced-motion, live regions.
Responsive: 360–1440 verified, no overflow.

## Runtime

API (Bearer/TTL/rate-limit) · WS `/ws/agent` · auth (boot guard) ·
router (cloud closed) · policy (central) · sandbox (fail-closed) ·
tools (allow-listed) · memory (isolated). All covered by 123-test
security suite, re-run green.

## Distribution

Archive `.tar.gz` + `.sha256` + `.release.json` · SBOM (968) ·
OpenAPI + IPC JSON schemas · installer (stdlib CLI + event protocol) ·
Docker (pinned, non-root, HEALTHCHECK) · desktop/mobile artifacts
only when actually built (never faked).

## Update

CHECK→DISCOVER→VERIFY→BACKUP→PREPARE→INSTALL→MIGRATE→HEALTH→COMMIT;
FAIL→RESTORE→HEALTH→ROLLBACK→REPORT. Downgrade needs explicit flag.
No success without health verification (code-enforced).

## Recovery

doctor/repair/rollback/uninstall/restore/backup; data never deleted
implicitly (tested: repair/update/rollback/uninstall + purge path
with typed confirmation).
