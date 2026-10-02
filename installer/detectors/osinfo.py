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
    if platform.system() == "Darwin":
        return "launchd"
    return "none"


def _wsl_info():
    """Detect WSL1/WSL2 via kernel release string. Returns '' when native."""
    try:
        rel = platform.release().lower()
        if "wsl2" in rel:
            return "wsl2"
        if "microsoft" in rel or "wsl" in rel:
            return "wsl1"
    except Exception:
        pass
    return ""


def _support_level(system, distro_id, machine):
    """(level, reason): SUPPORTED | PARTIAL | UNSUPPORTED."""
    if system == "Linux":
        if distro_id in ("nixos",):
            return ("PARTIAL", "declarative package management (see NixOS guidance)")
        if machine not in ("x86_64", "aarch64"):
            return ("PARTIAL", f"untested CPU architecture {machine}")
        return ("SUPPORTED", "")
    if system == "Darwin":
        return ("PARTIAL", "Homebrew + Docker Desktop path (no systemd)")
    if system == "Windows":
        return ("UNSUPPORTED", "native Windows unsupported — use WSL2")
    return ("UNSUPPORTED", f"unknown system {system}")


def detect(runner=None):
    rel = _os_release()
    system = platform.system()
    machine = platform.machine()
    distro_id = rel.get("ID", "unknown")
    wsl = _wsl_info() if system == "Linux" else ""
    level, reason = _support_level(system, distro_id, machine)
    if wsl:
        # WSL runs the Linux userland: supported as Linux, flagged honestly.
        level, reason = "PARTIAL", f"running inside {wsl} (Windows host)"
    return {
        "system": system,
        "distribution": rel.get("PRETTY_NAME") or rel.get("NAME") or system,
        "distro_id": distro_id,
        "distro_version": rel.get("VERSION_ID", "unknown"),
        "kernel": platform.release(),
        "architecture": machine,
        "package_manager": _pkg_manager(),
        "init": _init_system(runner),
        "wsl": wsl,
        "support": level,
        "support_reason": reason,
        "supported": level == "SUPPORTED" and machine in ("x86_64", "aarch64"),
    }
