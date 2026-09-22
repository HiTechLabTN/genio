"""
Genio Autonomous Runner with Self-Healing & Reflection
Executes tasks under Power Guard, routes models dynamically, and repairs errors autonomously.
"""

from __future__ import annotations
import logging
import traceback
from pathlib import Path
from core.skills.power_guard import keep_awake
from core.evolution.model_router import ModelRouter
from core.evolution.skill_engine import DynamicSkillRegistry
from core.evolution.self_healing import SelfHealingEngine

logger = logging.getLogger("genio.runner")


class AutonomousRunner:
    def __init__(self):
        self.registry = DynamicSkillRegistry()
        self.registry.load_all()
        self.router = ModelRouter(self.registry)
        self.healer = SelfHealingEngine()

    def execute_with_self_healing(self, target_file: Path, run_func, *args, **kwargs):
        """Runs a function; if it fails, attempts autonomous diagnosis, repair, and retry."""
        attempts = 0
        max_attempts = 2

        while attempts < max_attempts:
            try:
                return run_func(*args, **kwargs)
            except Exception as e:
                attempts += 1
                error_trace = traceback.format_exc()
                logger.warning(f"⚠️ Task failed (Attempt {attempts}/{max_attempts}): {e}")

                if attempts < max_attempts:
                    repaired = self.healer.diagnose_and_fix(
                        failed_file=target_file,
                        error_trace=error_trace,
                        context_notes=f"Failed while executing {run_func.__name__}"
                    )
                    if repaired:
                        logger.info("🔁 Re-executing task after successful autonomous repair...")
                        continue
                logger.error(f"❌ Execution permanently failed after {attempts} attempts.")
                raise e

    def run_pipeline(self, prompt: str, auto_publish: bool = True):
        with keep_awake(f"Running Genio Lab: {prompt[:30]}..."):
            logger.info("🚀 Starting Autonomous Pipeline Execution...")
            
            # Model Selection
            draft_model = self.router.select_best_model("fast_draft")
            reasoning_model = self.router.select_best_model("deep_reasoning")
            
            logger.info(f"🧠 Assigned Models -> Reasoning: {reasoning_model['model']} | Drafting: {draft_model['model']}")
            
            # Telemetry snapshot
            metrics = self.router.get_gpu_telemetry()
            logger.info(f"📊 Running on GPU Temp: {metrics.get('gpu_temp_c', 'N/A')}°C | Free VRAM: {metrics.get('vram_free_mb', 0)}MB")
            
            print(f"\n[GENIO READY] Active Stack: {draft_model['model']} on {draft_model['provider'].upper()}")
