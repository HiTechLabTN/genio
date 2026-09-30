# GENIO INTELLIGENT INSTALLER REPORT

# Executive Summary

The Genio installer now behaves like a first meeting with Genio instead of a
Linux-expert gate. Same deterministic engine and contracts, new
Tunisian-first assistant layer: full preflight, plain explanations, explicit
consent before privileged changes, minimal packages only, verify-after-repair,
bounded auto-retry, real smoke test, and a first useful interaction. Proven by
a real install (exit 0), a real interactive install (exit 0), a simulated
missing-git/docker recovery loop (honest exit 13), and 51 + 227 + 99 green tests.

# Previous Installation UX

- `curl … | bash` → `missing required tool: git` (exit 13), no explanation.
- `genio install` → `Missing required tools: ['pip', 'venv']` (exit 13).
- Any missing binary inside `Runner.run` → raw `FileNotFoundError` traceback.
- Docker: present/absent only (daemon stopped vs permission denied identical).
- Fix-one → retry → discover-next loop; no verify-after-repair; success ended
  with a flat `Installed …` line and no smoke test or first interaction.

# Root Causes

1. `Runner.run` caught only `TimeoutExpired`; `FileNotFoundError`/`OSError` escaped.
2. Bootstrap `need()` printed a bare English line and quit.
3. `cmd_install` aborted on the first missing list with zero diagnosis/repair.
4. No package-manager abstraction (apt assumed); no minimal-package maps.
5. No consent step, no verify step, no retry loop, no first-run.

# New Architecture

- `installer/i18n.py` — deterministic TN/FR/EN strings (TU default; GENIO_LANG/--lang/LANG). No LLM anywhere.
- `installer/preflight.py` — full machine report with states AVAILABLE/MISSING/BROKEN/DAEMON_DOWN/PERMISSION_DENIED/VERSION_TOO_OLD/UNKNOWN; never raises on missing binaries.
- `installer/packages.py` — pm families (apt/dnf/yum/pacman/zypper/apk), minimal maps (git NOT git-all, no sudo pip), argv-only commands, injectable Executor + dry-run, docker daemon enable/start.
- `installer/assistant.py` — TN conversation UI (yes/no/details, progress ✓/→/⚠/✗, tech-details gate); reads /dev/tty under curl|bash; `NeedInput` instead of prompts when non-interactive.
- `installer/flow.py` — welcome → preflight → report → explain → consent → repair → verify → bounded retry → install → smoke → first-run. Emits legacy event names.
- `installer/genio` — `--assistant`, `--lang`, `--dry-run`; TN port warnings; TN success/smoke/first-run; TN doctor rendering (`--json` unchanged); explicit-prefix existing install refused honestly (exit 11, health-aware message).
- `installer/bootstrap/install.sh` — TN missing-tool guidance + exact minimal fix command; `GENIO_ASSISTANT=1` selects assistant mode; trust model unchanged.

# Preflight System

OS/distro/arch/kernel/pm, python+version, pip, venv (real creation probe), git, docker CLI, network (DNS/HTTPS/offline), ports+owners, permissions, hardware (cpu/ram/disk/gpu), existing installs. All crash-safe.

# Dependency Detection

Per-tool states incl. docker CLI-vs-daemon-vs-permission split (info-format parsing, rc-127 aware). Version floors preserved from existing REQUIREMENTS.

# Package Manager Handling

Family detection by distro-id with binary fallback; honest unsupported-OS exit with manual commands. `yum` added to the family table.

# Interactive Tunisian UX

Full transcript captured in `e2e-assistant.log`: greeting → machine report → ready → install → smoke → celebration → start command → optional diagnostic → invitation. Non-technical wording throughout.

# Consent Model

`consent_sudo` + `consent_changes` + [yes / no / what-changes] (exact commands shown on request). Non-interactive never consents (reports + exits 13).

# Repair / Verify / Retry

Repair installs minimal sets, then RE-DETECTS (never trusts blindly); docker gets daemon-start + permission triage (`usermod -aG docker` guidance, re-login noted). One bounded retry round, then honest exit 13. Demonstrated in `e2e-missing-git.log` (simulated missing git+docker, dry-run).

# Resume / Idempotency

Discovery kept; explicit-prefix existing installs refuse with health-aware TN message (exit 11); `repair`/`update`/`rollback` untouched; reinstall requires `--force` (backup first).

# Doctor

TN/FR/EN rendering (`--lang`), same checks, same `--json` contract, same exit codes.

# First-Run Experience

Real smoke (manifest, venv python, doctor verdict) + celebration + start command + optional machine diagnostic + invitation. No faked AI: diagnostic is the deterministic preflight summary.

# Security

No new distribution mechanism; checksums/manifests path untouched; argv-only execution (AST-tested, no `shell=True`); no `sudo pip`; secrets scrubbed by existing Runner (tested); consent before every privileged change; non-interactive performs zero repairs.

# Tests

- New `installer/tests/test_assistant.py` (16): A–P matrix incl. git-all ban, daemon/permission states, pm maps, unsupported OS, resume/skip, network-mock shape, non-interactive silence, secrets, no-shell, TN-default, consent details, smoke structure.
- Full: installer 51 passed, backend 227 passed, frontend 99 passed.

# Clean-Machine E2E

No clean OS available (dev machine only) — marked UNVERIFIED where applicable:
1. ✅ Real install to isolated prefix (local source, --yes): exit 0, venv+pip+frontend PASS, smoke 3/3, doctor HEALTHY.
2. ✅ Real interactive install via pty: exit 0, full TN conversation + first-run.
3. ✅ Simulated missing git+docker (PATH isolation + dry-run): detect→explain→consent→repair→verify-FAIL→retry→exit 13, zero tracebacks, zero git-all, zero system changes.
4. ✅ Resume/refuse paths, repair-nothing-to-fix, doctor TN/FR/JSON.
5. ⏸ UNVERIFIED: real (non-dry) sudo package repair; truly clean OS; docker-daemon repair execution; network-fetched bootstrap.

# Evidence

`promt/qa-evidence/installer-intelligent/`: `e2e-install.log`, `e2e-assistant.log`, `e2e-missing-git.log`, `installer-e2e-results.json`. No secrets in evidence.

# Known Limitations

- Repair of truly missing system packages needs sudo + network and is dry-run-only in this environment (unit-covered, not live-executed).
- `docker.io` (Debian) vs Docker CE: distro package chosen deliberately for minimalism; documented in code.
- Venv probe costs up to ~60 s per full preflight on slow disks (honest check, not faked).
- Assistant reads /dev/tty when piped; without any TTY it aborts cleanly (exit 22) instead of hanging (EOF-hardened).

# Final Verdict

NOT VERIFIED (strict §28: clean-machine E2E with live privileged repair was impossible on the dev host). Everything verifiable was verified: detection without crashing, Tunisian communication, consent, minimal packages, no git-all, no FileNotFoundError, repair/verify/retry loop, real completion, real smoke, first-run, green tests, real evidence. Remaining item is exactly one environment-gated live repair run.
