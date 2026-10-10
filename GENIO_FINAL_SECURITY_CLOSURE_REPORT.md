# GENIO FINAL SECURITY CLOSURE REPORT (2026-10-10)

Branch: `fix/safety-reliability-gate`. HEAD at gate start: `22e772f`.
No merge / push / release performed (per mission). Scope: close and
independently verify all P0 + listed P1 before merge. No unrelated P2.

State preserved: HEAD + full status captured; gate-start backups of all
four live runtime files in `/tmp/closure-gate/`; prior evidence tarball
in `/tmp/genio-work-backup/`; no broad restore/reset/clean executed at
any point. Runtime files still live-mutating (system running) and left
uncommitted, except the documented 2-skill worktree quarantine.

## 1. Tool-layer destructive-command gap — CLOSED (PASS)

Root cause: `is_dangerous()` (shared by `run_command`,
`async_run_command`, and via routing the container path) exempted
relative recursive/force `rm` (`rm -rf build` → None) and its AST layer
exempted every absolute path except a stale `/work` root; `async_*`
ignored `GENIO_WORKSPACE`; invalid workspace silently fell back to
server cwd. Direct tool-API callers bypassed the interactive
confirmation gate entirely.

Fix (`genio_server/tools/bash_tool.py`, `bash_ast.py`, `tools/__init__.py`):
- `is_dangerous(command, workspace=None)` enforces workspace-canonicalized
  rm scoping (realpath: `..`/symlink-aware, raw-regex fallback for quoted
  payloads, true-roots-only raw backstop). No relative-path exemption.
- Refusal classes: HARD (roots `/` `/*`, system/cred/device/kernel-FS,
  privesc, fork, mkfs, container-escape, setuid — `refusal_overridable`
  False, never executable via agent) vs SCOPED (`scoped:` + workspace
  messages — executable only on fresh single-use approval bound to the
  exact command). AST defers non-system absolute targets to the canonical
  layer (stale `/work` exemption removed).
- `mv→/dev/null`, `shred`/`wipefs`, `dd of=<regular-file>` → SCOPED.
- `GENIO_WORKSPACE` valid → explicit disposable scope (recursive rm
  inside executes); unset/invalid → server cwd, recursive/force rm needs
  approval; invalid value warns loudly and never silently broadens.
- `run_command`/`async_run_command(..., approval=None)` verify via
  policy-engine `consume()` (single-use, exact-match, expiry) before
  overriding SCOPED refusals; `invoke()` threads the token.
- `core/policy_engine.py`: `resolve` single-use + expiry-enforced,
  `await_decision` no longer pops, new `consume(nonce, command)` +
  `release()`; `agent_loop` threads the token and executes the identical
  string; denied/timeout paths release; gate event now carries `cwd`,
  rendered in the dialog (`التنفيذ في …`).

Regression tests: `test_tool_boundary.py` (24: relative/absolute/multi/
traversal/symlink/missing-workspace/changed-targets/denied/expired/
replay/concurrent/validation-failure/async/invoke/classes — all on real
fixtures asserting zero destruction); `test_safety_gate.py` (+final-text
+ both-layers test); `test_bash_tool_safety.py` (contract updated:
relative-`rm -rf` now SCOPED, explicit-workspace executes);
`tests/test_policy_engine.py` (consume/release/purge lifecycle);
4 test doubles updated for the 4-arg invoke call (behavioral asserts kept).

Execution evidence:
- Unit: 101/101 focused (boundary+safety+reflex+registries+sandbox+tolerant-ws).
- Live WS :8009: reconnect-approve executes narrowly
  (`final/reconnect-stale-8009.jsonl`: scratch gone, CANARY intact);
  replay rejected (`known:false`); stale approve past 8 s timeout
  rejected, both fixtures intact (`final/stale-approve-8009.jsonl`).
- Live WS :8000: bare-`rm` gate event carries `"cwd":
  "/data/ai_tools/genio"` (`final/probe-bare-rm-8000.jsonl`).
- Live browser :8000: 3/3 adversarial variants gated (2 clicked denies,
  1 timeout); cwd-line dialog screenshotted + denied
  (`journey-B-dialog-cwd.png`).
Remaining risk: non-`rm` destruction idioms (`git clean -fdx`,
`find -delete`, interpreter rmtree, `>`-clobber of regular files) are
not string-matchable — documented; true isolation is container mode.

## 2. Systemd workspace configuration — DECIDED: OPTIONAL, UNSET (PASS)

Inspected `/etc/systemd/system/genio.service`: `WorkingDirectory=
/data/ai_tools/genio`, env has no `GENIO_WORKSPACE` (verified live via
`/proc/<pid>/environ`), defaults (development, 120 s confirm).
Setting a global workspace would redirect ALL agent cwd and break
repo-relative work (recon, git, builds). Omitting is SAFE under §1
(destructive requires approval; invalid value fails closed with
warning). Smallest justified change: NONE to the unit. No sudo
mutation performed.

## 3. Missing live E2E — COMPLETE (PASS)

- Kill-click: visible red button clicked mid-run → backend idle, no
  answer rendered (`journey-E-kill-visible.png` + snapshot). PASS.
- Empty-answer: `_final_text` unit-pinned (answer→synthesis→explicit TN
  non-success fallback); live runs observed honest non-success answers
  (missing-file explanation, quota synthesis). No empty/misleading
  completion observed in 15+ live runs. PASS (unit + observational).
- Reconnect during approval: socket dropped at gate → reconnected
  approve resolved `known:true`, narrow execution, replay rejected
  (run 1, EXIT-clean checks). PASS.
- Stale approvals: late approve past timeout → `known:false`, fixtures
  intact (run 2). Changed-target approve → refused, fixtures intact
  (unit + live deny chains). PASS.
- Silent-offline: ROOT CAUSE FOUND — `App.connected` never cleared on
  socket drop (only manual disconnect). Fixed (liveness-binding effect
  + 10 s reconnect retry); drop → 🔴 `تقطع الاتصال` screenshotted
  (`journey-offline-badge.png`); recovery accepts + green observed.
  PASS (with retry fix verified by accepts+green).
- `clients` metric: CLASSIFIED — counts running agent turns
  (`sum(_ACTIVE_RUNS)`), not connections; historic misnomer, code
  comment added, no behavior change. LIMITATION (documented).

## 4. Pre-existing backend failures — CONFIRMED PRE-EXISTING (PASS)

Clean worktrees of `22e772f` and pristine `986e25f`: both fail
identically on `TestPlanning::test_parse_plan_injects_auditor`
(external `/data/ai_tools/llm_utils.py` `OllamaConfig.model` gap) and
`TestEndToEndDryRun::test_pipeline_dispatch` (`preflight_env`
'Critical service(s) down'). Tracebacks + comparison recorded in
`regression-tests/prefail-clean-copy-comparison.md`. Environmental,
unrelated to this branch, left failing (explicitly deselected).

## 5. Quarantine + runtime data — VERIFIED (PASS)

Poison skills absent after backend restart; incident prompt matches no
skill; zero destructive steps across all 8 loaded skills; worktree file
byte-identical to gate-start backup apart from 2 benign read-only
skills learned under the compile guard (evidence it works).
`feedback_memory.json` / `gestures.db` / `GENIO_INSTALLER_UX_AUDIT.md`
live-mutating, backed up, never written by this work, uncommitted.

## 6. Final verification — GREEN (PASS)

- Backend: 504 passed, 0 failed (+2 documented environmental deselects).
- Frontend: tsc 0 errors, vitest 100/100, production build serving.
- Closure broke 9 tests mid-work (4-arg invoke doubles, pop-on-await
  contract) — all fixed at the right layer with intent preserved; final
  suite fully green (no suppression: the only deselects are the two
  proven-environmental failures).
- Diff reviewable in one commit; runtime files excluded from staging.

## Verdict: VERIFIED WITH LIMITATIONS

Merge recommended. Limitations (all documented, none P0): reconnect does
not carry approval state (orphans fail closed); `clients` misnomer;
EN/raw error events; no WS-action logging in journal; aggressive SW
caching of old bundles in tests; shell-string sandboxing is inherently
incomplete outside container mode (operator-visible residual).
