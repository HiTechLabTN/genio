"""Backup / restore — config + metadata + code version record (§10).

Never touches data/ (user data preserved by design). Rollback restores the
previous code checkout (git) + config files + manifest.
"""
import json
import os
import shutil
from pathlib import Path

from installer.core.errors import InstallerError, EXIT_BACKUP_FAIL, EXIT_ROLLBACK_FAIL
from installer.core.manifest import now_iso, read_manifest, write_manifest


def _stamp():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def create_backup(runner, prefix):
    from installer.core.paths import layout
    lay = layout(prefix)
    man = read_manifest(lay["manifest"])
    if man is None:
        raise InstallerError("no manifest — nothing to back up", EXIT_BACKUP_FAIL)
    lay["backups"].mkdir(parents=True, exist_ok=True)
    name = f"backup-{_stamp()}-{man.get('commit', 'unknown')}"
    dest = lay["backups"] / name
    try:
        dest.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        dest = lay["backups"] / f"{name}-{os.getpid()}"
        dest.mkdir(parents=True, exist_ok=False)
    # Config + manifest + code version pointer (NOT the whole repo, NOT data).
    if lay["env_file"].is_file():
        shutil.copy2(lay["env_file"], dest / ".env")
    if lay["ports_file"].is_file():
        shutil.copy2(lay["ports_file"], dest / "ports.json")
    if lay["manifest"].is_file():
        shutil.copy2(lay["manifest"], dest / "manifest.json")
    repo = lay["repo"]
    head = None
    if (repo / ".git").is_dir():
        r = runner.run(["git", "-C", str(repo), "rev-parse", "HEAD"], timeout=30)
        head = r["out"].strip() if r["ok"] else None
    (dest / "repo_head.txt").write_text((head or "nongit") + "\n")
    # Non-git repos: file-level code backup (excludes heavy/generated dirs)
    # so update-from-archive can roll back without git.
    if not head or head == "nongit":
        _backup_tree(repo, dest / "repo_files.tar.gz")
    meta = {"created": now_iso(), "commit": man.get("commit"),
            "version": man.get("version"), "repo_head": head}
    (dest / "backup.json").write_text(json.dumps(meta, indent=2))
    return dest


def _backup_tree(repo, dest_tar):
    """Tar repo excluding heavy/generated dirs (venv, node_modules, caches)."""
    import tarfile
    skip = {".git", "__pycache__", "node_modules", ".venv", "venv",
            "dist", ".pytest_cache", ".genio", "*.db", "*.db-journal"}
    with tarfile.open(dest_tar, "w:gz") as tar:
        for root, dirs, files in os.walk(repo):
            dirs[:] = [d for d in dirs if d not in skip and not d.endswith(".egg-info")]
            for f in files:
                if f.endswith((".db", ".db-journal", ".pyc")):
                    continue
                full = os.path.join(root, f)
                tar.add(full, arcname=os.path.relpath(full, repo))


def list_backups(prefix):
    from installer.core.paths import layout
    lay = layout(prefix)
    if not lay["backups"].is_dir():
        return []
    return sorted([p for p in lay["backups"].iterdir() if p.is_dir()])


def restore_backup(runner, prefix, backup_dir):
    """Restore config + manifest + code checkout. Returns manifest."""
    from installer.core.paths import layout
    lay = layout(prefix)
    man = read_manifest(lay["manifest"])
    backup_dir = Path(backup_dir)
    if not (backup_dir / "backup.json").is_file():
        raise InstallerError(f"not a backup: {backup_dir}", EXIT_ROLLBACK_FAIL)
    meta = json.loads((backup_dir / "backup.json").read_text())
    # 1. code checkout (git) or file restore (archive installs)
    if meta.get("repo_head") and meta["repo_head"] != "nongit" and (lay["repo"] / ".git").is_dir():
        r = runner.run(["git", "-C", str(lay["repo"]), "checkout", meta["repo_head"]], timeout=120)
        if not r["ok"]:
            raise InstallerError(f"code rollback failed: {r['err'][-300:]}", EXIT_ROLLBACK_FAIL)
    elif (backup_dir / "repo_files.tar.gz").is_file():
        import tarfile
        with tarfile.open(backup_dir / "repo_files.tar.gz", "r:gz") as tar:
            tar.extractall(lay["repo"])
    # 2. config files
    for name, dest in ((".env", lay["env_file"]), ("ports.json", lay["ports_file"])):
        src = backup_dir / name
        if src.is_file():
            shutil.copy2(src, dest)
    man = read_manifest(backup_dir / "manifest.json") or man or {}
    man["health"] = "unknown"
    from installer.core.manifest import record_event
    record_event(man, "rollback", f"restored {backup_dir.name}")
    write_manifest(lay["manifest"], man)
    return man
