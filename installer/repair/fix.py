"""Repair / update flows with backup-first + verify + rollback (§9-10)."""
from pathlib import Path

from installer.core.errors import InstallerError, EXIT_INSTALL_FAIL
from installer.core.manifest import read_manifest, record_event, write_manifest
from installer.core.paths import layout
from installer.core.state import create_backup, list_backups, restore_backup


def diagnose(prefix, runner):
    """Classify prefix health without changing anything."""
    from installer.discovery.find import inspect_prefix
    return inspect_prefix(prefix, runner)


def repair(runner, prefix):
    lay = layout(prefix)
    man = read_manifest(lay["manifest"])
    if man is None:
        raise InstallerError("no manifest at prefix — cannot repair, use install",
                             EXIT_INSTALL_FAIL)
    backup = create_backup(runner, prefix)
    fixed = []
    # venv missing -> recreate + reinstall deps
    if not (lay["venv"] / "bin" / "python").exists():
        from installer.installers.standalone import _make_venv, _install_deps
        _make_venv(runner, lay["venv"], runner.log_path)
        _install_deps(runner, lay["venv"], lay["repo"])
        fixed.append("venv recreated + deps reinstalled")
    # repo missing -> cannot repair code, report
    if not lay["repo"].is_dir():
        raise InstallerError("repo/ missing — repair needs install source; use install --source",
                             EXIT_INSTALL_FAIL)
    # config missing or corrupt -> regenerate defaults (never touch data/)
    corrupt = False
    if not lay["env_file"].is_file():
        corrupt = True
    else:
        try:
            for line in lay["env_file"].read_text().splitlines():
                s = line.strip()
                if s and not s.startswith("#") and "=" not in s:
                    corrupt = True
                    break
        except OSError:
            corrupt = True
    if corrupt:
        from installer.installers.standalone import _write_env
        _write_env(lay["env_file"], "", None)
        fixed.append("config/.env regenerated with safe defaults")
    for d in ("data", "cache", "logs", "tmp"):
        lay[d].mkdir(parents=True, exist_ok=True)
    man["health"] = "healthy" if fixed else man.get("health", "unknown")
    record_event(man, "repair", f"backup={backup.name} fixed={fixed or 'nothing-to-fix'}")
    write_manifest(lay["manifest"], man)
    return {"fixed": fixed, "backup": str(backup), "manifest": man}


def _version_key(v):
    import re
    parts = re.findall(r"\d+", str(v or ""))
    return tuple(int(x) for x in parts[:4])


def update(runner, prefix, ref="HEAD", archive=None, checksum=None,
           allow_downgrade=False):
    """git update (ref) or archive update (no-git path) with verify.

    Downgrades refused unless allow_downgrade. Rollback on any failure.
    """
    lay = layout(prefix)
    man = read_manifest(lay["manifest"])
    if man is None:
        raise InstallerError("no manifest — use install first", EXIT_INSTALL_FAIL)
    backup = create_backup(runner, prefix)
    old_head = (backup / "repo_head.txt").read_text().strip()
    try:
        if archive:
            from installer.dist.make_release import verify_archive
            try:
                verify_archive(archive, checksum_file=checksum)
            except SystemExit as e:
                raise InstallerError(str(e), EXIT_INSTALL_FAIL)
            import tarfile
            with tarfile.open(archive, "r:gz") as tar:
                members = tar.getmembers()
                top = (members[0].name.split("/")[0] + "/") if members else ""
                tmp = lay["prefix"] / "_update_tmp"
                if tmp.exists():
                    import shutil
                    shutil.rmtree(tmp)
                tar.extractall(tmp)
            inner = tmp / top.strip("/") if top else tmp
            _swap_tree(lay["repo"], inner)
            import shutil as _sh
            _sh.rmtree(tmp, ignore_errors=True)
            incoming = _archive_version(archive)
            _guard_downgrade(man.get("version"), incoming, allow_downgrade)
            man["commit"] = incoming.get("commit", man.get("commit"))
            man["version"] = incoming.get("version", man.get("version"))
        else:
            if not (lay["repo"] / ".git").is_dir():
                raise InstallerError("repo is not a git checkout — use update --archive",
                                     EXIT_INSTALL_FAIL)
            r = runner.run(["git", "-C", str(lay["repo"]), "fetch", "origin"], timeout=300)
            if not r["ok"]:
                raise InstallerError(f"fetch failed: {r['err'][-300:]}", EXIT_INSTALL_FAIL)
            r = runner.run(["git", "-C", str(lay["repo"]), "checkout", ref], timeout=120)
            if not r["ok"]:
                raise InstallerError(f"checkout {ref} failed: {r['err'][-300:]}", EXIT_INSTALL_FAIL)
            from installer.installers.standalone import _head_commit
            man["commit"] = _head_commit(lay["repo"])
        py = lay["venv"] / "bin" / "python"
        r = runner.run([str(py), "-c",
                        "import sys; sys.path.insert(0, '.');"
                        "import config; config.get_config(); print('ok')"],
                       cwd=lay["repo"], timeout=120)
        if not r["ok"]:
            raise InstallerError("post-update verify failed", EXIT_INSTALL_FAIL)
    except InstallerError:
        restore_backup(runner, prefix, backup)
        man = read_manifest(lay["manifest"])
        record_event(man, "update-failed-rollback", f"ref={ref} old={old_head}")
        write_manifest(lay["manifest"], man)
        raise
    man["health"] = "healthy"
    record_event(man, "update", f"{old_head} -> {man['commit']} (ref={ref})")
    write_manifest(lay["manifest"], man)
    return {"old": old_head, "new": man["commit"], "backup": str(backup)}


def _archive_version(archive):
    """Version/commit from sibling .release.json (shipped next to archive).

    The release manifest is NOT inside the tarball (git archive only packs
    tracked source); it travels alongside as genio-<v>.release.json.
    Absent manifest -> {} (version checks skipped honestly, verify stays).
    """
    from pathlib import Path as _P
    archive = _P(str(archive))
    sibling = archive.parent / (archive.name[:-7] + ".release.json" if archive.name.endswith(".tar.gz") else archive.name + ".release.json")
    if sibling.is_file():
        import json
        try:
            return json.loads(sibling.read_text())
        except (OSError, ValueError):
            pass
    import tarfile
    try:
        with tarfile.open(archive, "r:gz") as tar:
            for m in tar.getmembers():
                if m.name.endswith(".release.json"):
                    import json
                    f = tar.extractfile(m)
                    if f:
                        return json.loads(f.read().decode())
    except (OSError, ValueError):
        pass
    return {}


def _guard_downgrade(current, incoming, allow):
    if not incoming.get("version") or allow:
        return
    if _version_key(incoming["version"]) < _version_key(current):
        raise InstallerError(
            f"downgrade refused: {current} -> {incoming['version']} "
            "(use --allow-downgrade to override)", EXIT_INSTALL_FAIL)


def _swap_tree(repo, inner):
    """Replace repo content with extracted tree (keeps .git when present)."""
    import shutil
    gitdir = repo / ".git"
    kept = None
    if gitdir.is_dir():
        kept = repo.parent / ".git_kept"
        if kept.exists():
            shutil.rmtree(kept)
        shutil.move(str(gitdir), str(kept))
    for child in repo.iterdir():
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child, ignore_errors=True)
        else:
            child.unlink(missing_ok=True)
    for child in Path(inner).iterdir():
        shutil.move(str(child), str(repo / child.name))
    if kept is not None:
        if (repo / ".git").exists():
            shutil.rmtree(repo / ".git", ignore_errors=True)
        shutil.move(str(kept), str(gitdir))


def rollback(runner, prefix, which=None):
    backups = list_backups(prefix)
    if not backups:
        raise InstallerError("no backups available", EXIT_INSTALL_FAIL)
    target = None
    if which:
        for b in backups:
            if which in b.name:
                target = b
                break
        if target is None:
            raise InstallerError(f"backup not found: {which}", EXIT_INSTALL_FAIL)
    else:
        target = backups[-1]
    return restore_backup(runner, prefix, target)
