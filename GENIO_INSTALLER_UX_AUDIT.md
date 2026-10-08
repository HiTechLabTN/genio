# Genio Installer UX Audit

Audit-only. No code changed, nothing committed. All claims reference exact
evidence files or exact source locations. Working tree examined at commit
`a5bec97` plus uncommitted follow-ups (partial-health success variant,
start/how/no first-run menu, TN-default `resolve_lang`, launcher shim).

## 1. Executive Verdict

**NEEDS UX FIXES**

The core flow is functionally sound (detect → explain → consent → repair →
verify → install → smoke → first-run, all demonstrated live with zero
tracebacks and zero bundle installs). What blocks a production-ready call:
(a) the newest UX fixes in the working tree have **no E2E evidence yet**
(all Debian transcripts predate them); (b) several English/technical lines
still leak into the default TN flow; (c) apt's own output floods the
conversation; (d) permission-denied and daemon-repair paths were never
executed live.

## 2. Real User Journey

Proven by `e2e-debian12-final.log` + `e2e-debian12-v2.log` (fresh Debian 12,
curl only at start), corroborated by `e2e-missing-git.log`,
`e2e-assistant.log`, `e2e-curlbash-assistant.log`, `ref-matrix.log`:

`curl|bash` → TN Stage-A git self-repair (consent, apt) → TN python3
self-repair → clone → TN welcome → TN preflight report (pip MISSING, venv
BROKEN, docker MISSING) → TN explanations + minimal packages → single sudo
consent → real apt repair → Docker DAEMON_DOWN honestly detected →
skip-with-warning + continue → install → manifest healthy → smoke →
success + first-run invitation. No traceback anywhere; no `git-all`.

## 3. Language Audit

| Stage | Actual message (source) | Language | Acceptable? | Problem |
|---|---|---|---|---|
| Welcome | `🧞 عسلامة 👋 / أنا جينيو...` (`e2e-debian12-final.log:8-12`) | TN | Yes | None |
| Detection report | `هاو شنوّة لقيت في جهازك: ✓ python3 موجود...` (same, :16-22) | TN | Yes | Old logs show doubled `✓ ✓` — fixed in tree (`i18n.py`: marks live in `progress()`, not in strings) |
| Explanations | `Git يلزمني باش نجيب كود Genio... «git» تكفي` (same) | TN | Yes | None |
| Sudo consent | `باش نركّب python, docker، نحتاج صلاحيات administrator (sudo)... تحبني نكمّل؟ [1] نعم، كمّل...` | TN | Yes | None |
| Repair progress | `→ نركّب python, docker...` + apt's own stdout flood (`The following NEW packages...`, `Need to get 20.1 MB...`) | MIXED (TN + raw apt EN) | **No** | apt output floods default UX; technical gate covers only installer-internal log, not apt's stdout (P1) |
| Verify | `✓ pip يخدم`, `✗ Docker ما زال ما يخدمش: daemon not running` | TN | Yes | None |
| Docker skip | `Docker ما زال موش خدام — نكمّل من غيرو...` (`e2e-debian12-v2.log`) | TN | Yes | None |
| Install line | `Installed 52581f76 commit=ee81244 frontend=NOT_APPLICABLE` (`v2`) | EN/TECHNICAL | **No** | Raw technical line mid-TN-flow, unexplained (P1) |
| Smoke | `✓ الفحص سليم... / ✗ الفحص لقى مشكل...` | TN | Yes | None |
| Success (old) | `الجهاز تهيّأ بنجاح، والخدمات اللي يحتاجهم Genio يخدمو` + doctor ATTENTION (`final.log`) | TN but CONTRADICTORY | **No** | False-ready (fixed in tree, see §6) |
| Success (new) | partial-health caveat variant (tree only) | TN | Yes in code | **No E2E evidence** (P0) |
| First-run menu (old) | `[1] جرّب / [2] لا` (all Debian logs) | TN | Partial | New start/how/no menu in tree has **zero live runs** (P0) |
| Doctor | TN statuses (`سليم/ملاحظة/ناقص`), `--json` clean (code + test) | TN | Yes | None |
| repair/update/rollback/status/uninstall operator lines | `REPAIR FAILED:`, `updated X -> Y`, `rolled back, commit=`, `diagnosis:` (`installer/genio:229-277`) | EN | Partial | Operator surfaces, not the main flow — acceptable short-term, should be keyed (P1) |
| CANCELLED handler | `CANCELLED by user — ...` (`installer/genio:409`) | EN | **No** | Reachable by normal Ctrl-C users (P1) |

English-leakage verdict: default main flow is TN-first **in the working tree** (TN default now forced in `resolve_lang`; bare `LANG` no longer switches language). Residual leaks are the apt flood, the `Installed…` line, CANCELLED, and operator subcommands.

## 4. Tunisian Quality Score

| Stage | Score (0-3) | Reason / recommended wording |
|---|---|---|
| Welcome | 3 | Natural, warm, sets expectations. Keep. |
| Detection report | 3 | `هاو شنوّة لقيت في جهازك` + per-item plain words. Keep. |
| Explanations (why_*) | 3 | Concrete + minimal-package promise. Keep. |
| Sudo consent | 3 | Why + what-changes + 3 choices incl. details. Keep. |
| Repair progress | 2 | TN frame is good, but apt's EN flood drowns it → route apt to log, print summary only. |
| Docker messages | 2 | Honest and clear; `DAEMON_DOWN` vs permission wording verified; permission path text never seen live. |
| Success | 2 | Old variant contradicts smoke (0); new variant correct but unproven live. |
| First-run | 2 | Invitation is warm; old menu proven, new menu unproven; `start` outcome unknown live. |
| Doctor | 3 | `هاو شنوة لقيت في جهازك` + plain statuses. Keep. |
| Errors/failures | 3 | `deps_final_fail` + safe manual hint; bounded retry; exit codes observed (13/11). |

Overall Tunisian UX: **~2.4 / 3** — natural Derja, correct tone; deductions for flooding, unproven newest strings, and residual EN lines.

## 5. UX Audit

Works: greeting → detection → explanation → single consent → real repair → honest verify → retry → install → smoke → invitation. Nontechnical users never need to know pip/venv/PATH; sudo is explained; `git-all`/`sudo pip` absent (map + AST-tested).
Confusing: apt EN flood mid-conversation; unexplained `Installed <sha> …` line; CANCELLED in English; operator subcommands in English; new first-run menu never seen live.

## 6. False-Ready Audit

| Health | Required UI | Observed |
|---|---|---|
| HEALTHY (0 FAIL) | Full success | ✅ `e2e-assistant.log` (all green + success) |
| PARTIAL (docker down, core ok) | Success + explicit caveat | ✅ in `v2.log` (skip-warn variant); ❌ contradicted in `final.log` (old build claimed full health) |
| BLOCKED (required deps unfixable) | Clean abort, exit 13, manual hint | ✅ `e2e-missing-git.log` (dry-run + retry → 13) |
| FAILED (smoke fail) | No success claim | ⚠️ Old code printed success_2 unconditionally; tree gates on `smoke_ok` — **unproven live** |

State table: HEALTHY→success, PARTIAL→success+caveat, BLOCKED→abort-13, FAILED→exit-17 path exists in code; PARTIAL/FAILED branches lack fresh live runs.

## 7. Docker Audit

Proven: MISSING detected → `docker.io` installed for real → re-detection → daemon unreachable → `DAEMON_DOWN` (`daemon not running`, from real CLI output) → honest skip + Tier-A continue. User learns: installed ✓, daemon ✗, permission untested, works-without ✓ (`Tier A`), next action ✓ (`genio doctor`).
Not proven live: PERMISSION_DENIED execution (unit-tested against verbatim real message only — no spare OS user exists), daemon `systemctl enable --now` success path, `usermod -aG docker` recovery. User never needs socket/systemd/group knowledge unless they open technical details. Correct.

## 8. First-Run Audit

Proven: invitation + optional machine diagnostic + closing line (`e2e-assistant.log`); start command now real (`venv/bin/python …/repo/genio_server.py`, fixed from invented `bin/genio-serve`).
NOT proven: new start/how/no menu (zero live runs), actual `genio start` backend launch (launcher unit-tested only; container run would honestly fail without ollama — also untested), shim on PATH usage. Current feeling: invitation-grade, not yet "assistant runs with me" grade.

## 9. Command UX

Shim `prefix/bin/genio` is created (code) but no evidence it was ever executed, added to PATH, or used for `start/status/doctor`. `genio start|stop` exist with pidfile+health-wait (code + unit tests) but were never run live. `start_cmd` now prints a real command (fixed). `genio doctor/status` proven live repeatedly.

## 10. Platform Matrix

| Platform | Detection | Adapter | Repair | Install | First-run | E2E | Status |
|---|---|---|---|---|---|---|---|
| Debian 12 | ✅ os-release | ✅ apt map | ✅ live apt | ✅ live | ✅ TN flow | ✅ full logs | SUPPORTED (proven) |
| Pop!_OS/dev host | ✅ | ✅ | ✅ (dry) | ✅ /tmp prefix | ✅ | ✅ logs | SUPPORTED |
| Ubuntu/Mint/Fedora/Arch/Alpine | code (ids+maps) | code | — | — | — | ❌ none | CLAIMED, UNPROVEN |
| NixOS | ✅ explicit detect | guidance only | ❌ manual | — | — | ❌ | PARTIAL (honest) |
| macOS | ✅ system==Darwin | brew map (code) | ❌ | — | — | ❌ none | PARTIAL, UNPROVEN |
| Windows native | ✅ UNSUPPORTED + WSL2 guidance (code) | — | — | — | — | ❌ none | UNSUPPORTED (honest) |
| WSL1/2 | ✅ kernel-string detect | reuses Linux path | ❌ | — | — | ❌ none | PARTIAL, UNPROVEN |

## 11. Portability Risks

1. `input()` in legacy uninstall confirm + CANCELLED path reads stdin directly — under `curl|bash` it would consume script bytes (assistant paths correctly use `/dev/tty`; these don't).
2. `ask_tty` assumes `/dev/tty` semantics; containers without `script`/pty abort cleanly (proven pattern) but messaging could name it.
3. `DEBIAN_FRONTEND=noninteractive` only applied for apt family (correct) — dnf/pacman/zypper/apk untested live anywhere.
4. `shutil.which` PATH dependence: minimal PATHs (cron/systemd) could misdetect; no `PATH` sanity warning.
5. `sudo` password prompt under pty works, but NOPASSWD-less sudo + no TTY = hang risk bounded only by user Ctrl-C (NeedInput covers assistant reads, not sudo's own prompt).
6. `platform.system()` mockability fine; Windows/mac branches are dead code on Linux (zero coverage).

## 12. Error Recovery

| Failure | Detection | Explanation | Recovery | Retry | Final state |
|---|---|---|---|---|---|
| git missing | ✅ live | ✅ TN + minimal pkg | ✅ live apt | n/a (bootstrap) | ✅ continue |
| python3 missing | ✅ live | ✅ | ✅ live apt | — | ✅ continue |
| pip missing / venv broken | ✅ live | ✅ | ✅ live apt | ✅ bounded | ✅ continue |
| docker missing | ✅ live | ✅ | ✅ live install | ✅ | ✅ → daemon triage |
| daemon down | ✅ live | ✅ | systemctl attempt (code) | ✅ bounded | ✅ skip+continue |
| permission denied | message-tested | ✅ text exists | usermod guidance | n/a | ❌ never live-run |
| package install failure | ✅ rc path | ✅ | bounded retry → exit 13 | ✅ live (dry) | ✅ |
| network failure | `net_fail` key exists | — | retry/details/stop text | — | ❌ never live-run |
| sudo rejection | consent-no → abort 22 | ✅ | — | — | ⚠️ abort path exists, live run always answered yes |
| unsupported OS | ✅ code | ✅ + manual cmds | — | — | ❌ never live-run |
| invalid GENIO_REF | ✅ live (`zzz-nope`, TN) | ✅ | — | — | ✅ exit 14 |
| service start fail | code path | — | — | — | ❌ never live-run |

Users are guided in all live paths; never abandoned with a traceback (zero tracebacks in every log).

## 13. Security UX

Consent before every privileged change (proven in logs, incl. details view); argv-only execution (AST-tested, no `shell=True`); no `sudo pip`; no `git-all`; Runner secrets scrubber (tested); evidence contains no secrets; trust model unchanged (TLS + ref pin); retries bounded; destructive ops explicit (`--force` backup-first, PURGE typed). `sudo` password itself is never echoed/logged. Sound.

## 14. Exact Remaining Problems

**P0 (block product experience):**
1. **No E2E of the current tree.** Every Debian transcript predates: partial-health success variant (half-covered by v2), start/how/no menu, launcher shim/start, TN-default `resolve_lang`, `start_cmd_real`, doubled-mark fix. Symptom: can't claim any of it works. Evidence: log timestamps vs commit dates. Desired: one fresh Debian-container full run on HEAD.
2. **`genio start` never executed live.** Symptom: unknown whether first-run start succeeds/fails honestly (container lacks ollama → expect honest failure path, also unproven). Desired: live `start` → observe honest outcome; live `stop`.
3. **Permission-denied + daemon-repair never executed live.** Symptom: two central Docker branches are message-tested only. Desired: spare-user run or systemd host run.

**P1 (serious UX):**
4. apt stdout floods the TN conversation (evidence: every Debian log). Desired: apt output → log file, print one summary line.
5. `Installed <sha> commit=… frontend=…` raw line mid-TN-flow. Desired: key it or drop it in assistant mode.
6. `CANCELLED by user` in English. Desired: key it.
7. repair/update/rollback/status/uninstall operator lines in English. Desired: key them (keys pattern exists).
8. Uninstall `input()` without `/dev/tty` fallback. Desired: same NeedInput discipline as assistant.
9. Sudo-password hang (no TTY, passworded sudo): no timeout/guard. Desired: pre-check `sudo -n true`, explain non-interactive path.

**P2 (polish):** doc-corpus language; `åttention` casing mix (`À voir` vs `sain`); old `first_try_yes/no` dead keys; duplicate `✓` audit already fixed — verify in next E2E.
**P3 (optional):** Windows/macOS/Alpine/Fedora/Arch live runs; network-failure live run; sudo-rejection live run.

## 15. Recommended Next Mission

**`fix(installer): E2E-prove HEAD on fresh Debian (assistant, start, Docker branches)`** — and nothing else:
1. Fresh Debian 12 container, run HEAD's bootstrap → assistant → full install (proves partial-health success, start/how menu, shim, TN-default).
2. Live `genio start` (expect honest outcome), `genio stop`, shim via PATH.
3. Spare-user permission-denied run; daemon-down systemctl attempt where available.
4. Route apt output to log + key the 4 residual EN lines (Installed/CANCELLED/operator).
5. Re-capture evidence, then — and only then — declare the installer production-ready.
