#!/usr/bin/env python3
"""Add a minimal 2-joint skeleton (root + head) to v2_fallback_baked.glb.

Geometry (POSITION) and vertex colors (COLOR_0) are preserved BYTE-IDENTICAL —
we only append skinning data (JOINTS_0/WEIGHTS_0 + skin + 2 joints) so the
approved mesh keeps its exact look while gaining a head bone for the
procedural "eye saccades" (sin(t*0.3)*0.15) and accessory bone sockets.

Output: v2_fallback_baked_rigged.glb
"""
import json, struct, sys
import numpy as np

SRC = "/data/ai_tools/genio/assets-pipeline/mesh-v2/v2_fallback_baked.glb"
DST = "/data/ai_tools/genio/assets-pipeline/mesh-v2/v2_fallback_baked_rigged.glb"

with open(SRC, "rb") as f:
    magic, ver, length = struct.unpack("<III", f.read(12))
    chunks = []
    while f.tell() < length:
        clen, ctype = struct.unpack("<II", f.read(8))
        chunks.append((ctype, f.read(clen)))
j = json.loads(chunks[0][1].decode())
bin0 = bytearray(chunks[1][1])

# --- read positions to compute weights ---
pos_acc = j["accessors"][1]
bv = j["bufferViews"][pos_acc["bufferView"]]
off = bv.get("byteOffset", 0) + pos_acc.get("byteOffset", 0)
cnt = pos_acc["count"]
pos = np.frombuffer(bin0, dtype=np.float32, count=cnt * 3, offset=off).reshape(cnt, 3).copy()

# --- weight assignment: smooth head region ---
HEAD_JOINT = np.array([0.0, 1.30, -0.02])
y = pos[:, 1]
# smoothstep(1.05, 1.30, y): below 1.05 → root, above 1.30 → head
t = np.clip((y - 1.05) / 0.25, 0.0, 1.0)
w_head = t * t * (3 - 2 * t)
w_root = 1.0 - w_head

joints = np.zeros((cnt, 4), dtype=np.uint8)
weights = np.zeros((cnt, 4), dtype=np.float32)
# JOINTS_0 = indices into skin.joints array (skin.joints = [2 root, 3 head])
joints[:, 0] = 1  # head
joints[:, 1] = 0  # root
weights[:, 0] = w_head
weights[:, 1] = w_root

# --- inverse bind matrices (2 joints: root=identity, head=inv(T)) ---
ibm = np.zeros((2, 16), dtype=np.float32)
ibm[0] = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]  # root
tx, ty, tz = HEAD_JOINT
ibm[1] = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, -tx, -ty, -tz, 1]  # head inverse

# --- append to bin ---
def align4(n):
    return (n + 3) & ~3

ibm_bytes = ibm.tobytes()
joints_bytes = joints.tobytes()
weights_bytes = weights.tobytes()
base = len(bin0)
ibm_off = base
joints_off = ibm_off + len(ibm_bytes)
weights_off = joints_off + len(joints_bytes)
bin0 += ibm_bytes + joints_bytes + weights_bytes

# --- new bufferViews ---
n_bv = len(j["bufferViews"])
j["bufferViews"].append({"buffer": 0, "byteOffset": ibm_off, "byteLength": len(ibm_bytes)})
j["bufferViews"].append({"buffer": 0, "byteOffset": joints_off, "byteLength": len(joints_bytes)})
j["bufferViews"].append({"buffer": 0, "byteOffset": weights_off, "byteLength": len(weights_bytes)})

# --- new accessors ---
n_acc = len(j["accessors"])
j["accessors"].append({"componentType": 5126, "type": "MAT4", "bufferView": n_bv, "count": 2})       # IBM
j["accessors"].append({"componentType": 5121, "type": "VEC4", "bufferView": n_bv + 1, "count": cnt})  # JOINTS_0
j["accessors"].append({"componentType": 5126, "type": "VEC4", "bufferView": n_bv + 2, "count": cnt})  # WEIGHTS_0

# --- nodes: add root_joint (2) and head_joint (3), wired into the hierarchy ---
j["nodes"].append({"name": "root_joint", "children": [3]})
j["nodes"].append({"name": "head_joint", "translation": [float(x) for x in HEAD_JOINT]})

# --- skin ---
j["skins"] = [{
    "joints": [2, 3],
    "inverseBindMatrices": n_acc,
    "name": "genio_skeleton",
}]

# --- mesh node references skin AND owns the joint hierarchy ---
j["nodes"][1]["skin"] = 0
j["nodes"][1]["children"] = [2]
j["meshes"][0]["primitives"][0]["attributes"]["JOINTS_0"] = n_acc + 1
j["meshes"][0]["primitives"][0]["attributes"]["WEIGHTS_0"] = n_acc + 2

# --- buffer byteLength ---
j["buffers"][0]["byteLength"] = len(bin0)

# --- rebuild glb ---
json_bytes = json.dumps(j, separators=(",", ":")).encode()
json_bytes += b" " * ((4 - len(json_bytes) % 4) % 4)
out = struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(json_bytes) + 8 + len(bin0))
out += struct.pack("<II", len(json_bytes), 0x4E4F534A) + json_bytes
out += struct.pack("<II", len(bin0), 0x004E4942) + bytes(bin0)
with open(DST, "wb") as f:
    f.write(out)

# --- verify: POSITION/COLOR_0 byte-identical ---
def extract(path):
    with open(path, "rb") as f:
        magic, ver, length = struct.unpack("<III", f.read(12))
        ch = []
        while f.tell() < length:
            clen, ctype = struct.unpack("<II", f.read(8))
            ch.append((ctype, f.read(clen)))
    jj = json.loads(ch[0][1].decode())
    buf = ch[1][1]
    out = {}
    for key, acc_idx in jj["meshes"][0]["primitives"][0]["attributes"].items():
        acc = jj["accessors"][acc_idx]
        bv = jj["bufferViews"][acc["bufferView"]]
        o = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
        n = acc["count"]
        comp = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}[acc["type"]]
        dt = {5121: np.uint8, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}[acc["componentType"]]
        out[key] = np.frombuffer(buf, dtype=dt, count=n * comp, offset=o).tobytes()
    return out

a = extract(SRC)
b = extract(DST)
for k in a:
    print(f"{k}: identical={a[k] == b[k]} (src {len(a[k])}B)")
print("skinned glb written:", DST)
import os
print("size:", os.path.getsize(DST) / 1e6, "MB")