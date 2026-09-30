# GENIO INTELLIGENT INSTALLER FINAL REPORT

# Executive Summary

Follow-up to `GENIO_INTELLIGENT_INSTALLER_REPORT.md` (NOT VERIFIED then for
want of a clean-OS live repair). This gate fixes the reported
`GENIO_REF=<SHA>` bootstrap failure, hardens every remaining raw-error path,
completes the assistant UX contracts, and re-proves everything end to end.
Strict verdict below: every acceptance box is checked except live privileged
repair on a clean OS, which this dev host cannot provide.

# Starting Commit

`a349984` (docs: installer report, evidence index, README assistant mode).

# Ending Commit

`final/*` commits on `main` (bootstrap ref fix; hardening/UX completion;
tests/evidence/docs), pushed after verification. No tags, releases, version
bumps, history rewrites, or G6-C.

# Root Causes Found

1. Bootstrap passed EVERY ref to `git clone --branch` — commit SHAs always
   failed (the exact reported `4991070…` failure, reproduced verbatim).
2. Short SHAs cannot be fetched by OID at all (protocol needs full SHAs).
3. `make_release._run` still let `FileNotFoundError` escape (release path).
4. Doctor rendered its own tool checks instead of the shared preflight engine.
5. `doctor --json` polluted stdout (human lines + JSON mixed).
6. Success message advertised a non-existent `bin/genio-serve` starter.
7. Missing-mark duplication (`✓ ✓`) in several assistant lines.
8. Missing `readline` EOFError hardening in one assistant path (fixed).
9. Uninstall/refuse/repair/update/rollback messages bypassed i18n.

# GENIO_REF Fix

`installer/bootstrap/install.sh` now classifies via `ls-remote`:
branch → shallow `--branch` clone; tag → shallow `--branch` clone;
commit → `init + fetch <full-SHA> + checkout FETCH_HEAD` with prefix-match
verification (short SHAs resolved to full via GitHub API for github.com
repos, else an honest full-SHA demand). Unknown refs fail closed in
Tunisian (exit 14). Every run prints `ref kind=` + `resolved SHA=`.
New `GENIO_RESOLVE_ONLY=1` verifies a ref without installing.
`GIT_HTTP_LOW_SPEED_*` bounds stalled transfers instead of hanging.

# Prerequisite Detection

Unchanged engine (`installer/preflight.py`), now also consumed by doctor.
States AVAILABLE/MISSING/BROKEN/DAEMON_DOWN/PERMISSION_DENIED/
VERSION_TOO_OLD/UNKNOWN. Live proof: dead-socket docker CLI →
DAEMON_DOWN; permission-denied classified from the verbatim real message
(unit; no spare OS user exists for a live run).

# Assistant Architecture

Unchanged modules (`i18n`/`assistant`/`flow`/`packages`); completed gaps:
final-fail guidance with safe manual hint, EOF-proof reads, no doubled
marks, honest `start_cmd_real`, localized refuse/repair/update/rollback/
uninstall strings. No LLM anywhere; deterministic state machine.

# Tunisian UX

Default Derja end to end (proven in logs), FR/EN secondaries (FR proven
live via locale fallback in the pipe run). No Arabizi found in installer
user text (checked in review; `test_o_*` guards first strings).

# Sudo/Permission Handling

Consent (what + why + exact commands on demand) before every privileged
change; non-interactive never consents; docker permission path gives the
exact `usermod -aG docker` + re-login guidance. No `sudo pip`, no `git-all`
(AST + map assertions), argv-only execution.

# Real Installation Evidence

- `e2e-install.log`: isolated prefix, exit 0, frontend PASS, smoke 3/3.
- `e2e-assistant.log`: pty interactive, exit 0, full TN conversation.
- `e2e-missing-git.log`: isolated PATH (git+docker absent) + dry-run:
  detect → explain → consent → repair → honest verify-FAIL → retry →
  exit 13, zero tracebacks, zero system changes.
- `e2e-curlbash-assistant.log`: REAL pipe entry (`cat install.sh | … bash`),
  ref branch resolution, clone, assistant install exit 0 (FR locale).
- `ref-matrix.log`: main/tag/full-SHA/short-SHA PASS + bogus fail-closed.
- `installer-e2e-results.json`: machine-readable index.

# Test Results

- tsc: 0 errors. installer: 54 passed (incl. ref-kind, shared-engine,
  json-clean tests). backend: 227 passed. frontend: 99 passed.
- build: clean (9.39 s).

# Security Verification

- No `shell=True` (AST test over installer sources).
- Secrets scrubber tested; evidence contains no secrets.
- Trust model unchanged (GitHub TLS + ref pin; no new distribution).
- Retries bounded; privileged ops explicit; sudo never silent.

# Remaining Limitations

1. Live (non-dry) sudo package repair: deps present, uninstall forbidden.
2. Truly clean OS: dev host only.
3. Docker-daemon repair execution: daemon already healthy.
4. Permission-denied live run: no spare user (message-verbatim unit test).
5. Model-dialect variance: out of installer scope (frozen).

# Exact Commands Used

- `GENIO_REF=<main|v5.0.0|full|short> GENIO_RESOLVE_ONLY=1 bash installer/bootstrap/install.sh`
- `cat installer/bootstrap/install.sh | GENIO_REF=main GENIO_ASSISTANT=1 GENIO_PREFIX=/tmp/genio-pipe bash`
- `python3 installer/genio install --assistant --prefix … --source …` (+ `--dry-run` for simulation)
- `python3 installer/genio doctor [--json] [--lang tu|fr]`
- `python3 -m pytest installer/tests/ tests/ ; npx tsc --noEmit ; npx vitest run ; npm run build`

# Exact Exit Codes

0 OK · 11 already-installed · 13 deps-missing · 14 unknown-ref/download ·
16 install-fail · 17 verify/smoke-fail · 22 user-abort. All observed live
except 16/17 paths (unit-covered).

# Explicit Final Verdict

NOT VERIFIED — solely because live privileged repair on a clean OS cannot
be performed from this development host (same single item as the previous
gate, now narrower: everything else on the acceptance list passed with
real evidence). The three verdict blockers from the last report are closed:
ref matrix green incl. the exact blocking SHA, no-traceback paths hardened
and proven, assistant E2E demonstrated through the real pipe entry.
