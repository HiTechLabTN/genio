import os
os.environ["OMP_NUM_THREADS"] = "8"
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

BASE = "Qwen/Qwen2.5-Coder-7B-Instruct"
LORA = "/data/ai_tools/genio/training/genio_brain_lora"
OUT = "/data/ai_tools/genio/training/merged_model"

print("Loading base model on CPU (fp16)...")
model = AutoModelForCausalLM.from_pretrained(
    BASE,
    torch_dtype=torch.float16,
    device_map="cpu",
    low_cpu_mem_usage=True,
    trust_remote_code=True,
)

print("Loading LoRA adapter...")
model = PeftModel.from_pretrained(model, LORA)
model = model.merge_and_unload()
model.eval()

print("Saving merged fp16 model...")
model.save_pretrained(OUT)
tokenizer = AutoTokenizer.from_pretrained(LORA, trust_remote_code=True)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token
tokenizer.save_pretrained(OUT)
print("Done ->", OUT)