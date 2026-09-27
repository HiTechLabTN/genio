# GENIO_5_PLATFORM_CONTRACT (shared vs platform-specific)

## Shared (no silent divergence)

UX semantics (18+18 states) · API (14+WS) · WS protocol · auth model
(key/boot-guard/Bearer) · task state shape · presence state shape ·
installer protocol (JSON events v1) · update protocol (backup/verify/
rollback) · security model (policy central, sandbox fail-closed) ·
design tokens (`--g5-*`) · product-data (generated, CI-checked).

## Web-specific

Browser APIs (Clipboard, matchMedia, localStorage) · web storage
(prefs/keys in session/local, validated) · browser restrictions
(no exec, same-origin + documented hosts, CSP meta) · preview/static
serving (SPA fallback) · PWA (precache, offline NOT proven — limit).

## Desktop-specific (Tauri, contract only — build BLOCKED)

First launch → backend URL config → WS connect → key auth →
installer/update via CLI download+launch (no native bridge yet) →
tray/notifications/deep-links/filesystem/secure IPC/offline shell/
diagnostics/recovery/version display. Secure storage: Tauri Store
(preferred) over localStorage. No embedded secrets. No shell bridge
beyond audited `open(url)`.

## Mobile-specific (Capacitor, contract only — build BLOCKED)

Lifecycle (pause/resume → reconnect), offline (shell usable, AI
honestly unavailable), notifications (opt-in), permissions
(camera/mic/files, requested in context), filesystem limits (cache
dir), recovery (reconnect/backoff), compact presence default,
task-first layout, secure storage plugin (preferred).

## Divergence rule

Any platform behavior differing from shared semantics must be
declared in this file with reason + scope. None declared today.
