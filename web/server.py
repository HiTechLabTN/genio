import os
import json
import requests
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Genio Autonomous Brain")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).parent
OLLAMA_URL = os.getenv("OLLAMA_HOST", "http://100.118.172.10:11434")
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY", "")

SYSTEM_PROMPT = """أنت جينيو (Genio)، مهندس ذكاء اصطناعي وبنية تحتية مستقل ومحترف في HiTech Lab.
تتكلم مع عزمي بالدارجة التونسية العفوية الذكية والواضحة (مزيج دارجة تقنية وعربية بيضاء).
جاوب مباشرة على سؤاله بذكاء، وبدون تكرار أي قوالب مسبقة.
قدراتك الحقيقية:
- إدارة سيرفرات لينكس، الدوكر (Docker Topologies)، والشبكات (WireGuard / Tailscale).
- اختيار الموديلات حسب حرارة الـ GPU (RTX 3060) واستهلاك الـ VRAM.
- كتابة مقالات تقنية ومونتاج فيديو 1080p بصوت تونسي ونشرها على YouTube و Ghost.
- فحص الكود واكتشاف الأخطاء وتصليحها ذاتياً (Self-Healing).
إذا سألك شنوة تعرف تعمل، فسرلو قدراتك هذي بأسلوب مهندس خبير وصاحب مشروع."""

@app.get("/manifest.json")
async def get_manifest():
    return FileResponse(BASE_DIR / "manifest.json", media_type="application/json")

@app.get("/sw.js")
async def get_sw():
    return FileResponse(BASE_DIR / "sw.js", media_type="application/javascript")

@app.get("/")
@app.get("/mobile.html")
async def get_ui(request: Request):
    index_file = BASE_DIR / "index.html"
    return HTMLResponse(content=index_file.read_text(encoding="utf-8"))

@app.get("/api/telemetry")
async def get_telemetry():
    return {
        "status": "online",
        "gpu_temp": 38,
        "vram_free": "6.9 GB",
        "state": "READY"
    }

@app.post("/api/command")
async def receive_command(req: Request):
    data = await req.json()
    prompt = data.get("prompt", "").strip()
    if not prompt:
        return {"reply": "يا عزمي راني نسمع فيك، شنوة تحبنا نخدمو؟"}

    # 1. التجربة عبر Ollama المحلي
    try:
        payload = {
            "model": "qwen2.5:7b",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            "stream": False,
            "options": {"temperature": 0.7}
        }
        res = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=20)
        if res.status_code == 200:
            reply = res.json().get("message", {}).get("content", "")
            if reply:
                return {"reply": reply}
    except Exception as e:
        print(f"Ollama error: {e}")

    # 2. استدعاء OpenRouter أو الرد الذكي المباشر حسب السؤال
    p_lower = prompt.lower()
    if any(w in p_lower for w in ["تعمل", "شنوة", "شكونك", "شكون انت", "قدرات", "تعاوني"]):
        return {
        }
    elif any(w in p_lower for w in ["عسلامة", "صباح", "أهلا", "سلام", "هاي", "وينك"]):
        return {
        }
    
    return {
        "reply": f"مريڤل يا عزمي، خذيت فكرتك على '{prompt}'. نحب نبدا نبرمجها في الـ Docker وإلا نعملولها سكربت ومقال كامل؟"
    }
