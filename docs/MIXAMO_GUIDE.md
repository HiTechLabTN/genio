# Mixamo Guide — Genio Body OS

Founder can drop FBX clips from Mixamo to enable high-quality motion:

1. Go to https://www.mixamo.com/ → login → search "Genio" or basic human
2. Select Genio rig (if uploaded) or default human
3. Download FBX clips:
   - `wave.fbx` (Greeting)
   - `walk.fbx` (Locomotion)
   - `idle.fbx` (Breath)
   - `talk.fbx` (Jaw)
4. Drop into `media/mixamo/` (create folder if needed)
5. Run `python3 scripts/convert_mixamo.py` to retarget to `media/rig/mascot_rigged.glb`
6. Charter will auto-prefer `clipsOrProcedural: clips` when FBX present, else procedural.

Until FBX provided, procedural engine drives motion (walk cycle hip bob+leg swing, idle breath, wave via shoulder/elbow IK, talk jaw by audioLevel, blink 3-6s).

See `media/rig/README.md` for rig naming.
