# Gemma 4 12B (Unified) — Local Multimodal Evaluation for Genio-VL

- **Evaluated**: `gemma4:12b` (Q4_K_M, 11.9B params, encoder-free Unified) vs `qwen2.5vl:7b` (Q4_K_M, 8.3B)
- **Host**: Pop!_OS/Linux — NVIDIA GeForce RTX 3060 12 GB, driver 580.173.02, CUDA 13.0 (torch 2.11.0+cu130)
- **Runtime**: Ollama 0.32.1 `/api/generate` (stream=false, num_ctx=4096, temp 0.3)
- **Date**: 2026-08-30
- **Artifact**: `reports/vision_benchmark/test_sample.png` (1280×720 synthetic DevOps terminal failure: nginx `502`, systemd `app-worker.service (code=exited, status=1/FAILURE)`, docker.sock `Permission denied`)
- **Raw data**: `reports/models/gemma4_vs_qwen_results.json`

## 1. Model Loading & VRAM Footprint

| Metric (Q4_K_M, RTX 3060) | Gemma 4 12B | Qwen2.5-VL 7B |
|---|---|---|
| Disk size (Ollama)                        | 7.6 GB      | 6.0 GB        |
| Resident VRAM after load                  | 8733 MiB    | 7205 MiB      |
| VRAM before inference                     | 556 MiB     | 556 MiB       |
| **Peak VRAM during image inference**      | **8765 MiB**| **7273 MiB**  |
| Peak VRAM during text-only inference     | 8817 MiB    | 7273 MiB      |
| Model load time (2nd request, warm)       | ~0.5 s      | ~0.2 s        |
| Headroom left (of 12288 MiB)              | ~3.4–3.5 GB | ~5.0 GB       |

Notes:
- Both run from a single 12 GB card with headroom; **Gemma 4 12B uses ~21% more VRAM than Qwen-VL 7B** but stays comfortably below OOM (peak 8817/12288 MiB = 72%).
- Text-only and image+text peaks are nearly identical (encoder-free architecture → no separate vision-encoder spike, confirming Google's design claim).
- Quantization ladder (4-bit / 8-bit / Q4_K_M): both models were benchmarked at **Q4_K_M** (Ollama default). 8-bit / Q8 variants would need ~15 GB for the 12B → out of budget on this card; 4-bit (NF4 via bitsandbytes) is the only HF/runtime path on 12 GB. See §5.

## 2. Inference Throughput (Tokens/sec)

| Scenario                    | Gemma 4 12B | Qwen2.5-VL 7B | Ratio |
|---|---|---|---|
| Vision (terminal screenshot) | 34.97 tok/s | 62.27 tok/s  | Gemma 1.0x / Qwen 1.78x |
| Text (docker report)         | 35.13 tok/s | 62.86 tok/s  | 1.79x |
| Bilingual darja/EN reasoning | 35.26 tok/s | 62.65 tok/s  | 1.78x |
| **Mean throughput**          | **35.1 tok/s** | **62.6 tok/s** | **Qwen ≈ 1.8x faster** |

Latency per single-shot answer: Gemma 4 12B ≈ **52–56 s**, Qwen-VL 7B ≈ **11.6–12.5 s**.

- Qwen2.5-VL is **~1.8× faster** (12.4B total vs 8.3B effective weights + 2× arithmetic/layer count).
- Gemma 4 12B is, however, far more verbose per answer (~1.8k–2.5k tok) and correspondingly denser in signal.

## 3. Vision / OCR Accuracy on Terminal Screenshot

Task: diagnose the screenshot in Tunisian Arabic (3 embedded signals). Keyword-hit scoring + manual review:

| Signal | Gemma 4 12B | Qwen2.5-VL 7B |
|---|---|---|
| nginx `502 Bad Gateway`                  | ✓ (explicit) | ✓ |
| upstream backend `127.0.0.1:8080` dead   | ✓ (root cause chain) | partial |
| `app-worker.service` failed (`exit-code=1`) | ✓ | ✓ |
| `Permission denied` (worker)             | ✓ (docker.sock context) | ✓ |
| Correct self-healing steps               | ✓ chmod/chown + systemctl restart | partial (generic) |
| Keyword score                           | **8/11** | 6/11 |
| Coherent "chain of failure" narrative   | ✓ (nginx → upstream → worker → perms) | partial |

Verdict: **Gemma 4 12B is the clear winner on visual diagnosis** — it reads the full failure chain (curl 502 → dead upstream :8080 → failed worker with `Permission denied`) and produces a structured remediation plan. Qwen-VL is correct but shallower and drifts to a generic explanation.

## 4. Bilingual Tunisian/Arabic + Technical English

| Scenario | Gemma 4 12B | Qwen2.5-VL 7B |
|---|---|---|
| docker permission text diagnosis | 6/11 kw — strong root cause (crash-loop + group membership) | 9/11 kw — thorough, but responded in French |
| nginx `413` → `client_max_body_size` | **10/10 kw** — exact root-cause & fix | 6/10 kw — correct but no journald step |
| Dialect fidelity                | Tunisian/Egyptian Arabic ✓ (Latin-script Tunisian on text task) | Egyptian dialect drift, French fallback |
| Bilingual code-switching | ✓ natural (`w-ach nahkiw fi journald?` → journalctl step) | partial |

Verdict: **Gemma 4 12B** answers in the requested Arabic/Tunisian persona more reliably and handles mixed darja/English prompts better; Qwen-VL occasionally slips to French/English despite Arabic instructions. Gemma is the better fit for the Genio-VL darja persona out-of-the-box.

## 5. Readiness for LoRA / QLoRA Fine-Tuning with Unsloth

**Favorable factors**
- Dense, single-pass "unified token loop" per Google — multimodal data is fed into the LLM backbone directly, so a single LoRA on the LLM weights tunes vision behavior too (no separate encoder to freeze/adapter).
- Apache 2.0 license → unrestricted fine-tuning. 11.9B dense, 48 layers, 262K vocab.
- Tight but actionable VRAM estimate for QLoRA on 12 GB:
  - Base 4-bit NF4 weights ≈ 6.2 GB
  - LoRA r=16/α32 adapters + optimizer (paged AdamW 8-bit) ≈ 1.5–2.0 GB
  - Gradient checkpointing on → activations ≈ 1.5–2.5 GB
  - **Estimated peak ≈ 10–11 GB → fits RTX 3060** with `expandable_segments` + fp16 autocast; batch_size=1, seq≤2048.
- LoRA/QLoRA ready: **8.5/10** (with 7B-class data set ≤ 4k steps/session, gradient checkpointing, and `use_8bit` off).

**Risks / faster-before-tuning caveats**
- gemma4 is a **young architecture** — must confirm `transformers` 5.5.0 registers `Gemma4Model` (this box) and that **Unsloth** has a Gemma4 checkpoint/rotary rewrite; if unsupported yet, fall back to QLoRA via HF Trainer (bitsandbytes 0.50.1 pinned OK).
- 256K-context sliding-window attention → ensure `sliding_window` handling in PEFT `target_modules` (q/k/v/proj naming check before launch).
- MTP drafter models exist; fine-tune the base 12B, not the drafter.

**Max LoRA score (QLoRA, RTX 3060)**: 9/10 — the exact size Unsloth targets, `8.5/10` conservatively until support is verified on this box.

## 6. Conclusion & Recommendation for Genio-VL

| Criterion                  | Winner           |
|----------------------------|------------------|
| Vision/OCR + root-cause    | **Gemma 4 12B** |
| Bilingual darja fidelity   | **Gemma 4 12B** |
| Throughput / latency       | Qwen2.5-VL 7B   |
| VRAM efficiency            | Qwen2.5-VL 7B   |
| Fine-tune shelf life       | **Gemma 4 12B** |

**Recommendation**: adopt **Gemma 4 12B Unified (Q4_K_M)** as the Genio-VL engine for diagnostic + darja-heavy workloads, accepting ~1.8× slower answers; keep `qwen2.5vl:7b` as the low-latency/first-response path where speed matters. Next step: verify Unsloth transformer support, then run a QLoRA pilot (r=16, darja DevOps dataset) at batch=1 on this RTX 3060.

**Adopted in Genio**: `config.py` → `OllamaConfig.primary_model = "gemma4:12b"` (env override `GENIO_OLLAMA_MODEL`), backups `("qwen2.5vl:7b", "qwen2.5:7b", "qwen2.5-coder:14b")`; `core/model_router.py` floors `num_predict` to 1024 for Gemma models and retries empty results once before failover.

## 7. Known Issue — Ollama 0.32.1 × Gemma 4 MTP (empty generation)

Empirically reproduced on this box via `/api/generate`:
- **num_predict ≤ 512 → whole response silently dropped** (`done_reason=length`, `eval_count=N`, visible `response=""`).
- **Some Arabic/token-leading prompts → empty output regardless of options** (e.g. `"قال: كلمة وحدة, لكن عرفني شنو مدير المهام نتاعك."` yields 1447 sampled tokens but `response=15` chars, while other prompts return 1000+ chars).
- Impacted paths and workarounds:
  - All Genio Ollama calls must floor `num_predict ≥ 1024` (router does this for `gemma*`).
  - Empty responses are retried once, then fail over to `qwen2.5vl:7b` — never surfaces to the user.
- Next action: watch for an Ollama update that fixes Gemma 4 MTP buffer flushing; retest with the two repro prompts (`num_predict=60`, `"قال: كلمة وحدة, ..."`).