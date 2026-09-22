"""Genio — Cyberpunk Native HTML/SVG Cards with SMIL Animations.

Generates dark-mode, neon-accented SVG/HTML cards for Ghost publication.
"""
from __future__ import annotations

from typing import Optional

from loguru import logger


def generate_callout_box(title: str, text: str, kind: str = "warn") -> str:
    colors = {
        "warn": {"border": "#f59e0b", "bg": "#1a2332", "text": "#fbbf24", "icon": "⚠️"},
        "danger": {"border": "#ef4444", "bg": "#1a2332", "text": "#fca5a5", "icon": "🚫"},
        "info": {"border": "#3b82f6", "bg": "#1a2332", "text": "#93c5fd", "icon": "ℹ️"},
    }
    c = colors.get(kind, colors["warn"])
    return (f'<div dir="rtl" class="callout {kind}" '
            f'style="border-right:6px solid {c["border"]};'
            f'background:{c["bg"]};padding:16px;border-radius:10px;'
            f'color:{c["text"]};">'
            f'{c["icon"]} <strong>{title}</strong>: {text}</div>')


def generate_hero_box(text: str) -> str:
    return (f'<div dir="rtl" class="hero-box" '
            f'style="background:linear-gradient(135deg,#0f172a,#1e293b);'
            f'padding:24px;border-radius:12px;border:1px solid #00ff88;'
            f'color:#e2e8f0;font-size:18px;">'
            f'🎯 {text}</div>')
