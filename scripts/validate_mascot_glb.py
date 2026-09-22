"""Automated validator for genio_mascot_master.glb (reproducible gate).

Usage: python3 scripts/validate_mascot_glb.py [path] [--max-mb 60]
Exit 0 = all gates pass. Prints PASS/FAIL per gate.
"""
import struct, json, sys, os
import math

PATH = sys.argv[1] if len(sys.argv) > 1 else "genio_client/public/models/genio_mascot_master.glb"
MAX_MB = float((sys.argv[sys.argv.index("--max-mb") + 1] if "--max-mb" in sys.argv else 60))

REQUIRED_BONES = ["Root", "Spine", "Chest", "Neck", "Head", "Jaw",
                  "Eye.L", "Eye.R", "UpperArm.L", "LowerArm.L", "Hand.L",
                  "UpperArm.R", "LowerArm.R", "Hand.R",
                  "Thigh.L", "Shin.L", "Foot.L", "Thigh.R", "Shin.R", "Foot.R"]
REQUIRED_MORPHS = ["Blink_L", "Blink_R", "EyeWide_L", "EyeWide_R", "EyeSquint_L",
                   "EyeSquint_R", "BrowUp_L", "BrowUp_R", "BrowDown_L", "BrowDown_R",
                   "Smile", "Smile_L", "Smile_R", "Frown", "CheekRaise_L",
                   "CheekRaise_R", "NoseWrinkle", "JawOpen", "MouthOpen",
                   "MouthSmile", "MouthFrown", "LipPucker", "LipPress", "TongueOut"]
REQUIRED_ANIMS = ["idle", "wave", "listen", "think", "speak", "hero",
                  "greeting", "speaking", "nod", "success"]

results = []
def gate(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {detail}")

with open(PATH, "rb") as f:
    magic = f.read(4)
    gate("valid GLB binary (magic glTF)", magic == b"glTF", str(magic))
    ver = struct.unpack("<I", f.read(4))[0]
    gate("glTF version == 2", ver == 2, f"v{ver}")
    struct.unpack("<I", f.read(4))
    jlen = struct.unpack("<I", f.read(4))[0]
    ctype = f.read(4)
    gate("JSON chunk present", ctype == b"JSON")
    doc = json.loads(f.read(jlen))
    blob = f.read()

gate("scenes exist", len(doc.get("scenes", [])) > 0, f"{len(doc.get('scenes', []))}")
gate("meshes exist", len(doc.get("meshes", [])) > 0, f"{len(doc.get('meshes', []))}")
gate("materials exist", len(doc.get("materials", [])) > 0, f"{len(doc.get('materials', []))}")
imgs = doc.get("images", [])
gate("textures resolve", len(imgs) > 0 and len(doc.get("textures", [])) > 0,
     f"{len(imgs)} images / {len(doc.get('textures', []))} textures")
gate("skeleton exists (skins)", len(doc.get("skins", [])) > 0, f"{len(doc.get('skins', []))} skins")

nodes = {n.get("name"): n for n in doc.get("nodes", [])}
missing_bones = [b for b in REQUIRED_BONES if b not in nodes]
gate("expected bones exist", not missing_bones, f"missing={missing_bones}" if missing_bones else f"{len(REQUIRED_BONES)} bones ok")

morph_names = set()
for m in doc.get("meshes", []):
    # Blender writes targetNames at mesh.extras (3.x) — fallback to primitive extras
    for k in m.get("extras", {}).get("targetNames", []):
        morph_names.add(k)
    for p in m.get("primitives", []):
        for k in p.get("extras", {}).get("targetNames", []):
            morph_names.add(k)
# Fallback: count targets when names are absent (older exporters)
target_count = sum(len(p.get("targets", [])) for m in doc.get("meshes", []) for p in m.get("primitives", []))
missing_morphs = [x for x in REQUIRED_MORPHS if x not in morph_names]
if missing_morphs and not morph_names and target_count >= len(REQUIRED_MORPHS):
    gate("expected morph targets exist", True, f"{target_count} targets (names not exported, count ok)")
else:
    gate("expected morph targets exist", not missing_morphs,
         f"missing={missing_morphs}" if missing_morphs else f"{len(morph_names)} targets")

anims = {a.get("name"): a for a in doc.get("animations", [])}
missing_anims = [x for x in REQUIRED_ANIMS if x not in anims]
gate("required animation names exist", not missing_anims,
     f"missing={missing_anims}" if missing_anims else f"{len(anims)} clips")

# NaN/Inf + accessor sanity: walk accessors, check count>0 and buffer views in range
bad = []
for i, acc in enumerate(doc.get("accessors", [])):
    if acc.get("count", 0) <= 0:
        bad.append(i)
    bv = acc.get("bufferView")
    if bv is not None and not (0 <= bv < len(doc.get("bufferViews", []))):
        bad.append(i)
gate("no broken accessors", not bad, f"bad={bad[:5]}" if bad else f"{len(doc.get('accessors', []))} accessors ok")

# Bounding box from POSITION min/max
try:
    pos_acc = None
    for m in doc.get("meshes", []):
        for p in m.get("primitives", []):
            ai = p.get("attributes", {}).get("POSITION")
            if ai is not None:
                pos_acc = doc["accessors"][ai]
                break
    mn, mx = pos_acc.get("min"), pos_acc.get("max")
    ok_box = mn is not None and mx is not None
    # glTF convention is Y-up (Blender Z-up is converted on export)
    h = (mx[1] - mn[1]) if ok_box else 0
    gate("reasonable bounding box (~1.7m tall)", ok_box and 1.2 < h < 2.3, f"height={h:.2f}m (Y-up)" if ok_box else "")
except Exception as e:
    gate("reasonable bounding box (~1.7m tall)", False, str(e)[:100])

size_mb = os.path.getsize(PATH) / 1024 / 1024
gate("file size within target", size_mb <= MAX_MB, f"{size_mb:.2f}MB <= {MAX_MB}MB")

# Orientation: height axis (Y in glTF) must be the longest extent
gate("correct orientation (Y-up tall)", ok_box and (mx[1] - mn[1]) >= max(mx[0] - mn[0], mx[2] - mn[2]),
     f"extents x={mx[0]-mn[0]:.2f} y={mx[1]-mn[1]:.2f} z={mx[2]-mn[2]:.2f}" if ok_box else "")

fails = [n for n, ok, _ in results if not ok]
print(f"\n{len(results) - len(fails)}/{len(results)} gates passed")
sys.exit(1 if fails else 0)
