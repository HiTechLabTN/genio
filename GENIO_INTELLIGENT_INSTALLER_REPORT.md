# GENIO INTELLIGENT INSTALLER REPORT (repair mission)

This extends `GENIO_INTELLIGENT_INSTALLER_FINAL_REPORT.md` (which ended
NOT VERIFIED for want of a live privileged repair). That exact repair has
now been demonstrated on a real fresh Debian 12 container.

# Initial Failure

Fresh Debian 12 + `curl|bash`: assistant detected pip-missing, venv-broken,
docker-missing, then stopped with a manual command. Root cause: bootstrap
always forced `--yes` (non-interactive), so the repair branch never ran.

# Root Cause

1. Bootstrap mode selection ignored TTY (always `--yes` unless
   `GENIO_ASSISTANT=1`).
2. Stage A covered git only; python3 missing killed the installer launch.
3. `head -n 1` over-read the terminal answer buffer (later answers lost).
4. apt/debconf consumed `/dev/tty` answers mid-repair.
5. `ls-remote` misclassified local-path repos under foreign UIDs.
6. Docker verify used `--format` (misleading template errors) and skipped
   items still received ok-lines (false success).
7. Success block claimed full health even when smoke reported ATTENTION.

# Architecture Changed

- Bootstrap: TTY-aware default (assistant when usable TTY, `--yes` only
  with `GENIO_YES=1`/`--yes`/no-TTY); Stage A generalized to
  `ensure_tool` (git + python3); `ask_tty` via `IFS read`; apt stdin
  `/dev/null` + `DEBIAN_FRONTEND=noninteractive`; `safe.directory` guards.
- `Runner.run` + `packages.Executor`: `stdin=DEVNULL` always.
- `packages.install_needs`: noninteractive frontend for apt family.
- `preflight._docker_state`: plain `docker info` classification.
- `flow.repair_missing`: skipped-docker set (no ok-lines for skipped).
- `genio` CLI: partial-health success caveat; real `start_cmd`.
- `assistant.ask_yes_no`: bare Enter = yes.

# Bootstrap Changes

Two-stage + TTY default + wget fallback + ref matrix intact
(branch/tag/full/short SHA re-verified) + `GENIO_RESOLVE_ONLY`.

# Preflight Changes

Docker probe without `--format`; daemon/permission split preserved and
proven live (dead socket → DAEMON_DOWN).

# Package Mappings

Unchanged minimal maps (git / python3+venv+pip / docker.io per family);
`apt-get update` precedes installs; no git-all, no sudo pip, argv-only
(AST-tested).

# Sudo/TTY Behavior

Consent with what/why/exact-commands; `/dev/tty` under pipe; EOF-safe;
no-TTY → clean abort (exit 22), never hangs. Answers no longer eaten
(read builtin, DEVNULL children, noninteractive debconf).

# Docker Behavior

Install docker.io → verify CLI → daemon ensure (systemctl/service) →
permission triage → DAEMON_DOWN/PERMISSION unfixable ⇒ honest warn +
continue without Docker (Tier A), never abort, never false success.

# GENIO_REF Behavior

Unchanged and re-verified: branch/tag/full/short-SHA matrix green,
bogus fail-closed TN, never `--branch <SHA>`.

# Tests

- installer: 58 passed (added: Enter=yes, bootstrap TTY/ensure/safe-dir/
  DEVNULL assertions, docker-skip determinism).
- backend: 227 passed. frontend: 99 passed. tsc: 0 errors. build: clean.

# Real Human-Visible Evidence

- `e2e-debian12-final.log`: fresh Debian 12 (curl only) → Stage A git →
  Stage A python3 → clone → TN preflight (pip MISSING, venv BROKEN,
  docker MISSING) → single sudo consent → real apt repair → Docker
  DAEMON_DOWN honest skip → install → manifest healthy → smoke →
  success + first-run invitation. Zero tracebacks, zero git-all.
- `installer-e2e-results.json`: machine-readable index (incl. this run).

# Exact Commands Tested

- `docker run -d debian:12 sleep …` + curl-only prep + piped bootstrap
  with pty answers (full transcript in evidence).
- `GENIO_REF=<main|v5.0.0|full|short> GENIO_RESOLVE_ONLY=1 bash …`
- `python3 installer/genio install --assistant [--dry-run] …`
- `python3 installer/genio doctor [--json] [--lang …]`
- `pytest installer/tests/ tests/`, `vitest run`, `tsc --noEmit`, build.

# Known Limitations

1. Docker daemon cannot start without systemd (containers/limited hosts):
   handled by honest skip, not fixed (needs real host init).
2. Permission-denied live run needs a spare OS user (message-verbatim
   unit test instead).
3. First-run diagnostic answer lost when the E2E container's sleep
   expired; invitation + diagnostic path proven in prior pty run.
4. Model-dialect variance: out of installer scope (frozen).

# Explicit Final Verdict

PARTIALLY VERIFIED — the complete privileged repair flow is demonstrated
end to end on real Debian 12 (detect → explain → consent → repair →
verify → retry-safe → install → smoke → first-run invitation) with zero
tracebacks and zero bundle installs. Withheld from VERIFIED only for:
live permission-denied execution (no spare user) and daemon-start on a
systemd host (no such host available).
