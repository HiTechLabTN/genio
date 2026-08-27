"""Genio — Multi-Part YouTube OAuth Uploader with Timestamps.

Builds YouTube upload payloads with chaptered descriptions and tags.
Uploads when OAuth credentials are available, otherwise emits payload JSON.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Re-export from legacy module
from youtube_publisher import build_wireguard_payload, upload


def build_payload(title: str, description: str, tags: list,
                  category_id: int = 28, video_path: str = "") -> dict:
    return {
        "title": title,
        "description": description,
        "tags": tags,
        "categoryId": str(category_id),
        "videoPath": video_path,
    }
