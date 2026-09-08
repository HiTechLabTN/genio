# Genio Mascot Master — Architecture

```
User Input → Intent/Context → Emotion Estimator → Conversation State
  → Behavior Planner (MascotController.planDirective)
  → Animation + Expression + Gaze + Voice (MascotScene)
  → LayeredMixer (BASE/UPPER/HEAD/SPECIAL + FACE/LIPS/SECONDARY runtime)
  → Secondary motion springs + Rapier position driver
  → Rendered Mascot (+ reactive MascotEnvironment)
```

## Files

| File | Role |
|---|---|
| `genio_client/public/models/genio_mascot_master*.glb` | Production asset (draco 5.1M primary, 37M full fallback) |
| `components/mascot/master/MascotScene.tsx` | Canvas composition, loader chain, perf/a11y modes |
| `components/mascot/master/MascotMixer.ts` | Layered mixer + motion graph + procedural composer |
| `components/mascot/master/MascotFace.ts` | Expression controller + 22 visemes + TTS adapter |
| `components/mascot/master/MascotLife.ts` | Blink/saccades/breath (seeded) + secondary springs |
| `components/mascot/master/MascotEnvironment.tsx` | Procedural void, rings, particles, reactive lights |
| `components/mascot/master/MascotController.ts` | Intent → directive + memory client |
| `components/mascot/master/MascotEventBridge.ts` | Genio state → canonical events, clip allowlist |
| `components/mascot/master/MascotDebugPanel.tsx` | Dev-only diagnostics + triggers |
| `services/mascotBehavior.ts` | 4-dim planner (legacy) + 6-dim estimator + channel map |
| `components/mascot/MascotStage.tsx` | Host: physics driver + fallback chain + mic/voice |
| `genio_gestures/app.py` | Motion memory API (record/recommend, weighted scoring) |
| `scripts/validate_mascot_glb.py` | 15-gate GLB validator |

## Fallback hierarchy (§30)

`master draco → master full → RiggedMascot v3 → CyberAvatar → 2.5D StateLoopAvatar`.
Every layer is wrapped in `ErrorBoundary`; failures log + degrade, Genio stays up.

## Layout

```
genio_client/src/components/mascot/
  MascotStage.tsx        # host (physics, mic, mode switch, fallback chain)
  StateLoopAvatar.tsx    # 2.5D fallback
  RiggedMascot.tsx       # v3 GLB fallback
  Genio3D.tsx            # photoreal view (technical mode)
  master/                # master runtime (see table)
assets-pipeline/
  reference-views/       # source photos (front/back/neutral/grid/hero)
  mesh-raw/              # TripoSR output, cleaned, blends, final GLBs
```
