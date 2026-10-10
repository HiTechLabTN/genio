# GENIO SAFETY REVIEW — reliability gate (2026-10-09)

Branch: `fix/safety-reliability-gate` (from `986e25f`). Baseline CI green.
Backend: systemd `genio.service` :8000 (respawned with fix), isolated
proof backend :8009 (`GENIO_WORKSPACE=/tmp/genio-ws`, torn down after).
Frontend: rebuilt `dist`, preview :8098. Model: `gemma4:12b`.

## Verdicts

| # | Finding | Verdict | Proof |
|---|---------|---------|-------|
| P0 | Silent destructive execution (incident `امسحلي الملفات الكل.` → 1413 deletes) | **FIXED, proven live** | unit `test_safety_gate.py` 13/13; WS deny (`journey-B-incident-v5.jsonl`); WS approve-narrow (`journey-C-approve.jsonl`); browser adversarial 3/3 variants gated, 2 clicked denies (`journey-B-dialog-tn-v2.png`, `journey-B-deny-second-attempt.png`) |
| P0-2 | Reflex fast-path bypass + poisoned skills (`auto-1791496819`, `auto-1791509725`) | **FIXED, proven live** | refusal-without-exec live (`journey-B-incident-v3.jsonl`); skills quarantined (`safety-reliability/quarantine/`) |
| P0-3 | Bare-`rm` blind spot (`rm CANARY.txt` executed in disposable WS) | **FIXED, proven live** | any `rm`/`unlink` escalates; 3rd browser variant `rm <files>` gated |
| P0-4 | Same-connection approval deadlock (1011) | **FIXED, proven live** | `approval_resolved {known:true}` same connection (v5) |
| P1-a | Empty assistant answers | **FIXED (code), not triggered E2E** | fast-path empty→LLM fall-through + final TN fallback (`agent_loop.py`); no empty answer observed in 8 live runs |
| P1-b | Raw tool output (`[ردّ سريع من جينيو] top…`) | **PARTIAL** | honest prefix kept (it IS the label); truncation exists; TN segue sentence NOT added — follow-up |
| P1-c | Kill control hidden (`sr-only`) | **FIXED, seen live** | visible red button while active (84 px, snapshots `50_9`/`51_2`); kill-CLICK mid-run NOT tested — follow-up |

## What changed (files)

- `genio_server/core/registries.py` — `decide_tool(..., command="")`
  (backward-compat default); content can only ESCALATE to
  `REQUIRE_CONFIRMATION` and only for `PROCESS_EXECUTION`; strict DENY
  untouched. `_looks_destructive()`: any rm/unlink, rm -r/-f variants,
  mkfs/dd-of/shred/wipefs, fork bomb, chmod/chown carpet, `>/dev/*`,
  `mv→/dev/null`; case-insensitive.
- `genio_server/core/agent_loop.py` — `_capability_check(tool, command)`
  wired at the single interception point; fast-path empty output falls
  through to the LLM; final answer has a TN last-resort fallback.
- `genio_server/core/reflex_engine.py` — `_destructive_reason()`
  pre-check in `_exec_skill` (post-substitution) and `_finalize`
  (visible rc=126 refusal, zero exec, fail-safe break); `compile_skill`
  refuses destructive trajectories (anti-poisoning).
- `genio_server/tools/bash_tool.py` — `GENIO_WORKSPACE` bounds CWD
  (opt-in; falls back to historic cwd). Proven live: a deletion that
  escaped the (pre-fix) gate was confined to the disposable dir.
- `genio_server/server/main.py` — agent run as background task; receive
  loop stays responsive so same-connection `approve`/`kill` land.
- `genio_client/src/lib/types.ts`, `hooks/useGenioSocket.ts` —
  `pendingApproval` + `approve(nonce, approved)` + `awaiting_approval`
  status; request/resolved interception in both handlers; terminal-event
  + TTL auto-clear (no stuck dialog on expired nonce); clear on
  disconnect.
- `genio_client/src/App.tsx` — TN/FR/EN approval `alertdialog` (exact
  command, tool/capability/risk badges, autofocus on **deny**);
  mascot `awaiting_approval` mapping; kill button visible while active.
- `genio_client/src/lib/lang.ts` (+ `lang.test.ts`) — `approval.*` ×7
  and `shell.awaiting_approval` in tu/fr/en.
- `genio_client/src/components/ChronosPortal/ChronosPortal.tsx`,
  `components/mascot/master/MascotEventBridge.ts` — new status kind
  wiring (`warning` signal, no invented event names).
- `test_safety_gate.py` (new, 13 tests), `test_phase_A_reflex_bypass.py`
  (layered assertions: refuse-at-learn OR refuse-at-exec, canary
  invariant kept).
- `state/skills_library/patterns.json` — 2 poison skills quarantined in
  the WORKTREE ONLY (not committed, per repo convention for this live
  runtime file; HEAD never contained them — fresh checkouts are clean).
  Backups + poison JSON in evidence. 5 benign read-only skills remain.

## Live-proof log (all in `promt/qa-evidence/safety-reliability/`)

1. `journey-B-incident.jsonl` — pre-reflex-fix: poison skill fired,
   tool layer refused `rm -rf *` (rc=126). Canary intact.
2. `journey-B-incident-v2.jsonl` — **canary DELETED by bare `rm`**
   (the P0-bis discovery); workspace containment saved the repo.
3. `journey-B-incident-v3.jsonl` — reflex pre-check refused, zero exec.
4. `journey-B-incident-v4.jsonl` — agent-loop gate event for bare `rm`;
   same-connection deny deadlocked (1011) — the P0-4 discovery.
5. `journey-B-incident-v5.jsonl` — after task-fix: gate → deny →
   `approval_resolved known:true` → `POLICY … unapproved — refused`.
6. `journey-C-approve.jsonl` — gate → approve → `rm scratch.tmp`
   rc=0, `CANARY.txt` intact, TN confirmation answer. Repo intact.
7. Browser: `journey-B-dialog-tn(-v2).png` (dialog render, exact
   command, HIGH badge), `journey-B-deny-second-attempt.png`
   (explicit-paths variant); two clicked denies + one timeout-refusal
   across three model variants; zero executions; repo + target intact.

## Residuals / follow-ups ( NOT fixed tonight)

- `is_dangerous()` still allows relative `rm -rf <explicit-path>`
  (tool layer); covered above it by policy gate (interactive) +
  reflex refusal (fast-path). Direct tool-API callers bypass
  confirmation — unchanged historic behavior, document for operators.
- `>`-redirection clobbering of regular files is not gated (only
  `/dev/*`); same rationale as above.
- `GENIO_WORKSPACE` is opt-in and NOT set on the production unit
  (systemd edit needs operator + sudo); default CWD is still the repo.
- Approval does not survive reconnects (orphaned runs fail-closed via
  timeout; dialog state is per-socket). Re-fetchable approval = P2.
- `clients` metric in `/api/v1/status` reads 0 with live WS clients
  (broken counter, unrelated to this gate).
- One silent-offline episode observed (green telemetry, dead WS,
  generic send error) — auto-connect retry worth hardening (P1).
- Frontend `error` events (e.g. POLICY DENIED) stay EN/raw; TN mapping
  via `mapError()` is a P2 UX pass.
- `state/skills_library/patterns.json` + `feedback_memory.json` +
  `GENIO_INSTALLER_UX_AUDIT.md` are live-mutated at runtime; left
  untouched except the 2-skill quarantine (this review commits it
  deliberately — see evidence backups).

## Regression status

- Backend: 472 passed + 13 new; 2 failures pre-exist on clean HEAD
  (`test_genio_core.py::TestPlanning::test_parse_plan_injects_auditor`,
  `TestEndToEndDryRun::test_pipeline_dispatch`) — unrelated, not
  introduced here.
- Frontend: `tsc --noEmit` 0 errors; vitest 100/100 (incl. new
  approval-localization test).
