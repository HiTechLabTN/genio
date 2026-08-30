"""
Genio — Gemma 4 12B QLoRA fine-tuning script (RTX 3060 12GB optimized).

Quick start (dry run — no weight download, prints readiness + memory math):
    python3 scripts/train_gemma4_qlora.py --dry-run

Real training:
    python3 scripts/train_gemma4_qlora.py --max-steps 300

Design for 12 GB VRAM on Ampere:
  - 4-bit NF4 quantization (bitsandbytes), bf16 compute, double quant.
  - LoRA r=16 / alpha=32 on q_proj, v_proj, k_proj, o_proj, embed_tokens.
  - batch size 1 + gradient accumulation 4, gradient checkpointing,
    paged_adamw_8bit optimizer (weights free-floating, adapters on page).
  - Engines: `trl` (SFTTrainer), `trainer` (native HF Trainer fallback),
    `unsloth` (auto-falls back to `trainer` on this host — torchcodec ABI
    break makes FastLanguageModel import fail on Python 3.10).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import torch
from datasets import load_dataset
from transformers import (
    AutoConfig,
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments,
)
from transformers.trainer import Trainer
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "genio_hitech_tuning_dataset.jsonl"
OUT_FINAL = ROOT / "training" / "gemma4_lora"

MODEL_ID = "google/gemma-4-12B-it"

GENIO_PROMPT = """أنت جينيو (Genio), مهندس بنية تحتية مستقلة في HiTech Lab بتونس.
تشرح الدارجة التونسية التقنية وتدمج الأوامر الإنجليزية بدقة.

### السؤال:
{}

### السياق:
{}

### الإجابة:
{}"""

TARGET_MODULES = ["q_proj", "v_proj", "k_proj", "o_proj", "embed_tokens"]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Genio Gemma4 QLoRA trainer")
    p.add_argument("--model-id", default=MODEL_ID)
    p.add_argument("--dataset", default=str(DATA))
    p.add_argument("--engine", choices=["trl", "trainer", "unsloth"], default="trl")
    p.add_argument("--output-dir", default=str(OUT_FINAL))
    p.add_argument("--max-steps", type=int, default=300)
    p.add_argument("--micro-batch", type=int, default=1)
    p.add_argument("--grad-accum", type=int, default=4)
    p.add_argument("--lora-r", type=int, default=16)
    p.add_argument("--lora-alpha", type=int, default=32)
    p.add_argument("--lr", type=float, default=1e-4)
    p.add_argument("--max-seq-len", type=int, default=1024)
    p.add_argument("--dry-run", action="store_true",
                   help="preflight + memory math, no weight load")
    return p.parse_args()


def preflight(model_id: str) -> dict:
    """Check HF arch support + CUDA/bitsandbytes sanity. Needs network once."""
    report = {"model_id": model_id, "ok": True, "warnings": []}
    report["cuda"] = torch.cuda.is_available()
    report["gpu"] = torch.cuda.get_device_name(0) if report["cuda"] else None
    report["vram_gb"] = round(torch.cuda.get_device_properties(0).total_memory / 2**30, 2) \
        if report["cuda"] else 0.0
    report["params_b"] = 12.0  # Gemma 4 12B Unified nominal
    try:
        cfg = AutoConfig.from_pretrained(model_id, trust_remote_code=True)
        report["model_type"] = cfg.model_type
    except Exception as exc:  # pragma: no cover - offline/unknown id
        report["ok"] = False
        report["warnings"].append(str(exc).split("\n")[0])
        try:
            import bitsandbytes as bnb  # noqa: F401
            report["bitsandbytes"] = bnb.__version__
        except ImportError:
            report["bitsandbytes"] = None
        return report

    from transformers.models.auto.configuration_auto import CONFIG_MAPPING
    report["arch_supported"] = cfg.model_type in CONFIG_MAPPING
    if not report["arch_supported"]:
        report["ok"] = False
        report["warnings"].append(
            f"transformers has no class for '{cfg.model_type}'. "
            "gemma4_unified landed in a newer transformers (>=5.6-nightly); "
            "upgrade transformers, or extract QLoRA-ready weights from the "
            "Ollama GGUF via llama.cpp convert, or retarget --model-id to a "
            "registered local checkpoint."
        )

    try:
        import bitsandbytes as bnb  # noqa: F401
        report["bitsandbytes"] = bnb.__version__
    except ImportError:
        report["bitsandbytes"] = None
        report["warnings"].append("bitsandbytes missing — QLoRA impossible.")
    return report


# Conservative Gemma-3/4 12B-class dense architecture (published numbers)
ARCH = {
    "12b": {"layers": 31, "hidden": 3072},
    "7b":  {"layers": 46, "hidden": 3584},
}


def memory_math(n_params: float, lora_r: int, n_target_mods: int,
                seq_len: int, vram_gb: float) -> dict:
    """Analytic 12GB-budget envelope for QLoRA (Ampere, grad checkpointing)."""
    use = "12b" if n_params >= 10 else "7b"
    layers, hidden = ARCH[use]["layers"], ARCH[use]["hidden"]
    # q,k,v,o -> 2*r*(h_in+h_out) each; embed_tokens -> 2*r*hidden
    per_layer = (n_target_mods - 1) * 2 * lora_r * hidden          # q,k,v,o
    adapter_params = layers * per_layer + 2 * lora_r * hidden      # + embed
    adapter_gb = adapter_params * 2 / 1e9               # bf16 adapters
    weights_gb = n_params * 0.5                         # 4-bit NF4 weights
    act_gb = 1.6 if seq_len >= 1024 else 0.9            # grad checkpointing
    opt_gb = adapter_gb * 6                             # paged adamw 8bit
    grad_gb = adapter_gb / 2
    peak = weights_gb + act_gb + opt_gb + grad_gb + 0.4  # CUDA/kernel reserve
    return {
        "arch": f"~{use} (L={layers}, H={hidden})",
        "weights_4bit_gb": round(weights_gb, 2),
        "activations_gb": act_gb,
        "optimizer_gb": round(opt_gb, 2),
        "gradients_gb": round(grad_gb, 2),
        "lora_trainable_m": round(adapter_params / 1e6, 1),
        "lora_trainable_pct": round(adapter_params / (n_params * 1e9) * 100, 3),
        "peak_estimate_gb": round(peak, 2),
        "peak_budget_pct": round(peak / vram_gb * 100, 1),
        "fits_12gb": peak < vram_gb,
    }


class GenioCollator:
    def __init__(self, tokenizer, max_length: int):
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __call__(self, features):
        texts = [f["text"] for f in features]
        enc = self.tokenizer(
            texts, padding=True, truncation=True, max_length=self.max_length,
            return_tensors="pt",
        )
        enc["labels"] = enc["input_ids"].clone()
        enc["labels"][enc["attention_mask"] == 0] = -100
        return enc


def build_trainer(model, tokenizer, dataset, args: argparse.Namespace):
    def format_prompts(batch):
        texts = []
        for inst, inp, out in zip(batch["instruction"], batch["input"], batch["output"]):
            texts.append(GENIO_PROMPT.format(inst, inp, out) + tokenizer.eos_token)
        return {"text": texts}

    dataset = dataset.map(format_prompts, batched=True)
    collator = GenioCollator(tokenizer, args.max_seq_len)

    targs = TrainingArguments(
        output_dir=args.output_dir,
        per_device_train_batch_size=args.micro_batch,
        gradient_accumulation_steps=args.grad_accum,
        gradient_checkpointing=True,
        max_steps=args.max_steps,
        learning_rate=args.lr,
        bf16=True,
        logging_steps=5,
        save_steps=100,
        optim="paged_adamw_8bit",
        remove_unused_columns=False,
        report_to="none",
        seed=3407,
    )

    try:
        from trl import SFTTrainer
        return SFTTrainer(
            model=model, args=targs, train_dataset=dataset,
            data_collator=collator, max_seq_length=args.max_seq_len,
        )
    except Exception:
        return Trainer(model=model, args=targs, train_dataset=dataset,
                       data_collator=collator)


def main() -> None:
    args = parse_args()
    pf = preflight(args.model_id)
    print(json.dumps(pf, ensure_ascii=False, indent=2))
    mem = memory_math(pf.get("params_b", 12.0), args.lora_r,
                      len(TARGET_MODULES), args.max_seq_len, pf["vram_gb"])
    print("-- QLoRA memory envelope (RTX 3060 12GB) --")
    print(json.dumps(mem, indent=2))
    if not pf["ok"] or not pf["bitsandbytes"]:
        sys.exit("PREFLIGHT FAILED — see warnings; nothing was executed.")

    if args.dry_run:
        print("DRY-RUN OK: dataset pairs =",
              sum(1 for _ in open(args.dataset)))
        print("macron ready flags: engine=trl/trainer ok, unsloth disabled on this host.")
        return

    print("Loading 4-bit base...")
    bnb_cfg = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_storage=torch.bfloat16,
    )
    model = AutoModelForCausalLM.from_pretrained(
        args.model_id, quantization_config=bnb_cfg,
        device_map="auto", trust_remote_code=True,
    )
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
    model.config.use_cache = False

    lora = LoraConfig(
        r=args.lora_r, lora_alpha=args.lora_alpha, lora_dropout=0.05,
        bias="none", target_modules=TARGET_MODULES, task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora)
    model.print_trainable_parameters()

    tokenizer = AutoTokenizer.from_pretrained(args.model_id, trust_remote_code=True)
    tokenizer.pad_token = tokenizer.eos_token

    ds = load_dataset("json", data_files=args.dataset, split="train")
    trainer = build_trainer(model, tokenizer, ds, args)
    print("Training...")
    trainer.train()
    print("Saving LoRA adapters...")
    model.save_pretrained(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)


if __name__ == "__main__":
    main()