# GENIO_5_G5C_BASELINE (read-only capture, 2026-09-27)

- SHA: `73b557585cf13bcdf4b18b167749d07da670daec`
- status: clean except runtime DBs (feedback_memory.json, gestures.db)
  + self-improve `ts` churn in genio/core/compiled_skills/ (excluded).
- versions: product 4.1.0 (VERSION) · client 4.3.0 = tauri.conf
  (Cargo 0.1.0 scaffold debt) · installer 1.0.0 · IPC 1.0.
- native targets: linux AppImage+DEB PROVEN (G5-B) · Windows/macOS/
  Android/iOS BLOCKED (toolchains/secrets).
- Tauri perms (`default.json`): core/opener/updater/process/shell/os/
  http/upload/fs defaults; shell=open-only (no execute, grep-proven);
  fs+http scopes unrestricted (G5-C task A).
- bridge commands (`src/desktop/bridge.ts`): getInfo/openUrl/
  getDiagnostics/notification — typed, no execute; URL allowlist
  https+intent (tested, 5 tests).
- updater state: minisign pubkey present but labeled untrusted, NO
  private key, endpoint latest.json ABSENT from v4.1.0 release.
- notification state: abstraction only (web Notification if granted,
  else PERMISSION_REQUIRED); NOT wired to task events (G5-C task E).
- task-event state: hook exposes thinkingSteps/toolActivity/metrics/
  result/error/isProcessing; UnifiedShell consumes; desktop does not
  observe task events yet (G5-C task E).
- test matrix: backend 288+79 · installer 28 · vitest 43+ · tsc 0 ·
  CI 6/6 (run 36322597177).
- blockers: Rust signing key · Windows/macOS toolchains · Android
  SDK-use+secrets · Xcode · D-Bus control · get.genio.ai domain.
- G5-B proofs: AppImage 117MB launched under Xvfb, landing rendered
  (`promt/qa-evidence/g43-desktop-native.png`), DEB produced.
