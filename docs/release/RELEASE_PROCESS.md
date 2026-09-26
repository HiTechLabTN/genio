# Release process — Genio standalone distribution

## Versioning

`installer/__init__.py: INSTALLER_VERSION` (installer) + git tags
`vX.Y.Z[-suffix]` (product). IPC contract versions independently
(`PROTOCOL_VERSION`, v1.x negotiation).

## Support policy

- SUPPORTED: latest tag + previous minor (security fixes).
- DEPRECATED: announced one release ahead, still installable.
- UNSUPPORTED: refuses `update --to` without `--allow-downgrade`
  (downgrade guard, tested); installer warns.

## Building a release

```bash
python3 installer/dist/make_release.py /path/to/genio 2.1.0 /tmp/rel/
# → genio-2.1.0.tar.gz + .sha256 + .release.json
```

Artifacts: versioned archive (tracked files only via `git archive`),
SHA-256 checksum, release manifest (version/commit/date/size/min-IPC).
No signatures implemented (stated; TLS + checksum is the trust basis).

## Installing from a release (no git required)

```bash
python3 installer/genio install --prefix /opt/genio \
  --source genio-2.1.0.tar.gz --checksum genio-2.1.0.tar.gz.sha256 --yes
```

Checksum mismatch → `INTEGRITY FAIL`, nothing installed (fail closed).

## Update / rollback compatibility

- git checkouts: `update --to <ref>` (fetch/checkout/verify/rollback).
- archive installs: `update --archive <tgz> [--checksum]` (file-level
  backup + swap + verify + restore).
- Rollback restores code + config + manifest; `data/` untouched.
- Downgrades refused unless `--allow-downgrade`.

## Gates before tag

Full backend + frontend + lint + installer + IPC + chaos suites green,
Docker build green, clean-room install green, docs match reality.
