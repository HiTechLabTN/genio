# GENIO_5_LIMITATIONS (release gate classification)

## SUPPORTED NOW

- Linux x86_64 standalone (installer CLI, prefix install, systemd units)
- Docker (ghcr.io/hitechlabtn/genio:4.1.0, non-root, HEALTHCHECK)
- Web portal + app (all routes, honest states, offline shell for cached routes)
- API 14 routes + WS (Bearer, rate-limit, boot guard)
- Sandbox fail-closed (host + container, HOST_EXECUTION=0 proven)
- IPC v1.x contract (server + reference client, 24 tests)
- Updater verification (unsigned-development only)
- Linux AppImage+DEB (built, launched, unsigned)

## BLOCKED EXTERNAL

- Production signing (no private key; never fabricated)
- Windows/macOS builds (no toolchains here)
- Android (SDK present but unused here + signing secrets absent)
- iOS (no Xcode)
- HiTech-OS daemon IPC (TODO Phase 5 côté OS)
- D-Bus service control (this host)
- Docker `latest` tag (immutable-tags policy)
- get.genio.ai domain (GitHub release mechanism used instead)

## UNVERIFIED

- Native OS notification rendering (protocol proven, headless here)
- Xcode/iOS behaviors, Windows runtime behaviors
- PWA offline task execution (shell proven, tasks need backend)
- Slow-network beyond tested tc matrix

## FUTURE / PLANNED

- 5.0 tag + GitHub release (human decision only)
- fs/http scope tightening follow-ups
- Python package, registry push policy review
- Desktop installer native bridge, notifications→OS wiring
