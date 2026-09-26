"""Network / permissions / port detectors."""
import os
import shutil
import socket


def detect_network(runner, timeout=10):
    out = {"dns": False, "https": False, "offline": False}
    try:
        socket.gethostbyname("github.com")
        out["dns"] = True
    except OSError:
        out["offline"] = True
        return out
    if shutil.which("curl"):
        r = runner.run(["curl", "-fsSL", "--max-time", str(timeout),
                        "-o", os.devnull, "https://github.com"], timeout=timeout + 5)
        out["https"] = r["ok"]
    else:
        try:
            import ssl
            import urllib.request
            ctx = ssl.create_default_context()
            urllib.request.urlopen("https://github.com", timeout=timeout, context=ctx).close()
            out["https"] = True
        except Exception:
            pass
    out["offline"] = not (out["dns"] and out["https"])
    return out


def detect_permissions(prefix):
    prefix = str(prefix)
    return {
        "user": os.environ.get("USER") or os.environ.get("LOGNAME") or str(os.geteuid()),
        "euid": os.geteuid(),
        "is_root": os.geteuid() == 0,
        "sudo": shutil.which("sudo") is not None,
        "prefix_writable": os.access(os.path.dirname(os.path.abspath(prefix)) or "/", os.W_OK),
    }


def _port_owner(port, runner):
    """Identify PID/process/service holding a TCP port (never kills)."""
    info = {"pid": None, "process": None, "service": None}
    if shutil.which("ss"):
        r = runner.run(["ss", "-tlnp"], timeout=15)
        for line in r["out"].splitlines():
            if f":{port} " in line or f":{port}\t" in line:
                import re
                m = re.search(r"pid=(\d+)", line)
                if m:
                    info["pid"] = int(m.group(1))
                break
    if info["pid"]:
        try:
            with open(f"/proc/{info['pid']}/comm") as fh:
                info["process"] = fh.read().strip()
        except OSError:
            pass
        if shutil.which("systemctl"):
            r = runner.run(["systemctl", "status", str(info["pid"])], timeout=15)
            import re
            m = re.search(r"Loaded:.*?/([^/;]+\.service)", r["out"])
            if m:
                info["service"] = m.group(1)
    return info


def detect_ports(runner, ports):
    """ports: {name: port}. Returns per-port {free, owner} (read-only)."""
    result = {}
    for name, port in ports.items():
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind(("127.0.0.1", int(port)))
            result[name] = {"port": int(port), "free": True, "owner": {}}
        except OSError:
            result[name] = {"port": int(port), "free": False,
                            "owner": _port_owner(int(port), runner)}
        finally:
            s.close()
    return result
