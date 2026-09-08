# Animation System

## Layers (§14)

- **BASE**: idle, idle_variant_01/02, idle_thinking, walk, run, sit, stand,
  sleep, wake, step_*, turn_* — full-body / locomotion-in-place.
- **UPPER_BODY**: point, invite, speak_emphasis, executing, applaud-style work.
- **HEAD**: nod, shake_head, gaze looks, think, listen variants, wait.
- **SPECIAL**: hero, celebrate, success, greeting, wave, excited, happy…
  (exclusive, high priority, min-duration protected).
- **FACE** (runtime morphs): 24 targets, combinable
  (`smile 0.7 + browUp 0.2 + squint 0.15`).
- **LIPS** (runtime): 22 viseme groups → MouthOpen/JawOpen/LipPucker/LipPress
  + Jaw bone; consumes `LipSyncTimingProvider` or audio-level fallback.
- **SECONDARY** (runtime springs): Beard, Hair, Chachia_Tassel, Chachia, Jebba…

Blending: `fadeIn/fadeOut` crossfades via native `THREE.AnimationMixer`.

## Motion graph (§21)

`ruleFor()` per clip: priority, interruptible, blendDuration, cooldownMs,
minDurationMs. Higher priority interrupts; `greeting/wave/hero` are
non-interruptible for their min duration; idle never blocks.

## Adding animations

1. Author bone action in `master.blend` (or extend `/tmp/build_master.py`
   `CLIPS` + rebuild).
2. Push one NLA strip named exactly the clip id.
3. Re-export + validate + add id to `KNOWN_CLIPS` allowlist
   (`MascotEventBridge.ts`) if it must be triggerable.

## Adding expressions / visemes

- New morph: add `add_sk()` region in build script, rebuild, reference by
  exact shape-key name in `ExpressionController.setExpression()`.
- New viseme: extend `VISEME_MAP` in `MascotFace.ts` (weights 0..1).
