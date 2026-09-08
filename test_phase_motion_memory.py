"""Motion-memory scoring tests (master §29): record/recommend/ranking/decay."""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "genio_gestures"))

from fastapi.testclient import TestClient  # noqa: E402
from app import app  # noqa: E402

DB = os.path.join(os.path.dirname(__file__), "genio_gestures", "gestures.db")


def _clean():
    conn = sqlite3.connect(DB)
    conn.execute("DELETE FROM motion_memory WHERE context LIKE 'test-%'")
    conn.commit()
    conn.close()


def test_record_and_recommend_ranking():
    _clean()
    c = TestClient(app)
    assert c.post("/api/v1/motion/record", json={
        "context": "test-greet", "emotion": "happy",
        "gesture_name": "wave", "signal": 0.9}).status_code == 200
    assert c.post("/api/v1/motion/record", json={
        "context": "test-greet", "emotion": "happy",
        "gesture_name": "nod", "signal": 0.3}).status_code == 200
    r = c.get("/api/v1/motion/recommend",
              params={"context": "test-greet", "emotion": "happy"})
    assert r.status_code == 200
    body = r.json()
    assert body["gesture_name"] == "wave"
    assert body["score"] == 0.9
    assert body["fallback"] is False
    assert abs(sum(body["weights"]) - 1.0) < 0.01
    _clean()


def test_recommend_requires_context_and_running_average():
    _clean()
    c = TestClient(app)
    assert c.get("/api/v1/motion/recommend").status_code == 400
    c.post("/api/v1/motion/record", json={
        "context": "test-ctx", "emotion": "calm",
        "gesture_name": "idle", "signal": 0.8})
    c.post("/api/v1/motion/record", json={
        "context": "test-ctx", "emotion": "calm",
        "gesture_name": "idle", "signal": 0.6})
    r = c.get("/api/v1/motion/recommend", params={"context": "test-ctx"})
    assert r.json()["score"] == 0.7
    assert r.json()["use_count"] == 2
    _clean()
