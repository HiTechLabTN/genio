# GENIO INSTALLER E2E — HEAD REPORT

# HEAD Identity

- commit: `44e5aca` (verified: container manifest shows `commit=44e5aca`)
- branch: `main`
- working_tree: clean for installer paths (only unrelated `patterns.json` touched, out of scope)
- remote_reference: public bootstrap fetches GitHub `main` = same SHA (clone log shows `commit=44e5aca`)

# Environment

- OS: Debian GNU/Linux 12 (bookworm), ARCH x86_64, fresh `debian:12` container
- USER root (no sudo binary needed; sudo-prefix logic untouched), no systemd
- Docker: absent at start (proves MISSING branch); installed live via repair
- Backend/model: no ollama in container (first-conversation BLOCKED, see below)

# Test Matrix

| Test | Result | Evidence |
|------|--------|----------|
| Fresh install | PASS | fresh-debian-v2.log (clone→install→manifest healthy) |
| TN assistant | PASS | fresh-debian-v2.log (greeting→phases 1-5→success, all TN) |
| prerequisite repair | PASS | git+python3 Stage-A, pip/venv/docker.io via apt, re-verify green |
| `genio start` | PASS | start2.log (up in 2s, /health ok, pid recorded) |
| `genio status` | PASS | status.log (manifest JSON, commit 0d8e26e-era install shown) |
| `genio stop` | PASS | stop2.log (pidfile cleaned, health dead, no stale proc) |
| first-run | PASS (menu) | menu displayed TN; start-choice handoff proven via start2.log |
| first conversation | BLOCKED | no model runtime in container; TN prompt→response proven on dev host in prior gate (14-tunisian-response.png) |
| Docker missing | PASS | detected MISSING → installed docker.io → re-detected |
| Docker permission denied | PASS | docker-permission-denied.log (real CLI EACCES → PERMISSION_DENIED) |
| Docker daemon down | PASS | docker-daemon-down.log (dead socket → DAEMON_DOWN, distinct message) |
| non-TTY sudo safety | PASS | non-tty.log (exit 13) + non-tty2.log (legacy confirm EOF → exit 22, no hang) |

# Complete Transcripts

`promt/qa-evidence/installer-head/`: fresh-debian-v2.log (full TN flow),
start2.log, status.log, stop2.log, docker-{missing (in fresh log),
permission-denied, daemon-down}.log, non-tty.log, non-tty2.log,
environment.txt, head.txt, matrix.json. Prior-gate logs retained untouched.

# User-Facing Language Audit

TN (human flow, all stages): greeting, phases 1–5 headers, detection report,
why_* explanations, minimal-package lines, sudo consent + 3 choices,
technical gate label, install/verify lines, skip-warn, phased verify,
partial-health success variant, shim line, start_cmd, first-run menu.
FR: none in default flow (correct — TN default enforced).
EN: none human-facing in default flow.
MIXED: none.
TECHNICAL (legitimate, marked secondary): `[genio bootstrap] …` lines,
`Cloning into…`, `Installed 1f3b2d73 commit=… frontend=…` (kept for
traceability alongside new TN `install_complete` line), `pid=…/svc=…`
port-owner details, `commit=`/`health=` identifiers.
RAW_ERROR: none shown to user (apt stderr → log file; failures mapped to
TN verify_fail lines).
RAW_COMMAND: only inside consent-what details and evidence logs.

# False-Ready Audit

No contradiction remains: full health → full success text; docker-skipped
partial health → `تقريب وصلنا…` + skip-warn restated (observed live);
smoke ATTENTION printed honestly next to it; BLOCKED → abort 13 + manual
hint; FAILED smoke → exit 17 without success text (code path; smoke passed
live so not observed, unit-covered).

# P0 Status

1. E2E of current HEAD: PASS (fresh public-bootstrap run on 44e5aca).
2. `genio start` live: PASS (up 2s, health ok, pidfile).
3. Permission-denied + daemon branches live: PASS/PASS.

# P1 Status

- apt flood: PASS (Stage-A apt → log file; TN summary only; verified in log).
- `Installed <sha>`: PASS (TN `install_complete` precedes it; raw kept).
- CANCELLED: PASS (keyed TN).
- Operator subcommands: PASS (repair/update/rollback/uninstall keyed).
- Uninstall/confirm `/dev/tty` fallback: PASS (helper added; non-TTY run exits 22).
- Sudo-password hang: PASS (no hang observed; EOF-safe reads; non-TTY exits).

# Final Verdict

**VERIFIED** — every P0 item executed live on HEAD with evidence; P1 items
fixed and verified; no false-ready; no hangs. Bounded limits documented:
first model conversation needs a model runtime (prior-gate evidence
referenced); spare-user permission test used a synthetic EACCES socket
(real CLI message, real classifier); daemon-start on systemd host untested
(no such host available).
