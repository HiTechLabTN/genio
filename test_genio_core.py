"""
Genio — Unit & Integration tests (v2: modular Content Architect + hardened Auditor).

Run:  cd /data/ai_tools/genio && python3 -m pytest test_genio_core.py -v
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Dict

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from genio_executive_core import (  # noqa: E402
    AgentContext,
    Artifact,
    AuditorAgent,
    CodeSandboxAgent,
    ContentArchitectAgent,
    ExecutionPlan,
    NodeResult,
    PlanNode,
    MemoryEngine,
    RIGMA_FEWSHOT,
    PlanningEngine,
    Remediation,
    SelfHealingExecutor,
    dispatch,
    get_memory,
)


def run(coro):
    return asyncio.run(corr := coro)  # noqa: E999 — placeholder replaced below


def run(coro):  # noqa: F811 — real runner
    return asyncio.run(coro)


# =========================================================================== #
# Fixtures                                                                     #
# =========================================================================== #

SVG_BLOCK = ('<svg viewBox="0 0 900 420" width="100%" '
             'xmlns="http://www.w3.org/2000/svg">'
             '<rect width="900" height="420" fill="#0f172a"/>'
             '<text x="450" y="50" fill="#00ff87" font-size="24">التوبولوجي</text>'
             '<animate attributeName="opacity" values="1;0.5;1" dur="2s"/>'
             '</svg>')

CALLOUT_1 = ('<div dir="rtl" class="callout warn" '
             'style="border-right:6px solid #f59e0b;background:#1a2332;'
             'padding:16px;">⚠️ نقطة أمنية حساسة : الـ Private Key ما تخرجش '
             'من السيرفر أبدا</div>')

CALLOUT_2 = ('<div dir="rtl" class="callout warn" '
             'style="border-right:6px solid #ef4444;background:#1a2332;'
             'padding:16px;">⚠️ نقطة أمنية حساسة : نفعلو الـ Firewall قبل '
             'ما نفتحو الـ Port للعموم</div>')

COMPARISON_TABLE = """| المعيار | OpenVPN | WireGuard |
|---------|---------|-----------|
| الأداء | متوسط | مرتفع |
| حجم الكود | 400K سطر | 4K أسطر |
| Handshake | بطيء | أسرع بـ 4x |
"""

GOLD_TUTORIAL = f"""<div dir="rtl" class="hero-box">🎯 في هالمقال باش نركبو سيرفر VPN مريقل</div>

## 🗺️ خطة الخدمة
1. نصبو الحزم
2. نكتبو الكونفيغ

## 🧰 المتطلبات
- سيرفر ubuntu
- صلاحيات root

## ⚖️ المقارنة التقنية (Comparison)
{COMPARISON_TABLE}

{CALLOUT_1}

## 🖼️ البنية التقنية (Architecture)
{SVG_BLOCK}

## ⚙️ التنصيب (Installation)
نصبو الباكاج على خاطر النواة لازمها الموديل تاع WireGuard.
```bash
sudo apt install wireguard -y
```
نعملو المفاتيح على خاطر التشفير يستخدم curve25519.
```bash
wg genkey | tee privatekey | wg pubkey > publickey
```
نكتبو الكونفيغ كامل بلا أي اختصار:
```ini
[Interface]
PrivateKey = AAAxxx111=
Address = 10.0.0.1/24
ListenPort = 51820
PostUp = iptables -A FORWARD -i wg0 -j MASQUERADE
```
نشغلو السيرفس ونتأكدو من الستاتوس:
```bash
systemctl enable --now wg-quick@wg0
wg show
```

## 🔍 Under the Hood كيفاش تخدم من الداخل
WireGuard تستخدم cryptokey routing، الـ handshake يصير كل دقيقتين برشا مرات.

## 🔥 Troubleshooting (استكشاف الأخطاء)

{CALLOUT_2}

### ❌ `Destination unreachable`
علاش يصير: الفايروول مسدود على البورت.
تشخيص:
```bash
sudo tcpdump -i any udp port 51820 -nn
```
الحل — نفتحو البورت:
```bash
sudo iptables -A INPUT -p udp --dport 51820 -j ACCEPT
```

### ❌ `Handshake did not complete`
علاش يصير: الـ keys موش مبدلين بين الطرفين.
تشخيص:
```bash
wg show
```
الحل: نبدلو الـ privatekey ونعاودو نشغلو الواجهة.
"""


async def _audit(content: str, tmp_env_secrets: bool = True) -> NodeResult:
    agent = AuditorAgent()
    ctx = AgentContext("t")
    ctx.scratch["title"] = "T"
    ctx.scratch["content"] = content
    ctx.scratch["tags"] = ["linux", "wireguard"]
    ctx.scratch["env_checks"] = {"ollama": True, "cinema_engine": True}
    ctx.artifacts["article_md"] = Artifact("md", "/nonexistent.md")

    import genio_executive_core as core
    orig_Path = core.Path
    fake_env = "/tmp/opencode/_fakeenv"
    Path(fake_env).write_text(
        "OPENROUTER_API_KEY=fakekey1234567890abcdef1234\n"
        "GHOST_ADMIN_SECRET=fakesecret9876543210abcdef\n")

    def fake_path(p=None):
        if p == "/data/ai_tools/.env":
            return orig_Path(fake_env)
        return orig_Path(p)
    core.Path = fake_path
    try:
        return await agent.run(PlanNode(id="audit", agent="auditor",
                                        action="full_audit"), ctx)
    finally:
        core.Path = orig_Path


# =========================================================================== #
# Unit — planning & DAG                                                        #
# =========================================================================== #

class TestPlanning:

    def test_fallback_plan_is_valid_dag(self):
        plan = PlanningEngine.fallback_plan("wireguard lab")
        ordered = plan.topological()
        assert [n.id for n in ordered][0] == "preflight_env"
        ids = {n.id for n in ordered}
        assert {"write_tutorial", "gen_audio", "gen_video", "publish_ghost",
                "final_audit"} <= ids

    def test_topological_detects_cycles(self):
        plan = ExecutionPlan(goal="cyclic", nodes=[
            PlanNode(id="a", agent="sandbox", action="shell", depends_on=["b"]),
            PlanNode(id="b", agent="sandbox", action="shell", depends_on=["a"]),
        ])
        with pytest.raises(ValueError, match="Cycle"):
            plan.topological()

    def test_extract_json_from_noisy_llm_output(self):
        noisy = """Here is your plan!
        ```json
        {"goal": "lab", "nodes": [{"id": "n1", "agent": "content",
         "action": "generate_darija_lab", "params": {}, "depends_on": []}]}
        ```
        Hope that helps!"""
        data = PlanningEngine.extract_json(noisy)
        assert data and data["goal"] == "lab"

    def test_parse_plan_injects_auditor(self):
        engine = PlanningEngine()
        raw = json.dumps({
            "goal": "g",
            "nodes": [
                {"id": "w", "agent": "content", "action": "generate_darija_lab"},
                {"id": "m", "agent": "media", "action": "generate_audio",
                 "depends_on": ["w"]},
            ]})
        plan = engine._parse_plan(raw, "intent")
        assert plan is not None
        assert any(n.id == "final_audit" and n.agent == "auditor"
                   for n in plan.nodes)

    def test_normalize_action_maps_invented_verbs(self):
        cases = [
            ("sandbox", "research WireGuard VPN", "check_environment"),
            ("media", "record_audio", "generate_audio"),
            ("media", "create_thumbnail", "generate_cover"),
            ("media", "publish_tutorial", "publish_ghost"),
            ("media", "render_vertical_short", "generate_video"),
            ("content", "write_darija_tutorial", "generate_darija_lab"),
            ("auditor", "quality_audit", "full_audit"),
            ("media", "generate_audio", "generate_audio"),
        ]
        for agent, invented, expected in cases:
            assert PlanningEngine.normalize_action(agent, invented) == expected


# =========================================================================== #
# Unit — dispatcher                                                            #
# =========================================================================== #

class TestDispatch:

    @pytest.mark.parametrize("name,cls", [
        ("sandbox", CodeSandboxAgent),
        ("content", ContentArchitectAgent),
        ("auditor", AuditorAgent),
    ])
    def test_dispatch_returns_correct_agent(self, name, cls):
        assert isinstance(dispatch(name), cls)

    def test_dispatch_unknown_agent_raises(self):
        with pytest.raises(KeyError):
            dispatch("teleporter")


# =========================================================================== #
# Unit — error classification                                                  #
# =========================================================================== #

class TestRemediation:

    @pytest.mark.parametrize("error,expected", [
        ("quality=70/100 | regen:missing_svg,high_latin_ratio", "content_regen"),
        ("Connection refused on :9876", "wait_for_services"),
        ("node timed out", "escalate_timeout"),
        ("401 Unauthorized / invalid api token", "reload_secrets"),
        ("sqlite OperationalError: database is locked", "sqlite_backoff"),
        ("ffmpeg exited 1 / nvenc init fail", "ffmpeg_fallback"),
        ("HTTP 429 rate limit hit", "backoff_long"),
        ("something totally novel", "generic_backoff"),
    ])
    def test_classify(self, error, expected):
        assert Remediation.classify(error) == expected

    def test_extract_regen_codes(self):
        codes = Remediation.extract_regen_codes(
            "quality=60/100 security=90/100 | regen:missing_svg,high_latin_ratio "
            "| findings: no_explicit_troubleshooting")
        assert codes == ["missing_svg", "high_latin_ratio"]


# =========================================================================== #
# Self-healing loop                                                            #
# =========================================================================== #

class FlakyAgent(CodeSandboxAgent):
    calls = 0

    async def run(self, node, ctx):
        FlakyAgent.calls += 1
        if FlakyAgent.calls == 1:
            return NodeResult(node.id, False, error="connection refused :9876")
        if FlakyAgent.calls == 2:
            return NodeResult(node.id, False, error="node timed out")
        return NodeResult(node.id, True, output="recovered!")


class AlwaysFailsAgent(CodeSandboxAgent):
    async def run(self, node, ctx):
        raise RuntimeError("explosion cataclysmique")


class TestSelfHealing:

    def setup_method(self):
        FlakyAgent.calls = 0

    def test_recovers_after_transient_failures(self):
        executor = SelfHealingExecutor(default_retries=3)
        node = PlanNode(id="flaky", agent="sandbox", action="shell")
        result = run(executor.execute_node(node, AgentContext("t"),
                                            agent_override=FlakyAgent()))
        assert result.ok
        assert result.attempts == 3
        strategies = [t["strategy"] for t in executor.recovery_trace]
        assert "wait_for_services" in strategies
        assert "escalate_timeout" in strategies

    def test_exhausted_retries_report_failure(self):
        executor = SelfHealingExecutor(default_retries=3)
        node = PlanNode(id="doomed", agent="sandbox", action="shell")
        result = run(executor.execute_node(node, AgentContext("t"),
                                            agent_override=AlwaysFailsAgent()))
        assert not result.ok
        assert result.attempts == 3
        assert len(executor.recovery_trace) == 2


# =========================================================================== #
# Hardened Auditor                                                             #
# =========================================================================== #

class TestHardenedAuditor:

    def test_gold_tutorial_passes_strictly(self):
        res = run(_audit(GOLD_TUTORIAL))
        assert res.ok, res.output
        q = int(res.output.split("quality=")[1].split("/")[0])
        assert q >= 85

    def test_missing_svg_fails_with_regen_code(self):
        no_svg = GOLD_TUTORIAL.replace(SVG_BLOCK, "")
        res = run(_audit(no_svg))
        assert not res.ok
        assert "regen:missing_svg" in (res.error or "")

    def test_invalid_svg_detected(self):
        broken = GOLD_TUTORIAL.replace(SVG_BLOCK,
                                       '<svg viewBox="0 0 9"><unclosed/>')
        res = run(_audit(broken))
        assert not res.ok
        assert "invalid_svg" in (res.error or "")

    def test_low_code_density_penalized(self):
        thin = "\n".join(l for l in GOLD_TUTORIAL.splitlines()
                         if "```" not in l) + f"\n{SVG_BLOCK}\n"
        res = run(_audit(thin))
        assert "low_code_density" in (res.error or "")

    def test_english_prose_rejected_above_25_percent(self):
        english_dump = GOLD_TUTORIAL + ("\nThis paragraph explains how the tunnel "
                        "works with plenty of random english vocabulary thrown in, "
                        "talking about packets moving across interfaces quickly.")
        res = run(_audit(english_dump))
        sec_ok = res.ok
        flagged = "high_latin_ratio" in (res.error or "") \
            or "latin_prose" in (res.output or "")
        assert flagged

    def test_secret_leak_crashes_security_score(self):
        leaked = GOLD_TUTORIAL + "\nAPI key: fakekey1234567890abcdef1234"
        res = run(_audit(leaked))
        assert not res.ok
        sec = int(res.output.split("security=")[1].split("/")[0])
        assert sec < 60

    def test_placeholder_blocks_flagged(self):
        bad = GOLD_TUTORIAL + "\n```bash\n...\n```\nTODO fix later"
        res = run(_audit(bad))
        assert "placeholder:" in (res.output or "")


# =========================================================================== #
# Content Architect v2 — SVG handling                                          #
# =========================================================================== #

class TestContentSvg:

    def test_template_svg_is_valid_and_animated(self):
        svg = ContentArchitectAgent.default_topology_svg()
        parsed = ContentArchitectAgent.extract_svg(svg)
        assert parsed is not None
        assert "<animate" in parsed

    def test_extract_svg_from_noisy_llm_text(self):
        noisy = "Voici le diagramme:\n<svg viewBox='0 0 1 1'><g/></svg>\nDone."
        assert ContentArchitectAgent.extract_svg(noisy) is not None

    def test_invalid_llm_svg_returns_none(self):
        assert ContentArchitectAgent.extract_svg("<svg><oops></svg>") is None


# =========================================================================== #
# Integration — self-healing regeneration loop                                 #
# =========================================================================== #

class TestRegenLoop:

    def test_auditor_triggers_svg_regeneration(self, tmp_path):
        async def scenario():
            # Stub LLM: returns realistic content with code blocks & callouts
            GOOD_CONTENT = """## 🎯 علاش WireGuard؟
باش نركبو VPN خفيف往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复.

## ⚖️ المقارنة
| المعيار | WireGuard | OpenVPN |
|---|---|---|
| السرعة | عالي | متوسط |
| الكود | 4000 سطر | 100000+ |

## 🖥️ السيرفر往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复
```ini
[Interface]
Address = 10.8.0.1/24
ListenPort = 51820
SaveConfig = true
```
<div dir="rtl" class="callout warn">⚠️ نقطة أمنية : لا تشارك المفاتيح往复往复往复往复往复往复往复往复往复往复往复</div>

## 💻 الكليان往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复
```ini
[Interface]
Address = 10.8.0.2/24
[Peer]
AllowedIPs = 10.8.0.0/24
```

## ✅ التحقق往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复
验证往复往复往复往复往复往复往复往复往复往复往复
```bash
curl http://10.8.0.2:8000/test.txt
```
<div dir="rtl" class="callout warn">⚠️ نقطة أمنية : تأكد من الفايروول往复往复往复往复往复往复往复往复往复往复往复</div>

## 🔥 Troubleshooting往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复
### ❌ Handshake往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复
```bash
sudo tcpdump -i any udp port 51820
```
### ❌ Keys往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复往复
```bash
wg show
```
"""

            GOOD_TROUBLESHOOTING = """## 🔥 Troubleshooting

### ❌ Handshake does not establish
<div dir="rtl" class="callout warn">⚠️ نقطة أمنية : تأكد من فتح البورت في الفايروول قبل التشخيص</div>

**السبب**: الفايروول يسد UDP port 51820.
**تشخيص**:
```bash
sudo tcpdump -i any udp port 51820 -nn
```
**الحل**:
```bash
sudo iptables -A INPUT -p udp --dport 51820 -j ACCEPT
```

### ❌ Keys swapped between peers
<div dir="rtl" class="callout warn">⚠️ نقطة أمنية : المفاتيح私有 تبقى في السيرفر فقط</div>

**الsymptom**: wg show يظهر "handshake" but no transfer.
**تشخيص**:
```bash
wg show
```
**الحل**: نبدلو الـ Private Key ونعاودو:
```bash
wg-quick down wg0 && wg-quick up wg0
```
"""
            async def stub_gen(prompt: str, **kw) -> str:
                if "PASS SVG" in prompt or "PASS 2" in prompt:
                    return ("voila:\n" +
                            ContentArchitectAgent.default_topology_svg())
                if "PASS 4" in prompt or "TROUBLESHOOTING" in prompt:
                    return GOOD_TROUBLESHOOTING
                return GOOD_CONTENT

            content_agent = ContentArchitectAgent(generate_fn=stub_gen)

            import genio_executive_core as core
            orig_dispatch = core.dispatch

            def fake_dispatch(name):
                return content_agent if name == "content" else orig_dispatch(name)
            core.dispatch = fake_dispatch

            try:
                # Build a deficient article (no SVG) using new v3.5 section keys
                sections = {
                    "title": "Lab WG",
                    "hero": '<div dir="rtl">🎯 في هالمقال باش نركبو VPN مريقل</div>',
                    "intro": "## 🎯 علاش هذه التقنية؟\n_wireguard يستخدم curve25519往复与ChaCha20-Poly1305往复，比OpenVPN更轻量。",
                    "topology": "## 🗺️ المخطط المدير\nLAN client = 192.168.1.0/24\nTunnel = 10.8.0.0/24\nLAN distant = 192.168.100.0/24\nServer wg0 = 10.8.0.1\nPort = 51820/UDP",
                    "table": "## ⚖️ المقارنة التقنية\n| المعيار | WireGuard | OpenVPN |\n|---|---|---|\n| السرعة | عالي | متوسط |\n| الكود | 4000 سطر | 100000+ |\n| التشفير | ChaCha20 | AES-256 |\n\nWireGuard هو الأخف والأسرع.",
                    "svg": "",
                    "server": "## 🖥️ الجانب السيرفر\nsysctl -w net.ipv4.ip_forward=1\niptables -t nat -A POSTROUTING -s 10.8.0.0/24 -o eth0 -j MASQUERADE\nwg0.conf:\n```ini\n[Interface]\nAddress = 10.8.0.1/24\nListenPort = 51820\n```\nwg show",
                    "client": "## 💻 الجانب الكليان\nwg0.conf client:\n```ini\n[Interface]\nAddress = 10.8.0.2/24\n[Peer]\nAllowedIPs = 10.8.0.0/24\n```\nwg-quick up wg0",
                    "validation": "## ✅ التحقق النهائي\nwg show\nping -c 2 -I wg0 10.8.0.2\ncurl http://10.8.0.2:8000/test.txt",
                    "troubleshooting": f"## 🔥 Troubleshooting\n{CALLOUT_2}\n### ❌ Handshake\nwg show\niptables open port 51820\n### ❌ Keys swapped\nswap keys back",
                }
                deficient = ContentArchitectAgent._assemble(sections)

                md_file = tmp_path / "lab.md"
                md_file.write_text(deficient, encoding="utf-8")

                ctx = AgentContext("wireguard lab")
                ctx.scratch.update(title="Lab WG", content=deficient,
                                   tags=["linux"], sections=sections,
                                   env_checks={"ollama": True,
                                               "cinema_engine": True})
                ctx.artifacts["article_md"] = Artifact("md", str(md_file))

                healing = SelfHealingExecutor(default_retries=2)
                node = PlanNode(id="final_audit", agent="auditor",
                                action="full_audit")
                result = await healing.execute_node(node, ctx)
                return result, ctx, healing
            finally:
                core.dispatch = orig_dispatch

        result, ctx, healing = run(scenario())

        assert result.ok, result.output                       # healed on retry
        assert result.attempts == 2                           # 1 fail + regen + pass
        assert "<svg" in ctx.scratch["content"]               # svg injected
        strategies = [t["strategy"] for t in healing.recovery_trace]
        assert "content_regen" in strategies                  # recovery logged


# =========================================================================== #
# Self-learning memory engine                                                  #
# =========================================================================== #

class TestMemoryEngine:

    def test_seeds_default_rules_on_first_use(self, tmp_path):
        mem = MemoryEngine(tmp_path / "mem.json")
        assert len(mem.data["rules"]) == 12         # 4 v2.3 + 3 directives v3 + 5 v3.5
        assert any("tableau comparatif" in r for r in mem.data["rules"])
        assert any("PNG fixes" in r for r in mem.data["rules"])
        assert (tmp_path / "mem.json").exists()

    def test_inject_into_appends_rules_block(self, tmp_path):
        mem = MemoryEngine(tmp_path / "mem.json")
        out = mem.inject_into("BASE PROMPT")
        assert out.startswith("BASE PROMPT")
        assert "MEMORY RULES" in out
        assert "tableau comparatif" in out

    def test_record_rejection_synthesizes_and_dedups(self, tmp_path):
        mem = MemoryEngine(tmp_path / "mem.json")
        before = len(mem.data["rules"])
        added = mem.record_rejection(["missing_table", "missing_svg"],
                                     source="auditor")
        assert added, "expected synthesized rules"
        assert len(mem.data["rules"]) == before + len(added)
        # second identical rejection adds nothing
        added2 = mem.record_rejection(["missing_table"], source="auditor")
        assert added2 == []
        assert mem.data["stats"]["rejections"] == 2
        # lesson trail kept
        assert mem.data["lessons"][-1]["codes"] == ["missing_table"]

    def test_unknown_codes_are_ignored_gracefully(self, tmp_path):
        mem = MemoryEngine(tmp_path / "mem.json")
        added = mem.record_rejection(["mystery_code_xyz"])
        assert added == []
        assert mem.data["stats"]["rejections"] == 1

    def test_user_feedback_becomes_rule(self, tmp_path):
        mem = MemoryEngine(tmp_path / "mem.json")
        rule = "Toujours citer la version d'Ubuntu en prérequis"
        mem.record_feedback(rule)
        mem.record_feedback(rule)          # duplicate ignored
        assert mem.data["rules"].count(rule) == 1

    def test_global_memory_singleton_uses_real_file(self):
        m1, m2 = get_memory(), get_memory()
        assert m1 is m2


# =========================================================================== #
# v2.3 hard gates: table, callouts, literal phrasing                           #
# =========================================================================== #

class TestV23Gates:

    def test_missing_table_fails_hard(self):
        no_table = "\n".join(
            l for l in GOLD_TUTORIAL.splitlines()
            if not l.strip().startswith("|"))
        res = run(_audit(no_table))
        assert not res.ok
        assert "regen:missing_table" in (res.error or "")

    def test_single_callout_fails_hard(self):
        one_callout = GOLD_TUTORIAL.replace(CALLOUT_2, "")
        res = run(_audit(one_callout))
        assert not res.ok
        assert "regen:missing_callouts" in (res.error or "")

    def test_literal_translation_banned(self):
        bad = GOLD_TUTORIAL + "\nنحن نقوم بتثبيت الحزم الآن."
        res = run(_audit(bad))
        assert "literal_translation" in (res.error or "")

    def test_content_agent_prompt_includes_memory_and_rigma(self, tmp_path):
        async def scenario():
            agent = ContentArchitectAgent(generate_fn=lambda **kw: "")
            return agent.memory.inject_into(agent._pass1_prompt("wg lab"))
        out = run(scenario())
        assert "MEMORY RULES" in out
        assert "tableau comparatif" in out
        assert "Tunnel WireGuard من الصفر" in out   # Rigma few-shot present
        assert RIGMA_FEWSHOT.strip()[:20] in out


# =========================================================================== #
# Integration — full dry pipeline with injected LLM stub                       #
# =========================================================================== #

class TestEndToEndDryRun:

    def test_pipeline_dispatch(self, tmp_path):
        async def scenario():
            async def stub_generate(prompt: str, topic: str = "") -> str:
                return GOLD_TUTORIAL

            content_agent = ContentArchitectAgent(generate_fn=stub_generate)
            plan = ExecutionPlan(goal="wireguard lab", nodes=[
                PlanNode(id="preflight_env", agent="sandbox",
                         action="check_environment", timeout_s=30),
                PlanNode(id="write_tutorial", agent="content",
                         action="generate_darija_lab",
                         depends_on=["preflight_env"]),
                PlanNode(id="final_audit", agent="auditor",
                         action="full_audit",
                         depends_on=["write_tutorial"]),
            ])

            healing = SelfHealingExecutor(default_retries=2)
            ctx = AgentContext(goal=plan.goal, dry_run=True)
            results: Dict[str, NodeResult] = {}

            for node in plan.topological():
                if node.agent == "content":
                    results[node.id] = await healing.execute_node(
                        node, ctx, agent_override=content_agent)
                else:
                    results[node.id] = await healing.execute_node(node, ctx)
            return results, ctx

        results, ctx = run(scenario())

        assert all(r.ok for r in results.values()), \
            {k: v.error for k, v in results.items()}
        assert "article_md" in ctx.artifacts
        assert "wireguard" in (ctx.scratch.get("tags") or [])
        assert ctx.scratch["audit"]["security"] >= 60
