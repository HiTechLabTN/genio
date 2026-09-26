"""Hardware detection: CPU, RAM, disk, GPU (best-effort, never fatal)."""
import os
import shutil


def _mem_total_mb():
    try:
        with open("/proc/meminfo") as fh:
            for line in fh:
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) // 1024
    except (OSError, ValueError):
        pass
    return None


def _cpu():
    try:
        with open("/proc/cpuinfo") as fh:
            for line in fh:
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return None


def _disk(path="/"):
    try:
        st = os.statvfs(path)
        total = st.f_blocks * st.f_frsize // (1024 ** 3)
        free = st.f_bavail * st.f_frsize // (1024 ** 3)
        return {"total_gb": total, "free_gb": free}
    except OSError:
        return {"total_gb": None, "free_gb": None}


def _gpu(runner):
    info = {"present": False, "vendor": None, "memory_mb": None}
    if not shutil.which("nvidia-smi"):
        return info
    if runner is None:
        info["present"] = True
        return info
    r = runner.run(["nvidia-smi", "--query-gpu=name,memory.total",
                    "--format=csv,noheader"], timeout=30)
    if r["ok"] and r["out"].strip():
        name, mem = (r["out"].strip().splitlines()[0] + ",").split(",")[:2]
        info["present"] = True
        info["vendor"] = "nvidia"
        try:
            info["memory_mb"] = int("".join(c for c in mem if c.isdigit()))
        except ValueError:
            pass
    return info


def detect(runner=None, path="/"):
    return {
        "cpu": _cpu(),
        "ram_total_mb": _mem_total_mb(),
        "disk": _disk(path),
        "gpu": _gpu(runner),
    }
