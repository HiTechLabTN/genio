# Genio — Installation (standalone product)

Supported: Linux x86_64/aarch64 (Debian/Ubuntu, Fedora, Arch, Pop!_OS…),
systemd optional. No HiTech-OS required. No sibling repository required.

## Quickstart (official bootstrap)

```bash
curl -fsSL https://raw.githubusercontent.com/HiTechLabTN/genio/main/installer/bootstrap/install.sh | bash
```

Pin a release explicitly (recommended):

```bash
GENIO_REF=v2.0.0-sovereign-rc1 GENIO_PREFIX=~/.local/share/genio bash install.sh
```

Trust basis: GitHub TLS + reported checkout SHA. No checksum/signature
stage is implemented — see `installer/bootstrap/install.sh`.

## Manual install

```bash
git clone https://github.com/HiTechLabTN/genio.git
python3 installer/genio install --prefix ~/.local/share/genio --source ./genio --yes
```

## CLI model

| Command | Behavior |
|---|---|
| `genio install [--prefix P] [--source S] [--yes] [--check]` | Preflight → duplicate check → install → verify. Refuses a 2nd install without `--prefix`. `--check` = dry discovery only. |
| `genio install --api-port N --web-port M` | Persisted port overrides (never silent: stored in `config/ports.json`). |
| `genio install --with-services` | Renders a hardened systemd unit (sudo, explicit paths). Enable/start stays manual via systemctl. |
| `genio doctor [--prefix P] [--deep]` | PASS/WARN/FAIL/NOT_APPLICABLE. Exit 17 on any FAIL. |
| `genio status [--prefix P]` | Manifest + detected traces. |
| `genio repair [--prefix P]` | Backup-first repair of venv/config. Never touches `data/`. |
| `genio update [--to REF]` | Backup → git update → verify → automatic rollback on failure. |
| `genio rollback [--backup NAME]` | Restore last (or named) backup. |
| `genio uninstall [--purge-data]` | Removes code+config. `data/` preserved unless `--purge-data`. |
| `genio version` | Installer version. |

## Prefix layout

```
<PREFIX>/.genio/manifest.json   identity + health + history
<PREFIX>/.genio/backups/        pre-repair/update snapshots
<PREFIX>/repo/                  git checkout (application code)
<PREFIX>/venv/                  runtime environment
<PREFIX>/config/.env            configuration (0600)
/PREFIX>/config/ports.json      chosen ports
<PREFIX>/data/                  USER DATA — never deleted by repair/update
<PREFIX>/{cache,logs,tmp}/
```

## Prerequisites

Required: python3 ≥3.10 (with venv+ensurepip), git, pip.
Recommended: docker (sandbox), curl. Optional: node ≥18 + npm (frontend
build; honestly skipped as NOT_APPLICABLE when absent), ffmpeg (voice).

System packages are NEVER installed silently: without `--yes` the
installer prints what is missing; with `--yes` + sudo it uses the host
package manager (apt/dnf/pacman…) and logs every change.

## Ports (defaults)

api 8000 · web 8098 · voder 5050 · gestures 8001 · ollama 11434.
Occupied ports are reported with PID/process/service — never killed.
Use `--api-port/--web-port` to relocate and persist.

## Security model of the installed product

Same guarantees as development: strict boot guard (prod/strict refuses
keyless start), cloud closed by default, sandbox fail-closed, Bearer TTL,
telemetry scrubbed. `config/.env` is 0600. See `docs/SECURITY.md`.
