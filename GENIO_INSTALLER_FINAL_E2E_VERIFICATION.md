# GENIO INSTALLER FINAL E2E VERIFICATION

## Executive Summary

A real isolated lab (Debian 12, real systemd, real GPU, real spare user,
real Ollama + real models) executed the remaining installer scenarios live.
No product code was changed in this mission (verification only).

## Tested HEAD

- commit: `6aee04165c1b13d134b8b93e21544b84350e1b04`
- branch: `main` (remote `main` identical — public bootstrap == tested code)
- working_tree: clean (only evidence added; unrelated `patterns.json` untouched)

## Test Environment

- Lab: `debian:12` image + systemd committed (`geniolab-systemd:12`),
  run `--privileged --gpus all --cgroupns=host`, `/lib/systemd/systemd` PID 1
- OS: Debian GNU/Linux 12 (bookworm), x86_64, kernel 7.1.1, 12 CPUs
- systemd: `running`; GPU: RTX 3060 12 GB visible in lab
- Users: root + real spare user `genioqa` (uid 1000, own group only + NOPASSWD sudo)
- Docker Engine 20.10+/29.x installed live via repair; daemon via real systemd unit
- Ollama 0.40.1 (installed live) + `qwen2.5:7b` (845dbda0ea48, 4.7 GB) +
  `gemma4:12b` (6114515d63c1, 8.0 GB, Q4_K_M, 11.9B — product default)

## Environment Provisioning

All provisioned inside the lab with recorded commands: systemd image
commit, spare user + sudoers.d, curl, bootstrap pipe, apt repairs by the
installer itself, `docker.io`, ollama install script (+`zstd` dependency
found live), model pulls. No host state used except the docker image cache
and GPU device. (`environment.txt`, `lab-provision.log`.)

## P0 Results

| Test | Result | Evidence |
|---|---|---|
| Fresh install (public bootstrap) | PASS | fresh-install-v2.log (clone→install→manifest healthy @ HEAD) |
| TN assistant | PASS | greeting→phases→consent→success all Tunisian |
| Prerequisite repair | PASS | git/python3 Stage-A, pip/venv/docker.io via apt, re-verify green |
| `genio start` | PASS | up in ~2 s, pidfile, /health ok |
| `genio status` | PASS | manifest JSON shown |
| `genio stop` | PASS | pidfile cleaned, health dead, no residual proc |
| First-run | PASS | TN menu; start-choice → real launcher path |
| First conversation (product model) | PASS | model-conversation-gemma*.log (thought+answer, exit 0) |
| Docker missing | PASS | detected MISSING → installed → re-detected |
| Docker permission denied | PASS | real genioqa + real socket EACCES → PERMISSION_DENIED |
| Docker daemon down | PASS | real stopped daemon → DAEMON_DOWN, distinct message |
| non-TTY sudo safety | PASS | clean abort, no hang (exit 13/22) |

## P1 Results

apt flood, `Installed <sha>`, CANCELLED, operator EN, prefix-suppress,
docker-only continue — all fixed in HEAD and observed live in transcripts.

## Real Spare User Results

`genioqa` (uid 1000, groups=1000 only): real `docker ps` → real
`permission denied ... connect: permission denied`; installer classifier →
`{"state": "PERMISSION_DENIED"}`; after `usermod -aG docker` + fresh login,
access works (recovery proven). No traceback, exit codes preserved.
(`spare-user/`.)

## Real systemd Results

`systemctl is-system-running` → `running`; docker + ollama units
`active`; stop → `inactive` + distinct daemon-down message; start →
`active` + access recovered; backend stop/start cycle via launcher with
health confirmation and no orphans. Boot auto-start is NOT default
(contract: only with explicit `--with-services` unit); not tested beyond
contract statement.

## Real Ollama/Model Results

- `qwen2.5:7b`: conversation OK in ~1 s (GPU), answer MSA-leaning mixed
  (MSA forms with شنوّة) → classified MIXED (model property, frozen scope).
- `gemma4:12b` (product default): conversation 1 in 65 s (cold),
  conversation 2 in 16 s (warm), full thought + answer events, exit 0.
- Language: pure Tunisian Derja (عسلامة، متاع، نجم، برشا، نلوج، شنوّ) →
  classified TUNISIAN.
- Ollama-down control: explicit `model unreachable` error event + TN
  fallback message, no fake success, immediate.

## Full E2E Journey

Fresh lab → public bootstrap → Stage-A repairs → clone HEAD → TN
preflight → consent → apt repair → Docker skip (no systemd-path issue:
real unit used) → install → manifest healthy → smoke → first-run menu →
`genio start` → health → real TN prompt → real generated TN answer →
`genio stop` → restart → healthy again.

## Failure Matrix

| Scenario | Expected | Actual | Exit | Evidence |
|---|---|---|---|---|
| Docker missing | honest detection | MISSING → installed | 0 | fresh-install-v2.log |
| Docker permission denied | PERMISSION_DENIED | exact state, real socket | — | spare-user/ |
| Docker daemon down | DAEMON_DOWN | distinct message | — | docker-daemon-down.log |
| Genio daemon down | deterministic failure | doctor --deep FAIL api, verdict ATTENTION | — | failure-genio-daemon-down.log |
| Socket permission (Genio) | N/A | backend uses TCP :8000, no socket file | — | noted |
| Ollama missing | explicit error | `model unreachable` + TN fallback, no fake | — | failure-ollama-down.log |
| Model missing | explicit model error | covered by same path (no model → same error) | — | same |
| Network unavailable | graceful error | degraded detect (dns ok/https dead → offline) | — | failure-network.log |
| Sudo password unavailable | no hang | clean abort 13/22 | 13/22 | non-tty*.log, sudo-no-tty.log |
| Installer cancelled | clean CANCELLED | TN message, exit 22 | 22 | observed |
| Service stopped | deterministic failure | health dead, doctor FAIL | — | restart-cycle.log |
| Restart | recovery | healthy, new pid | 0 | restart-cycle.log |
| Non-root user | real permission behavior | EACCES → PERMISSION_DENIED → group recovery | — | spare-user/ |

## Evidence Index

`promt/qa-evidence/installer-final-lab/`: baseline.json, head.txt,
environment.txt, lab-provision.log, fresh-install.log,
fresh-install-v2.log, model-conversation-{qwen,gemma,gemma2}.log,
model-run-meta.log, genio-start.log, restart-cycle.log,
independent-checks.log, spare-user/, spare-user-setup.log,
failure-matrix/ (docker-daemon-down, non-tty, start/stop/status),
failure-{genio-daemon-down,ollama-down,network}.log, sudo-no-tty.log.

## Screenshots / Video

Headless lab without display server: no screenshots/video possible.
User-visible evidence = complete terminal transcripts + machine-readable
matrix.json + independent cross-checks (pidfile↔process, socket mode,
systemctl states, model digests). Stated explicitly, not substituted.

## Blockers

None remaining for installer scope. Model-dialect variance across models
(qwen MSA/Chinese bleed vs gemma pure TN) is a model property, frozen
scope, recorded.

## Bugs Found

1. (Lab artifact, not product) `/tmp` with `noexec` (from my own
   `--tmpfs /tmp` flag) makes the bootstrap `-x` check fail-closed.
   Root-caused, lab fixed, no product change made. Proposal: fall back
   to `$HOME/.cache` when `/tmp` is noexec (not implemented per freeze).
2. No product-code defects found during this mission. No fix applied.

## Security Observations

- Consent before every privileged change (observed live, incl. details).
- `usermod`/group changes explicit; re-login required (observed).
- No secrets/tokens/passwords in any evidence file.
- PID-file lifecycle clean (no stale running state).
- Socket `root:docker 0600`-equivalent (`srw-rw---- root docker`) confirmed.

## Reproducibility

1. `docker run -d --privileged --gpus all --cgroupns=host ... /lib/systemd/systemd` (needs systemd-capable host + NVIDIA runtime for GPU; CPU-only also works, slower).
2. Provision per `lab-provision.log` commands.
3. Public bootstrap + pty answers as in `fresh-install-v2.log`.
4. Model: `ollama pull gemma4:12b` (~8 GB); conversation via `/ws/agent`
   `{"action":"prompt",...}`.

## Final Verdict

**VERIFIED** — all P0 scenarios executed live with evidence; P1 previously
fixed and re-observed; remaining limits are documented environment facts
(no display server for screenshots; spare-user permission via real EACCES;
no spare systemd host needed — lab had real systemd).
