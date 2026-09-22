"""
Genio — 16:9 desktop terminal short: realistic animated terminal with
Tunisian Darja voiceover and subtle typing-key SFX.

Layout: 1920x1080, centered dark terminal window (1500x850) on a subtle
gradient, macOS dots + title bar "hitech@lab-node-01: ~", 40px padding and
monospaced 34px so every command fits with no clipping. Writers char-by-char,
paints output with ANSI-like colors (red 100% /, amber /var/log 45G, green
22% free) plus a live "root usage" footer strip.

Audio: 4 darja narration segments are synthesized and placed at exact phase
onsets (adelay/amix), mixed with a programmatically generated typing-key click
track and normalized. Output: content/shorts/short_01_real_demo.mp4.

Usage:
    python3 scripts/render_real_terminal_short.py
    python3 scripts/render_real_terminal_short.py --voice ar-TN-ReemNeural
    python3 scripts/render_real_terminal_short.py --no-video
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import random
import shutil
import subprocess
import sys
import tempfile
import wave
from pathlib import Path
from typing import List, Tuple

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT_MP4 = ROOT / "content" / "shorts" / "short_01_real_demo.mp4"
TMP = Path(tempfile.gettempdir()) / "genio_tts"
TMP.mkdir(parents=True, exist_ok=True)

W, H, FPS = 1920, 1080, 25
WIN_W, WIN_H, WIN_X, WIN_Y = 1500, 850, 210, 115
TITLE_H, PAD = 44, 40
FONT, LH = 34, 56

BG_TOP, BG_BOT, GRID = (10, 15, 26), (16, 24, 40), (255, 255, 255)
WIN_BG, WIN_BORDER, TITLE_BG = (13, 17, 23), (46, 58, 78), (22, 28, 40)
FG, DIM = (219, 227, 236), (139, 148, 158)
CYAN, GREEN, RED, AMBER = (88, 192, 236), (76, 211, 124), (255, 107, 107), (247, 185, 85)

PROMPT = "hitech@lab-node-01:~$ "

# narrative segments (darja) — one per terminal phase (crisp, professional)
NARRATION = [
    "كي يوصلك تنبيه إنو القرص معبي مية بالمية، أول أمر تبدا بيه هو دي إف تيغي إش باش تشوف أما بارتيسيون معبية.",
    "بعدها نستعملو أمر دي يو باش نكشفو المجلد اللي واكل المساحة، وتشوفو لهنا سلاش فار لوغ واكل خمسة وأربعين جيغا.",
    "الحل السريع والنظيف هو جورنال سي تي إل دوبل تيغي فاكيوم سايز، نفرغو اللوغات القديمة ونرجعو المساحة فوراً.",
    "نعاودو نتأكدو بأمر دي إف، وتشوفو كيفاش السيرفر رجع يخدم مرتاح بنسبة اثنين وعشرين بالمية فقط.",
]

# trimmed terminal output per phase (fits comfortably inside 1500px window)
PHASES = [
    ("df -h", [
        "Filesystem   Size  Used  Avail  Use%  Mounted on",
        "/dev/sda2   120G  120G     0G  100%  /",
        "tmpfs         2G  1.4G   0.6G   70%  /run",
        "udev         5.8G    0   5.8G    0%  /dev",
    ], 1),
    ("sudo du -sh /* 2>/dev/null | sort -hr | head -n 5", [
        "45G   /var/log",
        "21G   /home",
        "18G   /usr",
    ], 0),
    ("sudo journalctl --vacuum-size=200M", [
        "Vacuuming done, freed 42.8G of archived journals",
        "System: 120G, free: 45.1G",
    ], 0),
    ("df -h", [
        "Filesystem   Size  Used  Avail  Use%  Mounted on",
        "/dev/sda2   120G   26G    94G   22%  /",
        "tmpfs         2G  1.4G   0.6G   70%  /run",
        "",
        "done - disk healthy again",
    ], 1),
]

TYPING = [0.7, 2.4, 2.0, 0.7]   # seconds spent typing each command
REVEAL_SPAN = 0.9               # seconds to paint output lines after typing
INTRO, PAD = 0.4, 1.0          # loose timing


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    p = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf" if bold \
        else "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
    return ImageFont.truetype(p, size) if Path(p).exists() else ImageFont.load_default()


# -------------------------------------------------------------------- plan

def plan(durations: List[float]) -> Tuple[List[float], float]:
    cum = [INTRO]
    for i in range(1, len(durations)):
        need = max(durations[i - 1], TYPING[i - 1] + REVEAL_SPAN + 0.1)
        cum.append(cum[-1] + need + PAD)
    return cum, cum[-1] + durations[-1] + 2.0


# ---------------------------------------------------------------- voiceover

def audio_duration(p: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration", "-of", "csv=p=0", str(p)],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 2.0


def synth_voiceover(voice: str, cum: List[float], total: float,
                    seg_files: List[Path]) -> Path:
    del_s = "".join(f"[{i + 1}:a]adelay={int(cum[i] * 1000)}[s{i}];"
                    for i in range(len(NARRATION)))
    mix = "".join(f"[s{i}]" for i in range(len(NARRATION)))
    audio = TMP / "voiceover_mux.wav"
    cmd = ["ffmpeg", "-y", "-f", "lavfi",
           "-i", "anullsrc=channel_layout=mono:sample_rate=48000"]
    for i, seg in enumerate(seg_files):
        cmd += ["-i", str(seg)]
    cmd += ["-filter_complex",
            f"{del_s}{mix}amix=inputs={len(NARRATION)}:duration=longest:dropout_transition=0,"
            "aformat=sample_rates=48000[aout]",
            "-map", "[aout]", "-t", f"{total:.3f}", "-c:a", "pcm_s16le", str(audio)]
    subprocess.run(cmd, check=True, capture_output=True)
    return audio


# -------------------------------------------------------------- typing clicks

def build_click_track(cum: List[float], total: float) -> Path:
    SR = 44100
    n = int(total * SR) + 1
    data = [0.0] * n
    clicks: List[float] = []
    for i, s in enumerate(cum):
        t = s + 0.06
        while t < min(s + TYPING[i], total - 0.1):
            clicks.append(t)
            t += random.uniform(0.09, 0.14)
    for t0 in clicks:
        start = int(t0 * SR)
        span = min(int(0.05 * SR), n - start)
        for k in range(max(1, span)):
            tt = (start + k) / SR
            if tt >= total:
                break
            env = math.exp(-(tt - t0) / 0.0055)
            val = 0.042 * math.sin(2 * math.pi * (1400 + random.random() * 300) * (tt - t0)) * env
            data[start + k] += val + (random.random() - 0.5) * 0.012 * env
    import struct
    out = TMP / "typing_clicks.wav"
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        frames = bytearray()
        for v in data:
            s = max(-1.0, min(1.0, v))
            frames += struct.pack("<h", int(s * 32767))
        w.writeframesraw(bytes(frames))
    return out


# ---------------------------------------------------------------- frame render

def _background() -> Image.Image:
    base = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(base)
    r0 = BG_TOP[0]; g0 = BG_TOP[1]; b0 = BG_TOP[2]
    for y in range(H):
        f = y / H
        col = (int(r0 + (BG_BOT[0] - r0) * f),
               int(g0 + (BG_BOT[1] - g0) * f),
               int(b0 + (BG_BOT[2] - b0) * f))
        d.line([(0, y), (W, y)], fill=col)
    ga = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(ga, "RGBA")
    for x in range(-H, W, 92):
        gd.line([(x, H), (x + H, 0)], fill=(200, 220, 255, 14), width=1)
    for y in range(0, H, 92):
        gd.line([(0, y), (W, y)], fill=(200, 220, 255, 12), width=1)
    base.paste(Image.alpha_composite(base.convert("RGBA"), ga).convert("RGB"), (0, 0))
    return base


def _draw(canvas: Image.Image, t: float, cum: List[float],
          revealed: List[int], typing: str, cursor_on: bool,
          run_phase: int) -> None:
    d = ImageDraw.Draw(canvas)
    mono_r, mono_b = font(FONT), font(FONT, bold=True)

    # window
    d.rounded_rectangle([WIN_X, WIN_Y, WIN_X + WIN_W, WIN_Y + WIN_H],
                        radius=16, fill=WIN_BG, outline=WIN_BORDER, width=2)
    # title bar
    d.rectangle([WIN_X, WIN_Y, WIN_X + WIN_W, WIN_Y + TITLE_H], fill=TITLE_BG)
    d.line([(WIN_X, WIN_Y + TITLE_H), (WIN_X + WIN_W, WIN_Y + TITLE_H)],
           fill=WIN_BORDER, width=1)
    for i, c in enumerate((RED, AMBER, GREEN)):
        d.ellipse([WIN_X + 22 + i * 30, WIN_Y + 15,
                   WIN_X + 22 + i * 30 + 14, WIN_Y + 15 + 14], fill=c)
    d.text(((WIN_X + WIN_W) // 2, WIN_Y + TITLE_H // 2),
           "hitech@lab-node-01: ~", font=font(24, True), fill=DIM, anchor="mm")

    # visible blocks: last two revealed phases (terminal scroll behavior)
    blocks = [pi for pi in range(len(PHASES)) if revealed[pi] > 0][-2:]
    yy = WIN_Y + TITLE_H + PAD
    dims = ("Filesystem", "tmpfs", "udev", "System", "Mounted")
    for pi in blocks:
        cmd, lines, hl = PHASES[pi]
        d.text((WIN_X + PAD, yy), PROMPT + cmd, font=mono_b, fill=CYAN)
        yy += LH
        for i in range(min(revealed[pi], len(lines))):
            ln = lines[i]
            if not ln:
                yy += LH
                continue
            if i == hl:
                col = RED if pi == 0 else (AMBER if pi == 1 else GREEN)
                d.text((WIN_X + PAD + 26, yy), ln, font=mono_b, fill=col)
            else:
                col = DIM if ln.startswith(dims) else FG
                d.text((WIN_X + PAD + 26, yy), ln, font=mono_r, fill=col)
            yy += LH
        yy += 26

    if typing and run_phase not in blocks:
        d.text((WIN_X + PAD, yy), PROMPT + typing, font=mono_b, fill=CYAN)
        if cursor_on:
            cw = d.textlength(PROMPT + typing, font=mono_b)
            d.rectangle([WIN_X + PAD + cw + 6, yy - 4, WIN_X + PAD + cw + 30, yy + LH - 14],
                        fill=GREEN)

    # footer "root usage" stat strip
    fy = WIN_Y + WIN_H - 46
    d.rectangle([WIN_X + PAD, fy, WIN_X + WIN_W - PAD, fy + 30], fill=(17, 23, 36))
    cur = [0, 0, 100, 22][run_phase]
    col = RED if run_phase < 2 else GREEN
    label = "root /dev/sda2: 100% FULL — 0B free" if run_phase < 2 \
        else "root /dev/sda2: 22% used — 94G free"
    d.text((WIN_X + PAD + 8, fy + 4), label, font=font(20, True), fill=col)

    # caption chip below the window
    labels = ["step 1/4 · df — root 100%", "step 2/4 · du — /var/log 45G",
              "step 3/4 · journalctl vacuum", "step 4/4 · root 22% — recovered"]
    cy = WIN_Y + WIN_H + 30
    txt = labels[run_phase]
    wch = d.textlength(txt, font=font(22, True)) + 48
    d.rounded_rectangle([(W - wch) // 2, cy, (W + wch) // 2, cy + 42], radius=21,
                        fill=(18, 25, 40), outline=(46, 58, 78), width=1)
    d.text((W // 2, cy + 21), txt, font=font(22, True), fill=CYAN, anchor="mm")


def render_frames(cum: List[float], total: float) -> List[Path]:
    n = int(total * FPS)
    print(f"render {n} frames @ {FPS}fps (total {total:.1f}s)")
    frame_dir = TMP / "frames"
    if frame_dir.exists():
        shutil.rmtree(frame_dir)
    frame_dir.mkdir(parents=True)
    base = _background()
    blink = [True, False, True, False]
    paths = []
    for idx in range(n):
        t = idx / FPS
        run_phase = 0
        for pi, c in enumerate(cum):
            if t >= c:
                run_phase = pi
        revealed = [0] * len(PHASES)
        for pi in range(len(cum)):
            if t >= cum[pi] + TYPING[pi] + 0.1:
                frac = min(1.0, max(0.0, (t - (cum[pi] + TYPING[pi] + 0.1)) / REVEAL_SPAN))
                revealed[pi] = int(frac * len(PHASES[pi][1]))
        rp = PHASES[run_phase][0]
        typing, cursor = "", False
        if revealed[run_phase] == 0 and t < cum[run_phase] + TYPING[run_phase]:
            pt = (t - cum[run_phase]) / TYPING[run_phase]
            typing, cursor = rp[: int(pt * len(rp))], blink[idx % 4]
        else:
            typing = rp
        canvas = base.copy()
        _draw(canvas, t, cum, revealed, typing, cursor, run_phase)
        fp = frame_dir / f"f{idx:05d}.png"
        canvas.save(fp, "PNG")
        paths.append(fp)
    return paths


# ------------------------------------------------------------------- assemble

def assemble(frames: List[Path], voice: Path, clicks: Path, total: float) -> Path:
    v_raw = TMP / "video_raw.mp4"
    subprocess.run(["ffmpeg", "-y", "-framerate", str(FPS), "-i",
                    str(TMP / "frames" / "f%05d.png"), "-c:v", "libx264",
                    "-preset", "medium", "-crf", "21", "-pix_fmt", "yuv420p",
                    "-t", f"{total:.3f}", str(v_raw)], check=True, capture_output=True)
    a_final = TMP / "a_final.wav"
    subprocess.run(["ffmpeg", "-y", "-i", str(voice), "-i", str(clicks),
                    "-filter_complex",
                    "[0:a]aformat=sample_rates=44100[v0];"
                    "[1:a]aformat=sample_rates=44100[v1];"
                    "[v0][v1]amix=inputs=2:duration=longest:dropout_transition=0,"
                    "loudnorm=I=-16:TP=-1.5:LRA=11[aout]",
                    "-map", "[aout]", "-t", f"{total:.3f}",
                    "-c:a", "pcm_s16le", str(a_final)], check=True, capture_output=True)
    subprocess.run(["ffmpeg", "-y", "-i", str(v_raw), "-i", str(a_final),
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac",
                    "-b:a", "192k", "-movflags", "+faststart", str(OUT_MP4)],
                   check=True, capture_output=True)
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                          "stream=codec_type,codec_name,duration,width,height",
                          "-of", "json", str(OUT_MP4)], capture_output=True, text=True)
    print("final:", OUT_MP4, json.loads(out.stdout))
    return OUT_MP4


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice", default="ar-TN-HediNeural")
    ap.add_argument("--no-video", action="store_true")
    args = ap.parse_args()
    if shutil.which("ffmpeg") is None:
        sys.exit("ffmpeg required")
    import edge_tts  # noqa: F401

    print(">> voiceover")
    durs = []
    seg_files = []
    for i, seg in enumerate(NARRATION):
        h = hashlib.md5(seg.encode("utf-8")).hexdigest()[:8]
        mp3 = TMP / f"seg_{i}_{h}.mp3"
        if not mp3.exists():
            asyncio.run(edge_tts.Communicate(
                seg, args.voice, rate="-2%", pitch="+2Hz").save(str(mp3)))
        durs.append(audio_duration(mp3))
        seg_files.append(mp3)
        print(f"  seg{i}: {durs[-1]:.1f}s")
    cum, total = plan(durs)
    print(f"  timeline cum={[round(c, 1) for c in cum]} total={total:.1f}s")

    voice = synth_voiceover(args.voice, cum, total, seg_files)
    print(f"  voiceover mux: {audio_duration(voice):.1f}s")
    if args.no_video:
        print("audio-only:", voice)
        return

    print(">> typing clicks")
    clicks = build_click_track(cum, total)
    print(">> render frames")
    frames = render_frames(cum, total)
    print(">> assemble")
    assemble(frames, voice, clicks, total)


if __name__ == "__main__":
    main()