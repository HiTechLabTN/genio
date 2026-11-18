# GENIO — MASCOT VISUAL REVAMP REPORT

## 1. Current Visual Problem

Human review: the interface did not visually match the intended Genio product — no visible personnage, no convincing living-assistant animation, too static. Reproduced in a real headless browser (`mascot-revamp/00-before-technique.png`): the default technique mode is a **black void** (telemetry chips + mode buttons + chat FAB floating on nothing), and mascot mode showed only holo rings with no character (3D GLB fails under strict CSP / WebGL-less envs).

Internal diagnosis (A–O): A ✓ (no character in default mode), F (3D canvas fails) + G (fallback replaces mascot), H (mascot lives only in a mode users rarely enter / that previously crashed), O (UnifiedShell mascot tiny 56–112px circle, static hero most states). NOT B/C/D/E/I/K/L/M/N: no z-index/clipping/size/asset-load/reduced-motion causes — the expressive state assets (`genio-listen/think/speak.webp`) existed but were wired only into IntroCinematic/StateLoopAvatar/HologramMascot, never into the main `imageForState` mapping (thinking/executing/speaking all showed static hero).

## 2. Root Cause

Two gaps, both frontend composition (no backend involvement):
1. `imageForState` (presence → image) ignored the expressive state portraits.
2. No character anchor in the default experience; the 2D canvas layer renders nothing observable when WebGL is unavailable, and UnifiedShell shrank the mascot to a badge.

## 3. ComfyUI Environment

- Location: `/data/ai_tools/comfyui-app` (source install), API `:8188` — observed busy/unresponsive during audit (active generation by another job; empty API responses).
- Models: `v1-5-pruned-emaonly.safetensors` (4 GB, real); `sd_xl_base_1.0.safetensors` (dangling link); `sdxl_vae` present; no LoRAs, no background-removal models.
- Device: RTX 3060 12 GB shared with Ollama `gemma4:12b` (~5 GB resident).
- Prior turntable outputs (`mascotv2_*`) inspected: consistent face but different rig/blendshapes and non-transparent backgrounds.
- DECISION (per spec §8, quality > novelty): **no generation**. The existing canonical family covers all 8 required states with proven identity consistency; generating would risk identity drift, VRAM contention with the model backend, and fighting a busy server. No model weights touched or committed.

## 4. Generated Assets

None generated (deliberate — see §3). Production serves pre-existing optimized static WebP only.

## 5. Existing Assets Preserved

All canonical assets untouched. State mapping now uses the consistent bearded-jebba identity only: `genio-hero` (idle), `genio-listen` (listening), `genio-think` (thinking/working), `genio-speak` (speaking), `character/genio-wave` (greeting), `character/genio-wink` (success). Deliberately EXCLUDED as inconsistent faces: `genio-jebba-wave`, `genio-exec`, `genio-burnous-present` (different robot characters). Error/offline reuse base with honest CSS treatment (tone ring + dim) — no fake assets. Manifest: `promt/qa-evidence/mascot-revamp/mascot-assets.json` (family ~1.1 MB total, hero eager, rest lazy, nothing >300 KB).

## 6. Animation Architecture

CSS keyframes only (transform/opacity/filter): breathe (idle), lean (listening), sway (thinking), work-pulse (executing), speak-pulse (speaking), celebrate-bounce ×3 (success), slow-spin (reconnecting ring). Crossfade comes free from image swap on state change. No animation engine, no new deps. `prefers-reduced-motion: reduce` kills every keyframe (portrait stays visible static) — unit-tested. New `LivingMascot` (technique anchor, full portrait, status line) + upgraded `unified/Mascot` (140px default, per-state motion, localized aria via existing `shell.*` keys) + landing hero idle float.

## 7. Presence-State Mapping

Single source: presence semantic state → `imageForState` → component; engine phase → ring/motion. No second machine, no timers, no simulated activity:
idle→hero, listening→listen, thinking/understanding/planning→think, executing→think, explaining→speak, success/celebrating→wink, error→hero+red, offline/disconnected→hero+dim, reconnecting→hero+amber.
Plus a real fix found en route: `UnifiedShell` passed `lastOutcome: undefined` always, making engine COMPLETE unreachable — now derived honestly from chat (answer + inactive + no error → success; error → error).

## 8. Crash Isolation

`LivingMascot` is pure DOM/CSS (unit-asserted: no canvas/three/webgl strings), asset failure degrades hero → "G" letter, used inside the existing boundary structure. Deliberately tested: mascot mode still renders (rings + mic + escape) with zero whole-app risk; technique/unified never mount R3F for the anchor. Chat/backend/socket untouched.

## 9. Performance Measurements

- Added JS: ~0 (CSS only, one small component reusing existing imports).
- Image payload: ~1.1 MB family, lazy per state; hero (196 KB) was already eager on landing.
- Build: clean, ~8 s. No bundle-size inflation beyond images (already shipped).
- Runtime: transform/opacity animations only (compositor-friendly); reduced-motion disables all.
- Backend freed during the run (stale pages closed): :8000 conns 12→4, GPU util 30%→0%, runs 0.

## 10. Mobile Results

390×844 emulated mobile+touch: anchor scales to 0.6, character + status visible, chat FAB reachable, measured `overflowX = 0` (`10-mobile-390.png`).

## 11. Accessibility

- Localized accessible names everywhere new (anchor role=img uses the same TN status line; unified Mascot aria now TN via `shell.*`).
- Animation spans aria-hidden; live regions unchanged (single polite status); keyboard/focus/skip-link untouched; mic failure announces the TN error (proven in browser).
- Reduced motion: static portrait + all keyframes guarded (unit test + in-page style-block verification).

## 12. Language

Zero new English-first strings: status lines reuse `shell.*`; aria reuses `shell.*`; no new keys needed. RTL/LTR/dir behavior untouched (verified TN/FR/EN round-trips in prior gates; this change adds no text).

## 13. Browser Screenshots

`promt/qa-evidence/mascot-revamp/`: 00-before-technique, 01-landing-mascot, 02-app-ready-mascot, 03-listening (mic-less env → honest TN mic error; portrait mapping unit-covered), 04-thinking, 05-speaking, 06-complete (wink + `كمّلت المهمّة`), 07-error (offline emulation → TN reconnect toast), 08-unified-mode, 09-technical-mode, 10-mobile-390, 11-reduced-motion (+guards verified in DOM), mascot-assets.json.

## 14. Test Results

- TypeScript: 0 errors. Frontend: 99/99 (11 files) — incl. 7 LivingMascot tests (mapping ×5, a11y, isolation, motion guards) + 2 outcome tests (success drives wink; active task never claims completion) + retargeted mapping tests. Backend: 227/227. Build: clean; served chunks verified.

## 15. Known Limitations

1. This run's live model answer showed MSA/Egyptian drift (recorded verbatim in evidence; model prompt frozen per rules) — visual state machine unaffected.
2. Listening portrait cannot render live in mic-less headless (NotFoundError proven); covered by asset + unit test + honest TN error path.
3. `genio-jebba-wave/exec/burnous-present` excluded as identity-inconsistent (not deleted).
4. No ComfyUI-generated frames (documented decision); turntable `mascotv2_*` noted as future option only.
5. Complete/wink shows in Unified on real completion; technique anchor holds the speaking visual while the result stands (by design: result visible = still presenting).
