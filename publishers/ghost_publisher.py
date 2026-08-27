"""Genio — Mobiledoc Native HTML Card Publisher for Ghost CMS.

Publishes content with interactive HTML/SVG cards via Ghost Admin API.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Re-export from legacy module
from ghost_utils import GhostClient


def publish_article(title: str, content: str, tags: list = None,
                    ghost_url: str = "", admin_key: str = "") -> dict:
    client = GhostClient(ghost_url, admin_key)
    return client.create_post(title, content, tags=tags or [])
