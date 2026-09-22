"""Social Media Skills for Genio — darja tech-post formatter.

Formats article / video content into engagement-ready posts for LinkedIn,
X (Twitter) and Facebook in TechLab Tunisian-Darja tone, tagging the projects:

    #HighTechLab  #RT2R  #PopOS  #Gemma4

Inspired by the social-planning flow used for HighTechLab project content.
The ReAct loop calls this via the registered **social_post** tool; the payload
is a JSON string::

    {"content_type": "article", "raw_text": "...", "platform": "linkedin"}

content_type options: "article" | "rt2r_video" | "auto"
platform options:      "linkedin" | "twitter" | "facebook"
"""
from __future__ import annotations

import json
from typing import Dict, Tuple

HASHTAG_POOL = ["#HighTechLab", "#RT2R", "#PopOS", "#Gemma4", "#Linux", "#AI", "#Tunisia"]
PLATFORM_LIMITS = {"linkedin": 3000, "twitter": 280, "facebook": 2000}

_CT_LABEL = {
    "article": "مقال",
    "rt2r_video": "فيديو",
    "auto": "محتوى",
    "update": "تحديث",
}


def _hook(content_type: str) -> str:
    ct = content_type or "auto"
    tag = _CT_LABEL.get(ct, _CT_LABEL["auto"])
    hooks = {
        "article": f"🟢 {tag} جديد من HighTechLab اللي فمختبرنا:",
        "rt2r_video": f"🎬 {tag} جديد من RT2R — نكملو رحلة تشغيل المختبر بنفسنا:",
        "auto": f"🟢 {tag} جديد من فرق HighTechLab:",
        "update": f"⚡ تحديث سريع من HighTechLab:",
    }
    return hooks.get(ct, hooks["auto"])


def _teaser(raw_text: str, limit: int) -> str:
    txt = (raw_text or "").strip().replace("\n", " ")
    if not txt:
        return "تفاصيل كاملة داخل المقال 🚀"
    if len(txt) > limit:
        cut = txt.rfind(" ", 0, limit // 2)
        txt = txt[:cut if cut > 0 else limit // 2] + "…"
    return txt


def _hashtags(platform: str, content_type: str) -> Tuple[str, ...]:
    base = ["#HighTechLab", "#RT2R"]
    extra = {"PopOS": "#PopOS", "Gemma4": "#Gemma4", "Linux": "#Linux", "AI": "#AI", "TU": "#Tunisia"}
    tags = list(base)
    if content_type == "rt2r_video":
        tags += [extra["PopOS"], extra["Gemma4"]]
    elif platform == "linkedin":
        tags += [extra["Gemma4"], extra["AI"], extra["Linux"]]
    elif platform == "twitter":
        tags += [extra["Gemma4"], extra["TU"]]
    else:
        tags += [extra["Linux"], extra["AI"]]
    return tuple(tags)


def format_social_media_post(
    content_type: str,
    raw_text: str,
    platform: str,
) -> Dict[str, object]:
    """Build a platform-shaped darja post.

    Returns a dict with ``content``, ``char_count``, ``platform``,
    ``content_type``, ``hashtags`` and ``status`` so the loop can evaluate the
    result and hand it to a publisher.
    """
    platform = (platform or "linkedin").lower().strip()
    content_type = (content_type or "auto").lower().strip()
    if platform not in PLATFORM_LIMITS:
        return {
            "status": "error",
            "error": f"unsupported platform '{platform}' (use linkedin | twitter | facebook)",
            "platform": platform, "content": "", "char_count": 0, "hashtags": (),
        }
    if content_type not in _CT_LABEL:
        content_type = "auto"

    limit = PLATFORM_LIMITS[platform]
    tags = _hashtags(platform, content_type)
    tag_line = " ".join(tags)

    if platform == "twitter":
        teaser = _teaser(raw_text, 130)
        body = f"{_hook(content_type)}\n\n{teaser}\n\n{tag_line}"
    elif platform == "linkedin":
        teaser = _teaser(raw_text, 500)
        body = (
            f"{_hook(content_type)}\n\n"
            f"{teaser}\n\n"
            "نبني ونشغلو كلشي بنفسنا، سطر بسطر، من السيرفرات إلى الذكاء الاصطناعي "
            "اللي يخدم على نموذج Gemma4 فوق Pop!_OS. 🧠\n\n"
            "رتيكشن أو تعليق باش نكملو ونبعثو الحلقات الباقية بالتفصيل.\n\n"
            f"{tag_line}"
        )
    else:  # facebook
        teaser = _teaser(raw_text, 300)
        body = (
            f"{_hook(content_type)}\n\n"
            f"{teaser}\n\n"
            "التفاصيل والكود الكل داخل الموقع. شارك برأيك! ⚙️\n\n"
            f"{tag_line}"
        )

    return {
        "status": "ok",
        "platform": platform,
        "content_type": content_type,
        "hashtags": tags,
        "content": body,
        "char_count": len(body),
    }


def invoke_social_post(payload: object) -> Dict[str, object]:
    """ReAct entry point: ``payload`` is a JSON string of the args."""
    if isinstance(payload, dict):
        args = payload
    else:
        try:
            args = json.loads(str(payload or ""))
        except json.JSONDecodeError:
            return {
                "status": "error",
                "error": "social_post needs JSON args: "
                         '{"content_type": "...", "raw_text": "...", "platform": "..."}',
            }
    if not isinstance(args, dict):
        return {"status": "error", "error": "social_post args must be a JSON object"}
    return format_social_media_post(
        str(args.get("content_type", "auto")),
        str(args.get("raw_text", "")),
        str(args.get("platform", "linkedin")),
    )


if __name__ == "__main__":
    from pprint import pprint

    demo = json.dumps({
        "content_type": "article",
        "raw_text": "فهم هيكلة ملفات لينكس هو الفرق بين مهندس يعرف كيفاش يتحرك ويصلح المشاكل في ثواني.",
        "platform": "linkedin",
    })
    pprint(invoke_social_post(demo), sort_dicts=False, width=100)