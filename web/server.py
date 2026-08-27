import os
import json
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Genio Control Plane")

BASE_DIR = Path(__file__).parent

# تقديم ملفات PWA والـ Static
@app.get("/manifest.json")
async def get_manifest():
    return FileResponse(BASE_DIR / "manifest.json", media_type="application/json")

@app.get("/sw.js")
async def get_sw():
    return FileResponse(BASE_DIR / "sw.js", media_type="application/javascript")

@app.get("/mobile.html", response_class=HTMLResponse)
@app.get("/", response_class=HTMLResponse)
async def get_ui(request: Request):
    index_file = BASE_DIR / "mobile.html"
    if index_file.exists():
        return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
    return HTMLResponse("<h2>Genio Node is Live.</h2>")

@app.get("/api/telemetry")
async def get_telemetry():
    return {
        "status": "online",
        "muscle_node": "Pop!_OS (Legion RTX 3060)",
        "control_plane": "ThinkCentre .tn",
        "gpu_temp": 38,
        "vram_free": "6.9 GB",
        "active_models": ["qwen2.5-coder:14b", "qwen2.5:7b"]
    }

@app.post("/api/command")
async def receive_command(req: Request):
    data = await req.json()
    prompt = data.get("prompt", "")
    print(f"📥 [Genio Command Received]: {prompt}")
    return {"status": "accepted", "message": "تم استلام الأمر، جينيو بصدد المعالجة والتنفيذ."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
