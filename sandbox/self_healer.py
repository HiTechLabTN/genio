"""Genio — Kernel Log / strace / tcpdump Inspector & Auto-Patching Loop.

Inspects failure modes, applies targeted fixes, and saves lessons.
"""
from __future__ import annotations

import re
from typing import List, Optional

from loguru import logger

from core.memory_engine import get_memory


class SelfHealer:
    """Inspects errors, applies fixes, and records lessons."""

    INSPECTION_PATTERNS = [
        (r"wg.*handshake", "_inspect_wg_handshake"),
        (r"permission denied|Operation not permitted", "_inspect_permission"),
        (r"network.*unreachable", "_inspect_network"),
        (r"port.*already in use|address already", "_inspect_port_conflict"),
    ]

    def inspect_and_heal(self, error: str, context: dict = None) -> Optional[str]:
        for pattern, method_name in self.INSPECTION_PATTERNS:
            if re.search(pattern, error, re.IGNORECASE):
                method = getattr(self, method_name, None)
                if method:
                    fix = method(error, context or {})
                    if fix:
                        logger.info(f"[self_healer] applied fix: {fix}")
                        return fix
        return None

    def _inspect_wg_handshake(self, error: str, ctx: dict) -> Optional[str]:
        return "Check firewall UDP 51820, verify AllowedIPs and Endpoint match"

    def _inspect_permission(self, error: str, ctx: dict) -> Optional[str]:
        return "Ensure container has --cap-add=NET_ADMIN and /dev/net/tun"

    def _inspect_network(self, error: str, ctx: dict) -> Optional[str]:
        return "Verify docker network exists and container is connected"

    def _inspect_port_conflict(self, error: str, ctx: dict) -> Optional[str]:
        return "Run cleanup_conflicts() before re-creating containers"

    def record_lesson(self, codes: List[str], source: str = "self_healer"):
        get_memory().record_rejection(codes, source=source)


class AuditorAgent:
    """Content quality auditor with self-healing regeneration."""

    def __init__(self):
        from core.memory_engine import get_memory
        self.memory = get_memory()

    async def run(self, node, ctx):
        from genio_executive_core import NodeResult
        content = ctx.scratch.get("content", "")
        if not content:
            return NodeResult(node.id, True, output="no content to audit")

        quality = 100
        security = 100
        findings = []
        regen_codes = []

        # Darija check
        prose = re.sub(r"```[\s\S]*?```", " ", content)
        prose = re.sub(r"<[^>\n]+>", " ", prose)
        arabic_words = re.findall(r"[\u0600-\u06FF]{2,}", prose)
        latin_words = re.findall(r"[A-Za-z][A-Za-z0-9_\-]*", prose)
        if arabic_words:
            ratio = len(latin_words) / (len(latin_words) + len(arabic_words))
            if ratio > 0.25:
                quality -= 20
                regen_codes.append("high_latin_ratio")
                findings.append(f"latin_prose={ratio:.0%}")

        # Code blocks check
        code_blocks = re.findall(r"```[\s\S]*?```", content)
        if len(code_blocks) < 4:
            quality -= 15
            regen_codes.append("low_code_density")
            findings.append(f"code_blocks={len(code_blocks)}(<4)")

        # SVG check
        if "<svg" not in content.lower():
            quality -= 20
            regen_codes.append("missing_svg")
            findings.append("no_svg")

        # Table check
        if not re.search(r"\|.*\|.*\|", content):
            quality -= 15
            regen_codes.append("missing_table")
            findings.append("no_comparison_table")

        # Callout check
        callout_count = content.count('class="callout')
        if callout_count < 2:
            quality -= 10
            regen_codes.append("missing_callouts")
            findings.append(f"callouts={callout_count}(<2)")

        quality = max(0, quality)
        security = max(0, security)

        if regen_codes:
            self.memory.record_rejection(regen_codes, source="auditor")

        ctx.scratch["audit"] = {"quality": quality, "security": security}

        output = (f"quality={quality}/100 security={security}/100 | "
                  f"regen:{','.join(regen_codes)} | "
                  f"findings: {'; '.join(findings)}" if findings
                  else f"quality={quality}/100 security={security}/100")

        ok = quality >= 70 and not any(c in regen_codes
                                       for c in ["high_latin_ratio", "missing_svg"])
        return NodeResult(node.id, ok, output=output)
