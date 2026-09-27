"""G4.2: unified/portal/presence must never pull the 3D mascot runtime.

Fails if UnifiedShell, Presence*, or portal code imports three.js,
rapier, WebGL loaders, .glb assets or mascot 3D components. Three.js
itself is NOT banned repo-wide (legacy mascot mode + Dashboard keep
it deliberately) — only the unified path is asserted clean.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUARDED = [ROOT / "genio_client" / "src" / d for d in ("unified", "presence", "portal")]

BANNED = [
    r"from\s+['\"]three['\"]",
    r"@react-three",
    r"@dimforge",
    r"three-stdlib",
    r"\.glb",
    r"\.gltf",
    r"MascotStage",
    r"RiggedMascot",
    r"Genio3D",
    r"useGLTF",
    r"GLTFLoader",
    r"Rapier",
    r"mediapipe",
    r"WebGLRenderer",
]


def test_unified_path_has_no_3d_runtime():
    hits = []
    for base in GUARDED:
        for p in base.rglob("*.tsx"):
            if "test" in p.name:
                continue
            text = p.read_text()
            for pat in BANNED:
                if re.search(pat, text):
                    hits.append(f"{p.relative_to(ROOT)}: {pat}")
        for p in base.rglob("*.ts"):
            if "test" in p.name:
                continue
            text = p.read_text()
            for pat in BANNED:
                if re.search(pat, text):
                    hits.append(f"{p.relative_to(ROOT)}: {pat}")
    assert not hits, f"3D mascot runtime leaked into unified path: {hits}"


def test_canonical_assets_exist_and_tracked():
    import subprocess
    expected = [
        "genio_client/src/assets/mascot/genio-hero.webp",
        "genio_client/src/assets/character/genio-wave.webp",
        "genio_client/src/assets/character/genio-wink.webp",
    ]
    for rel in expected:
        p = ROOT / rel
        assert p.is_file(), f"canonical asset missing: {rel}"
        out = subprocess.run(["git", "-C", str(ROOT), "ls-files", "--error-unmatch", rel],
                             capture_output=True, text=True, timeout=30)
        assert out.returncode == 0, f"canonical asset untracked: {rel}"


def test_state_image_mapping_covers_key_states():
    text = (ROOT / "genio_client" / "src" / "presence" / "PresenceAvatar.tsx").read_text()
    for state in ("greeting", "listening", "success", "celebrating"):
        assert state in text, f"no canonical mapping for {state}"
    assert "heroBase" in text  # fallback = canonical base, never generic art
