# Genio — Recovery (repair / update / rollback / uninstall)

## States and responses

| Detected state | Installer behavior |
|---|---|
| HEALTHY | Refuses reinstall. Offers verify / update / repair. |
| DEGRADED/PARTIAL | Repairs only what is missing (venv, config), backup first. |
| BROKEN | Backup → diagnose → repair → verify. |
| UNKNOWN | Never overwrites automatically. Asks. |
| Multiple traces | Enumerates all, chooses nothing, requires explicit `--prefix`. |

## Backups

Every repair/update creates `.genio/backups/backup-<ts>-<commit>/`
containing: `.env`, `ports.json`, `manifest.json`, `repo_head.txt`
(code version pointer). `data/` is never copied nor deleted.

## Rollback

```bash
python3 installer/genio rollback --prefix <P>            # last backup
python3 installer/genio rollback --prefix <P> --backup <name>
```

Restores code checkout + config + manifest, marks health unknown
(re-verify with `doctor --deep`).

## Update

```bash
python3 installer/genio update --prefix <P> --to vX.Y.Z
```

Fetch → checkout → import-verify. ANY failure triggers automatic
restore of the backup. A half-upgraded installation is never left
behind by design (exception = finding, report it).

## Uninstall

```bash
python3 installer/genio uninstall --prefix <P>              # keeps data/
python3 installer/genio uninstall --prefix <P> --purge-data # deletes data/
```

Systemd units are listed, never removed silently (disable/remove
explicitly with systemctl when you installed `--with-services`).

## Clean-room reinstall procedure

1. `genio uninstall --prefix <P>` (data preserved).
2. Delete `<P>` only after verifying backups elsewhere (your decision).
3. Re-run the official bootstrap. 4. `genio doctor --deep`.
