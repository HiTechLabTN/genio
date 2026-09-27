# GENIO_5_CANONICAL_EXPERIENCE (UX contract for Web/Desktop/Mobile)

## States

Presence (18): idle greeting listening understanding thinking planning
explaining executing waiting asking_user success warning error
recovering celebrating sleeping disconnected attention.
Installer (18, G1): idle detecting checking ready downloading verifying
installing configuring securing health_check complete degraded failed
blocked requires_user_action rolling_back rolled_back cancelled.
Rule: UI renders states, never invents them (visualizer flags invalid).

## Layout modes

conversation (default) · thinking/planning · execution · result ·
disconnected/recovery · developer (opt-in only).
`layoutModeFor(presence, advanced)` is the single advisor (tested).
Attention target reorders panels (task-first vs status-first).

## Information levels

simple (state/task/result/next) · detailed (+steps/duration/resources/
model/connection/tools) · advanced (+event stream/WS/routing/sandbox/
API/telemetry/logs). Advanced is opt-in; density persists locally.

## Presence

`GenioPresenceState` {semanticState, attentionTarget, intensity,
gesture, mood, focusPanel, showResources, showTaskDetails}.
Canonical images: base/wave/wink from promt/ (mapped, never redrawn).
TelemetryBar exposes `data-presence`/`data-attention` (SSR-tested).

## Accessibility

Reduced motion (OS + explicit + kill-switch), keyboard (skip-link
first, dialogs Escapable, radios/checkboxes labelled), landmarks,
single polite live region (status), role=alert errors, touch ≥24px,
contrast ≥7 (measured pairs), alt policy (decorative empty,
meaningful labelled).

## Visual identity lock

Character = promt/ set (base/wave/wink); environment = in-image
compositions + void theme (compatible, no stock replacement).
3D stack retained for legacy mascot mode only; unified path has zero
three imports (tested). No reinterpretation, no generic avatar.
