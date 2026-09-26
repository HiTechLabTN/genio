"""Repair / update flows with backup-first + verify + rollback (§9-10)."""
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
    # config missing -> regenerate defaults (never touch data/)
    if not lay["env_file"].is_file():
        from installer.installers.standalone import _write_env
        _write_env(lay["env_file"], "", None)
        fixed.append("config/.env regenerated with safe defaults")
    for d in ("data", "cache", "logs", "tmp"):
        lay[d].mkdir(parents=True, exist_ok=True)
    man["health"] = "healthy" if fixed else man.get("health", "unknown")
    record_event(man, "repair", f"backup={backup.name} fixed={fixed or 'nothing-to-fix'}")
    write_manifest(lay["manifest"], man)
    return {"fixed": fixed, "backup": str(backup), "manifest": man}


def update(runner, prefix, ref="HEAD"):
    """git update with verify; rollback on any failure (§10)."""
    lay = layout(prefix)
    man = read_manifest(lay["manifest"])
    if man is None:
        raise InstallerError("no manifest — use install first", EXIT_INSTALL_FAIL)
    if not (lay["repo"] / ".git").is_dir():
        raise InstallerError("repo is not a git checkout — cannot update safely",
                             EXIT_INSTALL_FAIL,
                             hint="reinstall from a git source to enable updates")
    backup = create_backup(runner, prefix)
    old_head = (backup / "repo_head.txt").read_text().strip()
    try:
        r = runner.run(["git", "-C", str(lay["repo"]), "fetch", "origin"], timeout=300)
        if not r["ok"]:
            raise InstallerError(f"fetch failed: {r['err'][-300:]}", EXIT_INSTALL_FAIL)
        r = runner.run(["git", "-C", str(lay["repo"]), "checkout", ref], timeout=120)
        if not r["ok"]:
            raise InstallerError(f"checkout {ref} failed: {r['err'][-300:]}", EXIT_INSTALL_FAIL)
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
    from installer.installers.standalone import _head_commit
    man["commit"] = _head_commit(lay["repo"])
    man["health"] = "healthy"
    record_event(man, "update", f"{old_head} -> {man['commit']} (ref={ref})")
    write_manifest(lay["manifest"], man)
    return {"old": old_head, "new": man["commit"], "backup": str(backup)}


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
