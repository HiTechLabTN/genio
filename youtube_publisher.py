"""
HiTech Lab — Genio YouTube Publisher (v3)

Builds an optimized publication payload (Darija/English title, chaptered
description, technical tags) for every lab video. Performs the real upload
when OAuth credentials are available; otherwise emits the payload as a
ready-to-use artifact.

Credential contract (env):
    YOUTUBE_CLIENT_SECRET_PATH   path to OAuth client_secret.json
    YOUTUBE_TOKEN_PATH           path to stored token.pickle / token.json
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

PAYLOAD_DIR = Path("/data/ai_tools/genio/youtube_payloads")


@dataclass
class Chapter:
    ts: str        # "00:12"
    title: str


@dataclass
class YouTubePayload:
    title: str
    description: str
    tags: List[str]
    category_id: str = "28"            # Science & Technology
    privacy_status: str = "public"
    made_for_kids: bool = False
    lab_url: str = "https://lab.hitech.tn"
    video_path: str = ""
    chapters: List[Chapter] = field(default_factory=list)


def _fmt_ts(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"


def build_wireguard_payload(video_path: str, video_duration_s: float,
                            article_url: str, lab_title: str = "") -> YouTubePayload:
    """Chaptered description aligned with the recorded lab steps."""
    steps = [
        ("🧰 Installation des outils dans la sandbox", 0.0),
        ("🔑 Génération réelle des clés WireGuard", max(1, int(video_duration_s * 0.15))),
        ("🔥 L'erreur wg show avant configuration", max(2, int(video_duration_s * 0.35))),
        ("⚙️ Configuration wg0.conf + montage interface", max(3, int(video_duration_s * 0.55))),
        ("✅ Vérification finale : handshake + ping", max(4, int(video_duration_s * 0.8))),
    ]
    chapters = [Chapter(_fmt_ts(t), title) for title, t in steps]

    title = "🔐 WireGuard VPN من الصفر — Lab حقيقي خطوة بخطوة | HiTech Lab"

    desc_lines = [
        "🎬 Lab complet et RÉEL : installation, génération de clés, montée de "
        "l'interface wg0, erreurs authentiques et résolution — le tout exécuté "
        "en direct dans un sandbox Docker isolé.",
        "",
        "📌 Article complet (config files + troubleshooting) :",
        f"👉 {article_url}",
        "",
        "⏱️ Chapitres :",
    ] + [f"{c.ts} {c.title}" for c in chapters] + [
        "",
        "🧠 Ce que tu vas apprendre :",
        "• Comment WireGuard fonctionne sous le capot (cryptokey routing)",
        "• Les erreurs réelles et comment les diagnostiquer (wg show, tcpdump)",
        "• La configuration complète wg0.conf sans aucun raccourci",
        "",
        "#WireGuard #Linux #DevOps #Security #VPN #HiTechLab #Tunisie",
    ]

    return YouTubePayload(
        title=title[:100],
        description="\n".join(desc_lines)[:4900],
        tags=["WireGuard", "Linux", "VPN", "DevOps", "Sécurité", "Réseau",
              "HiTechLab", "Tunisie", "tutoriel", "sandbox", "docker"],
        video_path=video_path,
        chapters=chapters,
        lab_url=article_url,
    )


def credentials_available() -> bool:
    import os
    return bool(os.getenv("YOUTUBE_CLIENT_SECRET_PATH")) and \
        Path(os.getenv("YOUTUBE_CLIENT_SECRET_PATH", "")).exists()


async def upload(payload: YouTubePayload) -> Dict:
    """Real upload when OAuth is configured; otherwise persist payload."""
    PAYLOAD_DIR.mkdir(parents=True, exist_ok=True)
    payload_file = PAYLOAD_DIR / f"yt_{int(time.time())}.json"
    payload_file.write_text(json.dumps(asdict(payload), indent=2,
                                       ensure_ascii=False), encoding="utf-8")

    if not credentials_available():
        return {
            "status": "payload_ready",
            "reason": "OAuth credentials missing (set YOUTUBE_CLIENT_SECRET_PATH "
                      "+ YOUTUBE_TOKEN_PATH to enable live upload)",
            "payload_path": str(payload_file),
            "title": payload.title,
            "chapters": len(payload.chapters),
            "tags": payload.tags,
        }

    # ---- real resumable upload (requires google-api-python-client) ------
    try:
        from googleapiclient.discovery import build  # noqa: F401
        from googleapiclient.http import MediaFileUpload
        import google.oauth2.credentials  # noqa: F401
    except ImportError:
        return {"status": "payload_ready",
                "reason": "google-api-python-client not installed",
                "payload_path": str(payload_file)}

    import os
    import google.auth.transport.requests
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    token_path = os.getenv("YOUTUBE_TOKEN_PATH", "")
    scopes = ["https://www.googleapis.com/auth/youtube.upload"]
    creds = None
    if token_path and Path(token_path).exists():
        creds = Credentials.from_authorized_user_file(token_path, scopes)
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(
            os.environ["YOUTUBE_CLIENT_SECRET_PATH"], scopes)
        creds = flow.run_local_server(port=0)
        if token_path:
            Path(token_path).write_text(creds.to_json())

    yt = build("youtube", "v3", credentials=creds)
    media = MediaFileUpload(payload.video_path, chunksize=8 * 1024 * 1024,
                            resumable=True, mimetype="video/mp4")
    request = yt.videos().insert(
        part="snippet,status",
        body={
            "snippet": {"title": payload.title,
                        "description": payload.description,
                        "tags": payload.tags,
                        "categoryId": payload.category_id},
            "status": {"privacyStatus": payload.privacy_status,
                       "madeForKids": payload.made_for_kids},
        },
        media_body=media)
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"[youtube] upload {int(status.progress() * 100)}%")
    vid = response["id"]
    url = f"https://www.youtube.com/watch?v={vid}"
    payload_file.with_suffix(".uploaded").write_text(url)
    return {"status": "uploaded", "url": url, "payload_path": str(payload_file)}
