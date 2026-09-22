"""Genio — Multi-Pass TTS & Studio Audio Mastering.

Handles text-to-speech generation, voice cloning, and audio mastering
with loudness normalization and ducking.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
from loguru import logger

from config import get_config


class VoiceStudio:
    """TTS generation via Cinema Engine with audio mastering."""

    def __init__(self):
        self.config = get_config().cinema

    async def generate_tts(self, text: str, filename: str = "") -> dict:
        async with httpx.AsyncClient(timeout=600.0) as client:
            resp = await client.post(f"{self.config.tts_url}/tts", json={
                "text": text,
                "filename": filename or f"tts_{id(text)}.wav",
            })
            resp.raise_for_status()
            return resp.json()

    async def master_audio(self, input_path: str, output_path: str) -> str:
        """Apply loudness normalization via ffmpeg."""
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-i", input_path,
            "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
            output_path,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL)
        await proc.wait()
        return output_path
