# Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Avatar stuck on 2.5D / v3 | master GLB 404 or draco decoder offline | check `/models/genio_mascot_master*.glb` 200; full GLB is decoder-free fallback |
| `Bone Heat Weighting failed` | TripoSR meshes are non-manifold | use ENVELOPE parenting (`/tmp/fix_envelope.py` pattern), verify `verts with weights > 0` |
| Exported GLB has 0 skins | all vertex groups empty (see above) | re-parent + re-export, re-run validator |
| Only 1 animation exported | actions not in NLA | push one strip per action before export |
| Morph names missing in file | Blender 3.0 writes `mesh.extras.targetNames`, not primitive extras | validator reads mesh-level names |
| BBox looks rotated | glTF is Y-up; Blender is Z-up | compare Y extents, not Z |
| `woff2 fonts not supported` (troika) | 3D text needs TTF | use `/fonts/orbitron-variable.ttf` |
| Draco `libextern_draco.so` missing | Blender 3.0 Debian packaging | export plain + `gltf-transform --compress draco` afterwards |
| xatlas `mesh.glb` is ASCII | TripoSR writes OBJ text under `.glb` name | reload with `file_type='obj'` + re-export true GLB via trimesh |
| Headless FPS ~20 | SwiftShader software GL | expected; RTX 3060 prod ≈ 60 (overlay badge) |
| CORS telemetry errors on localhost | prod API allowlist | benign in dev; nginx proxies in prod |
