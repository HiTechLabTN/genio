"""
Genio — Autonomous Executive Meta-Agent Core (HiTech Lab)

An autonomous Executive AI Director. Accepts a high-level intent (Darija /
Arabic / English), decomposes it into an execution DAG, dispatches specialized
sub-agents (Sandbox, Content, Media, Auditor), self-heals on failure, and
produces an Executive Audit Report.

Usage:
    python3 genio_executive_core.py --prompt "Create an end-to-end hands-on
    lab on WireGuard VPN setup in Tunisian Darija with full assets"
"""

from __future__ import annotations

import argparse
import asyncio
import html as html_mod
import json
import os
import re
import resource
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

# --------------------------------------------------------------------------- #
# Path bootstrap: expose shared HiTech Lab modules                            #
# --------------------------------------------------------------------------- #
from config import GENIO_DIR  # noqa: E402
import core.memory_engine as core_memory_engine  # noqa: E402  (canonical memory)

_LEGACY_ROOT = Path("/data/ai_tools")
ROOT = _LEGACY_ROOT if _LEGACY_ROOT.exists() else Path(__file__).resolve().parent
BACKEND = ROOT / "webapp" / "backend"
for _p in (str(ROOT), str(BACKEND)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from loguru import logger as _loguru

    _loguru.remove()
    _loguru.add(sys.stderr, level="INFO",
                format="<green>{time:HH:mm:ss}</green> | <level>{level: <7}</level> | <level>{message}</level>")
    logger = _loguru
except ImportError:  # pragma: no cover
    import logging

    logger = logging.getLogger("genio")

try:
    from llm_utils import LLMRouter  # noqa: E402  (shared LLM router)
    import media_steps  # noqa: E402  (audio/video/cover/publish + gold gate)
    from ghost_utils import get_ghost_client  # noqa: E402
except ImportError:  # pragma: no cover — optional sibling modules in standalone deploys
    LLMRouter = None  # type: ignore[assignment]
    media_steps = None  # type: ignore[assignment]
    get_ghost_client = None  # type: ignore[assignment]


# =========================================================================== #
# Data models                                                                 #
# =========================================================================== #

@dataclass
class PlanNode:
    """A single executable unit inside the execution DAG."""
    id: str
    agent: str                      # sandbox | content | media | auditor
    action: str                     # agent-specific verb
    params: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)
    timeout_s: int = 600
    max_retries: int = 3
    on_error: str = "halt"          # halt | continue
    phase: str = "main"


@dataclass
class ExecutionPlan:
    goal: str
    nodes: List[PlanNode]
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    planner: str = "fallback"       # llm | fallback
    raw_intent: str = ""

    def topological(self) -> List[PlanNode]:
        """Kahn-ordered nodes; raises ValueError on cycles."""
        by_id = {n.id: n for n in self.nodes}
        indeg = {n.id: 0 for n in self.nodes}
        for n in self.nodes:
            for d in n.depends_on:
                if d in by_id:
                    indeg[n.id] += 1
        ready = [n.id for n in self.nodes if indeg[n.id] == 0]
        order: List[PlanNode] = []
        while ready:
            nid = ready.pop()
            order.append(by_id[nid])
            for n in self.nodes:
                if nid in n.depends_on:
                    indeg[n.id] -= 1
                    if indeg[n.id] == 0:
                        ready.append(n.id)
        if len(order) != len(self.nodes):
            raise ValueError("Cycle detected in plan dependencies")
        return order

    def to_json(self) -> str:
        return json.dumps({
            "goal": self.goal, "planner": self.planner,
            "created_at": self.created_at,
            "nodes": [asdict(n) for n in self.nodes],
        }, indent=2, ensure_ascii=False)


@dataclass
class Artifact:
    kind: str                       # wav | mp4 | png | md | html | ghost_post
    path_or_url: str
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NodeResult:
    node_id: str
    ok: bool
    output: str = ""
    artifacts: List[Artifact] = field(default_factory=list)
    duration_s: float = 0.0
    attempts: int = 1
    recovery_log: List[str] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class AgentContext:
    """Shared mutable state passed to every agent."""
    goal: str
    dry_run: bool = False
    publish: bool = True
    artifacts: Dict[str, Artifact] = field(default_factory=dict)
    scratch: Dict[str, Any] = field(default_factory=dict)   # cross-node data
    results: Dict[str, NodeResult] = field(default_factory=dict)


# =========================================================================== #
# Self-learning memory (feedback loop)                                        #
# =========================================================================== #

RIGMA_FEWSHOT = """Exemple de ton et d'esprit d'ingénieur à reproduire exactement:
"اليوم في HiTech Lab باش نخدمو على معضلة أمنية حقيقية ونركبو Tunnel WireGuard من الصفر. المشكل في أغلب الشروحات التقليدية إنها تعطيك سطور أوامر جافة وتهرب. نحنا هنا باش نفككو الـ Kernel Module، ونفهمو الـ Cryptography والـ Routing كيفاش يمشيو تحت الغطاء (Under the Hood)، خطوة بخطوة وبدون أي ثغرة."
"""


# Canonical implementation lives in `core.memory_engine` (single source of
# truth with file locking); re-exported here for backward compatibility so
# the legacy pipeline and tests use ONE shared class + store.
MemoryEngine = core_memory_engine.MemoryEngine  # noqa: N816


def get_memory() -> MemoryEngine:
    return core_memory_engine.get_memory()


# =========================================================================== #
# Planning engine                                                             #
# =========================================================================== #

class PlanningEngine:
    """LLM-driven decomposition with deterministic fallback."""

    SYSTEM = (
        "You are Genio, an executive planning engine for an AI content lab. "
        "Decompose the user's intent into an execution DAG as STRICT JSON only "
        "(no markdown fences, no commentary). Schema:\n"
        '{"goal": str, "nodes": [{"id": str, "agent": str, "action": str, '
        '"params": object, "depends_on": [str], "timeout_s": int, "phase": str}]}\n'
        "You MUST only use these exact agent/action combinations:\n"
        '- {"agent":"sandbox","action":"check_environment"}\n'
        '- {"agent":"sandbox","action":"ensure_dependencies","params":{"python_pkgs":[],"binaries":[]}}\n'
        '- {"agent":"content","action":"generate_darija_lab","params":{"topic":str}}\n'
        '- {"agent":"media","action":"generate_audio"}\n'
        '- {"agent":"media","action":"generate_video"}\n'
        '- {"agent":"media","action":"generate_cover"}\n'
        '- {"agent":"media","action":"publish_ghost"}\n'
        '- {"agent":"auditor","action":"full_audit"}\n'
        "Rules: start with check_environment; content before media; audit runs "
        "after media and BEFORE publish_ghost (publish depends on audit); "
        "keep <= 10 nodes."
    )

    # Closed action catalogs per agent (used to normalize LLM output)
    VALID_ACTIONS: Dict[str, Dict[str, str]] = {
        "sandbox": {"check_environment", "ensure_dependencies", "shell"},
        "content": {"generate_darija_lab"},
        "media": {"generate_audio", "generate_video", "generate_cover",
                  "publish_ghost"},
        "auditor": {"full_audit"},
    }

    @classmethod
    def normalize_action(cls, agent: str, action: str) -> str:
        """Map any invented LLM verb onto the closest real capability."""
        if action in cls.VALID_ACTIONS.get(agent, set()):
            return action
        low = (action or "").lower()
        if agent == "media":
            if re.search(r"audio|voice|tts|narrat|sound", low):
                return "generate_audio"
            if re.search(r"video|render|short|cinema|clip", low):
                return "generate_video"
            if re.search(r"cover|thumb|image|visual|banner", low):
                return "generate_cover"
            if re.search(r"publish|ghost|post|upload|deploy", low):
                return "publish_ghost"
            return "generate_cover"
        if agent == "content":
            return "generate_darija_lab"
        if agent == "auditor":
            return "full_audit"
        # sandbox
        if re.search(r"depend|package|install|pip", low):
            return "ensure_dependencies"
        if re.search(r"shell|run|exec|command", low):
            return "shell"
        return "check_environment"

    def __init__(self, router: Optional[LLMRouter] = None):
        self.router = router or LLMRouter()

    # ------------------------------------------------------------------ #
    async def build_plan(self, intent: str, use_llm: bool = True) -> ExecutionPlan:
        if use_llm:
            try:
                raw = await asyncio.to_thread(
                    self.router.route_request,
                    "complex_analysis", f"INTENT:\n{intent}", self.SYSTEM,
                    temperature=0.2,
                )
                plan = self._parse_plan(raw, intent)
                if plan:
                    plan.planner = "llm"
                    return plan
                logger.warning("LLM plan unusable -> deterministic fallback")
            except Exception as exc:  # network down, bad JSON...
                logger.warning(f"Planner LLM failed ({exc}) -> fallback")
        return self.fallback_plan(intent)

    # ------------------------------------------------------------------ #
    @staticmethod
    def extract_json(text: str) -> Optional[Dict]:
        """Robustly pull the first JSON object out of noisy LLM output."""
        if not text:
            return None
        text = re.sub(r"```(?:json)?", "", text).strip("` \n")
        start = text.find("{")
        while start != -1:
            depth, in_str, esc = 0, False, False
            for i in range(start, len(text)):
                c = text[i]
                if in_str:
                    if esc:
                        esc = False
                    elif c == "\\":
                        esc = True
                    elif c == '"':
                        in_str = False
                else:
                    if c == '"':
                        in_str = True
                    elif c == "{":
                        depth += 1
                    elif c == "}":
                        depth -= 1
                        if depth == 0:
                            blob = text[start:i + 1]
                            try:
                                return json.loads(blob)
                            except json.JSONDecodeError:
                                break
            start = text.find("{", start + 1)
        return None

    VALID_AGENTS = {"sandbox", "content", "media", "auditor"}

    def _parse_plan(self, raw: str, intent: str) -> Optional[ExecutionPlan]:
        data = self.extract_json(raw or "")
        if not data or not isinstance(data.get("nodes"), list) or not data["nodes"]:
            return None
        nodes: List[PlanNode] = []
        seen: set = set()
        for nd in data["nodes"][:12]:
            if not all(k in nd for k in ("id", "agent", "action")):
                continue
            if nd["agent"] not in self.VALID_AGENTS or nd["id"] in seen:
                continue
            seen.add(nd["id"])
            deps = list(nd.get("depends_on") or [])
            nodes.append(PlanNode(
                id=str(nd["id"]), agent=nd["agent"],
                action=self.normalize_action(nd["agent"], str(nd["action"])),
                params=dict(nd.get("params") or {}),
                depends_on=[str(d) for d in deps],
                timeout_s=int(nd.get("timeout_s") or 900),
                phase=str(nd.get("phase") or "main"),
            ))
        if not any(n.agent == "auditor" for n in nodes):
            nodes.append(PlanNode(
                id="final_audit", agent="auditor", action="full_audit",
                depends_on=[n.id for n in nodes], phase="audit"))
        # Quality gate MUST precede publishing (structural invariant)
        audit_id = next((n.id for n in nodes if n.agent == "auditor"), None)
        for n in nodes:
            if n.agent == "media" and n.action == "publish_ghost":
                if audit_id and audit_id not in n.depends_on:
                    n.depends_on.append(audit_id)
        return ExecutionPlan(goal=str(data.get("goal") or intent), nodes=nodes,
                             raw_intent=intent)

    @staticmethod
    def fallback_plan(intent: str) -> ExecutionPlan:
        """Canonical pipeline used when the LLM planner is unavailable."""
        nodes = [
            PlanNode(id="preflight_env", agent="sandbox", action="check_environment",
                     timeout_s=120, phase="preflight"),
            PlanNode(id="ensure_deps", agent="sandbox", action="ensure_dependencies",
                     params={"python_pkgs": ["httpx", "bs4", "loguru"],
                             "binaries": ["ffmpeg", "ffprobe"]},
                     depends_on=["preflight_env"], timeout_s=300, phase="preflight"),
            PlanNode(id="write_tutorial", agent="content", action="generate_darija_lab",
                     params={"topic": intent}, depends_on=["ensure_deps"],
                     timeout_s=1800, phase="content"),
            PlanNode(id="gen_audio", agent="media", action="generate_audio",
                     depends_on=["write_tutorial"], timeout_s=900, phase="media"),
            PlanNode(id="gen_video", agent="media", action="generate_video",
                     depends_on=["gen_audio"], timeout_s=1200, phase="media"),
            PlanNode(id="livetest_recording", agent="media",
                     action="generate_livetest_video",
                     depends_on=["write_tutorial"], timeout_s=1500,
                     phase="media"),
            PlanNode(id="youtube_prep", agent="media", action="prepare_youtube",
                     depends_on=["final_audit"], timeout_s=900,
                     phase="publish"),
            PlanNode(id="gen_cover", agent="media", action="generate_cover",
                     depends_on=["write_tutorial"], timeout_s=180, phase="media"),
            PlanNode(id="final_audit", agent="auditor", action="full_audit",
                     depends_on=["gen_video", "gen_audio", "gen_cover"],
                     timeout_s=120, phase="audit"),
            PlanNode(id="publish_ghost", agent="media", action="publish_ghost",
                     depends_on=["final_audit"], timeout_s=300, phase="publish"),
        ]
        return ExecutionPlan(goal=intent, nodes=nodes, planner="fallback",
                             raw_intent=intent)


# =========================================================================== #
# Sub-agents                                                                  #
# =========================================================================== #

class BaseAgent:
    """Contract for every Genio sub-agent."""
    name = "base"

    async def run(self, node: PlanNode, ctx: AgentContext) -> NodeResult:
        raise NotImplementedError


class CodeSandboxAgent(BaseAgent):
    """Executes whitelisted shell work and verifies environment status."""
    name = "sandbox"

    BLOCKLIST = (
        r"rm\s+-rf\s+/(?:\s|$)", r"mkfs", r"dd\s+if=", r">\s*/dev/sd[a-z]",
        r":\(\)\s*\{.*\};\s*:", r"\b(shutdown|reboot|init\s+0|init\s+6)\b",
        r"chmod\s+-R\s+777\s+/", r"\bhistory\s+-c\b", r"\bcurl\b.*\|\s*(ba)?sh",
    )

    SERVICE_PROBES: Dict[str, Tuple[str, Callable[[int], bool]]] = {}

    async def run(self, node: PlanNode, ctx: AgentContext) -> NodeResult:
        handler: Callable[..., Awaitable[NodeResult]] = {
            "check_environment": self._check_environment,
            "ensure_dependencies": self._ensure_dependencies,
            "shell": self._shell,
        }.get(node.action)  # type: ignore[assignment]
        if handler is None:
            return NodeResult(node.id, False, error=f"Unknown sandbox action: {node.action}")
        return await handler(node, ctx)

    # ------------------------------------------------------------------ #
    async def _http_ok(self, url: str, timeout: float = 6.0) -> bool:
        import httpx

        try:
            async with httpx.AsyncClient(timeout=timeout) as cli:
                r = await cli.get(url)
                return r.status_code == 200
        except Exception:
            return False

    async def _check_environment(self, node: PlanNode, ctx: AgentContext) -> NodeResult:
        checks: Dict[str, bool] = {}
        checks["ollama"] = await self._http_ok(
            os.getenv("OLLAMA_BASE_URL", "http://localhost:11434") + "/api/tags")
        checks["cinema_engine"] = await self._http_ok("http://localhost:9876/health")
        checks["ghost_cms"] = (await self._http_ok(
            f"{os.getenv('GHOST_URL', 'https://lab.hitech.tn')}/ghost/api/v3/content/posts/"
            f"?key={os.getenv('GHOST_CONTENT_KEY', '')}&limit=1", timeout=10))
        ff = await asyncio.create_subprocess_exec(
            "ffmpeg", "-version", stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL)
        await ff.wait()
        checks["ffmpeg"] = ff.returncode == 0

        ctx.scratch["env_checks"] = checks
        critical_ok = checks["ollama"] and checks["cinema_engine"]
        detail = ", ".join(f"{k}={'OK' if v else 'DOWN'}" for k, v in checks.items())
        return NodeResult(node.id, critical_ok, output=detail,
                          error=None if critical_ok else "Critical service(s) down")

    async def _ensure_dependencies(self, node: PlanNode, ctx: AgentContext) -> NodeResult:
        installed: List[str] = []
        for pkg in node.params.get("python_pkgs", []):
            probe = await asyncio.create_subprocess_exec(
                sys.executable, "-c", f"import {pkg}",
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
            await probe.wait()
            if probe.returncode != 0:
                if ctx.dry_run:
                    installed.append(f"{pkg}:MISSING(dry-run)")
                    continue
                logger.info(f"[sandbox] installing missing python pkg: {pkg}")
                pip = await asyncio.create_subprocess_exec(
                    sys.executable, "-m", "pip", "install", "--user", pkg,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
                out, _ = await pip.communicate()
                installed.append(f"{pkg}:{'OK' if pip.returncode == 0 else 'FAIL'}")
            else:
                installed.append(f"{pkg}:present")

        for binary in node.params.get("binaries", []):
            which = await asyncio.create_subprocess_exec(
                "which", binary, stdout=asyncio.subprocess.PIPE)
            out, _ = await which.communicate()
            installed.append(f"{binary}:{'present' if which.returncode == 0 else 'MISSING'}")

        return NodeResult(node.id, True, output=", ".join(installed))

    async def _shell(self, node: PlanNode, ctx: AgentContext) -> NodeResult:
        cmd = str(node.params.get("command", "")).strip()
        if not cmd:
            return NodeResult(node.id, False, error="Empty command")
        for pattern in self.BLOCKLIST:
            if re.search(pattern, cmd):
                return NodeResult(node.id, False,
                                  error=f"Blocked unsafe command (matched {pattern})")
        proc = await asyncio.create_subprocess_shell(
            cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        try:
            out, _ = await asyncio.wait_for(proc.communicate(), timeout=node.timeout_s)
        except asyncio.TimeoutError:
            proc.kill()
            return NodeResult(node.id, False, error="Command timed out")
        return NodeResult(node.id, proc.returncode == 0,
                          output=out.decode(errors="replace")[-2000:])


class ContentArchitectAgent(BaseAgent):
    """Multi-pass Darija lab architect.

    Pass 1: Hero Box (dir=rtl) + architecture plan
    Pass 2: animated SVG topology diagram (validated, template fallback)
    Pass 3: exhaustive implementation & configs (no summarization)
    Pass 4: real troubleshooting with diagnostic commands
    """

    name = "content"

    BANNED_LITERAL = (
        "نحن نقوم", "سنقوم ب", "نقوم بتثبيت", "يجب أن يتم",
        "تم إنجاز", "il faut procéder", "nous allons procéder",
    )

    def __init__(self, generate_fn: Optional[Callable[..., Awaitable[str]]] = None,
                 memory: Optional[MemoryEngine] = None):
        from darija_rewriter import call_ollama, validate_darija, DARIJA_POLICY

        self._call_ollama = call_ollama
        self.validate_darija = validate_darija
        self.DARIJA_POLICY = DARIJA_POLICY
        self._generate_fn = generate_fn
        self.memory = memory or get_memory()

    # ------------------------------------------------------------------ #
    # Prompts                                                             #
    # ------------------------------------------------------------------ #
    def _pass1_prompt(self, topic: str) -> str:
        return f"""{self.DARIJA_POLICY}

PASS 1 of 4 — ARCHITECTURE & HERO BOX for a hands-on tech lab.

Output format (STRICT):
TITLE: <catchy Tunisian Darija title, max 10 words>
<div dir="rtl" class="hero-box" style="background:linear-gradient(135deg,#0f172a,#1e293b);border:2px solid #00ff87;border-radius:16px;padding:24px;color:#e5e7eb;">
🎯 في هالمقال باش نخدمو: <one-line pitch in Darija>
<br>📦 <what will be built> · ⏱️ <duration> · 🧰 <tools list in English>
</div>

## 🗺️ خطة الخدمة
(numbered plan of the 5-6 main phases, each with one short Darija sentence)

## 🧰 المتطلبات
(bullet list of prerequisites)

Rules: ALL prose MUST be White Tunisian Tech Darija. ZERO full English
sentences anywhere outside code blocks - only isolated technical terms stay
English. If you catch yourself writing an English sentence, rewrite it in Darija.
The div block must be valid HTML on multiple lines and closed with </div>.

TONE REFERENCE - reproduce this exact senior-engineer spirit:
{RIGMA_FEWSHOT}

Topic: {topic}"""

    # ---- Canonical addressing plan (IT-Connect Professional Lab) ------- #
    ADDRESSING = {
        "lan_client": "192.168.1.0/24",
        "tunnel": "10.8.0.0/24",
        "lan_distant": "192.168.100.0/24",
        "server_wg_ip": "10.8.0.1/24",
        "client_wg_ip": "10.8.0.2/24",
        "server_lan_ip": "192.168.100.10",
        "port": "51820/UDP",
    }

    def _addressing_block(self) -> str:
        a = self.ADDRESSING
        return (f"Plan d'adressage OBLIGATOIRE du lab: "
                f"LAN client = {a['lan_client']} · Tunnel VPN = {a['tunnel']} · "
                f"LAN distant entreprise = {a['lan_distant']} · "
                f"Serveur wg0 = {a['server_wg_ip']} · Client wg0 = "
                f"{a['client_wg_ip']} · IP LAN serveur = {a['server_lan_ip']} · "
                f"Port = {a['port']}")

    def _pass_intro_prompt(self, topic: str) -> str:
        return f"""{self.DARIJA_POLICY}

PASS INTRO — WHY THIS TECHNOLOGY (pedagogical hook).

Write the opening section "## 🎯 علاش هذه التقنية؟ (Why This Technology)":
1. The real problem it solves (2-3 Darija sentences)
2. Concrete comparison paragraph mentioning lighter/faster alternatives and
   modern crypto (ex: ChaCha20-Poly1305 vs older ciphers, code size, handshake speed)
3. What the reader will have WORKING at the end of this lab

{self._addressing_block()}
All prose in White Tunisian Tech Darija, senior engineer tone.

Topic: {topic}"""

    def _pass_topology_prompt(self, topic: str) -> str:
        return f"""{self.DARIJA_POLICY}

PASS TOPOLOGY — THE MASTER BLUEPRINT (Le Schéma Directeur).

Write section "## 🗺️ المخطط المدير والخطة العنوانية (Master Blueprint)" :
1. Explain in Darija what we are building END-TO-END: a real two-node scenario
2. A markdown table of the addressing plan with columns:
   | الشبكة | Sous-réseau | دورها |
   covering: LAN client, Tunnel VPN, LAN distant entreprise
3. Explain WHY each IP range is chosen and which interface carries it
   (wg0 for tunnel, eth0 for LAN/WAN) and the listening port
4. List the two peers: Peer 1 (Serveur) and Peer 2 (Client distant) with their roles

{self._addressing_block()}
No commands here - pure architecture explanation in Darija.

Topic: {topic}"""

    def _pass_server_prompt(self, topic: str) -> str:
        return f"""{self.DARIJA_POLICY}

PASS SERVER — COMPLETE SERVER SIDE (Peer 1).

Section "## 🖥️ الجانب السيرفر (Peer 1 - Serveur)" with EXACTLY these sub-steps,
each explained (pourquoi AVANT la commande):
1. Kernel forwarding: add net.ipv4.ip_forward=1 to /etc/sysctl.conf + sysctl -p
   -> explain why without it packets never leave the tunnel
2. Firewall: UFW allow {self.ADDRESSING['port']} + NAT Masquerade rule
   (iptables -t nat -A POSTROUTING) -> explain why MASQUERADE is vital and how
   a wrong rule can lock you out of SSH
3. Key generation server side
4. FULL /etc/wireguard/wg0.conf in one complete ```ini block containing:
   Address = {self.ADDRESSING['server_wg_ip']}, ListenPort = {self.ADDRESSING['port']},
   SaveConfig = true (explain pourquoi), PostUp iptables rule,
   then the [Peer] block for the CLIENT with its PublicKey placeholder named
   CLIENT_PUBLIC_KEY, AllowedIPs = {self.ADDRESSING['client_wg_ip']}/32
5. wg-quick up wg0 + first wg show

Every config file shown COMPLETELY, no placeholders like "...". Minimum 5 code blocks.

Topic: {topic}"""

    def _pass_client_prompt(self, topic: str) -> str:
        return f"""{self.DARIJA_POLICY}

PASS CLIENT — REMOTE PEER CONFIGURATION (Peer 2).

Section "## 💻 الجانب الكليان البعيد (Peer 2 - Client)" covering BOTH:
1. Linux client path: key generation, full client wg0.conf ```ini block with
   [Interface] Address = {self.ADDRESSING['client_wg_ip']},
   PrivateKey = CLIENT_PRIVATE_KEY, and [Peer] pointing to server PUBLIC key,
   Endpoint = <SERVER_PUBLIC_IP>:{self.ADDRESSING['port'].split('/')[0]},
   AllowedIPs = {self.ADDRESSING['tunnel']}, {self.ADDRESSING['lan_distant']}
   -> explain precisely WHY AllowedIPs drives routing through the tunnel
2. Windows/Mobile variant: mention official clients + importing a tunnel file
   (QR code qrencode -t ansiutf8 < client.conf)
3. The key EXCHANGE ceremony: server needs client's public key, client needs
   server's public key - show the exact commands/files on each side
4. PersistentStorage / keepalive: explain PersistentKeepalive = 25 usefulness
   behind NAT

Minimum 4 code blocks, everything complete.

Topic: {topic}"""

    def _pass_validation_prompt(self, topic: str) -> str:
        return f"""{self.DARIJA_POLICY}

PASS VALIDATION — PROVE IT WORKS.

Section "## ✅ التحقق النهائي (Validation & Tests)" :
1. `wg show` on BOTH sides - show realistic output blocks (handshake received,
   transfer counters growing) in fenced blocks
2. Bidirectional ping THROUGH the tunnel: client pings {self.ADDRESSING['server_wg_ip'].split('/')[0]}
   AND server pings {self.ADDRESSING['client_wg_ip'].split('/')[0]} - both outputs shown
3. Real file transfer through the tunnel: python3 -m http.server bound to the
   server wg IP + curl/wget fetch from the client, showing real bytes transferred
4. Ping the remote LAN behind the server ({self.ADDRESSING['lan_distant']})
   proving routing + NAT work end-to-end

Minimum 4 fenced code blocks with REALISTIC outputs (not "...").

Topic: {topic}"""

    def _pass_troubleshooting_prompt(self, topic: str) -> str:
        return f"""{self.DARIJA_POLICY}

PASS TROUBLESHOOTING — REAL FAILURE MODES.

Section "## 🔥 Dépannage (استكشاف الأخطاء)" with AT LEAST 3 cases:
1. Handshake never establishes: firewall blocking UDP, port not forwarded on
   box/router -> diagnose with tcpdump -i any udp port {self.ADDRESSING['port'].split('/')[0]}
   and fix commands
2. Keys swapped between peers (public/private inverted): exact symptom in
   wg show + fix
3. Remote LAN unreachable though handshake OK: missing ip_forward or wrong
   AllowedIPs or missing MASQUERADE -> ip route check + fixes
Each case: verbatim error/symptom, diagnostic command block, fix command block.
All explanations in Darija.

Topic: {topic}"""

    def _pass_table_prompt(self, topic: str) -> str:
        return f"""{self.DARIJA_POLICY}

PASS 5 of 5 — TECHNICAL COMPARISON TABLE (MANDATORY).

Write section "## ⚖️ المقارنة التقنية (Comparison)" containing EXACTLY ONE
markdown pipe table comparing two relevant approaches for this topic
(ex: OpenVPN vs WireGuard, or Standard setup vs HiTech Lab hardening).
- 4 to 6 rows of real technical criteria (الأداء، الأمان، السهولة، الـ Handshake...)
- Header row + separator row + values; keep cell text short
- Technical terms stay in English inside cells
- One short Darija sentence under the table with your engineer verdict

Topic: {topic}"""

    DEFAULT_CALLOUT_1 = ('<div dir="rtl" class="callout warn" '
                         'style="border-right:6px solid #f59e0b;'
                         'background:#1a2332;padding:16px;border-radius:10px;'
                         'color:#fbbf24;">⚠️ نقطة أمنية حساسة : الـ Private '
                         'Key متاعك ما تخرجش من السيرفر أبدا — اللي يفقد الـ '
                         'key يفقد الشبكة الكل.</div>')

    DEFAULT_CALLOUT_2 = ('<div dir="rtl" class="callout warn" '
                         'style="border-right:6px solid #ef4444;'
                         'background:#1a2332;padding:16px;border-radius:10px;'
                         'color:#fca5a5;">⚠️ نقطة أمنية حساسة : نفعلو الـ IP '
                         'Forwarding والـ Firewall قبل ما نفتحو أي Port للعموم، '
                         'وإلا راك كتعرضو السيرفر مباشرة.</div>')

    @classmethod
    def _ensure_callouts(cls, sections: Dict[str, Any]) -> int:
        """Guarantee >= 2 security callouts regardless of LLM compliance."""
        total = sum((sections.get(k, "") or "").count('class="callout')
                    for k in ("plan", "implementation", "troubleshooting",
                              "table"))
        added = 0
        impl = sections.get("implementation", "")
        trbl = sections.get("troubleshooting", "")
        if total == 0 and impl:
            # place callout 1 right before the FIRST fenced code block
            m = re.search(r"^```", impl, re.MULTILINE)
            pos = m.start() if m else len(impl)
            sections["implementation"] = \
                impl[:pos] + cls.DEFAULT_CALLOUT_1 + "\n\n" + impl[pos:]
            added += 1
            total += 1
        if total < 2 and trbl:
            sections["troubleshooting"] = \
                cls.DEFAULT_CALLOUT_2 + "\n\n" + trbl
            added += 1
            total += 1
        if total < 2 and impl:
            sections["implementation"] = \
                str(sections.get("implementation", "")) + "\n\n" + \
                cls.DEFAULT_CALLOUT_2
            added += 1
        return added

    def _pass2_prompt(self, topic: str) -> str:
        return f"""{self.DARIJA_POLICY}

PASS 2 of 4 — ANIMATED SVG TOPOLOGY DIAGRAM.

Produce ONE self-contained inline SVG (starts with <svg ...> ends with </svg>)
depicting the architecture/topology relevant to this lab. For network labs show:
Clients → encrypted Tunnel → Server → Internet, with labeled arrows.
Requirements:
- viewBox="0 0 900 420", width="100%", dark background (#0f172a), neon strokes (#00ff87, #00f2fe)
- Darija labels inside <text> elements (font-size >= 18)
- At least 2 SMIL animations: <animate> or <animateTransform> (packet moving along path, pulsing lock icon)
- NO external resources, NO scripts, valid XML only
- Output ONLY the SVG, nothing else

Topic: {topic}"""

    def _pass3_prompt(self, topic: str) -> str:
        return f"""{self.DARIJA_POLICY}

PASS 3 of 4 — COMPLETE IMPLEMENTATION & CONFIGURATION.

Write the full hands-on implementation:
- EVERY file shown completely in its own ```bash or ```ini fenced block
- wg0.conf / service configs / sysctl.conf lines / iptables rules: NEVER summarize,
  NEVER use "..." placeholders — write every single line
- Each command preceded by one short Darija sentence explaining علاش نخدموها
- Minimum 5 distinct fenced code blocks
- Section headings in format ## <emoji> <Darija heading> (<English term>)
- CRITICAL: every explanation sentence must be Darija. English appears ONLY
inside code blocks and as isolated technical terms.
- MANDATORY: include AT LEAST 2 styled security callout boxes:
<div dir="rtl" class="callout warn" style="border-right:6px solid #f59e0b;background:#1a2332;padding:16px;border-radius:10px;color:#fbbf24;">⚠️ نقطة أمنية حساسة : <real warning in Darija></div>
Speak as a senior engineer: نركبو الـ Package ونفعلو الـ Service ديريكت —
NEVER passive literal phrasing like نحن نقوم بتثبيت.

Topic: {topic}"""

    def _pass4_prompt(self, topic: str) -> str:
        return f"""{self.DARIJA_POLICY}

PASS 4 of 4 — REAL TROUBLESHOOTING.

Write section "## 🔥 Troubleshooting (استكشاف الأخطاء)" containing AT LEAST 2 real error cases:
For each case this exact structure:
### ❌ <real error message verbatim between backticks>
Symptom in Darija + علاش يصير
Diagnostic commands in a fenced block (wg show, sudo tcpdump -i any udp port 51820,
ip route, journalctl -u wg-quick@wg0 ...)
Fix commands in another fenced block
Minimum 4 fenced code blocks total in this section. All explanations in Darija.

Topic: {topic}"""

    # ------------------------------------------------------------------ #
    async def _gen(self, prompt: str) -> str:
        prompt = self.memory.inject_into(prompt)
        if self._generate_fn is not None:
            try:
                return await self._generate_fn(prompt=prompt)
            except Exception as exc:
                logger.warning(f"[LLM] primary model failed: {exc}, "
                               "trying backup model")
        # Failover chain: primary → backup1 → backup2
        backup_models = ["qwen2.5:7b", "qwen2.5-coder:14b"]
        for model in backup_models:
            try:
                result = await self._call_ollama(prompt, model=model,
                                                  temperature=0.6)
                if result:
                    logger.info(f"[LLM] backup model '{model}' succeeded")
                    return result
            except Exception as exc:
                logger.warning(f"[LLM] backup '{model}' failed: {exc}")
        # Final attempt with default model
        return await self._call_ollama(prompt, temperature=0.6) or ""

    def _policy_clean(self, text: str) -> str:
        check = self.validate_darija(text)
        return check["cleaned_text"]

    # ------------------------------------------------------------------ #
    @staticmethod
    def extract_svg(text: str) -> Optional[str]:
        m = re.search(r"<svg[\s\S]*?</svg>", text or "", re.IGNORECASE)
        if not m:
            return None
        svg = m.group(0)
        try:
            import xml.etree.ElementTree as ET

            ET.fromstring(svg)
        except Exception:
            return None
        return svg

    @staticmethod
    def default_topology_svg(topic_hint: str = "") -> str:
        """Deterministic animated fallback diagram (Clients→Tunnel→Server→Internet)."""
        return (
            '<svg viewBox="0 0 900 420" width="100%" xmlns="http://www.w3.org/2000/svg">'
            '<defs>'
            '<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">'
            '<stop offset="0%" stop-color="#0f172a"/><stop offset="100%" stop-color="#1e293b"/>'
            '</linearGradient>'
            '<linearGradient id="tun" x1="0" y1="0" x2="1" y2="0">'
            '<stop offset="0%" stop-color="#00ff87"/><stop offset="100%" stop-color="#00f2fe"/>'
            '</linearGradient>'
            '</defs>'
            '<rect width="900" height="420" fill="url(#bg)" rx="18"/>'
            '<text x="450" y="42" fill="#00ff87" font-size="26" font-weight="bold" '
            'text-anchor="middle">🔐 كيفاش يسير التشفير فـ WireGuard</text>'
            '<rect x="40" y="160" width="180" height="90" rx="12" fill="#1e293b" stroke="#00f2fe" stroke-width="2"/>'
            '<text x="130" y="200" fill="#e5e7eb" font-size="20" text-anchor="middle">💻 الكليان</text>'
            '<text x="130" y="228" fill="#8892a0" font-size="15" text-anchor="middle">Client</text>'
            '<rect x="360" y="140" width="180" height="130" rx="60" fill="#0b1220" stroke="url(#tun)" stroke-width="3"/>'
            '<text x="450" y="195" fill="#00ff87" font-size="20" text-anchor="middle">🚇 النفق المشفر</text>'
            '<text x="450" y="222" fill="#8892a0" font-size="15" text-anchor="middle">Encrypted Tunnel</text>'
            '<g><circle cx="450" cy="285" r="14" fill="#00ff87" opacity="0.85"/>'
            '<animate attributeName="opacity" values="0.85;0.25;0.85" dur="1.8s" repeatCount="indefinite"/></g>'
            '<text x="450" y="315" fill="#00ff87" font-size="15" text-anchor="middle">🔒 UDP 51820</text>'
            '<rect x="680" y="160" width="180" height="90" rx="12" fill="#1e293b" stroke="#00ff87" stroke-width="2"/>'
            '<text x="770" y="200" fill="#e5e7eb" font-size="20" text-anchor="middle">🖥️ السيرفر</text>'
            '<text x="770" y="228" fill="#8892a0" font-size="15" text-anchor="middle">Server</text>'
            '<path d="M 220 205 C 290 205, 300 205, 358 205" stroke="url(#tun)" stroke-width="3" fill="none" marker-end="url(#arrow)"/>'
            '<path d="M 540 205 C 600 205, 610 205, 678 205" stroke="#00f2fe" stroke-width="3" fill="none"/>'
            '<path d="M 860 150 C 880 110, 850 80, 800 60" stroke="#f59e0b" stroke-width="2" stroke-dasharray="7 5" fill="none"/>'
            '<text x="845" y="55" fill="#f59e0b" font-size="19" text-anchor="middle">🌍 الإنترنت</text>'
            '<g><circle r="7" fill="#00f2fe">'
            '<animateMotion dur="2.4s" repeatCount="indefinite" path="M 220 205 C 290 205, 300 205, 358 205"/>'
            '</circle></g>'
            '<g><circle r="7" fill="#00ff87">'
            '<animateMotion dur="2.4s" begin="1.2s" repeatCount="indefinite" path="M 540 205 C 600 205, 610 205, 678 205"/>'
            '</circle></g>'
            '<text x="450" y="395" fill="#8892a0" font-size="16" text-anchor="middle">'
            'كل البيانات تتبع مشفرة من طرف لطرف — حتى الـ ISP ما يشوفش المحتوى</text>'
            '</svg>'
        )

    # ------------------------------------------------------------------ #
    async def run(self, node: PlanNode, ctx: AgentContext) -> NodeResult:
        topic = str(node.params.get("topic") or ctx.goal)

        sections: Dict[str, Any] = {}

        # ---- PASS INTRO : why this technology --------------------------- #
        p1_raw = self._policy_clean(await self._gen(self._pass_intro_prompt(topic)))
        title_m = re.search(r"^TITLE:\s*(.+)$", p1_raw, re.MULTILINE)
        title = (title_m.group(1).strip() if title_m else "")
        hero_html_m = re.search(r'<div dir="rtl"[\s\S]*?</div>', p1_raw)
        if hero_html_m:
            hero_html = hero_html_m.group(0)
        else:
            open_m = re.search(r'<div dir="rtl"[^\n]*', p1_raw)
            if open_m:
                block_lines = [open_m.group(0)]
                for ln in p1_raw[open_m.end():].splitlines():
                    if not ln.strip():
                        break
                    block_lines.append(ln)
                hero_html = "\n".join(block_lines)
                if "</div>" not in hero_html:
                    hero_html += "\n</div>"
            else:
                hero_html = (f'<div dir="rtl" class="hero-box">🎯 في هالمقال '
                             f'باش نخدمو: {html_mod.escape(topic)}</div>')
        body1 = p1_raw
        if title_m:
            body1 = re.sub(r"^TITLE:.*\n?", "", body1, flags=re.MULTILINE)
        if hero_html_m:
            body1 = body1.replace(hero_html, "").strip()
        sections["title"] = title or topic[:60]
        sections["hero"] = hero_html
        sections["intro"] = self._policy_clean(body1).strip()

        # ---- PASS TOPOLOGY : master blueprint + addressing plan --------- #
        topo_raw = self._policy_clean(
            await self._gen(self._pass_topology_prompt(topic)))
        sections["topology"] = ("## 🗺️ المخطط المدير والخطة العنوانية "
                                "(Master Blueprint)\n\n"
                                + self._addressing_block() + "\n\n"
                                + topo_raw.strip())

        # ---- PASS SVG : 2-node animated topology ------------------------- #
        p2_raw = await self._gen(self._pass2_prompt(topic))
        svg = self.extract_svg(p2_raw)
        svg_origin = "llm"
        if not svg:
            svg = self.default_topology_svg(topic)
            svg_origin = "template_fallback"
        sections["svg"] = svg
        sections["svg_origin"] = svg_origin

        # ---- PASS TABLE : comparison ------------------------------------- #
        p5_raw = self._policy_clean(await self._gen(self._pass_table_prompt(topic)))
        table_m = re.search(r"(?:^\|.*\|$\n?)+", p5_raw, re.MULTILINE)
        if table_m:
            verdict = p5_raw[table_m.end():].strip()
            sections["table"] = ("## ⚖️ المقارنة التقنية (Comparison)\n\n"
                                 + table_m.group(0).strip()
                                 + ("\n\n" + verdict if verdict else ""))
        else:
            sections["table"] = p5_raw.strip()

        # ---- PASS SERVER : Peer 1 complete ------------------------------- #
        srv_raw = self._policy_clean(await self._gen(self._pass_server_prompt(topic)))
        sections["server"] = srv_raw.strip()

        # ---- PASS CLIENT : Peer 2 complete ------------------------------- #
        cli_raw = self._policy_clean(await self._gen(self._pass_client_prompt(topic)))
        sections["client"] = cli_raw.strip()

        # ---- PASS VALIDATION : real end-to-end tests --------------------- #
        val_raw = self._policy_clean(await self._gen(self._pass_validation_prompt(topic)))
        sections["validation"] = val_raw.strip()

        # ---- PASS TROUBLESHOOTING ---------------------------------------- #
        p4_raw = self._policy_clean(await self._gen(self._pass_troubleshooting_prompt(topic)))
        sections["troubleshooting"] = p4_raw.strip()

        # ---- deterministic guarantees (v2.3) ----------------------------- #
        injected = self._ensure_callouts(sections)
        if injected:
            logger.info(f"[content] {injected} security callout(s) "
                        f"injected by guarantee")

        content = self._assemble(sections)
        ctx.scratch["sections"] = sections

        summary_m = re.search(r"^(.{80,400}?[.!؟])\s",
                              re.sub(r"<[^>]+>|```[\s\S]*?```", " ", content))
        tags = sorted({t.lower() for t in re.findall(
            r"\b(wireguard|docker|linux|vpn|security|network|devops|ai|tls|ssh|iptables)\b",
            content, re.IGNORECASE)})[:6] or ["linux", "tutorial"]

        out_dir = BACKEND / "media" / "articles"
        out_dir.mkdir(parents=True, exist_ok=True)
        md_path = out_dir / f"genio_lab_{int(time.time())}.md"
        md_path.write_text(f"# {sections['title']}\n\n{content}", encoding="utf-8")

        ctx.scratch["title"] = sections["title"]
        ctx.scratch["content"] = content
        ctx.scratch["summary"] = summary_m.group(1)[:280] if summary_m else ""
        ctx.scratch["tags"] = tags

        art = Artifact("md", str(md_path), {"words": len(content.split()),
                                            "passes": 4})
        ctx.artifacts["article_md"] = art
        return NodeResult(node.id, True,
                          output=f"'{sections['title']}' ({len(content.split())} words, "
                                 f"svg={sections['svg_origin']}, 4 passes)",
                          artifacts=[art])

    # ------------------------------------------------------------------ #
    @staticmethod
    def _assemble(s: Dict[str, Any]) -> str:
        """IT-Connect pedagogical order (v3.5):
        hook -> why -> comparison -> blueprint -> diagram ->
        server -> client -> validation -> troubleshooting."""
        parts = [
            s.get("hero", ""),
            s.get("intro", ""),
            s.get("table", ""),
            s.get("topology", ""),
            "## 🖼️ المخطط التقني (Architecture Diagram)",
            s.get("svg", ""),
            s.get("server", ""),
            s.get("client", ""),
            s.get("validation", ""),
            s.get("troubleshooting", ""),
        ]
        return "\n\n".join(p for p in parts if p and p.strip()).strip()

    # ------------------------------------------------------------------ #
    async def repair_deficiencies(self, ctx: AgentContext,
                                  findings: List[str]) -> NodeResult:
        """Regenerate ONLY the deficient passes, then rebuild the article."""
        sections: Dict[str, Any] = dict(ctx.scratch.get("sections") or {})
        if not sections:
            return NodeResult("content_repair", False, error="no sections to repair")

        topic = ctx.goal
        regenerated: List[str] = []

        if "missing_svg" in findings or "invalid_svg" in findings:
            p2 = await self._gen(self._pass2_prompt(topic))
            svg = self.extract_svg(p2) or self.default_topology_svg(topic)
            if svg == self.default_topology_svg(topic):
                sections["svg_origin"] = "template_fallback_repair"
            else:
                sections["svg_origin"] = "llm_repaired"
            sections["svg"] = svg
            regenerated.append("svg")

        if "high_latin_ratio" in findings:
            rewrite_prompt = """{policy}

TASK: Rewrite the PROSE of this tech-lab section so that EVERY explanation
sentence is in White Tunisian Tech Darija. Keep ALL code blocks, commands,
file contents and technical terms EXACTLY as they are. Do not drop any
section, list item or heading. Output the full rewritten section only.

Section to rewrite:
{body}

Rewritten section:"""
            rewrite_prompt = rewrite_prompt.replace("{policy}", self.DARIJA_POLICY)
            for key in ("plan", "implementation", "troubleshooting"):
                body = sections.get(key) or ""
                if not body.strip():
                    continue
                try:
                    rewritten = await self._gen(
                        rewrite_prompt.replace("{body}", body[:5000]))
                    if rewritten and len(rewritten.strip()) > 100:
                        sections[key] = self._policy_clean(rewritten.strip())
                except Exception as exc:  # noqa: BLE001
                    logger.warning(f"[regen] rewrite of {key} failed: {exc}")
            regenerated.append("darija_rewrite")

        if "missing_table" in findings:
            p5 = self._policy_clean(await self._gen(self._pass_table_prompt(topic)))
            t_m = re.search(r"(?:^\|.*\|$\n?)+", p5, re.MULTILINE)
            sections["table"] = ("## ⚖️ المقارنة التقنية (Comparison)\n\n"
                                 + (t_m.group(0).strip() if t_m else p5.strip()))
            regenerated.append("comparison_table")

        if "missing_callouts" in findings or "literal_translation" in findings \
                or "high_latin_ratio" in findings:
            # callouts live in implementation/troubleshooting passes
            callout_hint = ("\n\nMANDATORY reminder: include at least 2 styled "
                            "security callout boxes <div dir=\"rtl\" "
                            "class=\"callout warn\" ...>⚠️ نقطة أمنية حساسة..."
                            "</div> and speak as a senior engineer (نركبو، نفعلو "
                            "ديريكت) - never literal passive phrasing.")
            for key in ("implementation", "troubleshooting"):
                body = sections.get(key) or ""
                if body.strip():
                    try:
                        rewritten = await self._gen(body[:5000] + callout_hint)
                        if rewritten and len(rewritten.strip()) > 100:
                            sections[key] = self._policy_clean(rewritten.strip())
                    except Exception as exc:  # noqa: BLE001
                        logger.warning(f"[regen] {key} rewrite failed: {exc}")
            regenerated.append("callouts_darija")

        v35_map = {
            "missing_client_config": self._pass_client_prompt(topic),
            "missing_routing_fw": self._pass_server_prompt(topic),
            "missing_validation": self._pass_validation_prompt(topic),
            "missing_addressing_plan": self._pass_topology_prompt(topic),
        }
        key_for_code = {
            "missing_client_config": "client",
            "missing_routing_fw": "server",
            "missing_validation": "validation",
            "missing_addressing_plan": "topology",
        }
        for code, prompt in v35_map.items():
            if code in findings:
                regenerated_text = self._policy_clean(await self._gen(prompt))
                skey = key_for_code[code]
                header = {
                    "client": "## 💻 الجانب الكليان البعيد (Peer 2 - Client)",
                    "server": "## 🖥️ الجانب السيرفر (Peer 1 - Serveur)",
                    "validation": "## ✅ التحقق النهائي (Validation & Tests)",
                    "topology": "## 🗺️ المخطط المدير والخطة العنوانية "
                                "(Master Blueprint)",
                }.get(skey, "")
                sections[skey] = (header + "\n\n" + regenerated_text).strip() \
                    if header else regenerated_text.strip()
                regenerated.append(skey)

        if "low_code_density" in findings:
            p3 = self._policy_clean(await self._gen(self._pass3_prompt(topic)))
            if p3.strip():
                sections["implementation"] = p3.strip()
                regenerated.append("implementation")

        if "weak_troubleshooting" in findings:
            p4 = self._policy_clean(await self._gen(self._pass4_prompt(topic)))
            if p4.strip():
                sections["troubleshooting"] = p4.strip()
                regenerated.append("troubleshooting")

        if not regenerated:
            return NodeResult("content_repair", True, output="nothing to repair")

        content = self._assemble(sections)
        ctx.scratch["sections"] = sections
        ctx.scratch["content"] = content
        md_art = ctx.artifacts.get("article_md")
        if md_art and Path(md_art.path_or_url).exists():
            Path(md_art.path_or_url).write_text(
                f"# {ctx.scratch.get('title', '')}\n\n{content}", encoding="utf-8")
        return NodeResult("content_repair", True,
                          output=f"regenerated: {','.join(regenerated)}")


class MediaDirectorAgent(BaseAgent):
    """Real asset generation + Ghost publishing via the existing engines."""
    name = "media"

    async def run(self, node: PlanNode, ctx: AgentContext) -> NodeResult:
        handlers = {
            "generate_audio": self._audio,
            "generate_video": self._video,
            "generate_cover": self._cover,
            "publish_ghost": self._publish,
            "generate_livetest_video": self._livetest_video,
            "prepare_youtube": self._youtube,
        }
        h = handlers.get(node.action)
        if h is None:
            return NodeResult(node.id, False, error=f"Unknown media action: {node.action}")

        if ctx.dry_run and node.action != "publish_ghost":
            art = Artifact({"generate_audio": "wav", "generate_video": "mp4",
                            "generate_cover": "png"}[node.action],
                           f"(dry-run placeholder for {node.action})")
            return NodeResult(node.id, True, output="dry-run skip", artifacts=[art])
        return await h(node, ctx)

    # ------------------------------------------------------------------ #
    def _require_content(self, ctx: AgentContext) -> Tuple[str, str]:
        title = ctx.scratch.get("title") or ctx.goal[:70]
        content = ctx.scratch.get("content")
        if not content:
            raise RuntimeError("No article content produced yet")
        return title, content

    async def _voice_script(self, content: str) -> str:
        from darija_rewriter import generate_voice_script

        script = await generate_voice_script(content)
        return script or re.sub(r"```[\s\S]*?```", " ", content)[:1500]

    async def _audio(self, node: PlanNode, ctx: AgentContext) -> NodeResult:
        title, content = self._require_content(ctx)
        script = ctx.scratch.get("voice_script") or await self._voice_script(content)
        ctx.scratch["voice_script"] = script

        res = await media_steps.generate_audio(
            int(ctx.scratch.get("article_id", int(time.time())) % 100000), script)
        art = Artifact("wav", res["path"], {"duration_s": res.get("duration", 0),
                                            "size_mb": res.get("size_mb", 0)})
        ctx.artifacts["audio_wav"] = art
        return NodeResult(node.id, True,
                          output=f"wav ready ({art.meta['size_mb']}MB)",
                          artifacts=[art])

    async def _video(self, node: PlanNode, ctx: AgentContext) -> NodeResult:
        title, content = self._require_content(ctx)
        script = ctx.scratch.get("voice_script") or await self._voice_script(content)
        res = await media_steps.generate_video(
            int(ctx.scratch.get("article_id", int(time.time())) % 100000),
            title, content, script)
        art = Artifact("mp4", res["path"], {"size_mb": res.get("size_mb", 0)})
        ctx.artifacts["video_mp4"] = art
        return NodeResult(node.id, True,
                          output=f"vertical short rendered ({art.meta['size_mb']}MB)",
                          artifacts=[art])

    async def _cover(self, node: PlanNode, ctx: AgentContext) -> NodeResult:
        title, _ = self._require_content(ctx)
        category = (ctx.scratch.get("tags") or ["tech"])[0]
        res = await media_steps.generate_cover(
            int(ctx.scratch.get("article_id", int(time.time())) % 100000),
            title, category)
        art = Artifact("png", res["path"], {"size_mb": res.get("size_mb", 0)})
        ctx.artifacts["cover_png"] = art
        return NodeResult(node.id, True, output="cover 1200x630 generated",
                          artifacts=[art])

    async def _livetest_video(self, node: PlanNode, ctx: AgentContext) -> NodeResult:
        """REAL 2-node terminal screencast: commands executed between two docker
        containers with synchronized Darija voice-over (Genio v3.5 IT-Connect)."""
        if ctx.dry_run:
            art = Artifact("mp4", "(dry-run livetest placeholder)")
            return NodeResult(node.id, True, output="dry-run skip",
                              artifacts=[art])

        from livetest_recorder import LiveLabRecorder, wireguard_lab_chapters, flatten_chapters

        title, content = self._require_content(ctx)
        recorder = LiveLabRecorder()

        # v3.5: real 2-node topology (srv + cli containers)
        try:
            plan = await recorder.setup_two_node_network()
            logger.info(f"[livetest] 2-node topology ready: "
                        f"srv={plan['srv_wan_ip']} cli={plan['cli_wan_ip']}")
        except Exception as exc:
            logger.warning(f"[livetest] 2-node setup failed, "
                           f"falling back to single sandbox: {exc}")
            await recorder.start_sandbox()

        chapters = wireguard_lab_chapters()
        res = await recorder.record_lab(
            flatten_chapters(chapters), title,
            chapter_data=chapters)

        await recorder.stop_sandbox()

        if res.steps_ok < res.steps_total:
            return NodeResult(node.id, False,
                              error=f"only {res.steps_ok}/{res.steps_total} "
                                    f"steps recorded")
        art = Artifact("mp4", res.video_path,
                       {"kind": "live_terminal_2node",
                        "duration_s": res.duration_s,
                        "size_mb": res.size_mb})
        ctx.artifacts["livetest_video"] = art
        ctx.scratch["video_src"] = art.path_or_url
        return NodeResult(node.id, True,
                          output=f"2-node live lab recorded "
                                 f"{res.duration_s}s ({res.size_mb}MB)",
                          artifacts=[art])

    async def _youtube(self, node: PlanNode, ctx: AgentContext) -> NodeResult:
        """Build optimized YT payload; upload when OAuth creds exist."""
        from youtube_publisher import build_wireguard_payload, upload

        vid = ctx.artifacts.get("livetest_video") \
            or ctx.artifacts.get("video_mp4")
        if not vid:
            return NodeResult(node.id, False, error="no video to publish")
        ghost_art = ctx.artifacts.get("ghost_post")
        article_url = ghost_art.path_or_url if ghost_art else "https://lab.hitech.tn"

        payload = build_wireguard_payload(vid.path_or_url, 70.0, article_url)
        result = await upload(payload)

        art = Artifact("youtube_payload", result.get("payload_path", ""),
                       {"status": result["status"], "title": payload.title,
                        "url": result.get("url")})
        ctx.artifacts["youtube"] = art
        detail = result["status"]
        if result.get("url"):
            detail += f" -> {result['url']}"
        elif result.get("reason"):
            detail += f" ({result['reason'][:60]})"
        return NodeResult(node.id, True, output=detail, artifacts=[art])

    async def _publish(self, node: PlanNode, ctx: AgentContext) -> NodeResult:
        if ctx.dry_run or not ctx.publish:
            return NodeResult(node.id, True, output="publish skipped by config")
        title, content = self._require_content(ctx)
        cover = ctx.artifacts.get("cover_png")
        ghost = await asyncio.to_thread(get_ghost_client)
        video_src = None
        lv = ctx.artifacts.get("livetest_video")
        if lv:
            fname = Path(lv.path_or_url).name
            video_src = f"http://pop-os:8088/media/video/{fname}"

        res = await media_steps.publish_to_ghost(
            int(ctx.scratch.get("article_id", int(time.time())) % 100000),
            title, content, ctx.scratch.get("tags", []),
            cover.path_or_url if cover else None, ghost,
            video_src=video_src
        )
        art = Artifact("ghost_post", res["ghost_url"],
                       {"post_id": res["ghost_post_id"], "tags": res["tags_used"]})
        ctx.artifacts["ghost_post"] = art
        return NodeResult(node.id, True,
                          output=f"published -> {res['ghost_url']}",
                          artifacts=[art])


class AuditorAgent(BaseAgent):
    """Strict quality gate: structure, SVG, density, language policy, security.

    Quality scoring (content labs):
      - gold structure gate ............ 25 pts
      - valid inline SVG diagram ....... 15 pts
      - >= 4 distinct code blocks ...... 15 pts
      - explicit Troubleshooting ....... 10 pts
      - Darija compliance (prose) ...... 20 pts (hard fail > 25% latin)
      - placeholder / syntax penalties . -10 / -20 each
    PASS threshold: quality >= 85 AND security >= 60.
    Deficiencies are emitted as `regen:<codes>` so the self-healing loop can
    regenerate exactly the broken sections.
    """
    name = "auditor"

    PLACEHOLDER_PATTERNS = (
        re.compile(r"^```[^`]*?\n(?:\s*\.\.\.\s*\n)+```", re.M),
        re.compile(r"\bTODO\b|\bFIXME\b|\bXXX\b"),
        re.compile(r"<placeholder>|TBD\b"),
    )

    # Vocabulary allowed inside Latin-script prose (technical terms policy)
    TECH_TERMS = frozenset("""
        wireguard wg wg0 wg-quick vpn udp tcp port ip ipv4 ipv6 dns dhcp mtu
        server client peer endpoint tunnel networking interface kernel
        module firewall nat masquerade forward routing route table subnet
        gateway eth0 ens3 dev quick tools utils systemd enabled enable start
        restart status stop reload daemon service config configuration conf
        sysctl iptables nftables postup predown postdown saveconfig listenport
        address allowedips privatekey publickey presharedkey endpoint qrencode
        ping curl wget tcpdump journalctl apt apt-get install sudo umask chmod
        chown bash shell terminal root user password protocol encryption
        handshake crypto chacha20 poly1305 curve25519 blake2s docker linux
        ubuntu debian alpine tls ssh https http json yaml api cli gui cpu ram
        disk ssd gpu lan wan isp proxy reverse nginx openssl gpg git github lab
        hitech genio emoji rtl svg animate viewBox gradient stroke rect circle
        path text font fill opacity dur repeatcount begin attributename
        values keys error errors debug verbose log logs output input file line
        step steps check test testing production production-ready backup
        restore performance latency throughput bandwidth packet packets drop
        reject accept chain rule rules default policy aes openvpn ipsec
    """.split())

    # ------------------------------------------------------------------ #
    @classmethod
    def _strip_code(cls, text: str) -> str:
        text = re.sub(r"```[\s\S]*?```", " ", text)
        text = re.sub(r"`[^`\n]+`", " ", text)          # inline code
        text = re.sub(r"https?://\S+", " ", text)       # urls
        return text

    @classmethod
    def _prose_only(cls, text: str) -> str:
        """Code fences + inline code + URLs + raw HTML/SVG markup removed."""
        prose = cls._strip_code(text)
        prose = re.sub(r"<[^>\n]+>", " ", prose)         # xml/svg/html markup
        return prose

    @classmethod
    def _latin_ratio(cls, prose: str) -> float:
        """Share of non-technical Latin words among all prose words."""
        latin_words = [
            w.lower().strip("._-'’")
            for w in re.findall(r"[A-Za-z][A-Za-z0-9'’_\-.]*", prose)]
        arabic_words = re.findall(r"[\u0600-\u06FF]{2,}", prose)
        non_tech = [w for w in latin_words
                    if len(w) > 1 and w not in cls.TECH_TERMS]
        denom = len(non_tech) + len(arabic_words)
        return len(non_tech) / denom if denom else 0.0

    @staticmethod
    def _svg_ok(content: str) -> bool:
        m = re.search(r"<svg[\s\S]*?</svg>", content, re.IGNORECASE)
        if not m:
            return False
        try:
            import xml.etree.ElementTree as ET

            ET.fromstring(m.group(0))
            return True
        except Exception:
            return False

    @staticmethod
    def _code_block_count(content: str) -> int:
        fences = re.findall(r"^```", content, re.MULTILINE)
        return len(fences) // 2

    # ------------------------------------------------------------------ #
    async def run(self, node: PlanNode, ctx: AgentContext) -> NodeResult:
        findings: List[str] = []
        regen_codes: List[str] = []
        quality, security = 100.0, 100.0

        content = ctx.scratch.get("content") or ""
        hard_violations: List[str] = []

        if content:
            # ---- gold structure gate (hero/architecture/code/troubleshooting)
            gate = media_steps.validate_gold_standard(
                ctx.scratch.get("title", ""), content, ctx.scratch.get("tags", []))
            quality = 100 - 25 * (1 - gate["score"])
            for c in gate["checks"]:
                if not c["passed"]:
                    findings.append(f"gold:{c['check']}")

            # ---- SVG diagram mandatory ---------------------------------
            if not self._svg_ok(content):
                quality -= 15
                has_any = bool(re.search(r"<svg[\s>]", content))
                code = "invalid_svg" if has_any else "missing_svg"
                regen_codes.append(code)
                findings.append(code)
                hard_violations.append(code)

            # ---- technical density --------------------------------------
            blocks = self._code_block_count(content)
            if blocks < 4:
                quality -= 15
                regen_codes.append("low_code_density")
                findings.append(f"code_blocks={blocks}(<4)")
                hard_violations.append("low_code_density")

            trbl_ok = bool(re.search(
                r"troubleshooting|استكشاف\s*الأخطاء|حل\s*المشاكل",
                content, re.IGNORECASE))
            if not trbl_ok:
                quality -= 10
                regen_codes.append("weak_troubleshooting")
                findings.append("no_explicit_troubleshooting")
                hard_violations.append("weak_troubleshooting")

            # ---- linguistic policy: prose must be Darija-dominant -------
            prose = self._prose_only(content)
            ratio = self._latin_ratio(prose)
            if ratio > 0.25:
                quality -= 20                       # hard fail zone
                regen_codes.append("high_latin_ratio")
                findings.append(f"latin_prose={ratio:.0%}(>25%)")
                hard_violations.append("high_latin_ratio")
            elif ratio > 0.10:
                quality -= round((ratio - 0.10) * 100, 1)   # soft slope
                findings.append(f"latin_prose={ratio:.0%}")

            # ---- v3.5 pedagogical gates (network labs) ------------------
            # v3.5 gates apply ONLY for explicit 2-node lab scenario requests
            # (not just any article mentioning VPN)
            net_topic = bool(re.search(
                r"2[- ]?node|scénario complet|serveur.{0,20}client|"
                r"lab.*(complet|réseau|end.to.end)|end.to.end.*(lab|vpn)|"
                r"tutoriel.*complet|two.node",
                (ctx.goal or ""), re.IGNORECASE))
            if net_topic:
                two_iface = len(re.findall(r"^\[Interface\]", content, re.M)) >= 2
                has_peer = "[Peer]" in content and "AllowedIPs" in content
                client_cfg = re.search(r"client|kliyeh|الكليان", content, re.I)
                if not ((two_iface and has_peer) or (has_peer and client_cfg)):
                    quality -= 8
                    regen_codes.append("missing_client_config")
                    findings.append("no_two_peer_config")
                    hard_violations.append("missing_client_config")

                routing_ok = ("ip_forward" in content
                              and ("MASQUERADE" in content or "ufw" in content.lower()))
                if not routing_ok:
                    quality -= 7
                    regen_codes.append("missing_routing_fw")
                    findings.append("no_ip_forward_or_nat")
                    hard_violations.append("missing_routing_fw")

                validation_ok = ("wg show" in content and "ping" in content)
                if not validation_ok:
                    quality -= 6
                    regen_codes.append("missing_validation")
                    findings.append("no_validation_phase")
                    hard_violations.append("missing_validation")

                subnets = set(re.findall(r"\b(?:10\.\d{1,3}|192\.168)\.\d{1,3}\.\d{1,3}/\d{1,2}\b",
                                         content))
                if len(subnets) < 2:
                    quality -= 5
                    regen_codes.append("missing_addressing_plan")
                    findings.append(f"subnets={len(subnets)}(<2)")
                    hard_violations.append("missing_addressing_plan")

            # ---- mandatory comparison table (v2.3) ----------------------
            has_table = ("<table" in content.lower()
                         or bool(re.search(r"^\|[^|\n]+\|[\s\S]*?^\|[-\s|:]+\|$",
                                           content, re.MULTILINE)))
            if not has_table:
                quality -= 8
                regen_codes.append("missing_table")
                findings.append("no_comparison_table")
                hard_violations.append("missing_table")

            # ---- mandatory security callouts (v2.3) ----------------------
            callouts = len(re.findall(r'class="callout', content))
            if callouts < 2:
                quality -= 7
                regen_codes.append("missing_callouts")
                findings.append(f"callouts={callouts}(<2)")
                hard_violations.append("missing_callouts")

            # ---- banned literal translations (v2.3) ----------------------
            banned_hits = [p for p in ContentArchitectAgent.BANNED_LITERAL
                           if p in content]
            if banned_hits:
                quality -= 12
                regen_codes.append("literal_translation")
                findings.append(f"literal_phrasing={banned_hits[:2]}")
                hard_violations.append("literal_translation")

            # ---- placeholders -------------------------------------------
            for pat in self.PLACEHOLDER_PATTERNS:
                if pat.search(content):
                    quality -= 10
                    findings.append(f"placeholder:{pat.pattern[:20]}")

            # ---- python artifact syntax ----------------------------------
            md_art = ctx.artifacts.get("article_md")
            if md_art and Path(md_art.path_or_url).exists():
                py_blocks = re.findall(r"```python\n([\s\S]*?)```",
                                       Path(md_art.path_or_url).read_text())
                for i, block in enumerate(py_blocks):
                    try:
                        compile(block, f"<lab-block-{i}>", "exec")
                    except SyntaxError as exc:
                        quality -= 20
                        findings.append(f"py_syntax_block{i}: {exc.msg}")
        else:
            quality -= 100
            findings.append("no_content")

        # ---- security: secrets must never leak ---------------------------
        env_path = Path("/data/ai_tools/.env")
        if env_path.exists():
            secret_values = [
                ln.split("=", 1)[1].strip() for ln in env_path.read_text().splitlines()
                if "=" in ln and not ln.strip().startswith("#")
                and ln.split("=")[0].strip().endswith(("KEY", "TOKEN", "SECRET"))
                and len(ln.split("=", 1)[1].strip()) > 16]
            haystack = content + "".join(a.path_or_url for a in ctx.artifacts.values())
            leaked = [s for s in secret_values if s and s in haystack]
            if leaked:
                security -= 60 * min(len(leaked), 2)
                findings.append(f"secret_leak({len(leaked)})")

        checks = ctx.scratch.get("env_checks") or {}
        if not all([checks.get("ollama"), checks.get("cinema_engine")]):
            security -= 10
            findings.append("service_degraded")

        quality, security = max(quality, 0.0), max(security, 0.0)
        ctx.scratch["audit"] = {"quality": round(quality, 1),
                                "security": round(security, 1),
                                "deficiencies": regen_codes}

        ok = quality >= 85 and security >= 60 and not hard_violations
        summary = f"quality={quality:.0f}/100 security={security:.0f}/100"
        if regen_codes:
            summary += f" | regen:{','.join(regen_codes)}"
        if findings:
            summary += " | findings: " + "; ".join(findings)

        error = None
        if not ok:
            error = summary + (f" | regen:{','.join(regen_codes)}" if regen_codes else "")
            # SELF-LEARNING: every rejection becomes a durable memory rule
            try:
                added = get_memory().record_rejection(regen_codes or ["unspecified"],
                                                      source="auditor")
                if added:
                    logger.info(f"[memory] learned {len(added)} new rule(s)")
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"[memory] recording failed: {exc}")
        return NodeResult(node.id, ok, output=summary, error=error)


AGENT_REGISTRY: Dict[str, type] = {
    "sandbox": CodeSandboxAgent,
    "content": ContentArchitectAgent,
    "media": MediaDirectorAgent,
    "auditor": AuditorAgent,
}


def dispatch(agent_name: str) -> BaseAgent:
    """Sub-agent dispatcher factory."""
    cls = AGENT_REGISTRY.get(agent_name)
    if cls is None:
        raise KeyError(f"No sub-agent registered under '{agent_name}'")
    return cls()


# =========================================================================== #
# Self-healing executor                                                       #
# =========================================================================== #

class Remediation:
    """Maps error signatures to concrete recovery actions."""

    STRATEGIES: List[Tuple[str, str]] = [
        (r"regen:[\w,\s]+", "content_regen"),          # auditor demands section rebuild
        (r"connection refused|unreachable|ECONNREFUSED", "wait_for_services"),
        (r"timed?\s?-?out|timeout", "escalate_timeout"),
        (r"401|unauthorized|invalid api token|kid missing", "reload_secrets"),
        (r"database is locked", "sqlite_backoff"),
        (r"ffmpeg|nvenc|codec", "ffmpeg_fallback"),
        (r"429|rate.?limit", "backoff_long"),
    ]

    @classmethod
    def classify(cls, error: str) -> str:
        low = (error or "").lower()
        for pattern, strategy in cls.STRATEGIES:
            if re.search(pattern, low):
                return strategy
        return "generic_backoff"

    @staticmethod
    def extract_regen_codes(error: str) -> List[str]:
        codes: List[str] = []
        for m in re.finditer(r"regen:\s*([\w,\s]+)", error or ""):
            for part in m.group(1).split(","):
                code = part.strip()
                if code and code not in ("findings",):
                    codes.append(code)
        return codes


class SelfHealingExecutor:
    """Runs one node with up to N retries, applying remediation between tries."""

    def __init__(self, default_retries: int = 3):
        self.default_retries = default_retries
        self.recovery_trace: List[Dict[str, str]] = []

    async def _apply_remediation(self, strategy: str, node: PlanNode,
                                 attempt: int,
                                 failed_result: Optional[NodeResult] = None,
                                 ctx: Optional[AgentContext] = None) -> None:
        note = f"[recovery#{attempt}] {strategy} on node={node.id}"

        if strategy == "content_regen" and ctx is not None:
            try:
                codes = Remediation.extract_regen_codes(
                    failed_result.error if failed_result else "")
                agent = dispatch("content")
                repair = await agent.repair_deficiencies(ctx, codes)
                logger.info(f"[regen] {repair.output} (codes={codes})")
            except Exception as exc:  # noqa: BLE001
                logger.error(f"[regen] repair failed: {exc}")
        if strategy == "wait_for_services":
            wait = CodeSandboxAgent()
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                res = await wait.run(PlanNode(node.id + "_probe", "sandbox",
                                              "check_environment"), AgentContext(node.id))
                if res.ok:
                    break
                await asyncio.sleep(5)
        elif strategy == "escalate_timeout":
            node.timeout_s = min(int(node.timeout_s * 2), 3600)
            note += f" -> timeout={node.timeout_s}s"
        elif strategy == "reload_secrets":
            env_path = Path("/data/ai_tools/.env")
            if not env_path.exists():
                env_path = GENIO_DIR.parent / ".env"
            if env_path.exists():
                for line in env_path.read_text().splitlines():
                    if "=" in line and not line.strip().startswith("#"):
                        k, v = line.split("=", 1)
                        os.environ.setdefault(k.strip(), v.strip())
        elif strategy == "ffmpeg_fallback":
            node.params["ffmpeg_simple"] = True
        elif strategy in ("sqlite_backoff", "generic_backoff"):
            await asyncio.sleep(min(2 ** attempt, 15))
        elif strategy == "backoff_long":
            await asyncio.sleep(min(5 * attempt, 30))
        logger.info(note)
        self.recovery_trace.append({"node": node.id, "attempt": str(attempt),
                                    "strategy": strategy})

    def _dispatch(self, agent_name: str) -> BaseAgent:
        """Agent factory hook — overridable by downstream orchestrators."""
        return dispatch(agent_name)

    async def execute_node(self, node: PlanNode, ctx: AgentContext,
                           agent_override: Optional[BaseAgent] = None) -> NodeResult:
        agent = agent_override or self._dispatch(node.agent)
        retries = node.max_retries or self.default_retries
        started = time.monotonic()

        last: Optional[NodeResult] = None
        for attempt in range(1, retries + 1):
            try:
                coro = agent.run(node, ctx)
                result = await asyncio.wait_for(coro, timeout=node.timeout_s)
            except asyncio.TimeoutError:
                result = NodeResult(node.id, False, error="node timed out")
            except Exception as exc:  # noqa: BLE001 — executor boundary
                logger.error(traceback.format_exc(limit=3))
                result = NodeResult(node.id, False, error=f"{type(exc).__name__}: {exc}")

            result.duration_s = round(time.monotonic() - started, 2)
            result.attempts = attempt
            if result.ok:
                return result

            last = result
            if attempt < retries:
                strategy = Remediation.classify(result.error or "")
                await self._apply_remediation(strategy, node, attempt,
                                              failed_result=result, ctx=ctx)

        assert last is not None
        return last


# =========================================================================== #
# Executive reporting                                                         #
# =========================================================================== #

class ReportGenerator:
    @staticmethod
    def build(plan: ExecutionPlan, results: Dict[str, NodeResult],
              ctx: AgentContext, wall_time: float) -> str:
        ru = resource.getrusage(resource.RUSAGE_SELF)
        audit = ctx.scratch.get("audit", {})
        quality = float(audit.get("quality", 0))
        security = float(audit.get("security", 0))
        score = round((quality + security) / 2, 1)
        ok_count = sum(1 for r in results.values() if r.ok)
        overall = "SUCCESS" if ok_count == len(results) else ("PARTIAL" if ok_count else "FAILED")

        lines = [
            "# 🏛️ GENIO — EXECUTIVE AUDIT REPORT",
            f"**Generated:** {datetime.utcnow().isoformat()}Z  ",
            f"**Goal:** {plan.goal}  ",
            f"**Overall:** {overall} ({ok_count}/{len(results)} nodes OK) · "
            f"Composite Score **{score}/100** · Wall-time **{wall_time:.1f}s**",
            "",
            "## 1. Goal vs Outcome",
            "| Node | Agent | Status | Time | Detail |",
            "|------|-------|--------|------|--------|",
        ]
        for node in plan.topological():
            r = results.get(node.id)
            icon = "✅" if (r and r.ok) else "❌"
            detail = (r.output if r and r.ok else (r.error if r else "skipped"))
            lines.append(f"| {node.id} | {node.agent} | {icon} "
                         f"{('x' + str(r.attempts)) if r else ''} | "
                         f"{r.duration_s if r else '-'}s | {str(detail)[:110]} |")

        lines += ["", "## 2. Artifacts Created"]
        if ctx.artifacts:
            for key, a in ctx.artifacts.items():
                lines.append(f"- `{key}` [{a.kind}] → {a.path_or_url}"
                             + (f" · {a.meta}" if a.meta else ""))
        else:
            lines.append("- none")

        lines += [
            "", "## 3. Quality & Security",
            f"- Quality Score : **{quality:.0f}/100**",
            f"- Security Score: **{security:.0f}/100**",
            "", "## 4. Self-Healing Trace",
        ]
        exec_trace = ctx.scratch.get("recovery_trace") or []
        if exec_trace:
            for t in exec_trace:
                lines.append(f"- node `{t['node']}` attempt {t['attempt']} → {t['strategy']}")
        else:
            lines.append("- clean run, zero interventions")

        lines += [
            "", "## 5. Resource Usage",
            f"- CPU user/sys: {ru.ru_utime:.1f}s / {ru.ru_stime:.1f}s",
            f"- Peak RSS     : {ru.ru_maxrss / 1024:.1f} MB",
        ]
        return "\n".join(lines)


# =========================================================================== #
# Genio core orchestrator                                                     #
# =========================================================================== #

async def execute_prompt(prompt: str, *, max_retries: int = 3, publish: bool = True,
                         dry_run: bool = False, use_llm_planner: bool = True,
                         plan_path: Optional[Path] = None,
                         plan_override: Optional[ExecutionPlan] = None,
                         router: Optional[LLMRouter] = None,
                         report_dir: Optional[Path] = None) -> Tuple[str, ExecutionPlan, Dict[str, NodeResult], AgentContext]:
    """Full Genio cycle: plan → dispatch → heal → audit → report."""
    core_start = time.monotonic()

    # 1) PLAN
    planner = PlanningEngine(router=router)
    plan = plan_override or await planner.build_plan(prompt, use_llm=use_llm_planner)
    if plan_path:
        plan_path.write_text(plan.to_json(), encoding="utf-8")
    logger.info(f"📋 Plan ready ({plan.planner}): {len(plan.nodes)} nodes")

    # 2) DISPATCH + HEAL
    ctx = AgentContext(goal=plan.goal, dry_run=dry_run, publish=publish)
    healing = SelfHealingExecutor(default_retries=max_retries)
    results: Dict[str, NodeResult] = {}

    for node in plan.topological():
        deps_failed = [d for d in node.depends_on
                       if d in results and not results[d].ok]
        if deps_failed:
            results[node.id] = NodeResult(
                node.id, False,
                error=f"skipped: dependency failed {deps_failed}")
            logger.warning(f"⏭️  {node.id} skipped (deps failed)")
            continue
        if node.on_error == "halt":
            upstream_halt = any(d in results and not results[d].ok
                                and results[d].error for d in node.depends_on)
            if upstream_halt:
                results[node.id] = NodeResult(node.id, False,
                                              error="halted by upstream failure")
                continue
        logger.info(f"▶️  executing [{node.agent}] {node.id}")
        results[node.id] = await healing.execute_node(node, ctx)
        status = "✅" if results[node.id].ok else "❌"
        logger.info(f"{status} {node.id} -> {results[node.id].output or results[node.id].error}")

    ctx.scratch["audit"] = ctx.scratch.get("audit") or {}
    if "audit" not in ctx.scratch or not ctx.scratch["audit"]:
        # ensure scores exist even if auditor node was skipped
        ctx.scratch["audit"] = {"quality": 0, "security": 0}
        for r in results.values():
            if r.ok and "quality=" in (r.output or ""):
                m = re.match(r"quality=(\d+)/100 security=(\d+)/100", r.output)
                if m:
                    ctx.scratch["audit"] = {"quality": float(m.group(1)),
                                            "security": float(m.group(2))}
    ctx.scratch["recovery_trace"] = healing.recovery_trace

    wall = time.monotonic() - core_start
    try:
        get_memory().note_run()
    except Exception:
        pass
    report_md = ReportGenerator.build(plan, results, ctx, wall)
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    report_file = (report_dir or ROOT / "genio" / "reports") / f"genio_report_{stamp}.md"
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(report_md, encoding="utf-8")

    return report_md, plan, results, ctx


def build_autonomous_plan(topic: str) -> ExecutionPlan:
    """Deterministic pipeline: content → 2-node sandbox → video → audio →
    cover → audit → publish → youtube payload."""
    nodes = [
        PlanNode(id="env_check", agent="sandbox",
                 action="check_environment", timeout_s=60),
        PlanNode(id="content", agent="content",
                 action="generate_darija_lab",
                 params={"topic": topic}, timeout_s=1500),
        PlanNode(id="livetest_recording", agent="media",
                 action="generate_livetest_video",
                 params={"topic": topic},
                 depends_on=["content"], timeout_s=900),
        PlanNode(id="audio", agent="media",
                 action="generate_audio",
                 depends_on=["content"], timeout_s=600),
        PlanNode(id="cover", agent="media",
                 action="generate_cover",
                 depends_on=["content"], timeout_s=120),
        PlanNode(id="audit", agent="auditor",
                 action="full_audit",
                 depends_on=["content"], timeout_s=120),
        PlanNode(id="publish", agent="media",
                 action="publish_ghost",
                 depends_on=["audit", "audio", "cover"],
                 params={"force": True}, timeout_s=120),
        PlanNode(id="youtube", agent="media",
                 action="generate_youtube_payload",
                 depends_on=["livetest_recording", "publish"],
                 timeout_s=60),
    ]
    return ExecutionPlan(goal=f"Autonomous lab: {topic}",
                         nodes=nodes, planner="deterministic_v4")


async def execute_autonomous(topic: str, *, max_retries: int = 3,
                             publish: bool = True,
                             report_dir: Optional[Path] = None,
                             ) -> Tuple[str, ExecutionPlan, Dict[str, NodeResult], AgentContext]:
    """Full autonomous cycle with auto-healing at every friction point."""
    core_start = time.monotonic()
    plan = build_autonomous_plan(topic)
    logger.info(f"🤖 Autonomous plan ready: {len(plan.nodes)} nodes")

    ctx = AgentContext(goal=plan.goal, dry_run=False, publish=publish)
    healing = SelfHealingExecutor(default_retries=max_retries)
    results: Dict[str, NodeResult] = {}

    for node in plan.topological():
        deps_failed = [d for d in node.depends_on
                       if d in results and not results[d].ok]
        if deps_failed:
            results[node.id] = NodeResult(
                node.id, False,
                error=f"skipped: dependency failed {deps_failed}")
            logger.warning(f"⏭️  {node.id} skipped (deps failed)")
            continue
        logger.info(f"▶️  autonomous [{node.agent}] {node.id}")
        results[node.id] = await healing.execute_node(node, ctx)
        status = "✅" if results[node.id].ok else "❌"
        logger.info(f"{status} {node.id} -> "
                    f"{results[node.id].output or results[node.id].error}")

        # Auto-recovery: if content audit fails, force-regenerate content
        if (node.id == "audit" and not results[node.id].ok
                and "regen:" in (results[node.id].output or "")):
            logger.info("🔄 Auto-regenerating content after audit failure...")
            regen_node = PlanNode(
                id="auto_regen", agent="content",
                action="generate_darija_lab",
                params={"topic": topic}, timeout_s=1500)
            regen_result = await healing.execute_node(regen_node, ctx)
            if regen_result.ok:
                results["auto_regen"] = regen_result
                re_audit = PlanNode(
                    id="auto_re_audit", agent="auditor",
                    action="full_audit", timeout_s=120)
                re_audit_result = await healing.execute_node(re_audit, ctx)
                results["auto_re_audit"] = re_audit_result
                if re_audit_result.ok:
                    results["audit"] = re_audit_result

    ctx.scratch["recovery_trace"] = healing.recovery_trace

    wall = time.monotonic() - core_start
    try:
        get_memory().note_run()
    except Exception:
        pass
    report_md = ReportGenerator.build(plan, results, ctx, wall)
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    report_file = (report_dir or ROOT / "genio" / "reports") / f"autonomous_{stamp}.md"
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(report_md, encoding="utf-8")

    return report_md, plan, results, ctx


# =========================================================================== #
# CLI                                                                         #
# =========================================================================== #

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="genio_executive_core",
        description="Genio — Autonomous Executive Meta-Agent Core (HiTech Lab)")
    parser.add_argument("--prompt", required=True,
                        help="High-level intent (Darija/Arabic/English)")
    parser.add_argument("--auto", action="store_true",
                        help="Full autonomous pipeline: plan→content→sandbox→"
                             "video→audio→cover→audit→publish→youtube")
    parser.add_argument("--dry-run", action="store_true",
                        help="Plan + environment checks only, no media/publish")
    parser.add_argument("--no-publish", action="store_true",
                        help="Generate assets but do NOT push to Ghost")
    parser.add_argument("--no-llm-planner", action="store_true",
                        help="Use deterministic plan instead of LLM decomposition")
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--plan-out", type=Path, default=None,
                        help="Where to dump the execution DAG (JSON)")
    parser.add_argument("--report-out", type=Path, default=None,
                        help="Extra copy of the executive report")
    parser.add_argument("--feedback", type=str, default=None,
                        help="Record a user lesson into feedback_memory.json "
                             "and exit")
    args = parser.parse_args(argv)

    if args.feedback:
        added = get_memory().record_feedback(args.feedback)
        print(f"🧠 Memory updated ({len(get_memory().data['rules'])} rules). "
              f"Latest: {added}")
        return 0

    if args.auto:
        report_md, plan, results, ctx = asyncio.run(execute_autonomous(
            args.prompt,
            max_retries=args.max_retries,
            publish=not args.no_publish,
        ))
    else:
        report_md, plan, results, ctx = asyncio.run(execute_prompt(
            args.prompt,
            max_retries=args.max_retries,
            publish=not args.no_publish,
            dry_run=args.dry_run,
            use_llm_planner=not args.no_llm_planner,
            plan_path=args.plan_out,
        ))

    print("\n" + "=" * 74)
    print(report_md)
    print("=" * 74)

    if args.report_out:
        args.report_out.write_text(report_md, encoding="utf-8")

    return 0 if all(r.ok for r in results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
