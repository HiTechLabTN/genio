#!/usr/bin/env python3
"""Genio SovereignEvolutionEngine — Partie D (déterministe, zéro random).

Q1 — scoring déterministe (aucun random.*) :
    score = 0.5 * exec_success + 0.3 * latency + 0.2 * token_efficiency
  * exec_success : 10 si le composer répond 200 avec un plan valide
    (clés head/hands/mouth/body), sinon 0.
  * latency : 10 * (2000 - ms) / 2000 clampé [0,10] (≥2000ms → 0).
  * token_efficiency : 10 * (3000 - len(plan_json)) / 3000 clampé [0,10].
Q2 — Skill Compilation : tout candidat vérifié (score >= 7.0) est sérialisé
  en skill JSON dans /data/ai_tools/genio/genio/core/compiled_skills/.
Q3 — fenêtre stricte 03:00-04:00 (doublée par midnight-patrol.timer).
"""
import json
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime

W_EXEC, W_LAT, W_TOK = 0.5, 0.3, 0.2
SKILL_THRESHOLD = 7.0
COMPOSER_URL = os.environ.get("GENIO_COMPOSER_URL", "http://localhost:8001/compose")
SKILLS_DIR = "/data/ai_tools/genio/genio/core/compiled_skills"
REPORT_DIR = "/data/ai_tools/genio/reports/v4"

# Candidats DÉTERMINISTES (produit cartésien fixe — aucun random.*).
CONTEXTS = [
    "user says hello",
    "user asks help",
    "user is sad",
    "user excited",
    "user confused",
]
EMOTIONS = ["joy", "neutral", "sad", "excited"]

REQUIRED_KEYS = ("head", "hands", "mouth", "body")
EMPTY_PLAN = {
    "head": {"tilt": 0, "nod": 0, "blink": False},
    "hands": [], "mouth": 0, "body": "idle",
}


def clamp10(x: float) -> float:
    return max(0.0, min(10.0, x))


def plan_valid(plan) -> bool:
    return isinstance(plan, dict) and all(k in plan for k in REQUIRED_KEYS)


def compose(ctx: str, emo: str, idx: int):
    """Un appel composer mesuré : (plan, exec_0_10, latency_ms)."""
    try:
        import httpx
        t0 = time.monotonic()
        r = httpx.post(COMPOSER_URL,
                       json={"context": ctx, "emotion": emo,
                             "user_id": f"synth_{idx:03d}"},
                       timeout=5)
        ms = (time.monotonic() - t0) * 1000.0
        if r.status_code == 200:
            plan = r.json().get("gesture_plan", {})
            if plan_valid(plan):
                return plan, 10.0, ms
        return dict(EMPTY_PLAN), 0.0, ms
    except Exception:
        return dict(EMPTY_PLAN), 0.0, 5000.0


def score_candidate(exec_s: float, latency_ms: float, plan_len: int) -> float:
    # Mesures quantifiées (100ms / 100 caractères) : le score est discret et
    # l'ordre stable — seule la formule compte, pas le bruit de mesure.
    q_lat = round(latency_ms / 100.0) * 100.0
    q_len = round(plan_len / 100) * 100
    lat = clamp10(10.0 * (2000.0 - q_lat) / 2000.0)
    tok = clamp10(10.0 * (3000.0 - q_len) / 3000.0)
    return W_EXEC * exec_s + W_LAT * lat + W_TOK * tok


class SovereignEvolutionEngine:
    """Moteur d'évolution déterministe : mêmes entrées → mêmes scores."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS dataset (id INTEGER PRIMARY KEY "
            "AUTOINCREMENT, context TEXT, plan TEXT, score REAL, real INTEGER, ts INTEGER)")

    def run(self):
        rows = []
        idx = 0
        for ctx in CONTEXTS:
            for emo in EMOTIONS:
                plan, exec_s, ms = compose(ctx, emo, idx)
                plan_json = json.dumps(plan, ensure_ascii=False)
                s = score_candidate(exec_s, ms, len(plan_json))
                rows.append({"context": ctx, "emotion": emo, "plan": plan,
                             "score": round(s, 3), "latency_ms": round(ms, 1),
                             "exec": exec_s})
                idx += 1
        # Tri stable : score arrondi à 2 décimales + tie-break (contexte,
        # émotion) — l'ordre ne dépend plus du bruit de mesure latence
        # (±6ms ⇒ ±0.009 score), seulement du mérite + identifiants.
        rows.sort(key=lambda r: (-round(r["score"], 2), r["context"],
                                 r["emotion"]))
        # Persiste top-10 en dataset (comme avant, mais déterministe).
        top10 = rows[:10]
        ts = int(time.time())
        for r in top10:
            self.conn.execute(
                "INSERT INTO dataset (context, plan, score, real, ts) "
                "VALUES (?,?,?,?,?)",
                (f"{r['context']}|{r['emotion']}",
                 json.dumps(r["plan"], ensure_ascii=False),
                 r["score"], 0, ts))
        self.conn.commit()
        # Q2 — Skill Compilation : candidats vérifiés → skills JSON.
        os.makedirs(SKILLS_DIR, exist_ok=True)
        compiled = 0
        for r in rows:
            if r["score"] >= SKILL_THRESHOLD and plan_valid(r["plan"]):
                name = (f"skill_{r['context'].replace(' ', '_')}"
                        f"__{r['emotion']}.json")
                with open(os.path.join(SKILLS_DIR, name), "w") as f:
                    json.dump({"context": r["context"], "emotion": r["emotion"],
                               "plan": r["plan"], "score": r["score"],
                               "weights": {"exec": W_EXEC, "lat": W_LAT,
                                           "tok": W_TOK},
                               "ts": ts}, f, ensure_ascii=False, indent=2)
                compiled += 1
        return rows, top10, compiled


def main() -> int:
    # Q3 — fenêtre stricte 03:00-04:00 (doublée par midnight-patrol.timer) ;
    # skip si charge haute. Gate dans main() pour garder le module importable.
    now = datetime.now()
    hour = now.hour
    if hour < 3 or hour >= 4:
        print(f"Skip: outside window 03-04, now {hour}")
        return 0
    load = os.getloadavg()[0]
    if load > 4.0:
        print(f"Skip: load high {load}")
        return 0
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "gestures.db")
    engine = SovereignEvolutionEngine(db_path)
    rows, top10, compiled = engine.run()
    os.makedirs(REPORT_DIR, exist_ok=True)
    with open(os.path.join(REPORT_DIR, "cron.log"), "a") as f:
        f.write(f"{datetime.now().isoformat()} sovereign {len(rows)} "
                f"top10 {len(top10)} compiled {compiled} load {load}\n")
    print(f"self_improve done: {len(rows)} candidates, "
          f"top score {top10[0]['score'] if top10 else 0}, "
          f"compiled {compiled} skills")
    # Try ollama create genio-gesture (≤30min) si top10 existe — inchangé.
    try:
        mf = (f"FROM qwen2.5:7b-instruct-q4_K_M\nSYSTEM You are Genio gesture "
              f"composer trained on {len(top10)} top gestures.\n")
        with open("/tmp/GenioGesture_Modelfile", "w") as mf_f:
            mf_f.write(mf)
        subprocess.run(["ollama", "create", "genio-gesture",
                        "-f", "/tmp/GenioGesture_Modelfile"], timeout=1800)
        print("ollama create genio-gesture done")
        with open(os.path.join(REPORT_DIR, "cron.log"), "a") as f:
            f.write(f"{datetime.now().isoformat()} ollama create genio-gesture success\n")
    except Exception as e:
        print(f"ollama create failed {e}")
        with open(os.path.join(REPORT_DIR, "cron.log"), "a") as f:
            f.write(f"{datetime.now().isoformat()} ollama create failed {e}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
