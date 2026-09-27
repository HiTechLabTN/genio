# GENIO_5_G4_1_UNIFIED_EXPERIENCE_REPORT

## 1. Before/after architecture

Before: mascot XOR technique, telemetry badge only, no shared semantics.
After: third opt-in `unified` mode reusing the SAME hook data
(chat/agentStatus/telemetry/task processor) through
`resolvePresence` → one `GenioPresenceState` driving header, panels,
resources, events and settings. mascot/technique branches untouched.

## 2. Adaptive layout

`layoutModeFor` (conversation/thinking/execution/developer/result)
drives `data-layout-mode` + panel ordering (attentionTarget=task →
task first). Modes A–E mapped; full App re-layout deliberately NOT
executed (regression risk) — resolver + panels are the seam.

## 3. Information hierarchy

L1 status (role=status, polite) → L2 current detail → L3 last result
→ L4 technical `<details>` (opt-in). Density radio simple/detailed/
advanced changes rendering without reload (persisted).

## 4. Density controls — IMPLEMENTED (was missing)

Radio group persisted to localStorage, validated on load.

## 5. Ambient controls — IMPLEMENTED (was missing)

Glow/particles checkbox + reduced-motion checkbox; security/task/
error feedback explicitly never disabled (copy in UI).

## 6. Presence integration

`resolvePresence` mapping verified live (technique TelemetryBar
`data-presence` + unified header). States observed: idle, greeting
paths, listening, explaining, executing, disconnected, error.

## 7. Attention synchronization

`attentionTarget` reorders panels (task-first vs status-first) and
drives PresenceAvatar scale + title. No decoration-only motion.

## 8. Resource panel

CPU/RAM/GPU/Net/model/throughput from real telemetry; missing →
"Unavailable" (tested, never 0/placeholder).

## 9. Task panel

Title/steps (last 6 real events)/tool/duration (client-observed,
labelled)/status/cancel (wired to kill()). Long runs stay readable.

## 10. Offline shell

Offline banner (routes/docs/settings/prefs usable, AI honestly
unavailable). Failure card: Connection lost + Reconnect (wired to
connect(target)) + docs link. Reconnect transitions verified in code;
live reconnect depends on backend (honest).

## 11. Failure UX

role=alert, no spinners-as-state, retry wired, details expandable,
no stack traces.

## 12. Mobile behavior

Responsive grid, compact presence (56px), touch targets from G4 pass,
no overflow (re-verified after Card fix). Tap-to-expand: presence
title tooltip; full expand = G5+ (declared).

## 13. Accessibility

Single polite live region (no overuse), headings, fieldset/legends,
radios/checkboxes labelled, expandable details native, error alerts.
Reduced motion honored end-to-end (prefs + OS + MotionConfig).

## 14. Performance before/after

dist 89MB unchanged; UnifiedShell chunk ~12KB lazy (part of App
chunk — measured, within budgets); budgets green; LCP/CLS unchanged
(portal measured; /app re-verified no-404).

## 15. Visual QA

`docs/audit/evidence/qa-unified-desktop.png`: unified mode live
(status + presence + task + resources + details + settings).
Onboarding gate observed (existing auth wall, untouched).

## 16. Tests

9 unified (layout/density/honesty/offline/no-fake) + 9 presence +
3 states + 16 portal + contract SSR test — all green. tsc 0.

## 17. Remaining limitations

Full App re-layout pending (panels are the seam) · density affects
panels only (chat list unchanged) · run duration client-observed
(labelled) · model/provider rows depend on telemetry fields ·
tap-to-expand presence minimal (title) · onboarding chain untouched.

## 18. Exact commits

(next commit)

## 19. CI run

(to monitor)

## 20. Verdict

GREEN WITH LIMITATIONS — unified experience implemented, tested,
performance-safe; only declared non-critical limits remain.
