# Asset Pipeline — genio_mascot_master.glb

```
Reference Photo (assets-pipeline/reference-views/front.png)
  → TripoSR cuda:0 mc-resolution 512, bake-texture 2048  (/tmp/build: run.py)
  → OBJ-text misnamed .glb → trimesh → v3_true.glb (18M, 332k verts)
  → Blender clean: merge doubles, decimate 40k tris, scale 1.7m, floor
     → v3_clean.glb (5.3M) + v3_clean_mixamo.fbx (Mixamo manual path)
  → Rig: 34 deform bones (envelope weights, AUTO Bone Heat fails on TripoSR
     meshes — documented) + 7 secondary bones + 4 attachment empties
  → 28 morphs (4 legacy + 24 facial, region-based, bbox-relative)
  → 52 bone actions (in-place; face stays runtime-driven)
  → NLA one strip per action → export skins+morphs
  → genio_mascot_master.glb (37M) → gltf-transform draco (5.1M)
  → scripts/validate_mascot_glb.py (15/15 gates required)
```

## Rebuild

```bash
blender --background --python /tmp/build_master.py   # needs assets-pipeline/mesh-raw/v3_rigged.blend
python3 scripts/validate_mascot_glb.py
npx @gltf-transform/cli optimize genio_client/public/models/genio_mascot_master.glb \
  genio_client/public/models/genio_mascot_master_draco.glb --compress draco
```

Build scripts live in `/tmp/*.py` (clean_v3, rig_v3_8clips, fix_nla_export,
fix_envelope, build_master, fix_normals); `master.blend` is the reproducible
source (`assets-pipeline/mesh-raw/master.blend`).

## Reconstruction assumptions (§35)

Single-photo TripoSR cannot know hidden geometry: back/sides are hallucinated,
tall fez + glasses are approximate, no tongue geometry exists (TongueOut is a
lower-lip/chin nudge). Front/three-quarter likeness (beard, robe, G emblem
region, robotic limbs) is faithful; do not claim photogrammetric accuracy.
