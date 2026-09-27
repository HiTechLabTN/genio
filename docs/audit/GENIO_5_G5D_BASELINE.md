# GENIO_5_G5D_BASELINE (read-only, 2026-09-27)

- SHA: `f7d1b12f20bdfe088f19bd51c0ba463f5ca7d63a`
- status: clean except runtime DBs + self-improve `ts` churn (excluded).
- G5-C closure: `GENIO_5_G5C_CLOSURE_AUDIT.md` (CLOSED GREEN WITH LIMITATIONS).
- CI: `36341406888` 6/6 (to re-verify post-change).
- toolchains: rustc 1.95.0 + cargo (~/.cargo/bin) · tauri-cli 2.11.4 ·
  node 22.23.2 · python 3.10.12 · java 21 + Android SDK (unused) ·
  xcodebuild absent · Xvfb + import (screenshots) present.
- OS: Pop!_OS x86_64. D-Bus control broken (queries OK).
- services: genio :8000 200 · ollama :11434 200 · voder/gestures/web up.
- signing: NO private key (pubkey labeled untrusted in tauri.conf).
- HiTech-OS: clone present (/tmp/opencode/hitechos), daemon WITHOUT
  IPC (TODO Phase 5) — reconfirm live in §H.
- contracts frozen: API 14+WS · IPC 1.x · installer protocol ·
  states · product-data · versions (4.1.0 product).
