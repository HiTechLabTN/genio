# TripoSR High-Quality Image-to-3D — RTX 3060 12GB Setup (Pop!_OS 22.04)

Source image: `genio_client/src/assets/mascot/genio-hero.png` (2.4M) — crimson jebba + gold sfifa + red chachia + glasses + beard + robotic arms + G glow.

## Why stop blender fallback?
`genio_blender_glb_only.py` creates deformed primitive (cube + subdiv) unacceptable for production startup. Replaced by TripoSR neural reconstruction using 12GB VRAM.

## Exact Terminal Commands Executed (autonomous, no pause)

```bash
# 0. Discover GPU/RAM
nvidia-smi
free -h
df -h /data

# 1. Clone TripoSR
git clone https://github.com/VAST-AI-Research/TripoSR.git /data/ai_tools/TripoSR

# 2. System deps
sudo apt update && sudo apt install -y python3.10-venv

# 3. Venv with system torch (2.11+cu130) to leverage 12GB VRAM
python3 -m venv /data/ai_tools/TripoSR/venv --system-site-packages
/data/ai_tools/TripoSR/venv/bin/pip install --upgrade pip
/data/ai_tools/TripoSR/venv/bin/pip install omegaconf==2.3.0 Pillow==10.1.0 einops transformers==4.35.0 trimesh rembg huggingface-hub imageio onnxruntime xatlas moderngl timm scikit-image

# 4. Patch torchmcubes -> fallback to skimage (avoids CUDA build hell)
# Edit tsr/models/isosurface.py to try torchmcubes else skimage.marching_cubes with .copy() fix
# Patch trimesh util.py/base.py/bounds.py .ptp() -> np.ptp for numpy 2.2

# 5. Patch bake_texture device mismatch (cuda:0 vs cpu)
# tsr/bake_texture.py: positions = torch.tensor(..., device=scene_code.device) and .cpu().numpy()

# 6. Download model (1.68G) + rembg U2Net (176M) on first run (cached at ~/.cache/huggingface/hub + ~/.u2net)
# 7. Generate clean mesh (vertex colors 1.3M)
/data/ai_tools/TripoSR/venv/bin/python /data/ai_tools/TripoSR/run.py \
  /data/ai_tools/genio/genio_client/src/assets/mascot/genio-hero.png \
  --device cuda:0 --output-dir /data/ai_tools/genio/media/triposr_output \
  --model-save-format glb --mc-resolution 256 --chunk-size 8192

# 8. Generate baked texture high-quality (7.3M OBJ + 840K texture -> 3.1M GLB)
/data/ai_tools/TripoSR/venv/bin/python /data/ai_tools/TripoSR/run.py \
  /data/ai_tools/genio/genio_client/src/assets/mascot/genio-hero.png \
  --device cuda:0 --output-dir /data/ai_tools/genio/media/triposr_output \
  --model-save-format glb --bake-texture --texture-resolution 1024 \
  --mc-resolution 256 --chunk-size 8192

# Convert OBJ+texture to GLB with texture (trimesh TextureVisuals)
python -c "import trimesh, PIL.Image; mesh=trimesh.load('/tmp/baked.obj', force='mesh'); tex=PIL.Image.open('texture.png'); mesh.visual=trimesh.visual.texture.TextureVisuals(uv=mesh.visual.uv, image=tex); mesh.export('/tmp/baked_textured.glb')"
cp /tmp/baked_textured.glb /data/ai_tools/genio/media/mascot_raw.glb
cp /tmp/baked_textured.glb /data/ai_tools/genio/genio_client/public/media/mascot_raw.glb

# 9. Auto-rig preserving face/glasses (Blender 3.0.1, Rigify)
blender --background --python /tmp/rig_baked_obj2.py
# Script: import OBJ -> scale to 1.7m -> assign Principled+texture -> add Human Metarig 0.85 -> parent ARMATURE_AUTO (159 groups) -> export GLB 3.9M
# Outputs:
# /data/ai_tools/genio/media/rig/mascot_rigged.glb (3.9M, 49k verts, 63k faces)
# /data/ai_tools/genio/genio_client/public/media/rig/mascot_rigged.glb
```

## VRAM Usage
TripoSR chunk_size 8192 uses ~9GB /12GB during model run (1.5s) + marching cubes 2s on CPU fallback (skimage) -> total ~14s generation, texture baking 13s.

## Verification
- `media/mascot_raw.glb` 3.1M `glTF binary` (was 1.2M deformed) — 49k verts 63k faces bounds ~1.0 cube, not primitive
- `media/rig/mascot_rigged.glb` 3.9M glTF binary with 159 vertex groups, texture preserved
- `npx tsc --noEmit 0` + `npm run build 0` still pass (GenioBody lazy chunk 3.2M, mesh loaded at runtime)
- Face/beard/glasses intact via baked texture, not separate deformable primitives.

## Fallbacks Logged
- ComfyUI-3D-Pack Windows prebuild mismatch -> bypassed via standalone TripoSR
- torchmcubes CUDA build failed (CUDAToolkit missing) -> patched to skimage CPU fallback
- trimesh numpy 2.2 ptp removal -> patched to np.ptp
- bake_texture grid cpu vs cuda + .numpy() on cuda tensor -> patched to device + .cpu()
- xatlas.export writes OBJ despite .glb name -> converted via trimesh to true GLB
- Blender 3.0 glTF import Bad glTF on TripoSR GLB -> used OBJ import path
- Bone Heat Weighting warning for fingers -> procedural motion tolerates, keeps head/torso weighting.

## Next: MIXAMO_GUIDE pipeline still valid
Drop FBX clips into `media/mixamo/` -> `movement_charter.json` auto prefers `clips` when present. Until then procedural engine drives motion with clean mesh.
