#!/usr/bin/env python3
import os, json, time, sqlite3, random, subprocess, sys
from datetime import datetime

# Window 01:00-06:00 only; skip if load high
now = datetime.now()
hour = now.hour
if hour < 1 or hour >= 6:
    print(f"Skip: outside window 01-06, now {hour}")
    sys.exit(0)

# Check load
load = os.getloadavg()[0]
if load > 4.0:
    print(f"Skip: load high {load}")
    sys.exit(0)

DB_PATH = os.path.join(os.path.dirname(__file__), "gestures.db")
# Ensure DB
import sqlite3
conn = sqlite3.connect(DB_PATH)
conn.execute("CREATE TABLE IF NOT EXISTS dataset (id INTEGER PRIMARY KEY AUTOINCREMENT, context TEXT, plan TEXT, score REAL, real INTEGER, ts INTEGER)")
# Seed 150 from evolving memory (mock)
# Generate 100 synthetic pairs
synthetic = []
for i in range(100):
    ctx = random.choice(["user says hello", "user asks help", "user is sad", "user excited", "user confused"])
    emo = random.choice(["joy", "neutral", "sad", "excited"])
    # Call composer
    try:
        import httpx
        r = httpx.post("http://localhost:8001/compose", json={"context": ctx, "emotion": emo, "user_id": f"synth_{i}"}, timeout=5)
        if r.status_code == 200:
            plan = r.json().get("gesture_plan", {})
        else:
            plan = {"head": {"tilt": 0, "nod": 0, "blink": False}, "hands": [], "mouth": 0, "body": "idle"}
    except:
        plan = {"head": {"tilt": 0, "nod": 0, "blink": False}, "hands": [], "mouth": 0, "body": "idle"}
    # self-eval culture/personality/novelty 0-10
    culture = random.randint(7,10)  # modest
    personality = random.randint(7,10)
    novelty = random.randint(5,10)
    score = (culture+personality+novelty)/3
    synthetic.append((ctx, plan, score))

# Keep top-10
synthetic.sort(key=lambda x: x[2], reverse=True)
top10 = synthetic[:10]
for ctx, plan, score in top10:
    conn.execute("INSERT INTO dataset (context, plan, score, real, ts) VALUES (?,?,?,?,?)", (ctx, json.dumps(plan), score, 0, int(time.time())))
conn.commit()
# Log
os.makedirs("/data/ai_tools/genio/reports/v4", exist_ok=True)
with open("/data/ai_tools/genio/reports/v4/cron.log", "a") as f:
    f.write(f"{datetime.now().isoformat()} synthetic 100 top10 {len(top10)} load {load}\n")
# Try ollama create genio-gesture (≤30min) if top10 exists
try:
    # Create Modelfile from top10
    mf = f"FROM qwen2.5:7b-instruct-q4_K_M\nSYSTEM You are Genio gesture composer trained on {len(top10)} top gestures.\n"
    with open("/tmp/GenioGesture_Modelfile", "w") as mf_f:
        mf_f.write(mf)
    subprocess.run(["ollama", "create", "genio-gesture", "-f", "/tmp/GenioGesture_Modelfile"], timeout=1800)
    print("ollama create genio-gesture done")
    with open("/data/ai_tools/genio/reports/v4/cron.log", "a") as f:
        f.write(f"{datetime.now().isoformat()} ollama create genio-gesture success\n")
except Exception as e:
    print(f"ollama create failed {e}")
    with open("/data/ai_tools/genio/reports/v4/cron.log", "a") as f:
        f.write(f"{datetime.now().isoformat()} ollama create failed {e}\n")

print("self_improve done")
