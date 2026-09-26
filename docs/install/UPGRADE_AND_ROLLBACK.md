# Upgrade and rollback

Canonical flows: `RECOVERY.md` (update/rollback) + `RELEASE_PROCESS.md`
(version policy). Summary:

- `genio update --to <ref>` (git) or `--archive <tgz>` (releases).
- Every update takes a backup first; any failure restores it
  automatically (tested: killed update, corrupt config, broken venv).
- `genio rollback [--backup NAME]` restores code + config + manifest.
- Downgrades need `--allow-downgrade` (refused by default, tested).
- `data/` is never touched by update or rollback (tested).
