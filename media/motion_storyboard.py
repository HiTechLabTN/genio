"""Genio — Motion Storyboard Generator (4-act, high-retention Darija videos).

Turns a technical topic into a structured motion-graphics storyboard JSON with:

  * ``hook``           — 0-5s problem / mistake warning in Darija (glitch entry)
  * ``metaphor``       — real-world analogy viewers already understand
  * ``spec_breakdown`` — exploded spec cards with highlight colors
  * ``cta``            — redirect to the full article on the HiTech Lab site

Every act carries motion-graphics cues: ``animation`` codes, ``visual_cue``
instructions for the motion designer, ``sfx`` sound-effect triggers and an
accent ``color``.

CLI:
    python3 -m media.motion_storyboard --topic "Choosing CPU / RAM for Home Server"
    python3 -m media.motion_storyboard --topic "Docker Volumes" --out reports/storyboard.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loguru import logger  # noqa: E402

from config import GENIO_DIR, get_config  # noqa: E402

DEFAULT_OUT = GENIO_DIR / "reports" / "storyboard.json"
ARTICLE_SITE = get_config().ghost.url.rstrip("/") or "https://lab.hitech.tn"

SCHEMA = "genio.motion_storyboard.v1"

# --------------------------------------------------------------------------- #
# Motion-graphics primitives                                                    #
# --------------------------------------------------------------------------- #

SFX_LIBRARY: Dict[str, str] = {
    "whoosh": "soft whoosh sweep (150ms)",
    "glitch": "digital glitch stutter x2",
    "pop": "soft pop reveal",
    "tap": "typewriter tick per card",
    "count_up": "number count-up ticks",
    "impact": "bass impact hit",
    "chime": "bright confirmation chime",
    "scan": "radar scan sweep",
    "slide": "card slide-in swish",
    "heartbeat": "low heartbeat thump",
    "zap": "electric zap burst",
}

TRANSITIONS: List[Dict[str, str]] = [
    {"from": "hook", "to": "metaphor", "style": "glitch_split_wipe"},
    {"from": "metaphor", "to": "spec_breakdown", "style": "cards_explode"},
    {"from": "spec_breakdown", "to": "cta", "style": "zoom_punch_white_flash"},
]

PALETTE: Dict[str, str] = {
    "background": "#030712",
    "surface": "#0f172a",
    "primary": "#00f0ff",
    "accent": "#00ff87",
    "warn": "#f43f5e",
    "text": "#f8fafc",
}

# Schema for a single spec card.
_SPEC_KEYS = ("label", "value", "unit", "color", "highlight")


def _card(label: str, value: str, unit: str = "", color: str = "#22d3ee",
          highlight: bool = False) -> Dict[str, object]:
    return {"label": label, "value": value, "unit": unit,
            "color": color, "highlight": highlight}


# --------------------------------------------------------------------------- #
# Domain knowledge: specs, metaphors, hooks                                     #
# --------------------------------------------------------------------------- #

# keyword -> (metaphor_priority, hook, specs)
DOMAIN_MAP: Dict[str, Dict[str, object]] = {
    "cpu": {
        "hook": "غلطة يخلص فيها أغلب أصحاب الـ Home Server: تشري معالج غالي بالأنوية الكثيرة، وتبرىش أغلبهم خالين. تعرف قبل ما تصرف فلوسك شنو يلزمك.",
        "metaphor": "المعالج كيف مطبخ عائلي: وحدة شاف ومعه طبّاخين (الأنوية). أكثر طبّاخين عندك، أكثر حوايج تصايبهم في نفس الوقت — ولكن إذا ما عندكش الهدرة باش تربيهم (الـ RAM والقرص)، الطبق يخرج متأخر.",
        "scene": "مطبخ أنيمي متحرك، شاف مركزي يوزّع الأطباق بين الطبّاخين",
        "specs": [
            _card("الأنوية Cores", "8", "Cores", "#22d3ee", True),
            _card("الخيوط Threads", "16", "Threads", "#22d3ee"),
            _card("التردد الأساسي", "3.8", "GHz", "#38bdf8"),
            _card("التردد الأقصى", "5.1", "GHz", "#38bdf8"),
            _card("الذاكرة المخبئية", "32", "MB", "#818cf8"),
            _card("الاستهلاك TDP", "65", "W", "#f59e0b"),
        ],
    },
    "ram": {
        "hook": "هذي الغلطة اللي قتلت أجهزة التجميع: تزيد في قوة المعالج وتنسى الـ RAM. وغيرة: التركيب المغلوط وخلط السعات يعطّي النظام كامل.",
        "metaphor": "الـ RAM كيف طاولة العمل في المكتب: إذا كانت صغيرة، حتى ولو عندك أكثر صناديق (برامج)، ما تنجمش تخدم فيهم كاملين في نفس الوقت وكولشي يتوقّف.",
        "scene": "مكتب متحرك، طاولة تكبر وتصغر مع عدد الصناديق اللي عليها",
        "specs": [
            _card("السعة Capacity", "32", "GB", "#00ff87", True),
            _card("السرعة", "6000", "MHz", "#4ade80"),
            _card("النمط Channels", "DUAL", "Channel", "#22d3ee"),
            _card("الجيل Type", "DDR5", "", "#38bdf8"),
            _card("زمن التقليل", "CL", "30", "#818cf8"),
            _card("تصحيح الأخطاء", "Non", "ECC", "#f59e0b"),
        ],
    },
    "storage": {
        "hook": "مشكلة عمرها العمر: تفرح بقرص صلب رخيص، وكل ما يشغّل النظام يصيح البطء. الـ SSD المعاصر ماشي كمالية، هو الضرورة.",
        "metaphor": "SSD مقابل HDD كيف فنجان قهوة سريع مقابل محل يقلّب في الدفاتر القديمة: الحاجة اللي تاخذ ثانية مع SSD تاخذ نصف دقيقة مع القرص القديم.",
        "scene": "مقهى متحرك، فنجان يطلع بسرعة أمام دفتر كتب قديم يتقلّب بطيء",
        "specs": [
            _card("النوع", "NVMe", "Gen.4", "#00ff87", True),
            _card("القراءة", "7000", "MB/s", "#22d3ee", True),
            _card("الكتابة", "6000", "MB/s", "#22d3ee"),
            _card("السعة", "2", "TB", "#4ade80"),
            _card("التحمّل Endurance", "1200", "TBW", "#818cf8"),
            _card("الذاكرة المؤقتة", "SLC", "Cache", "#f59e0b"),
        ],
    },
    "gpu": {
        "hook": "قبل ما تشري كارت غالي تذكّر: الذكاء الاصطناعي يسكن في الـ VRAM — أكثر VRAM، أكبر الموديلات و أسرع الردود، ومش في قوة الشكل.",
        "metaphor": "الـ GPU كيف معمل فيه ألف عامل يخدمو بالتوازي: كل واحد يحسب جزء صغير من العمل، فالعمل الكبير يطلع في ثواني ماشي في ساعات.",
        "scene": "معمل متحرك، ملايين خطوط معالجة تتحرك بشكل متوازي ثم تتناغم في شاشة العمل",
        "specs": [
            _card("الذاكرة VRAM", "16", "GB", "#00ff87", True),
            _card("عرض النطاق", "600", "GB/s", "#22d3ee", True),
            _card("وحدات المعالجة", "8448", "CUDA", "#22d3ee"),
            _card("الاستهلاك", "200", "W", "#f59e0b"),
            _card("نسخة CUDA", "12.1", "", "#818cf8"),
            _card("التغذية", "6+2", "Pin", "#38bdf8"),
        ],
    },
    "docker": {
        "hook": "كل من يبني حاوية بدون Volumes يواعد نفسه في الضياعة: أعدت تشغيل الحاوية؟ ما لقيتش بياناتك. ها الحل من الأول.",
        "metaphor": "الحاوية كيف كرتون في مركب شحن: كل كرتون فيه حاجة معزولة، ولكن إذا ما وفّرشالو رصيف يتثبّت فيه (Volume)، يضيع وسط البحر.",
        "scene": "مركب شحن متحرك، حاويات ملوّنة تتنزّل على أرصفة بنفس الحجم",
        "specs": [
            _card("النواة الأساسية", "Volume", "persist", "#00ff87", True),
            _card("الشبكة Network", "bridge", "isolated", "#22d3ee", True),
            _card("الصورة Image", "ubuntu", "22.04", "#22d3ee"),
            _card("ربط المنفذ", "8080", ":80", "#4ade80"),
            _card("إعادة التشغيل", "unless", "stopped", "#818cf8"),
            _card("الموارد", "2 CPU /", "4 GB", "#f59e0b"),
        ],
    },
    "network": {
        "hook": "إذا كانت خدماتك مكشوفة للعالم بلا VPN، أنت تدعو المتطفلين للشاي. النفق المشفر ماشي ترف، هو الجدار الأول.",
        "metaphor": "النفق كيف نفق الجبل: ياخذك من نقطة لأخرى بمسار خاص ومعزول، ومحدش يسمع ولا يرى شحال كاين في الرحلة.",
        "scene": "جبل متحرك بنفق مضيء، حزمة بيانات صغيرة تسافر داخله بأمان",
        "specs": [
            _card("البروتوكول", "WireGuard", "", "#00ff87", True),
            _card("المنفذ", "51820", "UDP", "#22d3ee"),
            _card("التشفير", "ChaCha20", "Poly1305", "#38bdf8"),
            _card("MTU", "1420", "bytes", "#818cf8"),
            _card("النظائر Peers", "2", "nodes", "#4ade80"),
            _card("الإنتاجية", "~1", "Gbps", "#f59e0b"),
        ],
    },
    "server": {
        "hook": "غلطة التجميع الأغلى: تخطّط للسيرفر بدون نية للمراقبة، وتلقى روحك قدام جهاز يوقف بلا إنذار. توا نرتبو من دقة البداية.",
        "metaphor": "السيرفر كيف مطار صغير: الـ CPU هو برج المراقبة، الـ RAM هو مدرج الهبوط، والقرص هو المخازن — المطار عبقري فقط إذا داروا ثلاثتهم مع بعض.",
        "scene": "مطار مصغّر متحرك: برج مراقبة يوتّراض مع مدرج ومخازن مضيئة",
        "specs": [
            _card("المعالج CPU", "8", "Cores", "#22d3ee", True),
            _card("الذاكرة RAM", "32", "GB", "#00ff87", True),
            _card("التخزين", "2", "TB NVMe", "#00ff87"),
            _card("مصدر الطاقة", "80+", "Gold", "#f59e0b"),
            _card("نظام التشغيل", "Ubuntu", "22.04 LTS", "#818cf8"),
            _card("هدف التوفر", "99", "%", "#4ade80"),
        ],
    },
}

# Encoding order for hook/metaphor selection (highest specificity first).
# RAM is chosen before CPU so a "CPU / RAM" decision topic lands on the
# classic workbench metaphor instead of the kitchen one.
_DOMAIN_PRIORITY = ("ram", "cpu", "storage", "gpu", "network", "docker", "server")

# Topic keyword -> domain
_TOPIC_KEYWORDS: List[Tuple[Tuple[str, ...], str]] = [
    (("cpu", "processor", "معالج", "أنوية", "core"), "cpu"),
    (("ram", "memory", "ذاكرة", "الرام", "dram"), "ram"),
    (("ssd", "nvme", "hdd", "disk", "storage", "تخزين", "قرص", "هارد", "m.2"), "storage"),
    (("gpu", "graphics", "كارت", "رسومات", "cuda", "vram", "ai server", "llm"), "gpu"),
    (("vpn", "wireguard", "network", "شبكة", "tunnel", "نفق"), "network"),
    (("docker", "container", "حاوية", "حاويات", "compose", "volume", "kubernetes"), "docker"),
    (("server", "سيرفر", "proxmox", "home server", "nas", "home lab", "truenas"), "server"),
]

GENERIC_HOOK = "هذي المشكلة اللي ضيّعت وقت الغالبية الكبيرة: تشري العتاد بداياتك ماشي بالحاجة، وتتفاجأ بيه آخر حاجة. نتفكّرو توا في الحل من الجذور."
GENERIC_METAPHOR = "أي بنية تقنية كيف بناء عمارة: أولاً الأساسات (العتاد والبنية)، ثم الجدران (الخدمات)، وفوق راسك السقف (المراقبة). توا نكسرو التفاصيل حاجة حاجة."
GENERIC_SPECS = [
    _card("المعالج CPU", "8", "Cores", "#22d3ee", True),
    _card("الذاكرة RAM", "32", "GB", "#00ff87", True),
    _card("التخزين", "2", "TB NVMe", "#00ff87"),
    _card("الشبكة", "1", "Gbps", "#38bdf8"),
    _card("الطاقة", "80+", "Gold", "#f59e0b"),
    _card("المراقبة", "Live", "Telemetry", "#4ade80"),
]


def _match_domains(topic: str) -> List[str]:
    low = topic.lower()
    matched: List[str] = []
    for keywords, domain in _TOPIC_KEYWORDS:
        if any(k in low for k in keywords):
            matched.append(domain)
    # de-dupe, keep priority order
    seen = []
    for d in matched:
        if d not in seen:
            seen.append(d)
    return seen or ["server"]


def _slugify(topic: str, fallback: str = "genio-guide") -> str:
    ascii_slug = re.sub(r"[^a-z0-9]+", "-", unicodedata.normalize(
        "NFKD", topic.lower()).encode("ascii", "ignore").decode())
    ascii_slug = ascii_slug.strip("-")
    if len(ascii_slug) >= 3:
        return ascii_slug
    # Topics written fully in Arabic get a stable English slug hint.
    return fallback


# --------------------------------------------------------------------------- #
# Storyboard builder                                                            #
# --------------------------------------------------------------------------- #

class MotionStoryboardGenerator:
    """Generates the 4-act motion-graphics storyboard for a technical topic."""

    def __init__(self, topic: str, site_url: str = ARTICLE_SITE):
        self.topic = topic.strip()
        if not self.topic:
            raise ValueError("topic must not be empty")
        self.site_url = site_url.rstrip("/")
        self._domains = _match_domains(self.topic)
        self._domain = next((d for d in _DOMAIN_PRIORITY if d in self._domains),
                            self._domains[0])
        self.slug = _slugify(self.topic, fallback=f"{self._domain}-guide")

    # -- act builders -------------------------------------------------------- #
    def _act(self, act_id: str, start: int, end: int, voiceover: str,
             scene: str, animation: str, sfx: List[str], color: str,
             on_screen: str = "") -> Dict[str, object]:
        return {
            "act": act_id,
            "dialogue_text": on_screen or voiceover,
            "voiceover": voiceover,
            "scene": scene,
            "visual_cue": f"{animation} on surface; on-screen Arabic RTL text",
            "animation": animation,
            "sfx": [{"trigger": s, "desc": SFX_LIBRARY.get(s, s)} for s in sfx],
            "color": color,
            "timing_s": {"start": start, "end": end},
            "time_code": f"{self._tc(start)} - {self._tc(end)}",
        }

    @staticmethod
    def _tc(seconds: int) -> str:
        return f"{seconds // 60:02d}:{seconds % 60:02d}"

    def _build_hook(self, start: int, end: int) -> Dict[str, object]:
        voiceover = str(DOMAIN_MAP[self._domain]["hook"])
        act = self._act("hook", start, end,
                        voiceover,
                        "تحذير Glitch: نص أحمر قشّاش يرتجّ ثم يستقر",
                        "glitch_in", ["glitch", "whoosh"], PALETTE["warn"],
                        on_screen="⚠️ غلطة شائعة")
        act["warning"] = True
        return act

    def _build_metaphor(self, start: int, end: int) -> Dict[str, object]:
        act = self._act("metaphor", start, end,
                        str(DOMAIN_MAP[self._domain]["metaphor"]),
                        str(DOMAIN_MAP[self._domain]["scene"]),
                        "scale_in", ["pop", "slide"], PALETTE["primary"],
                        on_screen=f"تشبيه {self._domain}")
        return act

    def _build_spec_breakdown(self, start: int, end: int) -> Dict[str, object]:
        specs: List[Dict[str, object]] = []
        seen: set = set()
        for d in self._domains:
            for card in DOMAIN_MAP[d]["specs"]:  # type: ignore[union-attr]
                key = (card["label"], card["value"])
                if key in seen:
                    continue
                seen.add(key)
                specs.append(card)
            if len(specs) >= 8:
                break
        if not specs:
            specs = list(GENERIC_SPECS)

        act = self._act("spec_breakdown", start, end,
                        "هذي الأرقام المغيّرة للقرار — كل كارت يشرح مغزاه بعينه، ونشيرو للمعلومة الحاسمة بالأخضر.",
                        "بطاقات مواصفات تنفجر من المركز وترتب في شبكة، الأهم تقزّز ويلوّن",
                        "cards_explode", ["count_up", "tap"], PALETTE["accent"],
                        on_screen="تفاصيل المواصفات")
        act["specs"] = specs
        act["cards_animation"] = {"style": "explode_grid", "stagger_ms": 180}
        act["highlight"] = [
            i for i, c in enumerate(specs) if c.get("highlight")
        ]
        return act

    def _build_cta(self, start: int, end: int) -> Dict[str, object]:
        url = f"{self.site_url}/{self.slug}/"
        voiceover = ("تحب توصل للمقال الكامل بالتفسير والأوامر الجاهزة؟ "
                     f"زور {self.site_url}/{self.slug}/ و طبّق الخطوة بخطوة في لابك.")
        act = self._act("cta", start, end, voiceover,
                        "تسلسل Zoom Punch إلى شاشة بيضاء ثم ظهور رابط الموقع بألوان النيون",
                        "zoom_punch", ["impact", "chime"], PALETTE["primary"],
                        on_screen="للمقال الكامل زور الموقع")
        act["target"] = {
            "platform": "website",
            "url": url,
            "button_text": "📖 اقرأ المقال الكامل",
            "article_hint": f"{self.site_url}/{self.slug}/",
        }
        return act

    # -- public API ---------------------------------------------------------- #
    def build(self) -> Dict[str, object]:
        """Assemble the full storyboard document."""
        return {
            "schema": SCHEMA,
            "project": "HiTech Lab — Genio Motion",
            "topic": self.topic,
            "title": self.topic,
            "slug": self.slug,
            "article_url": f"{self.site_url}/{self.slug}/",
            "lang": "ar-TN",
            "total_duration_s": 56,
            "created_variant": self._domain,
            "resolution": "1920x1080",
            "fps": 30,
            "palette": dict(PALETTE),
            "motion": {
                "transitions": list(TRANSITIONS),
                "sfx_library": dict(SFX_LIBRARY),
                "typography": {"font": "Cairo", "mono": "JetBrains Mono",
                               "direction": "rtl"},
            },
            "acts": {
                "hook": self._build_hook(0, 5),
                "metaphor": self._build_metaphor(5, 18),
                "spec_breakdown": self._build_spec_breakdown(18, 42),
                "cta": self._build_cta(42, 56),
            },
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.build(), ensure_ascii=False, indent=indent)

    def save(self, path: str | Path) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(self.to_json(), encoding="utf-8")
        logger.info(f"🎬 Storyboard written -> {out}")
        return out


def main(argv: Optional[List[str]] = None) -> Path:
    parser = argparse.ArgumentParser(
        prog="media.motion_storyboard",
        description="Genio — 4-act motion storyboard generator (Darija).")
    parser.add_argument("--topic", required=True,
                        help="Technical topic, e.g. 'Choosing CPU / RAM for Home Server'")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT,
                        help="Output path (default: reports/storyboard.json)")
    args = parser.parse_args(argv)

    gen = MotionStoryboardGenerator(args.topic)
    path = gen.save(args.out)
    logger.info(f"🌐 matched domain '{gen._domain}' · slug '{gen.slug}' · "
                f"acts 4 · sfx triggers included")
    return path


if __name__ == "__main__":
    main()