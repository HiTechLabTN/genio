"""Package-manager abstraction + MINIMAL package maps.

Never installs bundles (git, NOT git-all). No `sudo pip`. All commands
are built as argv lists (no shell=True anywhere) and previewable before
any consent. The executor is injectable so tests never need root.
"""
import os

# distro-id (or family) -> manager + per-need minimal package lists.
FAMILIES = {
    "apt": {
        "manager": "apt-get",
        "ids": {"debian", "ubuntu", "pop", "linuxmint", "raspbian"},
        "update": ["apt-get", "update"],
        "git": ["git"],
        "python": ["python3", "python3-venv", "python3-pip"],
        "docker": ["docker.io"],
    },
    "dnf": {
        "manager": "dnf",
        "ids": {"fedora", "rhel", "centos", "rocky", "almalinux"},
        "update": [],
        "git": ["git"],
        "python": ["python3", "python3-pip"],
        "docker": ["docker"],
    },
    "yum": {
        "manager": "yum",
        "ids": set(),
        "update": [],
        "git": ["git"],
        "python": ["python3", "python3-pip"],
        "docker": ["docker"],
    },
    "pacman": {
        "manager": "pacman",
        "ids": {"arch", "manjaro", "endeavouros"},
        "update": ["pacman", "-Sy"],
        "git": ["git"],
        "python": ["python", "python-pip"],
        "docker": ["docker"],
    },
    "zypper": {
        "manager": "zypper",
        "ids": {"opensuse-leap", "opensuse-tumbleweed", "sles"},
        "update": ["zypper", "refresh"],
        "git": ["git"],
        "python": ["python3", "python3-pip", "python3-venv"],
        "docker": ["docker"],
    },
    "apk": {
        "manager": "apk",
        "ids": {"alpine"},
        "update": ["apk", "update"],
        "git": ["git"],
        "python": ["python3", "py3-pip"],
        "docker": ["docker"],
    },
    "brew": {
        "manager": "brew",
        "ids": set(),
        "update": ["brew", "update"],
        "git": ["git"],
        "python": ["python3"],
        "docker": ["docker"],
        "docker_cask": True,
    },
}

INSTALL_FLAGS = {
    "apt-get": ["apt-get", "install", "-y"],
    "dnf": ["dnf", "install", "-y"],
    "yum": ["yum", "install", "-y"],
    "pacman": ["pacman", "-S", "--noconfirm"],
    "zypper": ["zypper", "--non-interactive", "install", "-y"],
    "apk": ["apk", "add"],
    "brew": ["brew", "install"],
}


def family_for(distro_id, manager_bin=None):
    did = (distro_id or "").lower()
    # NixOS is declarative: never auto-install, guide instead.
    if did in ("nixos",):
        return "nix-manual"
    for fam, spec in FAMILIES.items():
        if did in spec["ids"]:
            return fam
    # Fallback: match the detected manager binary itself.
    for fam, spec in FAMILIES.items():
        if manager_bin == spec["manager"]:
            return fam
    # Homebrew on macOS (no /etc/os-release id to match on).
    import shutil as _sh
    if manager_bin is None and _sh.which("brew"):
        return "brew"
    return None


class Executor:
    """Runs argv lists. Wrap Runner or a test double with the same shape."""

    def __init__(self, runner=None, dry_run=False):
        self.runner = runner
        self.dry_run = dry_run
        self.commands = []

    def run(self, argv, **kw):
        self.commands.append([str(a) for a in argv])
        if self.dry_run:
            return {"ok": True, "rc": 0, "out": "dry-run", "err": ""}
        if self.runner is not None:
            return self.runner.run(argv, **kw)
        import subprocess
        try:
            p = subprocess.run([str(a) for a in argv], capture_output=True,
                               text=True, timeout=kw.get("timeout", 600),
                               stdin=subprocess.DEVNULL)
            return {"ok": p.returncode == 0, "rc": p.returncode,
                    "out": p.stdout, "err": p.stderr}
        except FileNotFoundError:
            return {"ok": False, "rc": 127, "out": "", "err": "not found"}
        except Exception as e:
            return {"ok": False, "rc": 126, "out": "", "err": str(e)[:200]}


def sudo_prefix():
    if os.geteuid() == 0:
        return []
    import shutil
    if shutil.which("sudo"):
        return ["sudo"]
    return None  # no privilege path at all


def plan_install(family, need):
    """Return the exact argv command lists (previewable, no execution)."""
    spec = FAMILIES.get(family)
    if not spec:
        return []
    # Homebrew Docker ships as a cask, not a formula.
    cmds = []
    if spec.get("update"):
        cmds.append(spec["update"])
    pkgs = []
    for n in need:
        pkgs.extend(spec.get(n, []))
    # Deduplicate, preserve order. Minimal by construction: maps above
    # contain only the small packages (git, never git-all).
    seen, minimal = set(), []
    for p in pkgs:
        if p not in seen:
            seen.add(p)
            minimal.append(p)
    if spec.get("docker_cask") and "docker" in need:
        minimal = [p for p in minimal if p != "docker"]
        cmds.append(["brew", "install", "--cask", "docker"])
    if minimal:
        cmds.append(INSTALL_FLAGS[spec["manager"]] + minimal)
    return cmds


def install_needs(executor, family, need, sudo=True, timeout=900):
    """Execute a planned install. Returns (ok, log_lines)."""
    import os as _os
    pre = sudo_prefix() if sudo else []
    if sudo and pre is None:
        return False, ["no privilege escalation path (not root, no sudo)"]
    log = []
    # Debian-family installers must never interrogate the terminal
    # (debconf reads /dev/tty and would swallow the user's next answer).
    env = None
    if family in ("apt",):
        env = dict(_os.environ)
        env["DEBIAN_FRONTEND"] = "noninteractive"
    for cmd in plan_install(family, need):
        full = pre + cmd
        log.append("$ " + " ".join(full))
        r = executor.run(full, timeout=timeout, env=env) if env else executor.run(full, timeout=timeout)
        log.append(f"rc={r['rc']}")
        if not r["ok"]:
            return False, log
    return True, log


def ensure_docker_daemon(executor, family):
    """Start/enable the daemon where the platform supports it. Read-only
    probe first; returns (state, log) with state in AVAILABLE/DAEMON_DOWN."""
    import shutil
    log = []
    if shutil.which("systemctl") and __import__("os").path.isdir("/run/systemd/system"):
        pre = sudo_prefix() or []
        for cmd in (["systemctl", "enable", "--now", "docker"],):
            full = pre + cmd
            log.append("$ " + " ".join(full))
            r = executor.run(full, timeout=120)
            log.append(f"rc={r['rc']}")
            if not r["ok"]:
                return "DAEMON_DOWN", log
        return "AVAILABLE", log
    if shutil.which("service"):
        pre = sudo_prefix() or []
        full = pre + ["service", "docker", "start"]
        log.append("$ " + " ".join(full))
        r = executor.run(full, timeout=120)
        log.append(f"rc={r['rc']}")
        return ("AVAILABLE" if r["ok"] else "DAEMON_DOWN"), log
    return "DAEMON_DOWN", log + ["no service manager found (manual start needed)"]
