# GENIO — GATE 3 RECOVERY AND TUNISIAN PUBLIC UX REPORT

## 1. Starting Commit

`de9504f` — fix(connectivity): same-origin /ws+/api proxy + local default target + resilient WS client.

## 2. Ending Commit

`gate3/*` commits on `main` (see git log): crash isolation, public UX refactor, README/tests/evidence. Pushed after verification. No tags, no releases, no version bumps, no G6-C.

## 3. Crash Reproduction

Fresh isolated browser context (`gate3-repro`), real app `http://localhost:8098/app`:
Landing → skip auth → continue permissions → technique mode (live telemetry) → click `وضع الماسكوت`.
Result: page body replaced ENTIRELY by `المشهد طاح — وضع الأمان يخدم.` — no buttons, no chat, no telemetry. User trapped; `genio.interfaceMode="mascot"` persisted, so reload re-crashed (permanent death loop, matching the human report).

Console (real):
- `R3F: Div is not part of the THREE namespace!` (+ `[v3 ErrorBoundary MascotStage-root]` stack through `MascotStage-*.js` → `Suspense` → `App-*.js`)
- Contributing env failures (not fixed, CSP stays strict): `blob:` texture blocked by `connect-src`, rapier wasm blocked by `script-src` (`unsafe-eval`), `THREE.WebGLRenderer: Context Lost` (headless).

## 4. Exact Root Cause

Two-level failure, root cause in OUR code (not the 3D engine):
1. Rapier/wasm fails under strict CSP → `<Physics>` throws inside the invisible physics `<Canvas>` (`MascotStage.tsx`).
2. The catching `MascotPhysics` ErrorBoundary rendered the DEFAULT fallback — a DOM `<div>` — **inside the R3F Canvas reconciler**. R3F rejects DOM host elements → the fallback itself threw the `Div` error, which propagated out to the screen-level `MascotStage-root` boundary and replaced the whole app.
3. That screen boundary offered no escape (message only) and the crashed mode persisted across reloads.

So: a contained visual failure was escalated into a full app kill BY the boundary's own fallback. Socket/backend were likely alive underneath — irrelevant, since all UI was gone (answers §2 Q-A/B/D/E/F: app must continue; boundary caused lifecycle trap, not a socket-first failure).

## 5. Exact Fix

`genio_client/src/components/v3/ErrorBoundary.tsx`:
- New `bare` prop: render `null` on error (R3F-safe) instead of a DOM div.
- New `onCrash(error)` observer hook (never breaks rendering).
- Default DOM fallback kept (now localized TN) for DOM contexts.

`genio_client/src/components/mascot/MascotStage.tsx`:
- `MascotPhysics` boundary → `bare` (physics loss = mascot stays centered, graceful).
- Mascot mic aria-labels localized (`mascot.mic_start/mic_stop`); mic errors mapped via `mapError` (raw English exceptions no longer shown).

`genio_client/src/App.tsx` (mascot branch only):
- `MascotStage-root` gets a real fallback: TN crash message + `boundary.mascot_crash_hint` + WORKING `الوضع التقني` / `الوضع الموحّد` buttons.
- `onCrash` persists `genio.interfaceMode=technique`, breaking the reload death-loop for that device only.

No 3D architecture changed, no assets replaced, no CSP weakened, no fake loading, no demo data.

## 6. Backend Connectivity Proof

Unchanged from Gate 2 and re-verified live during this run: same-origin `/api/v1/status` returns real backend JSON through the vite proxy; WS handshake + prompt delivery confirmed (`active_runs: 1` server-side during generation); chat `متصل — Genio جاهز` injected on open; live telemetry (ping ~23 ms, real CPU/RAM/GPU/Net) in screenshots. Zero `connect-src` violations.

## 7. Socket Lifecycle Proof

- Crash no longer touches the socket: after mascot render + escape back to technique, telemetry stayed live and chat sent normally (same session).
- Gate 2 resilience retained: heartbeat pause during runs, reconnect never drops when hidden, failed sends surface a TN error instead of eternal thinking.
- Presence states observed truthful (🟢 متصل / 🟡 thinking / connected chat badge).

## 8. Browser E2E Proof

Fresh flow on the final build: Landing → Try → Auth skip → Permissions continue → App → chat open → `شنوّة تنجم تعمللي؟` → full answer rendered (`gate3-tunisian-response.png`), thinking resolved, no toast, no error. Backend lifecycle intact AFTER the crash episode (same session previously entered mascot mode and escaped).

## 9. Actual Tunisian Response

Fluent Tunisian Derja (markers: متاع، نجم، برشا، نلوج، باش، شنوّ), multi-sentence capability answer + TN-labeled reasoning accordion (`🧠 تفكير جينيو`). Classification: TUNISIAN. Model prompt untouched (frozen scope).

## 10. README Audit

`README.md` at repo root was 100% ghost content from an unrelated project (AI Content Pipeline: Ghost CMS, ComfyUI, orchestrator.py, placeholder JWT) — contradictory product status per §16. Rewritten completely as Tunisian-first Genio README (structure per §15: شنوّة هو/ينجم يعمل/كيفاش تبدأ/ركّبو توّا/الأمان/للمطوّرين/التوثيق/API/Open Source/المساهمة/اللغات + FR/EN summaries). Commands and release facts sourced from `product-data.json` (v5.0.0) and `docs/releases/PUBLIC_RELEASE.json` — no invented claims.

## 11. Landing Audit

Was already ~90% TN hardcoded (no FR/EN path, no switcher, EN Product nav). Converted to `landing.*` keys (TU/FR/EN, ~70 keys) + `useLang` + on-page TN/FR/EN switcher + dynamic `dir`/`lang`. Verified in browser: TN default RTL, FR/EN LTR with fully translated hero, sections, roadmap, founder, platform, install steps, footer.

## 12. Every Public Route Audited

| Route | Before | After | Proof |
|---|---|---|---|
| `/` landing | TN hardcoded, EN nav, no switcher | keyed TN/FR/EN + switcher | gate3-01 |
| `/install` | EN body/steps/footer | keyed (locked-mirror-safe state layer) | gate3-04 |
| `/download` | EN | keyed, product-data URLs intact | body text |
| `/security` | EN (16 items) | keyed TN/FR/EN, proofs exact | gate3-07 |
| `/explore` | EN (14 areas) | keyed prose, tech nouns kept | body text |
| `/api` | EN | keyed chrome, schema untouched | body text |
| `/docs` | EN chrome | keyed chrome (corpus as-authored) | body text |
| Portal chrome | EN skip/menu/dialog/footer/copy | keyed (a11y/footer.*) | snapshots |
| SEO/meta | already TN-first | untouched | source |

Bonus root-cause fix found during audit: `setLang()` never dispatched `genio:lang`, so portal body content could NEVER switch language (only the nav, which used local state). Fixed centrally + `PortalLayout` moved to `useLang`. Proven: FR switch re-renders full body (gate3-10).

## 13. Language Switching

TN → FR → EN → TN verified on landing AND portal with measured `document.dir`/`lang` (rtl/ar, ltr/fr, ltr/en, back to rtl/ar). No stale strings (full-body re-render via event). Evidence: gate3-10/11/12.

## 14. Mobile

390×844 emulated mobile+touch: landing and install measured `scrollWidth === clientWidth` (overflowX = 0). Evidence: gate3-16-mobile-390.png.

## 15. Accessibility

- All new strings use existing localized a11y keys (skip/menu/dialog/copy/copied/aria).
- Mic/send/close/open/kill/disconnect labels already TN; mascot mic aria fixed this run (verified `احكي مع Genio` in browser).
- Focus-visible, skip-link, dialog Escape, keyboard-only journey previously verified; portal tests assert labelled copy buttons + landmarks.
- No English-only a11y labels remain in the TN experience.

## 16. Security

- No secrets/tokens/keys added; no URLs carry credentials; CSP meta untouched; `connect-src` not widened; proxy is loopback-only in local servers.
- `mapError` reused for mascot mic errors; boundary fallback drops internal component names.
- Backend `test_browser_security.py` honesty test updated to the i18n-backed contract (keys present ×3 langs + product-data URLs).

## 17. Automated Tests

- TypeScript: PASS, 0 errors.
- Frontend: PASS, 89/89 (10 files) — includes 3 new lang tests (full-table key probes, TN-surface barrier scan, `genio:lang` dispatch) and retargeted portal tests asserting TN-first rendering.
- Backend: PASS, 227/227 (incl. updated honesty test).
- Build: PASS clean; served chunks verified to contain the refactor.

## 18. Evidence Files

`promt/qa-evidence/g6b-tunisian-final/` (PNGs gitignored/local; JSON committed):
- gate3-01-landing-tn.png, gate3-04-install-tn.png, gate3-07-security-tn.png
- gate3-10-language-fr.png, gate3-11-language-en.png, gate3-12-language-back-tn.png
- gate3-16-mobile-390.png, gate3-mascot-mode.png, gate3-tunisian-response.png
- phase-f-browser-results.json (+gate3 section; prior failure history preserved)

## 19. Remaining Limitations

1. Doc corpus bodies (`docs-content/*.md`) stay as authored (mostly EN); viewer chrome is TN/FR/EN.
2. Explore area titles stay technical EN nouns (Agent runtime, Sandbox…); all prose TN/FR/EN.
3. Under strict-CSP/WebGL-less environments the 3D avatar may degrade to 2.5D/CyberAvatar or the honest fallback — never traps the user now.
4. Model dialect varies per generation (prompt frozen); this gate's UI run was pure TN.
5. `usePageMeta` titles come from localized page titles (TN default) — per-language SEO routes not architected (noted, out of scope).

## 20. Final Verdict

**TUNISIAN-FIRST UX VERIFIED** — the reported production crash is reproduced, root-caused, fixed and proven (mascot renders degraded + escape works + backend lifecycle intact + real TN response in UI); the full public surface (landing, all portal routes, footer, menus, README) is Tunisian-first with working FR/EN secondaries; regression is green (89/89 + 227/227); evidence is real and preserved.
