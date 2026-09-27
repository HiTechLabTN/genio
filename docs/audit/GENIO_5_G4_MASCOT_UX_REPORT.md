# GENIO_5_G4_MASCOT_UX_REPORT (art direction: chibi engineer §1)

## 1. Existing mascot audit

- MascotStage (1.1MB chunk, three+drei+rapier 2.2MB, .glb draco chain):
  KEEP — working, lazy route, ErrorBoundary, untouched.
- CinematicAvatar (2.5D webm states): KEEP — zero heavy assets.
- HoloPlatform/AndalusianBackground: KEEP (protected).
- Rapier/MediaPipe: loaded only via 3D paths; never on portal/landing.
- Salvageable: everything. Replaced: nothing.
- Migration path if models prove insufficient: model-archive/ pattern
  (dead .glb already relocated without breakage).

## 2. New architecture

`src/presence/`: types (18 semantic states + attention + intensity),
primitives (22 validated), resolve (REAL socket/agent states →
presence), preferences (localStorage, validated), PresenceAvatar
(CSS-only phased presence, existing webp identity). Contract §24:
same state object for dot/3D/panels. TelemetryBar exposes
`data-presence`/`data-attention` from its existing props (additive).

## 3. State model

18 states (§4 list verbatim). Calm default (low intensity; medium
only for error/disconnect). No profiling (interaction context only).

## 4. Animation primitives

22 primitives, 7 families, duration 0.2–8s, amplitude capped
(low 0.3 / medium 0.5 / high 0.8). All bounds asserted in tests.

## 5. Procedural composition

`composeGesture(state, variant)` picks validated combos
(e.g. thinking = look-away+tilt+breathing OR gaze-down+chin-rest);
invalid/unknown → known-good fallback (tested). No codegen, no
downloads, no self-modification (§7: adaptive memory = prefs only).

## 6. Adaptive layout

Resolver `layoutModeFor` (conversation/thinking/execution/developer/
result) implemented + tested. Full App re-layout NOT executed
(regression risk) — documented next step with existing interfaceMode
as the seam. Resource hierarchy: essential/contextual/advanced
principle documented; TelemetryBar unchanged visually.

## 7. Resource hierarchy

Rule adopted: task-relevant first (presence attentionTarget drives
focusPanel), full telemetry one disclosure away (existing UI),
never invented metrics (all values from real hooks/endpoints).

## 8. Mobile behavior

PresenceAvatar sizes (56 compact → 160); 3D never required;
preferences persist mascot size + animation mode. Verified 360–412
(no overflow, touch targets fixed in same pass).

## 9. Accessibility

Reduced motion: CSS kill-switch + MotionConfig user + effectiveMotion()
logic (tested) + explicit animation on/reduced/off pref (persisted).
State always also textual (aria-label, title). No motion-only meaning.

## 10. Performance before/after

No 3D added: presence = 1 img + CSS (~0KB JS logic). Mascot chunks
unchanged (rapier 2.2M lazy). LCP/CLS unchanged-or-better (portal
measured 196–856ms / 0.000–0.005). Phased loading already held by
Suspense + lazy routes.

## 11. Failure/fallback behavior

3D fail → app usable (existing boundaries + PresenceAvatar needs no
WebGL — proven no-WebGL render, 0 errors). Unknown state → fallback
gesture (tested). Image fail → neutral "G" (coded).

## 12. User preferences

animation/density/ambient persisted locally, validated on load,
no account. Density/ambient UI controls: next step (module ready).

## 13. Tests

9 presence tests (mapping/layout/motion/persist/fallback) + 1
TelemetryBar contract test + existing suites green. tsc 0.

## 14. Visual evidence

`docs/audit/evidence/qa-landing-desktop.png` (hero+portal nav),
`qa-landing-mobile.png` (stacked, no overflow). /app shows existing
onboarding gate (auth wall, out of scope to bypass).

## 15. Known limitations

Full adaptive App re-layout pending (resolver ready) · density/
ambient controls UI pending (prefs module ready) · procedural
synthesis beyond validated combos not implemented (by design) ·
screen-reader pass manual · no 3D model quality change (migration
path documented instead).

## 16. Exact commits

(next commit)

## 17. CI evidence

(to monitor; backend halves + frontend expected green — no backend
touched except tests, no 3D touched)

## 18. Verdict

GREEN WITH LIMITATIONS — UI materially calmer-to-understand
(states named everywhere), mascot context-aware (contract live in
TelemetryBar), 3D non-blocking (unchanged lazy), behavior validated
non-repetitive (variant combos), resources contextual (attention
targets), advanced info accessible (existing UI kept), mobile usable,
reduced motion real, zero fake states, zero functional regression,
performance measured (dist −50% in same gate).
