# GENIO 5 migration — 4.x → 5.0

Status: 5.0 UNRELEASED (this document is the policy, not a release).

## Compatibility promises

- API: 14 routes + `/ws/agent` frozen (additive only).
- IPC: v1.x envelope frozen; legacy v1.0 accepted.
- Installer: manifests/config/data formats unchanged; CLI extended only.
- User data (`data/`), models, logs: preserved across update/rollback.
- 4.x installations keep running; update is opt-in per prefix.

## Changed in 5.0 (portal, additive)

- New routes `/download /docs /explore /security /api /install`
  (frontend only; no backend change).
- `/genio/admin` gains an auth gate (Bearer, user-provided key).
  Until then it remains as-is (documented finding).
- Design tokens centralized for new code; existing theme untouched.

## Deprecated

- Nothing in 4.x is removed. Dead frontend components
  (SplashScreen/LiveGenio/ChronosPortal) stay dead (noted, not deleted).

## Breaking changes — NONE planned.

Any future breaking change must be listed here first with version,
impact, automatic migration (if any) and rollback path.

## Automatic migrations

- None required (formats unchanged).

## Rollback strategy

- Frontend: previous `dist/` (static, instant).
- Installer prefix: `genio rollback` (code+config+manifest, data kept).
- Downgrade guard: `--allow-downgrade` required (tested).

## Downgrade limitations

- 5.0 → 4.x: supported via installer rollback (same mechanisms);
  new 5.0-only config keys (if any) are ignored by 4.x, never crash.
