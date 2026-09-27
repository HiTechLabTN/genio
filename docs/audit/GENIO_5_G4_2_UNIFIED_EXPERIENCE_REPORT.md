# GENIO_5_G4_2_UNIFIED_EXPERIENCE_REPORT (canonical image character)

## Implementation

- Canonical set (all same character/environment, promt/ source of truth):
  base `assets/mascot/genio-hero.webp` (was already canonical, md5-identical
  to promt/a5e4096b), greeting `assets/character/genio-wave.webp`,
  celebrating `assets/character/genio-wink.webp` (converted PNG→WebP,
  ~2.5MB → ~265KB each, PIL quality 82, no redraw).
- `PresenceAvatar` is now the CharacterView: `imageForState()` maps
  greeting/listening/asking/attention→wave, success/celebrating→wink,
  rest→base + UI treatment (glow/badge/status). Artwork never altered.
- Unified mode unchanged otherwise (G4.1 panels/states/hooks intact).

## Assets

promt/a5e4096b (base, already in app) · promt/14436a27 (wave) ·
promt/ae56b050 (wink) · promt/ChatGPT-sheet (5-state reference,
consulted, not shipped as unit — no cropping of identity).
Background: reference compositions ship inside the images themselves;
app void theme kept compatible (no stock replacement).

## Architecture

Canonical assets → CharacterLayer (PresenceAvatar, state in/props out)
→ resolvePresence (untouched) → UnifiedShell panels. Character layer
owns no state, executes nothing.

## 3D Retirement

Removed: NOTHING executable. Retired from the unified path by
construction (unified never imported three — now asserted by test).
Retained deliberately: MascotStage (mascot mode), CyberAvatar
(Dashboard), Genio3D/RiggedMascot/AnimeMascot (wired internally —
grep-proven, deletion unsafe), three/rapier/mediapipe deps, all .glb
(referenced ones served; dead ones already archived in G4).
Deprecation documented here, not faked by deletion.

## Tests

- `tests/test_g42_no3d.py` (3): no 3D imports in unified/portal/
  presence; canonical assets exist+tracked; state mapping present.
- presence suite +2 (mapping + render per state): 11/11.
- Full backend halves + vitest + tsc: green (CI to confirm).
- Playwright: 0 .glb requests on portal routes; offline banner;
  task panel with seeded real events; mobile/desktop no-overflow.

## Build

`npm run build` OK; dist 89MB stable; budgets green; new chunks
(character images hashed, lazy with routes).

## Performance

Images: +534KB deploy (2 webp), lazy via routes; LCP/CLS unchanged
(portal measured); no 3D cost added anywhere (unified path has zero
three imports — tested).

## QA

`docs/audit/evidence/qa-g42-unified-{desktop,mobile,offline,task}.png`
(real implementation, unedited): canonical character in unified
header (desktop+mobile), offline banner live, smoke-seeded task steps
([thought]/[tool_call]/[tool_result]) rendering truthfully.

## Remaining limitations

- 3D stack retained for legacy mascot mode (disk, not runtime cost
  on unified path).
- 5-state sheet not shippable as units (would crop identity).
- Voice-commanded poses: not implemented (no such input exists).
- Density/ambient UI controls: present from G4.1, unchanged.

## Acceptance (§26)

- [x] character from promt/ · [x] background from promt/ (in-image)
- [x] no 3D in unified (tested) · [x] no GLB requests (measured)
- [x] no mascot physics in unified path · [x] resolvePresence intact
- [x] real hooks only · [x] TaskPanel/ResourcePanel/EventStream intact
- [x] offline + reconnect intact · [x] SSR contract intact
- [x] mobile intentional (shots) · [x] a11y passes · [x] reduced motion
- [x] existing tests green · [x] new tests green · [x] tsc green
- [x] build green · [x] no 404s · [x] no bundle regression
- [x] visual QA exists · [x] tree clean (2 runtime DBs excluded, as usual)
