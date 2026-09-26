"""systemd unit rendering + installation (explicit, least-privilege, §14)."""
import getpass
import shutil
from pathlib import Path

from installer.core.errors import InstallerError, EXIT_PERMISSION


def render(template_path, mapping):
    text = Path(template_path).read_text()
    for key, value in mapping.items():
        text = text.replace(key, str(value))
    if "%" in text and any(tok in text for tok in ("%USER%", "%REPO%", "%ENV_FILE%", "%VENV%", "%PORT%", "%PREFIX%")):
        raise InstallerError("unit template has unreplaced tokens")
    return text


def unit_text(prefix, repo, venv, env_file, port, user=None):
    from installer.core.paths import INSTALLER_DIR
    return render(INSTALLER_DIR / "manifests" / "genio.service.tmpl", {
        "%USER%": user or getpass.getuser(),
        "%REPO%": repo,
        "%ENV_FILE%": env_file,
        "%VENV%": venv,
        "%PORT%": port,
        "%PREFIX%": prefix,
    })


def install_unit(runner, name, text, use_sudo=True):
    """Write unit + daemon-reload. Requires sudo unless root. Explicit only."""
    import os
    dest = Path("/etc/systemd/system") / name
    if os.geteuid() != 0 and not (use_sudo and shutil.which("sudo")):
        raise InstallerError("systemd install needs root or sudo", EXIT_PERMISSION,
                             hint="run with sudo or use --no-services")
    argv = ["tee", str(dest)]
    if os.geteuid() != 0:
        argv = ["sudo", "tee", str(dest)]
    import subprocess
    try:
        p = subprocess.run(argv, input=text, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise InstallerError(f"unit write failed: {e}", EXIT_PERMISSION)
    if p.returncode != 0:
        raise InstallerError(f"unit write failed: {p.stderr[-200:]}", EXIT_PERMISSION)
    pre = [] if os.geteuid() == 0 else ["sudo"]
    r = runner.run(pre + ["systemctl", "daemon-reload"], timeout=60)
    if not r["ok"]:
        raise InstallerError("daemon-reload failed", EXIT_PERMISSION)
    return str(dest)
