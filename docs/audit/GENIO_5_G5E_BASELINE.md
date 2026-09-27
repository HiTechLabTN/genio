# GENIO_5_G5E_BASELINE (read-only, 2026-09-27)

- SHA: `09af3d50b385aba29a2574d446249791ef912bea`
- status: clean except runtime DBs + self-improve `ts` churn (excluded).
- G5-D: GREEN WITH LIMITATIONS (report `GENIO_5_G5D_FINAL_REPORT.md`).
- CI: `36349982746` 6/6 (to re-run post-change).
- versions: product 4.1.0 · client 4.3.0 = tauri.conf · installer 1.0.0 ·
  IPC 1.0 · API app 1.0.0 · Cargo 0.1.0 (scaffold debt, documented).
- artifacts: v4.1.0 GitHub release (6 files) · ghcr.io 4.1.0
  (sha256:61d4b42…) · AppImage+DEB local (unsigned).
- toolchains: rustc 1.95 · node 22 · python 3.10 · java 21 + SDK
  (unused) · xcodebuild absent · Xvfb/import present.
- signing: NO private key (BLOCKED, unchanged).
- platform availability: Linux full · Windows/macOS/Android/iOS absent.
- host fonts: 13 Arabic-capable families (Amiri/Noto/Cairo/Tajawal
  matches) — Xvfb tofu was env-specific, re-test in §8.
