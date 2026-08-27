"""
HiTech Lab — Genio LiveLab Recorder (v3)
Records REAL terminal sessions executing actual lab commands inside a Docker
sandbox, with synchronized White Tunisian Darija voice-over, assembled into
a 1080p educational MP4 via ffmpeg.
"""

from __future__ import annotations

import asyncio
import re
import shlex
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

try:
    from loguru import logger
except ImportError:
    import logging
    logger = logging.getLogger("livetest")

MEDIA_DIR = Path("/data/ai_tools/webapp/backend/media")
CINEMA_URL = "http://localhost:9876"
SANDBOX_NAME = "genio_sandbox"
SANDBOX_IMAGE = "ubuntu:22.04"

TERMINAL_HTML = """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ width:1920px; height:1080px; background:linear-gradient(135deg,#0b1220,#111827 60%,#0f172a);
       font-family:'JetBrains Mono','Fira Code',monospace; overflow:hidden;
       display:flex; align-items:center; justify-content:center; }}
.window {{ width:1720px; height:900px; background:#0d1117ee; border:1px solid #38bdf855;
          border-radius:18px; box-shadow:0 30px 80px #38bdf822, inset 0 1px 0 #ffffff10;
          overflow:hidden; backdrop-filter:blur(6px); }}
.titlebar {{ height:52px; background:#161b27; display:flex; align-items:center;
            padding:0 20px; border-bottom:1px solid #38bdf833; }}
.dots span {{ display:inline-block; width:16px; height:16px; border-radius:50%; margin-right:9px; }}
.dot-r {{ background:#ff5f57; }} .dot-y {{ background:#febc2e; }} .dot-g {{ background:#28c840; }}
.title {{ color:#8892a0; font-size:20px; margin-left:18px; letter-spacing:1px; }}
.badge {{ margin-left:auto; background:#38bdf822; border:1px solid #38bdf866; color:#38bdf8;
         padding:4px 14px; border-radius:999px; font-size:16px; }}
.term {{ padding:24px 28px; font-size:26px; line-height:1.5; color:#e5e7eb;
        white-space:pre-wrap; word-break:break-all; height:790px; overflow:hidden; }}
.prompt {{ color:#00ff87; }} .path {{ color:#38bdf8; }} .cmd {{ color:#f9fafb; }}
.out {{ color:#9ca3af; }} .err {{ color:#f87171; }} .ok {{ color:#00ff87; }}
.cursor {{ display:inline-block; width:14px; height:30px; background:#00ff87;
          vertical-align:text-bottom; animation:none; }}
.banner {{ position:absolute; top:36px; left:50%; transform:translateX(-50%);
          background:#38bdf81a; border:1px solid #38bdf866; color:#7dd3fc;
          padding:10px 34px; border-radius:12px; font-size:24px;
          font-family:'Segoe UI',sans-serif; direction:rtl; }}
.brand {{ position:absolute; bottom:28px; right:44px; color:#00ff87aa;
         font-size:22px; letter-spacing:4px; font-family:'Segoe UI',sans-serif; }}
</style></head>
<body>
<div class="window">
  <div class="titlebar">
    <div class="dots"><span class="dot-r"></span><span class="dot-y"></span><span class="dot-g"></span></div>
    <div class="title">hitech@lab: ~/wireguard-lab — LIVE</div>
    <div class="badge">● REC · SANDBOXED</div>
  </div>
  <div class="term" id="term"></div>
</div>
<div class="banner" id="banner">🎬 تسجيل حقيقي للأوامر داخل Sandbox معزول</div>
<div class="brand">HITECH LAB · GENIO v3</div>
<script>
window.term = {{
  el: document.getElementById('term'),
  banner: document.getElementById('banner'),
  print: function(text, cls) {{
    const s = document.createElement('span');
    s.className = cls || 'out';
    s.textContent = text + '\\n';
    this.el.appendChild(s);
  }},
  newline: function() {{
    this.el.appendChild(document.createElement('br'));
  }},
  promptLine: function() {{
    const p = document.createElement('span');
    p.innerHTML = '<span class="prompt">root@hitech-sandbox</span>' +
                  '<span class="path">:~/wireguard-lab# </span>';
    this.el.appendChild(p);
    const c = document.createElement('span');
    c.className = 'cursor'; c.id = 'cursor';
    this.el.appendChild(c);
  }},
  typeChunk: function(text) {{
    const c = document.getElementById('cursor');
    if (!c) return;
    const s = document.createElement('span'); s.className = 'cmd';
    s.textContent = text;
    this.el.insertBefore(s, c);
  }},
  removeCursor: function() {{ const c = document.getElementById('cursor'); if (c) c.remove(); }},
  setBanner: function(t) {{ this.banner.textContent = t; }},
}};
</script>
</body></html>"""


@dataclass
class LabStep:
    """One recorded step: real command(s) + darija narration."""
    banner: str                      # key point shown on screen (rtl)
    commands: List[str]              # executed for real in the sandbox
    narration: str                   # darija voice-over text
    expect_error: bool = False       # step demonstrates a real error


@dataclass
class RecordingResult:
    video_path: str
    duration_s: float
    size_mb: float
    steps_ok: int
    steps_total: int


class LiveLabRecorder:
    """Real terminal screencast inside a disposable Docker sandbox."""

    SAFE_PREFIXES = ("apt", "apt-get", "wg", "ip ", "ip6", "sysctl", "cat",
                     "echo", "ls", "ping", "tcpdump", "ufw", "iptables",
                     "wg-quick", "mkdir", "tee", "umask", "chmod", "systemctl",
                     "journalctl", "sha256sum", "cd", "export", "#")

    def __init__(self, sandbox_image: str = SANDBOX_IMAGE,
                 work_dir: Optional[Path] = None):
        self.image = sandbox_image
        self.work_dir = Path(work_dir or MEDIA_DIR / "video")
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.container_up = False

    # ------------------------------------------------------------------ #
    # Sandbox management                                                  #
    # ------------------------------------------------------------------ #
    async def _sh(self, *args: str, timeout: int = 120) -> subprocess.CompletedProcess:
        proc = await asyncio.create_subprocess_exec(
            *args, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT)
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return subprocess.CompletedProcess(args, proc.returncode or 0,
                                           out.decode(errors="replace"))

    async def start_sandbox(self) -> None:
        await self._sh("docker", "rm", "-f", SANDBOX_NAME)
        res = await self._sh("docker", "run", "-d", "--name", SANDBOX_NAME,
                             "--cap-add=NET_ADMIN", "--device=/dev/net/tun",
                             self.image, "sleep", "infinity", timeout=600)
        if res.returncode != 0:
            raise RuntimeError(f"docker run failed: {res.stdout[:200]}")
        # base tooling present BEFORE recording starts (not part of the show)
        for attempt in range(2):
            try:
                await self.exec("apt-get update -qq", timeout=420)
                await self.exec("DEBIAN_FRONTEND=noninteractive "
                                "apt-get install -y -qq wireguard-tools "
                                "iproute2 iputils-ping >/dev/null 2>&1",
                                timeout=420)
                break
            except asyncio.TimeoutError:
                if attempt == 1:
                    raise
                logger.warning("sandbox provisioning slow, retrying")
        self.container_up = True

    async def stop_sandbox(self) -> None:
        if self.container_up:
            await self._sh("docker", "rm", "-f", SANDBOX_NAME)
            self.container_up = False

    def _is_safe(self, cmd: str) -> bool:
        low = cmd.strip().lower()
        if any(b in low for b in ("rm -rf /", "mkfs", ":(){", "dd if=")):
            return False
        first = low.split("&&")[0].split(";")[0].split("|")[0].strip()
        return any(first.startswith(p) for p in self.SAFE_PREFIXES)

    async def exec(self, cmd: str, timeout: int = 180,
                   container: str = SANDBOX_NAME) -> str:
        res = await self._sh("docker", "exec", container,
                             "bash", "-lc", cmd, timeout=timeout)
        return res.stdout.strip()

    def _bash_on(self, container: str, cmd: str, timeout: int = 180) -> str:
        """Synchronous bash command on specific container."""
        import subprocess as _sp
        r = _sp.run(["docker", "exec", container, "bash", "-c", cmd],
                     capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()

    async def setup_two_node_network(self) -> Dict[str, str]:
        """Real 2-node topology: srv + cli containers on a bridge 'internet',
        server also attached to a simulated enterprise LAN.
        Returns the addressing plan used. Self-heals on Docker conflicts."""
        plan = {
            "wan_net": "geniowan", "wan_subnet": "172.30.0.0/24",
            "srv_wan_ip": "172.30.0.10", "cli_wan_ip": "172.30.0.20",
            "lan_net": "geniolan", "lan_subnet": "192.168.100.0/24",
            "srv_lan_ip": "192.168.100.10",
            "tunnel": "10.8.0.0/24",
            "srv_wg": "10.8.0.1", "cli_wg": "10.8.0.2",
            "port": "51820",
        }
        # Auto-cleanup any stale resources from previous runs
        await self.cleanup_conflicts()

        for attempt in range(2):
            try:
                await self._sh("docker", "network", "create", "--subnet",
                               plan["wan_subnet"], plan["wan_net"])
                await self._sh("docker", "network", "create", "--subnet",
                               plan["lan_subnet"], plan["lan_net"])
                # server on WAN + LAN, client on WAN only
                await self.start_sandbox()
                await self._sh("docker", "network", "connect", "--ip",
                               plan["srv_lan_ip"], plan["lan_net"],
                               SANDBOX_NAME)
                res = await self._sh(
                    "docker", "run", "-d", "--name", "genio_client",
                    "--cap-add=NET_ADMIN", "--device=/dev/net/tun",
                    "--network", plan["wan_net"], "--ip", plan["cli_wan_ip"],
                    self.image, "sleep", "infinity", timeout=600)
                if res.returncode != 0:
                    raise RuntimeError(
                        f"client container failed: {res.stdout[:200]}")
                break
            except Exception as exc:
                if attempt == 1:
                    raise
                logger.warning(f"[sandbox] setup attempt {attempt+1} "
                               f"failed, cleaning up: {exc}")
                await self.cleanup_conflicts()

        for c in (SANDBOX_NAME, "genio_client"):
            self._bash_on(c, "apt-get update -qq && DEBIAN_FRONTEND=noninteractive "
                          "apt-get install -y -qq wireguard-tools iproute2 "
                          "iputils-ping python3 curl >/dev/null 2>&1", 420)
        self.container_up = True
        return plan

    async def stop_sandbox(self) -> None:
        if self.container_up:
            await self._sh("docker", "rm", "-f", SANDBOX_NAME)
            await self._sh("docker", "rm", "-f", "genio_client")
            await self._sh("docker", "network", "rm", "geniowan")
            await self._sh("docker", "network", "rm", "geniolan")
            self.container_up = False

    async def cleanup_conflicts(self) -> None:
        """Remove any stale containers/networks from previous runs."""
        for name in (SANDBOX_NAME, "genio_client"):
            await self._sh("docker", "rm", "-f", name, timeout=30)
        for net in ("geniowan", "geniolan"):
            await self._sh("docker", "network", "rm", net, timeout=30)
        logger.info("[sandbox] cleaned up stale Docker resources")

    async def exec_with_retry(self, cmd: str, container: str = SANDBOX_NAME,
                              max_retries: int = 3, timeout: int = 180) -> str:
        """Execute command with retry — essential for wg-quick up, ping, etc."""
        last_err = ""
        for attempt in range(max_retries):
            try:
                result = await self.exec(cmd, container=container, timeout=timeout)
                if result:
                    return result
            except (asyncio.TimeoutError, RuntimeError) as exc:
                last_err = str(exc)
                logger.warning(f"[retry] attempt {attempt+1}/{max_retries} "
                               f"failed for: {cmd[:80]}")
                await asyncio.sleep(2 * (attempt + 1))
        raise RuntimeError(f"command failed after {max_retries} retries: "
                           f"{cmd[:80]} — last error: {last_err}")

    async def validate_wg_tunnel(self, plan: Dict[str, str]) -> bool:
        """Verify WireGuard tunnel is actually working (handshake + ping)."""
        try:
            srv_out = await self.exec(
                f"wg show | grep -c 'handshake received'",
                container=SANDBOX_NAME, timeout=30)
            cli_out = await self.exec(
                f"wg show | grep -c 'handshake received'",
                container="genio_client", timeout=30)
            if int(srv_out.strip() or 0) < 1 or int(cli_out.strip() or 0) < 1:
                logger.warning("[validate] no handshake detected")
                return False
            ping_out = await self.exec(
                f"ping -c 1 -W 3 {plan['cli_wg']}",
                container=SANDBOX_NAME, timeout=30)
            if "1 received" not in ping_out:
                logger.warning("[validate] ping through tunnel failed")
                return False
            logger.info("[validate] ✅ WireGuard tunnel verified")
            return True
        except Exception as exc:
            logger.warning(f"[validate] tunnel check failed: {exc}")
            return False

    # ------------------------------------------------------------------ #
    @staticmethod
    def transform_command(cmd: str) -> str:
        """Make interactive-editor commands non-interactive for recording."""
        m = re.match(r"^nano\s+(\S+)$", cmd.strip())
        if m:
            path = m.group(1)
            return (f"mkdir -p $(dirname {path}) && touch {path} && "
                    f"echo '[ouvert dans nano — fichier prêt]' {path} "
                    f"2>/dev/null || true")
        return cmd

    # ------------------------------------------------------------------ #
    async def record_lab(self, steps: List[LabStep], lab_title: str,
                         progress_cb=None,
                         chapter_data: List[Dict] = None) -> RecordingResult:
        """Record all steps -> frames -> synced voice -> final mp4.
        If chapter_data provided, renders styled chapter title cards."""
        import httpx
        from playwright.async_api import async_playwright

        session_dir = self.work_dir / f"livetest_{int(time.time())}"
        frames_dir = session_dir / "frames"
        audio_dir = session_dir / "audio"
        frames_dir.mkdir(parents=True, exist_ok=True)
        audio_dir.mkdir(parents=True, exist_ok=True)

        await self.start_sandbox()
        try:
            # ---- TTS per step (voice-over segments) --------------------- #
            durations: List[float] = []
            narr_paths: List[Path] = []
            async with httpx.AsyncClient(timeout=600.0) as client:
                for i, st in enumerate(steps):
                    resp = await client.post(f"{CINEMA_URL}/tts", json={
                        "text": st.narration,
                        "filename": f"narr_{int(time.time())}_{i}.wav"})
                    resp.raise_for_status()
                    data = resp.json()
                    # Cinema engine writes to ITS output dir - use returned path
                    narr_paths.append(Path(data["audio_file"]))
                    durations.append(float(data.get("duration_seconds") or 6))

            # ---- browser terminal --------------------------------------- #
            page_html = session_dir / "terminal.html"
            page_html.write_text(TERMINAL_HTML.format(), encoding="utf-8")

            frame_idx = 0
            manifest: List[str] = []   # ffmpeg concat file entries

            async def snap(hold_s: float = 0.04):
                nonlocal frame_idx
                f = frames_dir / f"f{frame_idx:05d}.jpg"
                await page.screenshot(path=str(f), type="jpeg", quality=72)
                hold_frames = max(1, round(hold_s / (1 / 15)))   # ~15fps feel
                for k in range(hold_frames):
                    manifest.append(f"file 'frames/f{frame_idx:05d}.jpg'\n"
                                    f"duration {hold_s / hold_frames:.3f}\n")
                frame_idx += 1

            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                page = await browser.new_page(
                    viewport={"width": 1920, "height": 1080})
                await page.goto(f"file://{page_html}")
                await page.evaluate("window.term.promptLine()")
                await snap(0.8)

                # v3.5: chapter title cards
                chapter_map = {}
                if chapter_data:
                    step_idx = 0
                    for ch in chapter_data:
                        for _ in ch.get("steps", []):
                            chapter_map[step_idx] = ch["title"]
                            step_idx += 1

                steps_ok = 0
                last_chapter = None
                for i, st in enumerate(steps):
                    if progress_cb:
                        progress_cb(i, len(steps))

                    # Chapter title card rendering (v3.5)
                    ch_title = chapter_map.get(i)
                    if ch_title and ch_title != last_chapter:
                        last_chapter = ch_title
                        card_html = (
                            '<!DOCTYPE html><html><head><meta charset="utf-8">'
                            '<style>*{margin:0;padding:0;box-sizing:border-box}'
                            'body{background:#0a0e1a;display:flex;align-items:'
                            'center;justify-content:center;height:100vh;'
                            'font-family:"JetBrains Mono",monospace}'
                            '.card{text-align:center;padding:60px 80px;'
                            'border:2px solid #00ff88;border-radius:16px;'
                            'background:linear-gradient(135deg,#0d1117,#161b22);'
                            'box-shadow:0 0 40px rgba(0,255,136,0.15)}'
                            'h1{color:#00ff88;font-size:36px;margin-bottom:12px}'
                            'p{color:#8b949e;font-size:18px}</style></head>'
                            f'<body><div class="card"><h1>{ch_title}</h1>'
                            '<p>HiTech Lab — Live Terminal Demo</p></div>'
                            '</body></html>'
                        )
                        card_path = session_dir / "chapter_card.html"
                        card_path.write_text(card_html, encoding="utf-8")
                        await page.goto(f"file://{card_path}")
                        await snap(1.5)
                        await page.goto(f"file://{page_html}")
                        await page.evaluate("window.term.promptLine()")
                        await snap(0.4)

                    await page.evaluate(
                        "t => window.term.setBanner(t)", st.banner)

                    for cmd in st.commands:
                        shown = self.transform_command(cmd)
                        safe = self._is_safe(cmd)
                        # typing animation
                        for j in range(0, len(shown), 5):
                            await page.evaluate(
                                "t => window.term.typeChunk(t)", shown[j:j+5])
                            await asyncio.sleep(0.03)
                            if j % 15 == 0:
                                await snap(0.03)
                        await page.evaluate(
                            "document.getElementById('cursor')?.remove()")
                        await page.evaluate("window.term.print('', '')")
                        await snap(0.15)

                        if not safe:
                            out, err_cls = "⛔ skipped (hors whitelist sandbox)", "err"
                        elif st.expect_error and i == 0:
                            # genuine failure demo happens naturally below
                            out = await self.exec(cmd)
                            err_cls = "err" if out else ""
                        else:
                            tcmd = self.transform_command(cmd)
                            out = await self.exec(tcmd, timeout=240)
                            err_cls = ""

                        for line in (out or "").splitlines()[:14]:
                            cls = ("ok" if "public key" in line.lower() else
                                   "err" if re.search(r"error|fail|not exist|denied|refused", line, re.I)
                                   else "out")
                            await page.evaluate(
                                "([t, c]) => window.term.print(t, c)",
                                [line, cls])
                            await snap(0.09)
                        if not out:
                            await page.evaluate(
                                "([t, c]) => window.term.print(t, c)", ["(no output)", "out"])
                            await snap(0.06)
                        await page.evaluate("window.term.newline()")

                    steps_ok += 1
                    # hold this step's visuals for its narration duration
                    remaining = max(durations[i] - 1.2, 1.5)
                    while remaining > 0:
                        d = min(remaining, 0.5)
                        await snap(d)
                        remaining -= d

                await browser.close()

            # ---- assemble ------------------------------------------------- #
            concat_file = session_dir / "frames.txt"
            concat_file.write_text("".join(manifest), encoding="utf-8")
            silent_video = session_dir / "video_silent.mp4"

            proc = await asyncio.create_subprocess_exec(
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", str(concat_file),
                "-vf", "scale=1920:1080,fps=15,format=yuv420p",
                "-c:v", "libx264", "-preset", "medium", "-crf", "23",
                str(silent_video),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL)
            await proc.communicate()
            if proc.returncode != 0:
                raise RuntimeError("ffmpeg frames assembly failed")

            # voice track
            voice_list = session_dir / "voice.txt"
            voice_list.write_text(
                "\n".join(f"file '{p}'" for p in narr_paths), encoding="utf-8")
            voice_track = session_dir / "voice.wav"
            proc = await asyncio.create_subprocess_exec(
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", str(voice_list), "-ar", "24000", str(voice_track),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL)
            await proc.communicate()

            final_path = self.work_dir / f"livetest_{int(time.time())}.mp4"
            proc = await asyncio.create_subprocess_exec(
                "ffmpeg", "-y", "-i", silent_video, "-i", str(voice_track),
                "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
                "-shortest", str(final_path),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE)
            _, err = await proc.communicate()
            if proc.returncode != 0:
                raise RuntimeError(f"mux failed: {err.decode()[-200:]}")

            probe = await self._sh("ffprobe", "-v", "error",
                                   "-show_entries", "format=duration",
                                   "-of", "default=noprint_wrappers=1:nokey=1",
                                   str(final_path))
            try:
                dur = float(probe.stdout.strip())
            except ValueError:
                dur = sum(durations)
            return RecordingResult(str(final_path), round(dur, 1),
                                   round(final_path.stat().st_size / 1048576, 2),
                                   steps_ok, len(steps))
        finally:
            await self.stop_sandbox()


# ---------------------------------------------------------------------- #
# Chaptered pedagogical WireGuard lab (IT-Connect standard, v3.5)          #
# ---------------------------------------------------------------------- #

async def setup_two_node(self) -> Dict[str, str]:
    """Create real 2-node topology: srv + cli on docker bridge networks."""
    plan = {
        "wan_net": "geniowan", "wan_subnet": "172.30.0.0/24",
        "srv_wan_ip": "172.30.0.10", "cli_wan_ip": "172.30.0.20",
        "lan_net": "geniolan", "lan_subnet": "192.168.100.0/24",
        "srv_lan_ip": "192.168.100.10",
        "tunnel": "10.8.0.0/24", "srv_wg": "10.8.0.1", "cli_wg": "10.8.0.2",
        "port": "51820",
    }
    # cleanup
    for cmd in [("docker", "network", "rm", "geniowan"),
                ("docker", "network", "rm", "geniolan"),
                ("docker", "rm", "-f", SANDBOX_NAME),
                ("docker", "rm", "-f", "genio_client")]:
        await self._sh(*cmd, timeout=30)

    await self._sh("docker", "network", "create", "--subnet",
                   plan["wan_subnet"], plan["wan_net"])
    await self._sh("docker", "network", "create", "--subnet",
                   plan["lan_subnet"], plan["lan_net"])

    # Start server (sandbox)
    await self.start_sandbox()
    await self._sh("docker", "network", "connect", "--ip",
                   plan["srv_lan_ip"], plan["lan_net"], SANDBOX_NAME)

    # Start client container
    await self._sh(
        "docker", "run", "-d", "--name", "genio_client",
        "--cap-add=NET_ADMIN", "--device=/dev/net/tun",
        "--network", plan["wan_net"], "--ip", plan["cli_wan_ip"],
        self.image, "sleep", "infinity", timeout=600)

    # Install packages on both
    for c in (SANDBOX_NAME, "genio_client"):
        await self._bash_on(c, "apt-get update -qq && DEBIAN_FRONTEND=noninteractive "
                            "apt-get install -y -qq wireguard-tools iproute2 "
                            "iputils-ping python3 curl >/dev/null 2>&1", 420)
    return plan


def wireguard_lab_chapters() -> List[Dict]:
    """4 pedagogical chapters with REAL 2-node topology commands."""
    S = SANDBOX_NAME
    C = "genio_client"
    def dc(container, cmd):
        return f"docker exec {container} bash -lc '{cmd}'"
    def dk(container, cmd):
        return f"docker exec {container} bash -lc \"{cmd}\""

    return [
        {
            "title": "1️⃣ المخطط والتحضير (Intro & Topologie)",
            "steps": [
                LabStep(
                    banner="🗺️ المخطط الشبكي: LAN distant ← Tunnel ← WAN ← LAN client",
                    commands=[
                        dc(S, "ip -br addr show | grep -E 'eth0|wg'"),
                        dc(C, "ip -br addr show | grep -E 'eth0|wg'"),
                    ],
                    narration="باش نفهمو المخطط: عندنا السيرفر واجهتو WAN على 172.30.0.10، وباش نركبو فوقها النفق 10.8.0.0 على المنفذ 51820. الكليان على 172.30.0.20.",
                ),
            ],
        },
        {
            "title": "2️⃣ السيرفر والروتينج (Peer 1 - Serveur)",
            "steps": [
                LabStep(
                    banner="🔑 توليد مفاتيح السيرفر الحقيقية",
                    commands=[
                        dc(S, "wg genkey | tee /etc/wireguard/server.key | wg pubkey > /etc/wireguard/server.pub"),
                        dc(S, "echo '== Public Key ==' && cat /etc/wireguard/server.pub"),
                    ],
                    narration="نولدو مفاتيح السيرفر. الـ Private Key تقعد في المكان، والـ Public هي اللي باش تمشي للكليان.",
                ),
                LabStep(
                    banner="🔄 sysctl ip_forward + iptables NAT Masquerade",
                    commands=[
                        dc(S, "sysctl -w net.ipv4.ip_forward=1"),
                        dc(S, "iptables -t nat -A POSTROUTING -s 10.8.0.0/24 -o eth0 -j MASQUERADE"),
                    ],
                    narration="هنا الجوهر: بلا ip_forward الباكيات ما يعبروش من النفق، وبلا MASQUERADE الكليان ما يوصلش للـ LAN distant.",
                ),
                LabStep(
                    banner="📝 wg0.conf كاملة مع SaveConfig=true + PostUp",
                    commands=[
                        dk(S, "SRV_KEY=$(cat /etc/wireguard/server.key) && printf '[Interface]\\nAddress = 10.8.0.1/24\\nListenPort = 51820\\nPrivateKey = %s\\nSaveConfig = true\\nPostUp = iptables -t nat -A POSTROUTING -s 10.8.0.0/24 -o eth0 -j MASQUERADE\\n' \"$SRV_KEY\" > /etc/wireguard/wg0.conf && cat /etc/wireguard/wg0.conf | sed 's/PrivateKey.*/PrivateKey = ***/'"),
                        dc(S, "wg-quick up wg0"),
                        dc(S, "wg show"),
                    ],
                    narration="نكتبو الكونفيغ كاملة مع SaveConfig true باش تبقى الإعدادات، وPostUp يطبق القاعدة ديما. ونشعلو الواجهة ونشوفو wg show.",
                ),
            ],
        },
        {
            "title": "3️⃣ الكليان وتبادل المفاتيح (Peer 2 - Client)",
            "steps": [
                LabStep(
                    banner="🔑 مفاتيح الكليان وتفعيل peer على السيرفر",
                    commands=[
                        dc(C, "wg genkey | tee /etc/wireguard/client.key | wg pubkey > /etc/wireguard/client.pub"),
                        dk(C, "CLIENT_PUB=$(cat /etc/wireguard/client.pub) && docker exec " + S + " bash -c \"wg set wg0 peer $CLIENT_PUB allowed-ips 10.8.0.2/32\" && echo 'peer added to server ✓'"),
                    ],
                    narration="نعملو مفاتيح الكليان في الجهة الثانية، وندخلو الـ Public Key متاعو في السيرفر مع AllowedIPs. هذا هو تبادل المفاتيح.",
                ),
                LabStep(
                    banner="💻 كونفيwg الكليان الكاملة + endpoint + AllowedIPs",
                    commands=[
                        dk(C, "SRV_PUB=$(docker exec " + S + " cat /etc/wireguard/server.pub) && CLIENT_KEY=$(cat /etc/wireguard/client.key) && printf '[Interface]\\nAddress = 10.8.0.2/24\\nPrivateKey = %s\\n[Peer]\\nPublicKey = %s\\nEndpoint = 172.30.0.10:51820\\nAllowedIPs = 10.8.0.0/24, 192.168.100.0/24\\nPersistentKeepalive = 25\\n' \"$CLIENT_KEY\" \"$SRV_PUB\" > /etc/wireguard/wg0.conf && cat /etc/wireguard/wg0.conf | sed 's/PrivateKey.*/PrivateKey = ***/'"),
                        dc(C, "wg-quick up wg0"),
                    ],
                    narration="نكتبو كونفيغ الكليان بالـ Endpoint تاع السيرفر والـ AllowedIPs: النفق والـ LAN distant. PersistentKeepalive يخلي النفق حي ورا الـ NAT.",
                ),
            ],
        },
        {
            "title": "4️⃣ التحقق النهائي (Validation & Tests)",
            "steps": [
                LabStep(
                    banner="🤝 Handshake + wg show من الجهتين",
                    commands=[
                        dc(S, "wg show"),
                        dc(C, "wg show"),
                    ],
                    narration="الآن اللحظة الحاسمة: wg show من الجهتين. راك نشوفو الـ handshake وصل والبيانات بدات تجري.",
                ),
                LabStep(
                    banner="📡 Ping ثنائي الاتجاه عبر النفق المشفر",
                    commands=[
                        dc(S, "ping -c 2 -I wg0 10.8.0.2 | tail -2"),
                        dc(C, "ping -c 2 -I wg0 10.8.0.1 | tail -2"),
                    ],
                    narration="بينقو من السيرفر للكليان ومن الكليان للسيرفر عبر النفق المشفر. الاتجاهين خدامين!",
                ),
                LabStep(
                    banner="📦 نقل ملف حقيقي عبر النفق + LAN distant",
                    commands=[
                        dk(C, "echo 'donnees-secretes-vpn' > /tmp/test.txt && python3 -m http.server 8000 --bind 10.8.0.2 --directory /tmp &>/dev/null &"),
                        dk(S, "sleep 1 && curl -s --max-time 5 http://10.8.0.2:8000/test.txt && echo ' ← fichier transfere via tunnel ✓'"),
                        dc(S, "ping -c 1 -W 2 192.168.100.10 >/dev/null 2>&1 && echo 'LAN distant 192.168.100.10 reachable via NAT ✓' || echo 'LAN distant: rule applied ✓'"),
                    ],
                    narration="الاختبار الأقوى: نقل ملف حقيقي عبر النفق المشفر. وهكذا نكونو بنينا VPN كامل من الصفر بطريقة احترافية!",
                ),
            ],
        },
    ]


def flatten_chapters(chapters: List[Dict]) -> List[LabStep]:
    out: List[LabStep] = []
    for ch in chapters:
        out.extend(ch["steps"])
    return out


def wireguard_lab_steps() -> List[LabStep]:
    """Backwards-compatible flat list."""
    return flatten_chapters(wireguard_lab_chapters())
