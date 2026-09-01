"""Genio — Dynamic Configuration & Multi-LLM Routing."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent
GENIO_DIR = ROOT
REPORTS_DIR = GENIO_DIR / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default)


@dataclass(frozen=True)
class OllamaConfig:
    base_url: str = field(default_factory=lambda: _env("OLLAMA_BASE_URL", "http://localhost:11434"))
    primary_model: str = field(default_factory=lambda: _env("GENIO_OLLAMA_MODEL", "gemma4:12b"))
    backup_models: tuple = ("qwen2.5vl:7b", "qwen2.5:7b", "qwen2.5-coder:14b")
    num_ctx: int = 8192
    temperature: float = 0.6


@dataclass(frozen=True)
class OpenRouterConfig:
    api_key: str = field(default_factory=lambda: _env("OPENROUTER_API_KEY"))
    base_url: str = "https://openrouter.ai/api/v1"
    model: str = "anthropic/claude-3.5-sonnet"


@dataclass(frozen=True)
class GhostConfig:
    url: str = field(default_factory=lambda: _env("GHOST_URL", "https://lab.hitech.tn"))
    admin_key: str = field(default_factory=lambda: _env("GHOST_ADMIN_KEY"))
    content_key: str = field(default_factory=lambda: _env("GHOST_CONTENT_KEY"))


@dataclass(frozen=True)
class CinemaConfig:
    tts_url: str = field(default_factory=lambda: _env("CINEMA_URL", "http://localhost:9876"))
    render_url: str = field(default_factory=lambda: _env("CINEMA_URL", "http://localhost:9876"))


@dataclass(frozen=True)
class VoiceConfig:
    language: str = "fr"
    speaker_wav: Optional[str] = None


@dataclass(frozen=True)
class SandboxConfig:
    image: str = field(default_factory=lambda: _env("GENIO_SANDBOX_IMAGE", "python:3.11-slim"))
    wan_net: str = "geniowan"
    wan_subnet: str = "172.30.0.0/24"
    lan_net: str = "geniolan"
    lan_subnet: str = "192.168.100.0/24"
    tunnel_subnet: str = "10.8.0.0/24"
    srv_wan_ip: str = "172.30.0.10"
    cli_wan_ip: str = "172.30.0.20"
    srv_lan_ip: str = "192.168.100.10"
    srv_wg_ip: str = "10.8.0.1"
    cli_wg_ip: str = "10.8.0.2"
    port: int = 51820
    # Phase C: allow-list for container egress (npm/pip/git) — Q2 Allow-list registries
    allowed_registries: tuple = (
        "registry.npmjs.org",
        "registry.yarnpkg.com",
        "pypi.org",
        "files.pythonhosted.org",
        "github.com",
        "gitlab.com",
    )
    # Network policy: "none" (isolated), "allowlist" (bridge + egress filter), "bridge" (full)
    # Default allowlist per Q2
    network_policy: str = field(default_factory=lambda: _env("GENIO_CONTAINER_NETWORK", "allowlist"))


@dataclass(frozen=True)
class GenioConfig:
    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    openrouter: OpenRouterConfig = field(default_factory=OpenRouterConfig)
    ghost: GhostConfig = field(default_factory=GhostConfig)
    cinema: CinemaConfig = field(default_factory=CinemaConfig)
    voice: VoiceConfig = field(default_factory=VoiceConfig)
    sandbox: SandboxConfig = field(default_factory=SandboxConfig)
    data_dir: Path = GENIO_DIR
    api_token: str = field(default_factory=lambda: _env("GENIO_API_TOKEN", ""))


_config: Optional[GenioConfig] = None


def get_config() -> GenioConfig:
    global _config
    if _config is None:
        _config = GenioConfig()
    return _config
