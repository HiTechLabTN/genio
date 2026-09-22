"""Genio — Automated Video Assembly with Styled Titlecards & Audio Sync.

Orchestrates video recording, title card generation, audio sync,
and final H.264 1080p assembly.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loguru import logger

from config import get_config
from genio_executive_core import PlanNode, NodeResult, AgentContext, Artifact


class CinemaDirectorAgent:
    """Orchestrates video/audio/cover generation and Ghost publication."""

    async def run(self, node: PlanNode, ctx: AgentContext) -> NodeResult:
        action = node.action

        if action == "generate_livetest_video":
            return await self._generate_video(node, ctx)
        elif action == "generate_audio":
            return await self._generate_audio(node, ctx)
        elif action == "generate_cover":
            return await self._generate_cover(node, ctx)
        elif action == "publish_ghost":
            return await self._publish_ghost(node, ctx)
        elif action == "generate_youtube_payload":
            return await self._generate_youtube(node, ctx)
        else:
            return NodeResult(node.id, False, error=f"Unknown media action: {action}")

    async def _generate_video(self, node: PlanNode, ctx: AgentContext) -> NodeResult:
        from livetest_recorder import LiveLabRecorder, wireguard_lab_chapters, flatten_chapters
        title = ctx.scratch.get("title", ctx.goal)
        recorder = LiveLabRecorder()
        try:
            plan = await recorder.setup_two_node_network()
            logger.info(f"[video] 2-node topology ready")
        except Exception as exc:
            logger.warning(f"[video] 2-node setup failed: {exc}")
            await recorder.start_sandbox()
        chapters = wireguard_lab_chapters()
        res = await recorder.record_lab(
            flatten_chapters(chapters), title, chapter_data=chapters)
        await recorder.stop_sandbox()
        if res.steps_ok < res.steps_total:
            return NodeResult(node.id, False,
                              error=f"only {res.steps_ok}/{res.steps_total} steps")
        art = Artifact("mp4", res.video_path,
                       {"duration_s": res.duration_s, "size_mb": res.size_mb})
        ctx.artifacts["livetest_video"] = art
        ctx.scratch["video_src"] = art.path_or_url
        return NodeResult(node.id, True,
                          output=f"video {res.duration_s}s ({res.size_mb}MB)",
                          artifacts=[art])

    async def _generate_audio(self, node: PlanNode, ctx: AgentContext) -> NodeResult:
        content = ctx.scratch.get("content", "")
        if not content:
            return NodeResult(node.id, False, error="no content for audio")
        cfg = get_config()
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"{cfg.cinema.tts_url}/health")
                if r.status_code != 200:
                    return NodeResult(node.id, False,
                                      error="cinema engine unavailable (TTS down)")
        except Exception as exc:
            return NodeResult(node.id, False,
                              error=f"cinema engine unreachable: {exc}")
        try:
            from media.voice_studio import VoiceStudio
            summary = ctx.scratch.get("summary", content[:500])
            studio = VoiceStudio()
            result = await studio.generate_tts(summary, "article_summary.wav")
            audio_file = result.get("audio_file", "")
            if not audio_file:
                return NodeResult(node.id, False,
                                  error="TTS returned no audio file")
            art = Artifact("wav", audio_file,
                           {"duration": result.get("duration_seconds", 0)})
            ctx.artifacts["audio"] = art
            return NodeResult(node.id, True, output="audio generated", artifacts=[art])
        except Exception as exc:
            return NodeResult(node.id, False,
                              error=f"audio generation failed: {exc}")

    async def _generate_cover(self, node: PlanNode, ctx: AgentContext) -> NodeResult:
        import html as html_mod

        title = ctx.scratch.get("title", ctx.goal)
        cover_art = ctx.artifacts.get("article_md")
        if not cover_art:
            return NodeResult(node.id, False,
                              error="no article_md artifact for cover")
        cover_path = Path(cover_art.path_or_url)
        if cover_path.suffix != ".md":
            return NodeResult(node.id, False,
                              error=f"unsupported cover source: {cover_path}")
        png_path = cover_path.with_suffix(".png")
        try:
            from media.visual_generator import generate_hero_box
            hero = generate_hero_box(html_mod.escape(title))
            cover_html = (
                "<!DOCTYPE html><html><head><meta charset='utf-8'>"
                "<style>html,body{margin:0;height:100%;display:flex;"
                "align-items:center;justify-content:center;"
                "background:#0f172a;font-family:monospace}</style>"
                f"</head><body>{hero}</body></html>")
            html_file = cover_path.with_suffix(".cover.html")
            html_file.write_text(cover_html, encoding="utf-8")
            import subprocess
            proc = subprocess.run([
                "chromium-browser", "--headless", "--disable-gpu",
                "--screenshot=" + str(png_path),
                "--window-size=1200,630",
                "--virtual-time-budget=3000",
                "file://" + str(html_file),
            ], timeout=20, capture_output=True)
            if not png_path.exists() or png_path.stat().st_size == 0:
                return NodeResult(
                    node.id, False,
                    error=f"cover render failed (rc={proc.returncode}): "
                          f"{proc.stderr.decode(errors='replace')[-200:]}")
            art = Artifact("png", str(png_path))
            ctx.artifacts["cover"] = art
            return NodeResult(node.id, True, output="cover generated",
                              artifacts=[art])
        except Exception as exc:
            return NodeResult(node.id, False,
                              error=f"cover generation failed: {exc}")

    async def _publish_ghost(self, node: PlanNode, ctx: AgentContext) -> NodeResult:
        if not ctx.publish:
            return NodeResult(node.id, True, output="publish skipped (--no-publish)")
        content = ctx.scratch.get("content", "")
        title = ctx.scratch.get("title", ctx.goal)
        tags = ctx.scratch.get("tags", [])
        if not content:
            return NodeResult(node.id, False, error="no content to publish")
        try:
            from ghost_utils import GhostClient
            from config import get_config
            cfg = get_config()
            client = GhostClient(cfg.ghost.url, cfg.ghost.admin_key)
            post = client.create_post(title, content, tags=tags)
            url = post.get("url", "")
            art = Artifact("ghost_post", url, {"post_id": post.get("id", "")})
            ctx.artifacts["ghost_post"] = art
            return NodeResult(node.id, True, output=f"published: {url}", artifacts=[art])
        except Exception as exc:
            return NodeResult(node.id, False, error=f"Ghost publish failed: {exc}")

    async def _generate_youtube(self, node: PlanNode, ctx: AgentContext) -> NodeResult:
        vid = ctx.artifacts.get("livetest_video") or ctx.artifacts.get("video_mp4")
        if not vid:
            return NodeResult(node.id, True, output="no video for YouTube")
        try:
            from youtube_publisher import build_wireguard_payload
            from dataclasses import asdict
            from config import REPORTS_DIR
            import json
            import time as _time

            ghost_art = ctx.artifacts.get("ghost_post")
            article_url = ghost_art.path_or_url if ghost_art else "https://lab.hitech.tn"
            payload = build_wireguard_payload(vid.path_or_url, 70.0, article_url)
            payload_dict = asdict(payload) if hasattr(payload, '__dataclass_fields__') else payload
            payload_path = REPORTS_DIR / f"yt_{int(_time.time() * 1000)}.json"
            payload_path.parent.mkdir(parents=True, exist_ok=True)
            import json
            payload_path.write_text(json.dumps(payload_dict, indent=2, ensure_ascii=False))
            art = Artifact("youtube_payload", str(payload_path))
            ctx.artifacts["youtube_payload"] = art
            return NodeResult(node.id, True, output=f"payload: {payload_path}")
        except Exception as exc:
            return NodeResult(node.id, False, error=str(exc))
