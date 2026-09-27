# G3 execution boundary + threat model

## Decision: Option B (user-launched official installer) + event protocol

Evaluated (§2 charter):

- **A (local bridge daemon)** : REJECTED — new permanently-running
  privileged surface, unjustified while CLI exists and works.
- **B (browser guides → user runs official installer)** : ADOPTED.
  Zero new privilege, zero new attack surface. The browser NEVER
  executes host commands.
- **C (companion API)** : REJECTED — same as A with more surface.
- **D (desktop native bridge)** : BLOCKED — no Tauri build here.
  Architecture ready (typed protocol below), implementation pending.
- **E (web-only install)** : REJECTED — technically impossible
  without arbitrary code execution from the browser.

The integration contract is the **JSON event protocol**: the CLI
emits typed, scrubbed events (`--json-events`); any UI (portal
visualizer, future desktop, support tooling) renders them
deterministically. No second installer implementation exists.

## Threat model

| Threat | Mitigation (implemented) |
|---|---|
| Malicious website input | Portal renders only; no exec path exists in browser code (proven by grep test) |
| CSRF | No state-changing browser→host channel exists at all |
| Command injection | Browser never builds shell commands; CLI uses argv arrays, no shell=True |
| Path traversal | Prefix validated (absolute, no `..` escape); archive members sanitized on extract |
| Arbitrary command exec | No `/execute` endpoint; installer CLI is user-launched, not browser-launched |
| Artifact replacement | SHA-256 verified fail-closed; checksum never trusted from download response (CLI flag/file only) |
| Checksum substitution | `--checksum` is a user-provided file, compared locally; mismatch aborts |
| Privilege escalation | No sudo in normal path; systemd install is explicit + separate; browser never privileged |
| Confused deputy | Events are informational (CLI→human); no authority flows UI→installer |
| Localhost attacks | Portal only calls same-origin API/WS + explicit documented hosts (allowlist tested) |
| Malicious extensions | Out of scope (browser platform); installer verifies independently regardless of what UI showed |
| Compromised network | TLS + independent checksum; offline mode degrades honestly |
| Compromised release | Checksum mismatch aborts; SBOM + manifest cross-checkable |
| Replay | Nonces are runtime IPC concern; installer operations are user-confirmed each run |
| Stale installer | `version` command + manifest `installer_version`; update path documented |
| Downgrade | `--allow-downgrade` required (tested) |

## Trust chain

GitHub TLS → pinned ref/SHA → archive SHA-256 (user-side file) →
extract → venv from pinned requirements → import verify → manifest.
Every link verified locally; a break aborts with a stable error code.
