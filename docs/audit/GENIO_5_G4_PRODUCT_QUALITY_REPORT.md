# GENIO_5_G4_PRODUCT_QUALITY_REPORT

## 1. Baseline

dist 178MB (JS 4MB, CSS 76K, fonts 64K, media+models ~170MB, 0 maps).
LCP/committed budgets: none. a11y: aria 0 in Landing, no skip link,
no focus system. Headers: no CSP/HSTS/XCTO/Referrer/frame (measured
at :8098 and tunnel). Admin open. UA in analytics body.

## 2. Bundle analysis

Top: rapier 2.2M, mascot_cutout.png 1.3M, MascotStage 1.1M,
intro_voiceover .m4a 0.6M, hero webp 196K. Entry chunks ≤28KB.
5 unreferenced .glb (~110MB) shipped in dist; 1 referenced .glb
moved by mistake and restored (verified). Duplicates: three
deduped OK; png+webp fallback pair is intentional resilience.

## 3. Optimizations

- 5 dead .glb → `genio_client/model-archive/` (tracked, unserved).
- Result: dist 178M → 89M (-50%), JS/CSS/fonts untouched.
- Kept: png fallback (onError resilience), all 3D, all features.
- CSP `<meta>` added (tested live, 0 functional breakage);
  frame-ancestors removed from meta (ineffective there — edge headers required, documented).

## 4. Before/after measurements

| Metric | Before | After |
|---|---|---|
| dist total | 178MB | 89MB |
| JS total | 4.0MB | 3.88MB |
| LCP / (1440) | — | 856ms |
| CLS / | — | 0.005 |
| /app, /explore LCP | — | 568ms, 524ms |
| glb 404s after move | — | 0 |
| http>=400 | 1 (analytics beacon, pre-existing fire-and-forget) | same |

Budgets (`budgets.json`, CI-enforced): dist ≤100MB, JS ≤6MB,
CSS ≤300KB, route chunk ≤200KB, 3D chunk ≤2.5MB — all green.

## 5. Accessibility audit

Contrast (computed): neon/void 11.2, white/void 20.2, dim/void 7.1,
slate/cyan 9.9 (AAA). Landmarks + skip link + named buttons verified
live. Fixed: h1 missing on portal pages (sr-only h1 in layout),
MotionConfig reducedMotion="user" globally, touch targets ≥24px
(copy buttons, brand, footer), CodeBlock min-w-0. Portal uses native
semantics; dialogs labelled + Escape; errors via role=alert.

## 6. Mobile audit

360/390/412/768/1440: overflow 0 everywhere after Card min-w-0 fix
(/download was 597px — root-caused to grid min-width, fixed,
re-verified). Touch targets fixed. Mobile landing stacks cleanly
(screenshot evidence).

## 7. Design-system audit

3 hardcoded `#020B1E` in portal → `var(--g5-void)`. Rest uses tokens
or Tailwind scale. No new abstraction layer.

## 8. Security hardening

- CSP meta (measured safe); frame-ancestors/HSTS/XCTO →
  edge responsibility (documented, Cloudflare adds none today).
- No postMessage/innerHTML/eval/Command.execute in client (tested);
  DocsViewer escapes (tested); updater `open(url)` audited legitimate;
  location.href targets are self-written cache files (audited).
- Admin: Bearer gate implemented + SSR no-leak test.
- API: CORS/rate-limit/auth unchanged (regression green).
- Analytics: UA removed from beacon body; PRIVACY.md created.

## 9. Supply-chain audit

npm audit: 2 moderate (unchanged, non-blocking). pip-audit: 0.
SBOM 968 components regenerated. Lockfiles intact. ruff pinned,
node 22 pinned.

## 10. Reliability tests

API-blocked → app renders degraded notice. No-WebGL → renders, 0
errors. Reduced-motion honored. Offline hard-fail = browser-level
(Chromium offline blocks localhost too) → LIMITATION (no offline
shell proven). Slow-network: not measured (noted).

## 11. Observability decisions

Beacon = path+ts only (first-party, fire-and-forget, zero app
dependency). No silent third-party collection exists. Diagnostics
copy stays user-initiated + scrubbed. Documented PRIVACY.md.

## 12. Documentation consistency

Fixed: INSTALLATION bootstrap ref pointed at deleted tag
(v2.0.0-sovereign-rc1 → v4.1.0). Docs links `/docs#x` → real slugs
(all resolve live). product-data + docs sync --check green.

## 13. Remaining limitations

Offline shell unproven · contrast instrumented by sampling (4 pairs) ·
screen-reader pass manual-only · edge headers need infra action ·
dist still 89MB (3D/models by design) · slow-network unmeasured.

## 14. External blockers

Unchanged (Tauri/APK toolchains, HiTech-OS daemon, D-Bus control).

## 15. Exact commits

(this report committed next; code commits in log)

## 16. CI run

(to monitor after push)

## 17. Final verdict

GREEN WITH LIMITATIONS (budgets met, a11y materially improved,
no regression; only documented non-critical limits remain).
