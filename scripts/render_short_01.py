"""
Genio — Render-ready automation for short_01_filesystem_hook.

Reads content/shorts/short_01_filesystem_hook.json (vertical 1080x1920 Shorts
motion spec), draws each act keyframe with PIL (RTL Arabic via arabic_reshaper
+bidi, JetBrains-Mono-style terminal panels), and assembles a 45s preview MP4
with ffmpeg (cross-fade slides, no audio).

Run:
    python3 scripts/render_short_01.py              # frames + preview.mp4 + contact sheet
    python3 scripts/render_short_01.py --only-frames
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display

SHORTS = Path(__file__).resolve().parent.parent / "content" / "shorts"
SPEC = SHORTS / "short_01_filesystem_hook.json"
FRAMES = SHORTS / "frames"
W, H = 1080, 1920


def text_rtl(s: str) -> str:
    return get_display(arabic_reshaper.reshape(s))


def hex2rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def find_font(bold: bool = False) -> str:
    for cand in ("/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Bold.ttf",
                 "/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Regular.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"):
        if Path(cand).exists():
            return cand
    raise FileNotFoundError("no mono font found")


def draw_terminal(draw: ImageDraw, x: int, y: int, w: int, h: int,
                  lines: list[str], palette: dict,
                  warn_line: str | None = None) -> None:
    draw.rounded_rectangle([x, y, x + w, y + h], radius=28,
                           fill=hex2rgb(palette["surface"]), outline=(148, 163, 184), width=2)
    draw.ellipse([x + 34, y + 30, x + 46, y + 42], fill=(244, 63, 94))
    draw.ellipse([x + 58, y + 30, x + 70, y + 42], fill=(250, 204, 21))
    draw.ellipse([x + 82, y + 30, x + 94, y + 42], fill=(0, 255, 135))
    mono = find_font()
    font = ImageFont.truetype(mono, 44)
    fy = y + 90
    for ln in lines:
        color = hex2rgb(palette["accent"]) if ln.startswith("$") else hex2rgb(palette["text"])
        if warn_line and warn_line in ln:
            color = hex2rgb(palette["warn"])
        draw.text((x + 46, fy), ln, font=font, fill=color)
        fy += 74


def resolve_color(palette: dict, key: str) -> tuple[int, int, int, int]:
    raw = palette.get(key, key)
    return hex2rgb(raw) + (255,)


def draw_heading(draw: ImageDraw, title: str, palette: dict, color_key: str,
                 cy: int) -> None:
    font = ImageFont.truetype(find_font(), 96)
    t = text_rtl(title)
    # subtle glow
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.text((W // 2, cy), t, font=font, fill=resolve_color(palette, color_key)[:3] + (40,),
            anchor="mm")
    glow = glow.filter(ImageFilter.GaussianBlur(6))
    draw.bitmap((0, 0), glow)
    draw.text((W // 2, cy), t, font=font, fill=hex2rgb(palette["text"]), anchor="mm")


def render_act(name: str, act: dict, palette: dict) -> Image.Image:
    bg = hex2rgb(palette["background"])
    img = Image.new("RGBA", (W, H), bg + (255,))
    draw = ImageDraw.Draw(img, "RGBA")

    # subtle diagonal neon grid
    grid = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grid)
    for i in range(-H, W, 140):
        gd.line([(i, H), (i + H, 0)], fill=(15, 23, 42, 120), width=3)
    img.alpha_composite(grid)

    lines = act.get("terminal_lines", [])
    box_h = 74 * len(lines) + 150 if lines else 300
    if act.get("warn"):
        banner = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        bd = ImageDraw.Draw(banner)
        for i in range(0, W, 12):
            bd.rectangle([0, i % W, W, (i % W) + 60], fill=(244, 63, 94, 28))
        img.alpha_composite(banner)

    if act.get("command"):
        draw_heading(draw, act["command"], palette, "accent", 380)
    key = act.get("title_color") or ("warn" if act.get("warn") else "primary")
    draw_heading(draw, act["title_ar"], palette, key, 250)

    term_x, term_y, term_w, term_h = 90, 660, W - 180, box_h
    draw_terminal(draw, term_x, term_y, term_w, term_h, lines, palette,
                  warn_line=act.get("warn_line"))

    if act.get("cta"):
        card_y = H - 430
        draw.rounded_rectangle([150, card_y, W - 150, card_y + 200], radius=40,
                               fill=(0, 240, 255, 26), outline=(0, 240, 255), width=4)
        font = ImageFont.truetype(find_font(), 60)
        draw.text((W // 2, card_y + 100), text_rtl("HiTech Lab — سلسلة LPI"),
                  font=font, fill=(0, 255, 135), anchor="mm")
        if act.get("link"):
            lnk = ImageFont.truetype(find_font(), 42)
            draw.text((W // 2, card_y + 150), act["link"].replace("https://", ""),
                      font=lnk, fill=(248, 250, 252), anchor="mm")

    if act.get("time_code"):
        tc = ImageFont.truetype(find_font(), 34)
        draw.text((W - 60, H - 90), act["time_code"], font=tc,
                  fill=(148, 163, 184, 200), anchor="rm")
    return img


def _assemble(spec: dict, names: list[str], out: Path) -> None:
    """Concatenate per-act stills into one vertical 45s MP4 (fade transitions)."""
    acts = [spec["acts"][n.upper()] for n in names]
    n = len(acts)
    filt = []
    # per-clip: loop the still for its duration with fade in/out
    for i, act in enumerate(acts):
        dur = act["time_range_s"][1] - act["time_range_s"][0]
        filt.append(
            f"[{i}:v]format=yuv420p,"
            f"trim=duration={dur},setpts=PTS-STARTPTS,"
            f"fade=t=in:st=0:d=0.12,fade=t=out:st={dur - 0.12:.2f}:d=0.12,"
            f"scale=1080:1920:force_original_aspect_ratio=decrease,"
            f"pad=1080:1920:(ow-iw)/2:(oh-ih)/2[v{i}];"
        )
    # xfade chain
    prev = "v0"
    offset = acts[0]["time_range_s"][1] - 0.2
    for i in range(1, n):
        out_name = f"x{i}" if i < n - 1 else "vout"
        filt.append(
            f"[{prev}][v{i}]xfade=transition=fade:duration=0.2:offset={offset:.2f}[{out_name}]"
        )
        if i < n - 1:
            offset += acts[i]["time_range_s"][1] - acts[i]["time_range_s"][0] - 0.2
            prev = out_name
        else:
            prev = "vout"
        filt.append(";" if i < n - 1 else "")
    total = sum(a["time_range_s"][1] - a["time_range_s"][0] for a in acts)
    cmd = ["ffmpeg", "-y"]
    # one looped still input per act slot
    for i, name in enumerate(names):
        cmd += ["-loop", "1", "-i", str(FRAMES / f"{name}.png")]
    cmd += ["-filter_complex", "".join(filt),
            "-map", "[vout]", "-t", f"{total}", "-r", "30",
            "-an", "-crf", "23", "-pix_fmt", "yuv420p", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("ffmpeg failed:", r.stderr[-800:])
    else:
        print(f"preview mp4: {out} ({total:.0f}s)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only-frames", action="store_true", help="skip mp4 assembly")
    args = ap.parse_args()

    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    palette = spec["palette"]
    FRAMES.mkdir(parents=True, exist_ok=True)
    rendered: list[str] = []

    for name, act in spec["acts"].items():
        safe = name.lower().replace("/", "_")
        frame = render_act(name, act, palette).convert("RGB")
        frame.save(FRAMES / f"{safe}.png", "PNG")
        rendered.append(safe)
        print(f"rendered {FRAMES / (safe + '.png')}")

    sheet = Image.new("RGB", (1140, 2000), (3, 7, 18))
    positions = [(20, 20), (590, 20), (20, 998), (590, 998)]
    for safe, pos in zip(rendered, positions):
        sheet.paste(Image.open(FRAMES / f"{safe}.png").resize((530, 960)), pos)
    sheet_save = SHORTS / "short_01_contact_sheet.png"
    sheet.save(sheet_save, "PNG")
    print(f"contact sheet: {sheet_save}")

    if not args.only_frames and shutil.which("ffmpeg"):
        _assemble(spec, rendered, SHORTS / "short_01_filesystem_hook_preview.mp4")
    elif not args.only_frames:
        print("ffmpeg not found; skipped mp4 assembly")


if __name__ == "__main__":
    main()