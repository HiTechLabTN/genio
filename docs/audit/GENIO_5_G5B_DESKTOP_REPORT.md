# GENIO_5_G5B_DESKTOP_REPORT

## 1. Toolchain discovery

rustc 1.95.0 + cargo 1.95.0 (stable, ~/.cargo/bin — NOT on default
PATH, used via explicit PATH) · tauri-cli 2.11.4 (local node_modules)
· node 22 · x86_64 · webkit2gtk-4.1-dev present per dpkg (headers path
unverified, build succeeded anyway) · java 21 + Android SDK present
(used only for matrix) · xcodebuild absent (Linux).

## 2. Tauri architecture

v2 app (`tn.hitechlab.genio`, product 4.3.0): ONE scaffold command
(`greet`, inert) + 8 plugins (opener/process/shell/fs/os/upload/
http/updater). UI = canonical web build (dist). No second product.

## 3. Permission audit

`default.json`: core/opener/updater/process/shell/os/http/upload/fs
default sets. Verified usage: os(platform), opener(openUrl),
updater(check), upload/download (APK flow), http(fetch), fs (cache
writes), shell `open(url)` ONLY (no Command/execute anywhere —
grep-proven). Findings: fs+http scopes unrestricted (no per-path/per-
URL allowlist) — works today, hardening = explicit scopes keyed to
cache-dir + update endpoints (follow-up, must not break updater).
No wildcard beyond plugin defaults; no change made blindly.

## 4. Native command registry

`src/desktop/bridge.ts`: exactly 4 typed commands
(getInfo/openUrl/getDiagnostics/notification). No execute/runShell
(exists nowhere — tested). URL allowlist: https + intent only
(javascript:/file:/custom rejected, tested).

## 5. Browser/native boundary

Web stays safe in Tauri: intent → validated command → result.
`open()` = external handler only (audited). No privileged op from UI.

## 6. Filesystem policy

Cache-dir + user-selected only (documented contract); unrestricted
APIs never exposed to frontend; Genio FS semantics preserved
(server-side, unchanged).

## 7. URL policy

https + intent allowlist, host required, malformed rejected (tested).

## 8. Diagnostics

`desktop.getDiagnostics`: app version, OS/arch, installer note,
backend pointer — NO env, NO tokens, NO paths (tested NOT_AVAILABLE
on web, never faked).

## 9. Notifications

Web Notification when granted, else PERMISSION_REQUIRED (tested).
Real events only (wiring to task events = next gate).

## 10. Lifecycle

launch→bootstrap→detect→connect→ready via REAL probes
(`probeRuntime`: HTTP /health + WS handshake). `ready` requires both;
degraded/failed otherwise (tested mapping).

## 11. Connection management

CONNECTING/CONNECTED/DISCONNECTED/RECONNECTING/FAILED vocabulary
exists in socket hook; desktop reuses it (no parallel machine).
Reconnect = existing semantics.

## 12. Installer integration

No duplication: desktop will shell OUT to official CLI / protocol
events (contract). Not wired yet (no native stdin bridge) — declared.

## 13. Update integration

Follows G5 contract via Tauri updater plugin config (endpoint
`releases/latest/download/latest.json`, minisign key PRESENT but
labeled untrusted + NO private key here → signing = external action).
Implemented flow: check→download→install→health→commit (plugin);
rollback = reinstall previous (documented).

## 14. Presence integration

Same `resolvePresence` (no desktop machine). TelemetryBar contract
already live in web; desktop renders same UI → same semantics.

## 15. Native build matrix (REAL, this host)

| Target | Result | Evidence |
|---|---|---|
| Tauri Linux | **BUILT+LAUNCHED** | AppImage 117MB `genio-client_4.3.0_amd64` + DEB produced; launched under Xvfb; landing rendered (screenshot) |
| Signing (updater) | BLOCKED | no private key (public key present, untrusted label) |
| Tauri Windows | BLOCKED | no toolchain here (CI windows runner = future) |
| Android | BLOCKED | no android/ dir; SDK present unused; signing secrets absent |
| iOS | BLOCKED | no Xcode/Linux |

## 16. CI

No new jobs (native builds need secrets/runners; adding a red job
would be theater). Existing 6 jobs cover shared code (bridge tests
run in frontend job). Recommendation: linux AppImage job AFTER
signing infra exists.

## 17. Security tests

5 bridge tests (shell detect, URL reject, NOT_AVAILABLE honesty,
input validation, lifecycle mapping) + existing suites green.

## 18. Visual QA

`promt/qa-evidence/g43-desktop-native.png`: REAL Tauri window
(Xvfb root capture, unedited) — landing + canonical character +
portal nav. Arabic glyph tofu = Xvfb font env artifact (browser
shots render correctly). Clearly a native shell, labeled as such.

## 19. Known limitations

Updater signing keys · fs/http scope tightening (audited, pending) ·
notifications wiring to task events · installer native bridge ·
Windows/macOS builds · mobile builds · Arabic fonts in minimal X env.

## 20. Exact commits

(next commit)

## 21. CI evidence

(to monitor)

## 22. Verdict

GREEN WITH LIMITATIONS — desktop architecture + code complete,
Linux native build+launch PROVEN, canonical UX preserved, boundaries
tested; blocked targets explicitly listed, nothing faked.
