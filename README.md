# 🧠 Genio — Autonomous Multimodal AI Executive Director

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
[![Platform](https://img.shields.io/badge/platform-linux-lightgrey.svg)]()

> **Genio** is a fully autonomous, multimodal AI Executive Director and Infrastructure Engineer that transcends standard LLM limitations through dynamic multi-model routing, self-evolving vector memory, live multi-node sandbox validation, and automated content production.

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    GENIO AUTONOMOUS PIPELINE                 │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────┐   ┌──────────────┐   ┌───────────────────────┐ │
│  │  PLANNER │──▶│ CONTENT ARCH │──▶│   MULTI-NODE SANDBOX  │ │
│  │  (DAG)   │   │ (8 passes)   │   │  (WireGuard + NAT)    │ │
│  └─────────┘   └──────────────┘   └───────────────────────┘ │
│       │              │                       │                │
│       ▼              ▼                       ▼                │
│  ┌─────────┐   ┌──────────────┐   ┌───────────────────────┐ │
│  │ MEMORY  │   │   AUDITOR    │   │   VIDEO + TTS + COVER │ │
│  │ ENGINE  │   │ (self-heal)  │   │   (1080p Darija)      │ │
│  └─────────┘   └──────────────┘   └───────────────────────┘ │
│       │              │                       │                │
│       ▼              ▼                       ▼                │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │              PUBLISHERS (Ghost + YouTube)                │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

## ⚡ Quick Start

```bash
# One-command setup (installs dependencies, probes hardware)
./bootstrap.sh

# Full autonomous lab generation
python3 core/executive_director.py --auto "WireGuard VPN Multi-Node Lab"

# Dry-run (plan only)
python3 core/executive_director.py --prompt "Docker Reverse Proxy" --dry-run

# Record feedback lesson
python3 core/executive_director.py --feedback "Toujours citer la version de l'OS"
```

## 📦 Installation

```bash
git clone https://github.com/hitech-lab/genio.git
cd genio
pip install -r requirements.txt
```

### Prerequisites
- Python 3.10+
- Docker (for sandbox validation)
- Ollama (local LLM inference)
- ffmpeg + Chromium (media generation)

## 🧩 Module Overview

| Module | Purpose |
|--------|---------|
| `core/executive_director.py` | Master ReAct reasoning loop & DAG task decomposition |
| `core/model_router.py` | Dynamic LLM routing with automatic failover |
| `core/memory_engine.py` | Dual-vector memory (SQLite-vec) + episodic self-debrief |
| `core/perception/` | Video analysis, web scraping, voice parsing |
| `sandbox/node_manager.py` | Multi-container network orchestration |
| `sandbox/live_recorder.py` | 1080p terminal recording with Darija voice-over |
| `sandbox/self_healer.py` | Kernel log inspector & auto-patching loop |
| `media/visual_generator.py` | Cyberpunk HTML/SVG cards with SMIL animations |
| `media/voice_studio.py` | Multi-pass TTS & studio audio mastering |
| `media/cinema_director.py` | Automated video assembly |
| `publishers/ghost_publisher.py` | Mobiledoc native HTML card publisher |
| `publishers/youtube_publisher.py` | YouTube OAuth uploader with timestamps |
| `web/server.py` | FastAPI backend with SSE, WebSocket, Tool Calling |

## 🎯 Key Features

- **Autonomous Pipeline**: Single command → full lab generation, validation, and publication
- **Self-Healing**: Auto-retries on Docker failures, LLM rate limits, and command errors
- **IT-Connect Standard**: 2-node scenarios, real routing, pedagogical Darija writing
- **Multi-Model Failover**: gemma2 → qwen2.5 → qwen2.5-coder (automatic on failure)
- **Memory Evolution**: Learns from every rejection, never repeats mistakes

## 📊 Supported LLM Backends

| Backend | Status | Failover |
|---------|--------|----------|
| Ollama (local) | ✅ Primary | auto-retry |
| OpenRouter (API) | ✅ Cloud | 429→backup |
| Claude (API) | 🔄 Ready | manual |
| GPT-4 (API) | 🔄 Ready | manual |

## 📄 License

Apache License 2.0 — see [LICENSE](LICENSE) for details.

---

**Built with ❤️ by [HiTech Lab](https://lab.hitech.tn)**
