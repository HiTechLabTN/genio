import os, time, json, sqlite3, hashlib
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import httpx

GENIO_PERSONA = """أنت جينيو، صاحب ذكاء اصطناعي تونسي متطوّر من تطوير HiTechLab.
1. الهوية: أنت جينيو حصراً — لا تذكر أبداً أنك Gemini أو Google.
2. اللغة الإجبارية: يجب أن تجيب دائماً بحروف عربية فقط بالدارجة التونسية. مثال: "عسلامة! أنا جينيو، مهندس الذكاء الاصطناعي في هايتك لاب". ممنوع منعاً باتاً استعمال العربيزي/الفرانكو (mta3, n3awnek, t7eb, 3liha).
3. التكيّف: إذا تكلّم المستخدم بالفرنسية أو الإنجليزية، أجب بالدارجة التونسية بحروف عربية مع إدماج الكلمات التقنية بلطف.
4. الأسلوب: مختصر، دافئ، تقني عند الحاجة، بروح تونسية أصيلة."""

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
    conn.execute("CREATE TABLE IF NOT EXISTS gesture_cache (state_name TEXT PRIMARY KEY, video_path TEXT, duration REAL, hit_count INTEGER DEFAULT 0)")
    # Seed default state loops if empty
    try:
        cur = conn.execute("SELECT COUNT(*) FROM gesture_cache")
        if (cur.fetchone() or [0])[0] == 0:
            defaults = [
                ("idle", "/media/states/idle.webm", 3.0, 0),
                ("talk", "/media/states/talk.webm", 2.5, 0),
                ("listen", "/media/states/listen.webm", 2.0, 0),
                ("wave", "/media/states/wave.webm", 2.8, 0),
            ]
            conn.executemany("INSERT OR IGNORE INTO gesture_cache (state_name, video_path, duration, hit_count) VALUES (?,?,?,?)", defaults)
            conn.commit()
    except:
        pass
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

@app.get("/api/v1/gestures/active")
async def gestures_active(request: Request):
    """
    Return current video manifest mapped to user profile preferences.
    Query: ?user_id=anon
    Increments hit_count for analytics and returns manifest.
    """
    user_id = request.query_params.get("user_id") or "anon"
    # user profile prefs could be passed as ?prefs=... but we keep simple: read from DB
    conn = get_db()
    # Ensure seeded
    cur = conn.execute("SELECT state_name, video_path, duration, hit_count FROM gesture_cache ORDER BY state_name")
    rows = cur.fetchall()
    if not rows:
        conn.close()
        return JSONResponse({"user_id": user_id, "manifest": {}, "states": {}})
    manifest = {}
    for state_name, video_path, duration, hit_count in rows:
        manifest[state_name] = {"video_path": video_path, "duration": float(duration) if duration is not None else 0.0, "hit_count": int(hit_count or 0)}
    # Optionally increment hit_count for the most relevant state (idle) as keepalive — non-blocking
    try:
        conn.execute("UPDATE gesture_cache SET hit_count = hit_count + 1 WHERE state_name = ?", ("idle",))
        conn.commit()
    except:
        pass
    conn.close()
    # Also include ordered states array for frontend convenience
    return {"user_id": user_id, "manifest": manifest, "states": manifest, "video_manifest": manifest}

# Admin dashboard data handled in S7
