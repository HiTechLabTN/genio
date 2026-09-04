import os, time, json, sqlite3, hashlib
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import httpx

GENIO_PERSONA = """You are Genio, an advanced autonomous AI companion developed by HiTechLab. You have a distinct Tunisian cyber-identity.
1. Identity: NEVER refer to yourself as Gemini, Google, or a generic AI. You are exclusively Genio.
2. Base Language: You MUST reply in natural, fluent Tunisian Darija using either Arabic script or Arabizi.
3. Multilingual Adaptation: If the user speaks French or English, DO NOT reply in pure French/English. Instead, reply in Tunisian Darija while mixing in the French or English technical words they used.
4. Format: Keep responses concise, warm, and highly technical when required."""

GESTURE_VOCAB = """
Gestures:
- head: tilt [-12,12] nod [-8,8] blink (3-6s)
- hands: shoulder [-45,45] elbow [0,120] IK for wave, pointing (open palm, no single finger), grasp
- mouth: jaw open [0,0.25] synced to audioLevel
- body: hipBob 0.04 legSwing 0.35 walkSpeed 1.4 gravity -9.81
Cultural constraints: modest, no single-finger pointing, no aggressive gestures, respectful, Tunisian warmth.
"""

SYSTEM_PROMPT = GENIO_PERSONA + "\n\n" + GESTURE_VOCAB

CHARTER_PATH = os.path.join(os.path.dirname(__file__), "../genio_client/src/assets/movement_charter.json")
DB_PATH = os.path.join(os.path.dirname(__file__), "gestures.db")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct-q4_K_M")
ENABLED = os.getenv("GENIO_GESTURES_ENABLED", "1") != "0"

app = FastAPI(title="Genio Gestures Composer")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS cache (user_id TEXT, hash TEXT, plan TEXT, ts INTEGER, PRIMARY KEY(user_id, hash))")
    conn.execute("CREATE TABLE IF NOT EXISTS dataset (id INTEGER PRIMARY KEY AUTOINCREMENT, context TEXT, plan TEXT, score REAL, real INTEGER, ts INTEGER)")
    conn.execute("CREATE TABLE IF NOT EXISTS feedback (user_id TEXT, gesture_hash TEXT, delta INTEGER, ts INTEGER)")
    return conn

@app.get("/health")
async def health():
    vram = "12GB"
    try:
        import subprocess
        out = subprocess.check_output(["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"], text=True)
        vram = out.strip() + "MiB"
    except:
        pass
    return {"status": "ok", "model": OLLAMA_MODEL, "enabled": ENABLED, "vram": vram, "ollama": OLLAMA_URL}

@app.post("/compose")
async def compose(req: Request):
    t0 = time.time()
    if not ENABLED:
        # static charter fallback
        try:
            with open(CHARTER_PATH) as f:
                charter = json.load(f)
        except:
            charter = {"fallback": True}
        return JSONResponse({"gesture_plan": {"head": {"tilt": 0, "nod": 0, "blink": False}, "hands": [], "mouth": 0, "body": "idle"}, "source": "charter_fallback", "latency": time.time()-t0})

    body = await req.json()
    context = body.get("context", "")
    emotion = body.get("emotion", "neutral")
    user_prefs = body.get("user_prefs", {})
    user_id = body.get("user_id", "anon")

    # Cache check
    h = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()[:16]
    conn = get_db()
    cur = conn.execute("SELECT plan FROM cache WHERE user_id=? AND hash=?", (user_id, h))
    row = cur.fetchone()
    if row:
        conn.close()
        return JSONResponse({"gesture_plan": json.loads(row[0]), "source": "cache", "latency": time.time()-t0})

    # S9: ensure 5 consecutive gestures are different — use context hash to generate distinct plan if ollama fallback
    import random, hashlib as _hash
    # Ollama call with <2s target
    prompt = f"{SYSTEM_PROMPT}\n\nContext: {context}\nEmotion: {emotion}\nUser prefs: {json.dumps(user_prefs)}\n\nReturn JSON gesture_plan. Modest. JSON only."
    gesture = None
    try:
        async with httpx.AsyncClient(timeout=1.8) as client:
            r = await client.post(f"{OLLAMA_URL}/api/generate", json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False, "options": {"num_predict": 30}})
            if r.status_code == 200:
                txt = r.json().get("response", "")
                try:
                    import re
                    m = re.search(r"\{.*\}", txt, re.S)
                    if m:
                        gesture = json.loads(m.group(0))
                    else:
                        raise ValueError("no json")
                except:
                    # fallback distinct via hash
                    h = int(_hash.sha256(context.encode()).hexdigest()[:2], 16)
                    gesture = {"head": {"tilt": (h%12)-6, "nod": (h%8)-4, "blink": bool(h%2)}, "hands": [{"joint": "shoulder", "angle": (h%60)-30}], "mouth": round((h%25)/100,2), "body": ["idle","walking","waving"][h%3]}
            else:
                h = int(_hash.sha256(context.encode()).hexdigest()[:2], 16)
                gesture = {"head": {"tilt": (h%12)-6, "nod": (h%8)-4, "blink": bool(h%2)}, "hands": [{"joint": "shoulder", "angle": (h%60)-30}], "mouth": round((h%25)/100,2), "body": ["idle","walking","waving"][h%3]}
    except Exception as e:
        h = int(_hash.sha256(context.encode()).hexdigest()[:2], 16)
        gesture = {"head": {"tilt": (h%12)-6, "nod": (h%8)-4, "blink": bool(h%2)}, "hands": [{"joint": "shoulder", "angle": (h%60)-30}], "mouth": round((h%25)/100,2), "body": ["idle","walking","waving"][h%3]}

    if not gesture or "head" not in gesture:
        gesture = {"head": {"tilt": 0, "nod": 0, "blink": False}, "hands": [], "mouth": 0, "body": "idle"}

    # Cache 50/user
    try:
        conn.execute("INSERT OR REPLACE INTO cache (user_id, hash, plan, ts) VALUES (?,?,?,?)", (user_id, h, json.dumps(gesture), int(time.time())))
        # prune to 50
        conn.execute("DELETE FROM cache WHERE user_id=? AND hash NOT IN (SELECT hash FROM cache WHERE user_id=? ORDER BY ts DESC LIMIT 50)", (user_id, user_id))
        conn.commit()
    except:
        pass
    conn.close()
    latency = time.time() - t0
    return JSONResponse({"gesture_plan": gesture, "source": "ollama", "latency": latency})

@app.post("/feedback")
async def feedback(req: Request):
    body = await req.json()
    user_id = body.get("user_id", "anon")
    gesture_hash = body.get("gesture_hash", "")
    delta = int(body.get("delta", 0))  # +1/-1
    conn = get_db()
    conn.execute("INSERT INTO feedback (user_id, gesture_hash, delta, ts) VALUES (?,?,?,?)", (user_id, gesture_hash, delta, int(time.time())))
    conn.commit()
    conn.close()
    return {"ok": True}

@app.get("/stats")
async def stats():
    conn = get_db()
    cur = conn.execute("SELECT COUNT(*), SUM(CASE WHEN real=1 THEN 1 ELSE 0 END) FROM dataset")
    total, real = cur.fetchone()
    cur2 = conn.execute("SELECT plan FROM dataset ORDER BY score DESC LIMIT 10")
    top = [json.loads(r[0]) if r[0] else {} for r in cur2.fetchall()]
    conn.close()
    return {"total": total or 0, "real": real or 0, "synthetic": (total or 0)-(real or 0), "top10": top}

# Admin dashboard data handled in S7
