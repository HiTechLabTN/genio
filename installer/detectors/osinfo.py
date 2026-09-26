"""Platform detection: distro, kernel, arch, package manager, init."""
import os
import platform
import shutil


def _os_release():
    info = {}
    try:
        with open("/etc/os-release") as fh:
            for line in fh:
                if "=" in line:
                    k, v = line.strip().split("=", 1)
                    info[k] = v.strip('"')
    except OSError:
        pass
    return info


def _pkg_manager():
    for name in ("apt-get", "dnf", "pacman", "zypper", "apk"):
        if shutil.which(name):
            return name
    return None


def _init_system(runner):
    if os.path.isdir("/run/systemd/system"):
        return "systemd"
    if shutil.which("systemctl"):
        return "systemctl-no-daemon"
    if shutil.which("service"):
        return "sysv"
    return "none"


def detect(runner=None):
    rel = _os_release()
    return {
        "system": platform.system(),
        "distribution": rel.get("PRETTY_NAME") or rel.get("NAME") or platform.system(),
        "distro_id": rel.get("ID", "unknown"),
        "distro_version": rel.get("VERSION_ID", "unknown"),
        "kernel": platform.release(),
        "architecture": platform.machine(),
        "package_manager": _pkg_manager(),
        "init": _init_system(runner),
        "supported": platform.system() == "Linux" and platform.machine() in ("x86_64", "aarch64"),
    }
