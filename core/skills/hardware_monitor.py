"""
Hardware Telemetry Skill for Genio
Monitors GPU temperature, VRAM allocation, and thermal safety limits.
"""

from dataclasses import dataclass
import subprocess
import shutil
import logging

logger = logging.getLogger("genio.skill.hardware")

@dataclass
class SkillMeta:
    name: str = "hardware_monitor"
    version: str = "1.0.0"
    description: str = "Monitors NVIDIA GPU thermals, VRAM, and system load."

meta = SkillMeta()

def execute() -> dict:
    status = {"gpu_available": False, "gpu_temp": 0, "vram_free_mb": 0, "status": "safe"}
    
    if shutil.which("nvidia-smi"):
        try:
            res = subprocess.run(
                ["nvidia-smi", "--query-gpu=temperature.gpu,memory.used,memory.free,memory.total", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, check=True
            )
            line = res.stdout.strip().split("\n")[0]
            temp, used, free, total = [int(v.strip()) for v in line.split(",")]
            
            status = {
                "gpu_available": True,
                "gpu_temp_c": temp,
                "vram_used_mb": used,
                "vram_free_mb": free,
                "vram_total_mb": total,
                "status": "warning_hot" if temp > 82 else "safe"
            }
        except Exception as e:
            logger.error(f"nvidia-smi query failed: {e}")
    return status

def self_test() -> bool:
    data = execute()
    return isinstance(data, dict) and "status" in data
