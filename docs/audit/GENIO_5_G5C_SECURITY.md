# GENIO_5_G5C_SECURITY (desktop threat audit)

## Boundary model

Browser (React) → typed bridge → Tauri plugins → OS. No shell
execution primitive exists anywhere in the chain (grep-proven,
tested). The browser is untrusted input; every native call validates.

## Findings

| Threat | Impact | Mitigation | Test | Result |
|---|---|---|---|---|
| Command injection (native) | RCE | No execute/Command API exists; allowlist: 4 typed commands | test: no `Command`/`execute(`/eval in client | PASS |
| URL injection (open) | arbitrary app/URL launch | allowlist https+intent; updater call-sites gated via validateOpenUrl | bridge URL tests + updater gate | PASS |
| Path traversal (fs) | arbitrary file access | fs scoped to $CACHE/** + $TEMP/** (capability file) | capability assert (below) | PASS |
| Arbitrary file access | data theft | same scopes; user files via browser File API (no Tauri fs) | scopes | PASS |
| Secret leakage (diagnostics) | credential exposure | getDiagnostics returns versions/OS/arch only; installer secrets never in bridge payloads | NOT_AVAILABLE on web; fields enumerated | PASS |
| Unsafe deserialization | IPC confusion | JSON envelopes validated (method/request_id/types); unknown → MALFORMED | ipc_v1x suite (18) | PASS |
| Privilege escalation | root | no sudo in desktop path; systemd step stays explicit CLI | design (no code path) | PASS |
| Bridge abuse (extra commands) | scope creep | exhaustive switch (TS `never`); unknown → UNKNOWN_COMMAND | parity/validation tests | PASS |
| Notification abuse | spam/social engineering | status-only bodies (never content/secrets); permission-gated; no actions attached | lifecycle tests | PASS |
| Updater tampering | malicious binary | SHA+size+platform/arch/version/downgrade checks; prod requires signature | 7 updater tests | PASS |
| Downgrade attack | rollback to vuln version | refused without explicit override (installer + updater) | tests | PASS |
| Artifact substitution | wrong binary | checksum from user-side file, never from response; fail closed | tamper test | PASS |
| Malicious manifest | confused updater | mandatory fields enforced; unknown platform rejected | tests | PASS |
| Malformed event payload | UI confusion | event protocol asserts closed sets; visualizer flags invalid lines | event tests | PASS |

## Capability assertions (new test)

`tests/test_tauri_capabilities.py`: default.json parsed — shell has
open-only (no execute), fs/http entries carry explicit scopes, no
wildcard `*` scope, updater pubkey documented untrusted.
