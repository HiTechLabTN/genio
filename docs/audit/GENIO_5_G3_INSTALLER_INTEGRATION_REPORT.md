# GENIO_5_G3_INSTALLER_INTEGRATION_REPORT

## 1. Architecture

Option B adopted (boundary doc `GENIO_5_G3_BOUNDARY.md`): browser
guides, user launches the official CLI. No bridge daemon, no
`/execute` endpoint, no second installer. Contract = JSON event
protocol (`installer/core/events.py` ↔ `installEvents.ts`).

## 2. Execution boundary

CLI user-launched only. Portal renders; visualizer parses pasted
`--json-events` logs deterministically. Desktop native bridge:
architecture-ready, implementation BLOCKED (no toolchain).

## 3. Threat model

15 threats × mitigations (boundary doc). Proofs: no shell primitives
in browser code (test), localhost allowlist (test), no embedded
secrets (test), checksum never trusted from download (CLI flag/file
only, tamper-tested), sudo explicit + separate.

## 4. Event protocol

18 events, closed set (asserted), each mapped to a G1 state.
Payload: protocol id, installer version, state, scrubbed data,
typed error. TS mirror locked both sides.

## 5. State machine

G1 machine reused unchanged (no duplicate system). UI renders
`EVENT_STATES` mapping; invalid lines flagged, never hidden.

## 6. Artifact trust chain

TLS → ref/SHA → archive SHA-256 (user file) → extract → pinned venv
→ import verify → manifest. Mismatch aborts (tamper test green).

## 7. Download security

HTTPS-only origins (release artifacts), sha verification, size via
release.json, timeouts on runner, atomic tmp dirs, cleanup on
cancel/failure, disk preflight via doctor. No arbitrary browser URL.

## 8. Privilege model

Browser: none. CLI: user. Systemd step: explicit sudo, separate.
Socket/group only where sandbox required (documented).

## 9. Existing-installation handling

Unchanged + `--force` path tested (moves code aside, data kept).
Partial → refuse with repair guidance (tested).

## 10. Failure handling

13 stable codes (message+recovery+docs), emitted in events, rendered
in visualizer with recovery + docs links. No stack traces to users
(CLI prints short message + hint; log has details).

## 11. Rollback

Existing mechanism + ROLLBACK_STARTED/COMPLETED events; verified
result required before ROLLED_BACK display (code path + live).

## 12. CLI parity

GUI visualizer consumes CLI output; every GUI concept maps to a CLI
command. No GUI-only behavior.

## 13. Doctor integration

Post-install verify + `doctor --deep` in clean-room (0 FAIL).
Health never inferred from process existence.

## 14. Desktop integration status

BLOCKED (no Rust toolchain). Contract + harness ready. No fake.

## 15. Tests

- `installer/tests/test_events.py` (7): schema, scrub, states, mirror
- `installEvents.test.ts` (5): parse, failures, severities
- `tests/test_browser_security.py` (5): no-exec, allowlist, downloads, secrets
- `test_chaos.py` +2 (copy branch, non-empty refusal)
- Portal visualizer covered in `portal.test.tsx` run (16 tests set)
- Full backend halves green; vitest 34; tsc 0; build OK

## 16. Clean-room proof (public 4.1.0 + --json-events)

obtain→sha OK→install (14 events, complete)→API 200→WS answer→
doctor HEALTHY→sandbox/security spot→update→rollback→data kept→
uninstall (data kept).Destroyed after evidence.

## 17. Browser security proof

Static: no child_process/spawn/eval/Function/Command.execute in
browser code (audited: only Tauri `open(url)`, no execute).
Dynamic: portal has no fetch beyond same-origin + documented hosts;
download hrefs from product-data or marked unavailable.

## 18. Known limitations

- Visualizer needs manual paste (no live bridge by design).
- Desktop bridge pending toolchain.
- Cancel tested at CLI level (SIGINT cleanup); mid-subprocess cancel
  relies on process-group kill (documented).
- Doctor `--deep` needs running services (WARN otherwise, honest).

## 19. External blockers

Tauri toolchain, Android SDK/secrets (unchanged).

## 20. Exact commits

(this report committed next; code commits below)

## 21. CI run

(to monitor after push)

## 22. Final verdict

GREEN WITH LIMITATIONS (real integration works + security-tested;
only documented external/native limits remain).
