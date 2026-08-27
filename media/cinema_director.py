"""Genio — Automated Video Assembly with Styled Titlecards & Audio Sync.

Orchestrates video recording, title card generation, audio sync,
and final H.264 1080p assembly.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loguru import logger

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
        from media.voice_studio import VoiceStudio
        content = ctx.scratch.get("content", "")
        if not content:
            return NodeResult(node.id, True, output="no content for audio")
        summary = ctx.scratch.get("summary", content[:500])
        studio = VoiceStudio()
        try:
            result = await studio.generate_tts(summary, "article_summary.wav")
            art = Artifact("wav", result.get("audio_file", ""),
                           {"duration": result.get("duration_seconds", 0)})
            ctx.artifacts["audio"] = art
            return NodeResult(node.id, True, output="audio generated", artifacts=[art])
        except Exception as exc:
            return NodeResult(node.id, False, error=str(exc))

    async def _generate_cover(self, node: PlanNode, ctx: AgentContext) -> NodeResult:
        title = ctx.scratch.get("title", ctx.goal)
        from media.visual_generator import generate_hero_box
        hero_html = generate_hero_box(title)
        cover_path = Path(ctx.artifacts.get("article_md", Artifact("", "")).path_or_url)
        if cover_path and cover_path.suffix == ".md":
            png_path = cover_path.with_suffix(".png")
            try:
                import subprocess
                subprocess.run([
                    "chromium-browser", "--headless", "--disable-gpu",
                    "--screenshot=" + str(png_path),
                    "--window-size=1200,630",
                    "--virtual-time-budget=3000",
                    f"data:text/html,<html><body style='background:#0f172a;display:flex;align-items:center;justify-content:center;height:100vh;font-family:monospace'><div style='color:#00ff88;font-size:32px;text-align:center;padding:40px'>{title}</div></body></html>",
                ], timeout=15, capture_output=True)
                if png_path.exists():
                    art = Artifact("png", str(png_path))
                    ctx.artifacts["cover"] = art
                    return NodeResult(node.id, True, output="cover generated")
            except Exception:
                pass
        return NodeResult(node.id, True, output="cover skipped")

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
            ghost_art = ctx.artifacts.get("ghost_post")
            article_url = ghost_art.path_or_url if ghost_art else "https://lab.hitech.tn"
            payload = build_wireguard_payload(vid.path_or_url, 70.0, article_url)
            payload_path = Path("/data/ai_tools/genio/reports") / f"yt_{id(payload)}.json"
            payload_path.parent.mkdir(parents=True, exist_ok=True)
            import json
            payload_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
            art = Artifact("youtube_payload", str(payload_path))
            ctx.artifacts["youtube_payload"] = art
            return NodeResult(node.id, True, output=f"payload: {payload_path}")
        except Exception as exc:
            return NodeResult(node.id, False, error=str(exc))
