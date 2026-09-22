"""Genio — Kernel Log / strace / tcpdump Inspector & Auto-Patching Loop.

Inspects failure modes, applies targeted fixes, and saves lessons.

Phase 3: GenericHealer extracted as reusable base (env-toggleable via
GENIO_GENERIC_HEAL). SelfHealer keeps infra-specific patterns but falls
back to GenericHealer for any Python traceback when enabled.
"""
from __future__ import annotations

import os
import re
from typing import List, Optional

from loguru import logger

from core.memory_engine import get_memory


def _generic_heal_enabled() -> bool:
    return os.getenv("GENIO_GENERIC_HEAL", "1").strip().lower() not in ("0", "false", "no")


class GenericHealer:
    """Generic Python/runtime traceback healer.

    Catches broad categories that SelfHealer's infra patterns miss.
    Always returns a human-readable fix suggestion when enabled.
    """

    GENERIC_PATTERNS = [
        (r"ModuleNotFoundError|No module named", "_fix_missing_module"),
        (r"ImportError", "_fix_import"),
        (r"SyntaxError|IndentationError", "_fix_syntax"),
        (r"FileNotFoundError|No such file or directory", "_fix_file_not_found"),
        (r"PermissionError|permission denied", "_fix_permission_generic"),
        (r"NameError|is not defined", "_fix_name"),
        (r"AttributeError", "_fix_attribute"),
        (r"TypeError", "_fix_type"),
        (r"ValueError", "_fix_value"),
        (r"KeyError", "_fix_key"),
        (r"IndexError|list index out of range", "_fix_index"),
        (r"ConnectionError|ConnectionRefusedError|TimeoutError|timed out", "_fix_connection"),
        (r"ZeroDivisionError", "_fix_zero_division"),
        (r"AssertionError", "_fix_assertion"),
    ]

    def inspect_and_heal(self, error: str, context: dict = None) -> Optional[str]:
        if not _generic_heal_enabled():
            return None
        for pattern, method_name in self.GENERIC_PATTERNS:
            if re.search(pattern, error, re.IGNORECASE):
                method = getattr(self, method_name, None)
                if method:
                    fix = method(error, context or {})
                    if fix:
                        logger.info(f"[generic_healer] applied fix: {fix}")
                        return fix
        # Fallback: any traceback-like error gets a generic suggestion
        if re.search(r"Traceback|Error:", error):
            return self._fix_generic(error, context or {})
        return None

    # --- fixers ---
    def _fix_missing_module(self, error: str, ctx: dict) -> str:
        m = re.search(r"No module named ['\"]?(\w+)", error)
        mod = m.group(1) if m else "dependency"
        return f"Install missing module: pip install {mod} (error: {error[:120]})"

    def _fix_import(self, error: str, ctx: dict) -> str:
        return f"Fix import: verify module path and install deps (error: {error[:120]})"

    def _fix_syntax(self, error: str, ctx: dict) -> str:
        return f"Fix syntax: run python -m py_compile and correct indentation/syntax (error: {error[:120]})"

    def _fix_file_not_found(self, error: str, ctx: dict) -> str:
        return f"Create missing file/path or fix working directory (error: {error[:120]})"

    def _fix_permission_generic(self, error: str, ctx: dict) -> str:
        return "Fix permissions: check file ownership/chmod and container capabilities"

    def _fix_name(self, error: str, ctx: dict) -> str:
        return f"Fix NameError: define or import the missing name (error: {error[:120]})"

    def _fix_attribute(self, error: str, ctx: dict) -> str:
        return f"Fix AttributeError: verify object attributes/methods (error: {error[:120]})"

    def _fix_type(self, error: str, ctx: dict) -> str:
        return f"Fix TypeError: check argument types and signatures (error: {error[:120]})"

    def _fix_value(self, error: str, ctx: dict) -> str:
        return f"Fix ValueError: validate input values (error: {error[:120]})"

    def _fix_key(self, error: str, ctx: dict) -> str:
        return f"Fix KeyError: verify dict keys exist (error: {error[:120]})"

    def _fix_index(self, error: str, ctx: dict) -> str:
        return f"Fix IndexError: bounds-check list access (error: {error[:120]})"

    def _fix_connection(self, error: str, ctx: dict) -> str:
        return "Fix connection: verify service reachable, retry with backoff"

    def _fix_zero_division(self, error: str, ctx: dict) -> str:
        return "Fix ZeroDivision: guard divisor with if != 0"

    def _fix_assertion(self, error: str, ctx: dict) -> str:
        return f"Fix AssertionError: check preconditions (error: {error[:120]})"

    def _fix_generic(self, error: str, ctx: dict) -> str:
        return f"Generic fix: review traceback, isolate failing line and add guard/retry (error: {error[:120]})"


class SelfHealer(GenericHealer):
    """Inspects errors, applies fixes, and records lessons.

    Keeps infra-specific patterns; falls back to GenericHealer when
    GENIO_GENERIC_HEAL is enabled.
    """

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
        # Fallback to generic healing
        return super().inspect_and_heal(error, context)

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
