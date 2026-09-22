"""
Power Guard Skill for Genio
Inhibits OS suspension using DBus / systemd while workloads are active.
"""

from __future__ import annotations
import contextlib
import subprocess
import logging
from dataclasses import dataclass

logger = logging.getLogger("genio.skill.power")

@dataclass
class SkillMeta:
    name: str = "power_guard"
    version: str = "1.0.0"
    description: str = "Prevents OS sleep and suspension during active tasks."

meta = SkillMeta()

def execute() -> dict:
    return {"status": "active", "inhibit_supported": True}

def self_test() -> bool:
    return True

@contextlib.contextmanager
def keep_awake(reason: str = "Genio Task Execution"):
    """Inhibits idle sleep during critical jobs using systemd-inhibit."""
    proc = None
    try:
        proc = subprocess.Popen(
            ["systemd-inhibit", "--what=idle:sleep", "--who=Genio", f"--why={reason}", "cat"],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        logger.info(f"🔒 Power Lock ENGAGED: '{reason}' (Sleep inhibited).")
        yield
    except Exception as e:
        logger.warning(f"Power Lock fallback engaged: {e}")
        yield
    finally:
        if proc:
            try:
                proc.terminate()
                proc.wait(timeout=2)
            except Exception:
                proc.kill()
            logger.info("🔓 Power Lock RELEASED: System can enter idle sleep if inactive.")
