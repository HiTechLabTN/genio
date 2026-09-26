# Genio — Troubleshooting

## `install` refuses: "Already installed" / "Multiple traces"

Expected: the no-duplicate rule. Run `genio status --prefix <P>` to see
what exists, then `repair`, `update`, or install isolated with an
explicit `--prefix`.

## DWARN ports held by genio.service / uvicorn / node`

Another Genio (dev checkout or service) owns the ports. Either stop it
explicitly yourself, or install with `--api-port/--web-port` overrides.

## `venv creation failed` (ensurepip absent)

Some distros strip ensurepip (`python3-venv` missing on Debian/Ubuntu).
Install it with the host package manager (`apt install python3-venv`),
then retry. The doctor reports this honestly instead of guessing.

## `pip install failed`

See `.genio/install.log` (scrubbed of secrets). Usual cause: missing
system library (e.g. `libsndfile1` for audio). Install via package
manager, then `genio repair --prefix <P>`.

## Frontend NOT_APPLICABLE

npm/node absent → static UI skipped, API unaffected. Install node ≥18
and re-run install, or accept API-only mode.

## `doctor` FAIL on manifest/config/venv

Prefix incomplete → `genio repair --prefix <P>` (backup-first).

## Diagnostic bundle

Share `.genio/install.log` (secret-scrubbed by construction) +
`genio doctor --json` output. Never paste your real `.env`.
