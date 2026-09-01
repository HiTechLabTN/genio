"""Phase 6 — rich artifacts + tolerant WS typing.

Run: pytest test_phase6_tolerant_ws.py -v
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def test_artifact_panel_exists():
    p = ROOT / "genio_client" / "src" / "components" / "ArtifactPanel.tsx"
    assert p.exists(), "ArtifactPanel.tsx missing"
    txt = p.read_text()
    assert "Artifact" in txt
    assert "artifactsFromChat" in txt


def test_types_tolerant():
    t = (ROOT / "genio_client" / "src" / "lib" / "types.ts").read_text()
    # must have tolerant fallback union (type: string with index signature)
    assert 'type: string' in t
    assert 'tolerant' in t.lower() or '[key: string]' in t
    assert 'artifact' in t.lower()


def test_ws_tolerant():
    w = (ROOT / "genio_client" / "src" / "lib" / "ws.ts").read_text()
    assert 'malformed' in w or 'tolerant' in w.lower() or 'non-JSON' in w
    assert 'isChatEvent' in w
    # must not drop unknown types silently without handling
    assert 'CHAT_EVENT_TYPES' in w
    assert 'artifact' in w.lower()


def test_hook_tolerant():
    h = (ROOT / "genio_client" / "src" / "hooks" / "useGenioSocket.ts").read_text()
    assert 'artifact' in h.lower()
    # should handle unknown fallback
    assert 'Unknown' in h or 'tolerant' in h.lower() or 'fallback' in h.lower()
