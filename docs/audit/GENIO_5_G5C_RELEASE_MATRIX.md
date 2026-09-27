# GENIO_5_G5C_RELEASE_MATRIX

| Capability | Web | CLI | Linux Desktop | Windows | macOS | Android | iOS | Evidence | Status | Blocker |
|---|---|---|---|---|---|---|---|---|---|---|
| Chat/agent | PASS | N/A | PASS (same UI) | BLOCKED | BLOCKED | BLOCKED | BLOCKED | browser shots + native shot | PASS web/linux | toolchain |
| Install | N/A | PASS | N/A | N/A | N/A | N/A | N/A | 19 tests + clean-room | PASS | — |
| Doctor/repair/update/rollback | N/A | PASS | N/A | N/A | N/A | N/A | N/A | chaos + live cycles | PASS | — |
| IPC v1.x | N/A | PASS | PASS (contract) | N/A | N/A | N/A | N/A | 18+6 tests | PASS | daemon impl (OS) |
| Sandbox | PASS* | PASS | PASS* | BLOCKED | BLOCKED | NOT_APPLICABLE | NOT_APPLICABLE | fail-closed + exec proofs | PASS where runnable | toolchain |
| Voice | PASS | N/A | PASS (same UI) | BLOCKED | BLOCKED | BLOCKED | BLOCKED | live matrix | PASS web | signing/SDK |
| Presence/states | PASS | N/A | PASS | BLOCKED | BLOCKED | BLOCKED | BLOCKED | 9+11 tests + shots | PASS | — |
| Notifications | UNAVAILABLE | N/A | UNAVAILABLE* | BLOCKED | BLOCKED | BLOCKED | BLOCKED | permission-gated, unwired to tasks live | LIMITATION | wiring = next |
| Updater verify | N/A | PASS | PASS (manifest) | BLOCKED | BLOCKED | BLOCKED | BLOCKED | 7 tests | PASS unsigned-dev only | signing key |
| Packaging Linux | N/A | N/A | PASS (AppImage+DEB) | N/A | N/A | N/A | N/A | artifacts + launch + shot | PASS | signing |
| Diagnostics honest | PASS | PASS | PASS | BLOCKED | BLOCKED | BLOCKED | BLOCKED | bridge tests | PASS | — |

*Sandbox in browser context = backend capability surfaced, not browser-exec.
*Notifications: pipeline code complete, live OS delivery not exercised
(permission flow needs real desktop session interaction).
