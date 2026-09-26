"""Subprocess runner with logging + secret-safe output."""

import re
import subprocess
from datetime import datetime, timezone

SECRET_PATTERNS = (
    re.compile(r"(?i)(api[_-]?key\s*[:=]\s*)([^\s'\"]{6,})"),
    re.compile(r"(?i)(token\s*[:=]\s*)([^\s'\"]{6,})"),
    re.compile(r"(?i)(password\s*[:=]\s*)([^\s'\"]{6,})"),
    re.compile(r"(?i)(secret\s*[:=]\s*)([^\s'\"]{6,})"),
    re.compile(r"(sk-[A-Za-z0-9]{10,})"),
    re.compile(r"(ghp_[A-Za-z0-9]{10,})"),
)


def scrub(text):
    if not text:
        return text
    out = str(text)
    for pat in SECRET_PATTERNS:
        out = pat.sub(lambda m: (m.group(1) if m.lastindex and m.lastindex > 1 else "") + "***REDACTED***", out)
    return out


class Runner:
    """Runs commands, appends timestamped scrubbed lines to the install log."""

    def __init__(self, log_path=None):
        self.log_path = log_path

    def _log(self, line):
        if not self.log_path:
            return
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.log_path, "a") as fh:
                ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                fh.write(f"{ts} {scrub(line)}\n")
        except OSError:
            pass

    def run(self, argv, cwd=None, env=None, timeout=600, check_text=""):
        self._log(f"$ {' '.join(str(a) for a in argv)} (cwd={cwd})")
        try:
            p = subprocess.run(
                [str(a) for a in argv], cwd=str(cwd) if cwd else None,
                env=env, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            self._log(f"TIMEOUT after {timeout}s: {check_text}")
            return {"ok": False, "rc": 124, "out": "", "err": "timeout"}
        self._log(f"rc={p.returncode} out={p.stdout[-800:]} err={p.stderr[-800:]}")
        return {"ok": p.returncode == 0, "rc": p.returncode,
                "out": p.stdout, "err": p.stderr}
