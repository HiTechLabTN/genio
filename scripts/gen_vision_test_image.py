"""
Genio — Vision benchmark test artifact generator.
Renders a realistic DevOps terminal failure screenshot (nginx 502 + systemd
unit failure) using pure PIL, saved to reports/vision_benchmark/test_sample.png.
"""
from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT_DIR = Path(__file__).resolve().parent.parent / "reports" / "vision_benchmark"
OUT_PATH = OUT_DIR / "test_sample.png"

W = 1280
H = 720
BG = (18, 22, 30)
PANEL = (24, 30, 42)
PANEL_EDGE = (51, 65, 89)
TEXT = (222, 230, 240)
DIM = (140, 155, 175)
RED = (248, 113, 113)
AMBER = (251, 191, 36)
GREEN = (52, 211, 153)
CYAN = (96, 222, 244)
ORANGE = (251, 146, 60)


def load_font(size: int, bold: bool = False):
    """Try DejaVu Mono first (always on Linux), fallback silently."""
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def draw():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    f_mono = load_font(17)
    f_mono_b = load_font(17, bold=True)
    f_title = load_font(16, bold=True)
    f_status = load_font(15, bold=True)

    # --- top bar: fake terminal title bars ---
    d.rectangle([0, 0, W, 34], fill=(36, 42, 56))
    d.ellipse([14, 12, 22, 20], fill=RED)
    d.ellipse([28, 12, 36, 20], fill=AMBER)
    d.ellipse([42, 12, 50, 20], fill=GREEN)
    d.text((60, 10), "genio@hitech-devops: ~", font=f_title, fill=DIM)

    y = 54
    left = 28

    def line(text, color=TEXT, y_=None, font=None, pad=4):
        nonlocal y
        yy = y if y_ is None else y_
        d.text((left, yy), text, font=font or f_mono, fill=color)
        return yy + 22

    # --- left column: curl / nginx 502 ---
    y = line("$ curl -I https://app.hitech.tn/api/v1/status", font=f_mono_b, color=CYAN)
    y = line("HTTP/1.1 502 Bad Gateway", color=RED, font=f_mono_b)
    y = line("server: nginx/1.24.0", color=DIM)
    y = line("date: Sat, 29 Aug 2026 04:45:12 GMT", color=DIM)
    d.text((left, y), "Connection refused by upstream backend (127.0.0.1:8080)", font=f_mono, fill=ORANGE)

    # --- right column: systemd unit failure panel ---
    panel_x0, panel_y0 = 760, 82
    panel_x1, panel_y1 = 1252, 330
    d.rounded_rectangle([panel_x0, panel_y0, panel_x1, panel_y1], radius=10, fill=PANEL, outline=PANEL_EDGE, width=2)
    d.text((panel_x0 + 16, panel_y0 + 14), "● app-worker.service - Genio Worker", font=f_title, fill=TEXT)
    d.text((panel_x0 + 16, panel_y0 + 42), "Loaded: loaded (/etc/systemd/system/app-worker.service; enabled)", font=f_mono, fill=DIM)
    d.text((panel_x0 + 16, panel_y0 + 70), "Active: failed (Result: exit-code) since Sat 2026-08-29 04:44:57 UTC", font=f_mono, fill=RED)
    d.text((panel_x0 + 16, panel_y0 + 98), "Process: 4012 ExecStart=/usr/bin/python3 /opt/app/worker.py", font=f_mono, fill=DIM)
    d.text((panel_x0 + 16, panel_y0 + 126), "Status: \"exit-code=1 status=1/FAILURE\"", font=f_mono, fill=ORANGE)
    d.text((panel_x0 + 16, panel_y0 + 154), "Main PID: 4012 (code=exited, status=1/FAILURE)", font=f_mono, fill=GREEN)
    d.text((panel_x0 + 16, panel_y0 + 182), "Aug 29 04:44:57 genio worker[4012]: Permission denied: '/var/run/docker.sock'", font=f_mono, fill=RED)
    d.text((panel_x0 + 16, panel_y0 + 210), "Aug 29 04:44:57 genio systemd[1]: app-worker.service: Failed with result 'exit-code'.", font=f_mono, fill=DIM)

    # --- bottom status bar ---
    d.rectangle([0, H - 34, W, H], fill=(36, 42, 56))
    d.text((28, H - 26), "● Failed: app-worker.service                    ▲ 2 running / 1 degraded", font=f_status, fill=RED)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    img.save(OUT_PATH)
    print(f"saved -> {OUT_PATH} ({img.size[0]}x{img.size[1]})")


if __name__ == "__main__":
    draw()