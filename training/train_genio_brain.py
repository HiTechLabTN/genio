"""Genio — Standalone QLoRA fine-tuning script for the `genio-brain` model.

Fine-tunes ``Qwen/Qwen2.5-Coder-7B-Instruct`` on the Tunisian Darija technical
dataset (``training/genio_dataset.jsonl``, Alpaca format) using 4-bit NF4
quantization so it fits on a single NVIDIA RTX 3060 (12 GB VRAM).

Stack: ``transformers`` + ``peft`` (LoraConfig) + ``trl`` (SFTTrainer) +
``bitsandbytes`` (BitsAndBytesConfig). No unsloth / torchcodec.

Usage:
    python3 training/train_genio_brain.py \\
        --dataset training/genio_dataset.jsonl \\
        --max_steps 100 \\
        --output training/genio_brain_lora

The script is resilient across trl versions: it prefers the classic
``trl.SFTTrainer`` API and transparently falls back to the newer
``trl.Trainer`` + ``SFTConfig`` API when SFTTrainer was removed.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import torch
import transformers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("genio.train")

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATASET = ROOT / "training" / "genio_dataset.jsonl"
DEFAULT_OUTPUT = ROOT / "training" / "genio_brain_lora"

BASE_MODEL = "Qwen/Qwen2.5-Coder-7B-Instruct"

# Qwen2.5-7B attention + MLP projectors (standard PEFT target set for Qwen).
TARGET_MODULES = [
    "q_proj", "k_proj", "v_proj", "o_proj",
    "gate_proj", "up_proj", "down_proj",
]

ALPACA_TEMPLATE_WITH_INPUT = (
    "### Instruction:\n{instruction}\n\n### Input:\n{input}\n\n"
    "### Response:\n{output}"
)
ALPACA_TEMPLATE = (
    "### Instruction:\n{instruction}\n\n### Response:\n{output}"
)
RESPONSE_TEMPLATE = "\n### Response:\n"


# --------------------------------------------------------------------------- #
# Argument parsing                                                              #
# --------------------------------------------------------------------------- #

def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="train_genio_brain",
        description="QLoRA fine-tune of Qwen2.5-Coder-7B on the Genio Darija dataset.",
    )
    parser.add_argument("--base_model", type=str, default=BASE_MODEL,
                        help="Base model id (default: %(default)s)")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET,
                        help="Path to Alpaca-format JSONL dataset")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT,
                        help="Directory to save LoRA adapters")
    parser.add_argument("--resume_from_checkpoint", type=str, default=None,
                        help="Optional checkpoint (dir path) to resume training")

    # Required hyperparameters (Session defaults)
    parser.add_argument("--max_seq_length", type=int, default=1536)
    parser.add_argument("--per_device_train_batch_size", type=int, default=2)
    parser.add_argument("--gradient_accumulation_steps", type=int, default=4)
    parser.add_argument("--optim", type=str, default="paged_adamw_8bit")
    parser.add_argument("--fp16", action="store_true", default=True)
    parser.add_argument("--bf16", action="store_true", default=False)
    parser.add_argument("--max_steps", type=int, default=100)

    # LoRA hyperparameters
    parser.add_argument("--lora_r", type=int, default=16)
    parser.add_argument("--lora_alpha", type=int, default=32)
    parser.add_argument("--lora_dropout", type=float, default=0.05)

    # Training behaviour
    parser.add_argument("--learning_rate", type=float, default=2e-4)
    parser.add_argument("--warmup_ratio", type=float, default=0.05)
    parser.add_argument("--lr_scheduler_type", type=str, default="cosine")
    parser.add_argument("--weight_decay", type=float, default=0.01)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--save_steps", type=int, default=25)
    parser.add_argument("--save_total_limit", type=int, default=2)
    parser.add_argument("--gradient_checkpointing", action="store_true",
                        default=True,
                        help="Trade compute for VRAM (recommended on 12 GB)")
    parser.add_argument("--single_gpu", action="store_true", default=True,
                        help="Simplify device mapping for a single GPU")
    parser.add_argument("--overwrite_output_dir", action="store_true",
                        default=True)
    parser.add_argument("--mask_instructions", action="store_true",
                        default=True,
                        help="Only compute loss over the assistant response")
    return parser.parse_args(argv)


# --------------------------------------------------------------------------- #
# Dataset loading                                                               #
# --------------------------------------------------------------------------- #

def load_alpaca_dataset(path: Path):
    """Load ``{instruction, input, output}`` records from a JSONL file."""
    from datasets import load_dataset

    if not Path(path).exists():
        raise FileNotFoundError(f"dataset not found: {path}")
    ds = load_dataset("json", data_files=str(path), split="train")
    # Drop any extra fields so the Alpaca mapper never trips over schema drift.
    ds = ds.select_columns(["instruction", "input", "output"])
    return ds


def make_alpaca_formatter(tokenizer) -> Any:
    """Return a formatting function that renders Alpaca text for the model."""

    def _format(example: Dict[str, Any]) -> Dict[str, str]:
        instruction = str(example["instruction"]).strip()
        inp = str(example.get("input") or "").strip()
        output = str(example["output"]).strip()
        text = (ALPACA_TEMPLATE_WITH_INPUT if inp else ALPACA_TEMPLATE).format(
            instruction=instruction, input=inp, output=output)
        return {"text": text + tokenizer.eos_token}

    return _format


def _get_completion_collator(tokenizer):
    """Best-effort instruction-masking collator (trl's canonical sentinel)."""
    try:
        from trl import DataCollatorForCompletionOnlyLM
        return DataCollatorForCompletionOnlyLM(
            RESPONSE_TEMPLATE, tokenizer=tokenizer)
    except Exception:  # noqa: BLE001 — trl version drift
        logger.warning("DataCollatorForCompletionOnlyLM unavailable; "
                       "training over the full sequence instead.")
        return None


# --------------------------------------------------------------------------- #
# Trainer construction (robust across trl 0.1x / >=0.19 / 1.x)                 #
# --------------------------------------------------------------------------- #

def _training_args_dict(args: argparse.Namespace, output_dir: str) -> Dict[str, Any]:
    return {
        "output_dir": output_dir,
        "per_device_train_batch_size": args.per_device_train_batch_size,
        "gradient_accumulation_steps": args.gradient_accumulation_steps,
        "optim": args.optim,
        "fp16": args.fp16 and not args.bf16,
        "bf16": args.bf16,
        "max_steps": args.max_steps,
        "learning_rate": args.learning_rate,
        "warmup_ratio": args.warmup_ratio,
        "lr_scheduler_type": args.lr_scheduler_type,
        "weight_decay": args.weight_decay,
        "logging_steps": 1,
        "log_level": "info",
        "report_to": "none",
        "save_strategy": "steps",
        "save_steps": max(1, args.save_steps),
        "save_total_limit": args.save_total_limit,
        "save_only_model": True,
        "gradient_checkpointing": args.gradient_checkpointing,
        "remove_unused_columns": False,
        "seed": args.seed,
        "overwrite_output_dir": args.overwrite_output_dir,
        "dataloader_num_workers": 0,
    }


def build_trainer(model, tokenizer, ds, args) -> Any:
    """Construct and (resume if requested) train, returning the trainer.

    Works with both the classic ``trl.SFTTrainer`` API (trl < 1.0) and the
    newer ``trl.Trainer`` + ``SFTConfig`` API (trl >= 1.0).
    """
    try:
        from trl import SFTTrainer  # classic API (trl < 1.0)
        trainer_kwargs = dict(
            model=model,
            tokenizer=tokenizer,
            args=transformers.TrainingArguments(
                **_training_args_dict(args, str(args.output))),
            train_dataset=ds,
            dataset_text_field="text",
            formatting_func=make_alpaca_formatter(tokenizer),
            max_seq_length=args.max_seq_length,
            packing=False,
        )
        if args.mask_instructions:
            collator = _get_completion_collator(tokenizer)
            if collator is not None:
                trainer_kwargs["data_collator"] = collator
        trainer = SFTTrainer(**trainer_kwargs)
    except ImportError:
        try:
            from trl import SFTConfig, Trainer as TRLTrainer  # trl >= 1.0
        except ImportError:
            raise SystemExit(
                "trl is not installed. Install it with: "
                "pip install 'transformers>=4.44' 'peft>=0.12' 'trl>=0.11' "
                "'bitsandbytes>=0.43' 'datasets>=2.20' 'accelerate>=0.34'")
        cfg = SFTConfig(
            dataset_text_field="text",
            max_seq_length=args.max_seq_length,
            packing=False,
            **_training_args_dict(args, str(args.output)),
        )
        trainer = TRLTrainer(
            model=model,
            args=cfg,
            tokenizer=tokenizer,
            train_dataset=ds,
            data_collator=(_get_completion_collator(tokenizer)
                           if args.mask_instructions else None),
        )
    except Exception as exc:  # noqa: BLE001 — other trl surprises
        logger.exception("Failed to build trainer")
        raise SystemExit(f"trainer construction failed: {exc}")

    trainer.train(resume_from_checkpoint=args.resume_from_checkpoint or None)
    return trainer


# --------------------------------------------------------------------------- #
# Main entry point                                                              #
# --------------------------------------------------------------------------- #

def main(argv: Optional[List[str]] = None) -> Path:
    args = parse_args(argv)

    if not torch.cuda.is_available():
        logger.error("CUDA is not available — QLoRA training requires an "
                     "NVIDIA GPU (RTX 3060 class).")
        raise SystemExit(1)
    props = torch.cuda.get_device_properties(0)
    logger.info("GPU: %s · %.1f GB VRAM · PyTorch %s",
                props.name, props.total_memory / 1024**3, torch.__version__)

    transformers.set_seed(args.seed)
    ds = load_alpaca_dataset(args.dataset)
    logger.info("Dataset: %s examples from %s", len(ds), args.dataset)

    from peft import LoraConfig, get_peft_model
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(args.base_model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    from transformers import BitsAndBytesConfig
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.float16 if not args.bf16 else torch.bfloat16,
    )

    logger.info("Loading %s in 4-bit NF4 …", args.base_model)
    model = AutoModelForCausalLM.from_pretrained(
        args.base_model,
        quantization_config=bnb_config,
        device_map="auto" if not args.single_gpu else {"": 0},
        use_cache=False,          # incompatible with gradient checkpointing
        attn_implementation="sdpa",  # no flash-attn/unsloth dependency
    )
    model.config.use_cache = False

    peft_config = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=TARGET_MODULES,
    )
    model = get_peft_model(model, peft_config)
    model.enable_input_require_grads()
    model.print_trainable_parameters()

    trainer = build_trainer(model, tokenizer, ds, args)

    out_dir = Path(args.output)
    trainer.save_model(str(out_dir))
    tokenizer.save_pretrained(str(out_dir))
    logger.info("Training complete. LoRA adapters saved to %s", out_dir)
    return out_dir


if __name__ == "__main__":
    main()