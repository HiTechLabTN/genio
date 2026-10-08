"""Local launcher: prefix/bin/genio shim + start/stop commands.

The shim dispatches to the installed CLI copy so the user never types
venv paths. `start` launches the backend daemonized (pidfile + log +
/health wait); `stop` terminates it. No systemd required; systemd units
remain the production path via --with-services.
"""
import json
import os
import signal
import subprocess
import sys
import time

SHIM_TEMPLATE = """#!/usr/bin/env sh
# Genio launcher — dispatches to this installation. Do not edit by hand.
exec "{python}" "{cli}" --prefix "{prefix}" "$@"
"""


def shim_path(prefix):
    from installer.core.paths import layout
    return layout(prefix)["prefix"] / "bin" / "genio"


def install_shim(prefix):
    """Write prefix/bin/genio. Best-effort: never fails an install."""
    from installer.core.paths import layout
    try:
        lay = layout(prefix)
        dest = lay["prefix"] / "bin" / "genio"
        dest.parent.mkdir(parents=True, exist_ok=True)
        cli = lay["repo"] / "installer" / "genio"
        py = lay["venv"] / "bin" / "python"
        interp = str(py) if py.exists() else sys.executable
        dest.write_text(SHIM_TEMPLATE.format(python=interp, cli=cli, prefix=lay["prefix"]))
        dest.chmod(0o755)
        return str(dest)
    except OSError:
        return ""


def pidfile(prefix):
    from installer.core.paths import layout
    return layout(prefix)["prefix"] / "genio-server.pid"


def _health(port, timeout=5):
    try:
        import urllib.request
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health",
                                    timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def _read_ports(prefix):
    from installer.core.paths import layout
    try:
        return json.loads((layout(prefix)["ports_file"]).read_text())
    except (OSError, ValueError):
        return {}


def start(prefix, timeout=60):
    """Launch backend daemonized. Returns (ok, detail). Idempotent."""
    from installer.core.paths import layout
    lay = layout(prefix)
    pf = pidfile(prefix)
    try:
        pid = int(pf.read_text().strip())
        os.kill(pid, 0)
        return True, f"already running (pid {pid})"
    except (OSError, ValueError):
        pass
    py = lay["venv"] / "bin" / "python"
    srv = lay["repo"] / "genio_server.py"
    if not py.exists():
        return False, "venv python missing — run genio repair"
    if not srv.is_file():
        return False, "genio_server.py missing — reinstall from source"
    ports = _read_ports(prefix)
    port = int(ports.get("api", 8000))
    log = lay["logs"] / "genio-server.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(log, "ab") as fh:
            p = subprocess.Popen(
                [str(py), str(srv)], cwd=str(lay["repo"]),
                stdin=subprocess.DEVNULL, stdout=fh, stderr=subprocess.STDOUT,
                start_new_session=True)
    except OSError as e:
        return False, f"cannot spawn backend: {e}"
    try:
        pf.write_text(str(p.pid))
    except OSError:
        pass
    deadline = time.time() + timeout
    while time.time() < deadline:
        if p.poll() is not None:
            return False, f"backend exited rc={p.returncode} (see {log})"
        if _health(port, timeout=3):
            return True, f"backend up on :{port} (pid {p.pid})"
        time.sleep(2)
    return False, f"backend did not answer /health in {timeout}s (see {log})"


def stop(prefix):
    """Stop a start()-launched backend. Returns (ok, detail)."""
    pf = pidfile(prefix)
    try:
        pid = int(pf.read_text().strip())
    except (OSError, ValueError):
        return True, "not running (no pidfile)"
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    except OSError as e:
        return False, f"cannot signal pid {pid}: {e}"
    for _ in range(25):
        try:
            os.kill(pid, 0)
        except OSError:
            break
        time.sleep(0.4)
    else:
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass
    try:
        pf.unlink()
    except OSError:
        pass
    return True, f"stopped pid {pid}"
