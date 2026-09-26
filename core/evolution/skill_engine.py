"""
Genio Autonomous Skill Engine
Allows Genio to dynamically load, test, and register new operational skills.
"""

from __future__ import annotations
import importlib.util
import logging
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict

logger = logging.getLogger("genio.evolution.skills")
SKILLS_DIR = Path("/data/ai_tools/genio/core/skills")

@dataclass
class SkillMeta:
    name: str
    version: str
    description: str
    author: str = "Genio-Autonomous-Agent"

class DynamicSkillRegistry:
    def __init__(self, skills_dir: Path = SKILLS_DIR):
        self.skills_dir = skills_dir
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self.active_skills: Dict[str, Callable] = {}

    def test_and_register(self, skill_file: Path) -> bool:
        """Loads a Python skill dynamically, tests its contract, and registers it safely."""
        try:
            module_name = f"genio_skill_{skill_file.stem}"
            spec = importlib.util.spec_from_file_location(module_name, skill_file)
            if not spec or not spec.loader:
                logger.error(f"Cannot load spec for {skill_file}")
                return False
            
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module  # Required for dataclasses / reflection in Python 3.10+
            spec.loader.exec_module(module)

            # Contract check: Each skill must define 'execute' and 'meta'
            if not hasattr(module, "execute") or not hasattr(module, "meta"):
                logger.warning(f"Skill {skill_file.name} missing 'execute' or 'meta'. Skipped.")
                return False

            if hasattr(module, "self_test"):
                if not module.self_test():
                    logger.warning(f"Skill {skill_file.name} failed self-test verification.")
                    return False

            self.active_skills[module.meta.name] = module.execute
            logger.info(f"✅ Skill successfully registered: {module.meta.name} v{module.meta.version}")
            return True

        except Exception as e:
            logger.error(f"❌ Error loading skill {skill_file.name}: {e}\n{traceback.format_exc()}")
            return False

    def load_all(self):
        """Scans the skills directory and loads all valid modules."""
        for file in self.skills_dir.glob("*.py"):
            if file.name.startswith("_"):
                continue
            self.test_and_register(file)
