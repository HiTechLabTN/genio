# GENIO_5_G1_ARCHITECTURE — Product Architecture & Design System (gate G1)

Baseline: v4.1.0 (`8f6cebe`), CI 6/6. Charter: strictly additive.

## 1. Current architecture

- Frontend: React 18 + TS + Vite 7 + Tailwind (darkMode class),
  three/fiber/drei + rapier + mediapipe (avatar), framer-motion,
  react-router (`/`, `/app`, `/about`, `/genio/admin`).
- Served: `vite preview :8098` → cloudflared (`/ws/*`, `/api/*` → :8000).
- Backend: FastAPI :8000 (14 routes + WS), policy/router/sandbox/tools,
  VODER :5050, gestures :8001, ollama :11434.
- Installer CLI (stdlib): 9 commands, manifests, backups, 19 tests.
- IPC v1.x UDS: hello/capabilities/infer + legacy v1.0, auth UID,
  nonce, rate-limit, audit. HiTech-OS daemon: no IPC yet
  (CONTRACT READY / IMPLEMENTATION PENDING).
- SEO/OG/canonical present. `aria-*` in Landing: 0. dist 178MB.

## 2. Target architecture (5.0 portal, additive)

Portal routes added beside the app (no existing route touched):
`/` keeps Landing (CTAs extended) + `/download /docs /explore
/security /api /install`. Shared `PortalLayout` (nav, breadcrumbs,
footer). Data: `product-data.json` generated at build from
authoritative sources (single truth). States: `installStates.ts`
mirror of `installer/core/states.py` (locked by tests both sides).

## 3. Route map

| Route | Responsibility | Data source | Live? |
|---|---|---|---|
| `/` | hero (try/install/docs/github), narrative | static + product-data | static |
| `/app` | chat (UNCHANGED) | WS live | LIVE |
| `/about` | UNCHANGED | static | static |
| `/download` | per-platform cards; real artifacts only, else "unavailable" | product-data.artifacts/platforms | static+client detect |
| `/docs` | viewer (bundled curated md) + search/nav/version | build-copied docs | static |
| `/explore` | clickable architecture (client→API/IPC→policy→tools→sandbox→model) | product-data + IPC schema | static |
| `/security` | guarantees, CAN/CANNOT/approval/failure | docs/SECURITY + code facts | static |
| `/api` | OpenAPI explorer, read-only (no live console) | bundled openapi-genio.json | static |
| `/install` | assistant: platform detect (client-side), real commands, honesty states | installStates + product-data | client-side |
| `/genio/admin` | PROTECT in G2 (auth gate design §8) | backend | LIVE gated |

## 4. Component architecture

`src/portal/`: PortalLayout, HeroActions, DownloadCenter,
PlatformDetect (client-only, no fingerprint exfil),
DocsViewer, ArchitectureExplorer, SecurityCenter, ApiExplorer,
InstallAssistant, StatusPill (severity vocabulary), CodeBlock (copy).
`src/design/`: tokens.css (+ future components). Boundaries: portal
never imports app internals; app never imports portal; both read
product-data + installStates only.

## 5. Design-token architecture

Single file `src/design/tokens.css` (`--g5-*`): colors mirror
tailwind theme (no restyle), typography, spacing, radii, elevation,
borders, focus ring, status colors, light overrides, reduced-motion
kill-switch. Rule: new code uses vars; old code untouched until
measured migration.

## 6. Product-data schema

`genio_client/scripts/gen-product-data.mjs` → `src/product-data.json`
(keys: product/version/installer_version/client_version/ipc_protocol/
api_routes/ipc_error_codes/ipc_events/capabilities(+unavailable)/
artifacts{base,archive,checksum,manifest,sbom,docker}/
platforms{linux,docker,windows,macos,android with status+reason}/
release_notes/known_limitations). CI `distribution` job runs
`--check` (drift = fail). No hand-maintained release facts in UI.

## 7. State-machine definition

`installer/core/states.py`: 18 states (charter list), each with
id/label/explanation/severity/transitions/recovery; `validate_graph()`
tested. TS mirror `installStates.ts` + `canTransition()`, locked by
`tests/test_states_mirror.py` AND `installStates.test.ts`.
Terminal: complete/rolled_back/cancelled (no out-edges).

## 8. Security boundaries

- Admin: G2 gate — `/genio/admin` behind Bearer (localStorage key,
  user-entered, never embedded) verified against backend
  `require_key`; gestures :8001 stats proxied same-origin (never
  direct localhost:8001 from public clients). Until G2 lands: route
  stays as-is (documented finding, NOT silently hidden).
- CSP/headers: audit vite preview + tunnel in G2 (§33); no inline
  secrets; external scripts: fonts.googleapis only (preconnect).
- Origins: same-origin + genio.hitech.tn explicit; no wildcard
  credentials.
- Downloads: URLs pinned to release tag assets; checksum shown beside
  every button; installer verifies fail-closed.
- Installer trust: TLS + ref pin + SHA report (documented, no fake sigs).
- External links: `rel="noopener noreferrer"`, no trackers (analytics
  lib is first-party only).
- Privacy: local-first statement; telemetry scrubbed; diagnostics
  copy excludes secrets (doctor --json guidance).

## 9. Accessibility requirements

Keyboard: all portal actions focusable + visible ring
(`.g5-focusable`); skip-link on PortalLayout; landmarks
(header/nav/main/footer); dialogs with focus trap + Escape;
live regions for async status; contrast ≥ 4.5:1 text (measured in
G2); reduced-motion respected (CSS kill-switch + framer-motion
`useReducedMotion` in new code); screen-reader labels on icon
buttons; error announcements via role=alert. Test: vitest a11y
queries + manual keyboard pass in G2.

## 10. Performance budgets

| Metric | Budget |
|---|---|
| Portal initial JS (new routes, lazy) | ≤ 150KB gzip per route chunk |
| Initial CSS | ≤ 30KB gzip |
| LCP (portal, 4G) | ≤ 2.5s |
| three/rapier chunks | lazy, never on portal first load |
| dist total | measure, must not regress app load |
| Route transitions | < 100ms (code-split) |

Baseline measured in G2 before/after (dist 178MB today). No blind
optimization: rapier/MascotStage stay (measured reason required).

## 11. Migration strategy

`docs/releases/GENIO_5_MIGRATION.md`: 4.x installs keep working
(manifest/config/data compatible; installer additive); no breaking
API (14 routes frozen); IPC 1.x frozen; portal is frontend-only
addition; rollback = previous dist (static). No data migration.

## 12. Files to add

- `genio_client/src/portal/*`, `src/design/*` (done: tokens),
  `src/product-data.json` (+ generator), `src/lib/installStates.ts`
  (+ test), `installer/core/states.py`, `tests/test_states_mirror.py`,
  `docs/releases/GENIO_5_MIGRATION.md`, this file.

## 13. Files to modify (G2)

- `main.tsx` (routes only), `Landing.tsx` (CTAs only),
  `index.html` (meta/sitemap/robots), `Admin.tsx` (auth gate),
  `.github/workflows/ci.yml` (product-data --check),
  `package.json` build (prebuild hook, additive).

## 14. Files explicitly protected

MascotStage/HoloPlatform/AndalusianBackground/CinematicAvatar,
agent_loop/budgets, policy_engine, session_container, auth_tokens,
protocol.py, installer CLI behavior, `tests/test_*.py` semantics.

## 15. Risks

Portal bloats dist (mitigate: lazy routes, budgets enforced in CI);
docs drift (mitigate: --check gate); admin gate complexity
(mitigate: minimal Bearer check, no new backend).

## 16. Open blockers

Tauri/APK native builds (external toolchains); HiTech-OS daemon IPC
(OS side); D-Bus control on this host; registry push policy
(immutable tags only — decided).

## 17. Test strategy

pytest: states mirror/validity; vitest: installStates, portal
components, a11y queries; tsc; vite build; product-data --check in
CI; Lighthouse/manual keyboard pass in G2; full backend suite
unchanged (regression gate).
