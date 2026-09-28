# GENIO v5.0.0 — RELEASE EXECUTION REPORT

## Source
- expected: 891c5efbd2cca805cf6ffdc137483581cdc262b7
- actual: same (verified `git rev-parse`, tag dereference local + remote)
- tag target: 891c5ef (exact, `v5.0.0^{}` both sides)
- tree: clean except runtime churn (DBs, self-improve `ts`; never committed)

## Version
- public: v5.0.0 (tag + GitHub Release, no premature creation — this execution)
- product: 4.1.0 · client: 4.3.0 · installer: 1.0.0 · API: 1.0.0 · IPC: 1.x
- No rewrites; no drift (version tests green).

## Tag
- local: `v5.0.0` → 891c5ef (annotated)
- remote: `refs/tags/v5.0.0^{}` → 891c5ef (verified via ls-remote)

## GitHub Release
- status: PUBLISHED — https://github.com/HiTechLabTN/genio/releases/tag/v5.0.0
- URL above; notes = factual v5.0.0 notes (capabilities, matrix, unsigned status, limits)
- assets (9): tarball + sha + manifest + sbom + AppImage + AppImage.sha + DEB + DEB.sha + notes

## Artifacts
- source: genio-5.0.0.tar.gz (137598376 B, sha 415ba958…, git archive 891c5ef minus 2 tracked runtime DBs — documented)
- AppImage: 117135864 B (sha 1c87c518…, launched, measured, shot)
- DEB: 39680552 B (sha 90e187ab…)
- checksums: all generated + verified pre/post publish
- SBOM: 968 components, CycloneDX-lite
- manifest: versions/commits/hashes/platforms/signing/limits, no placeholders
- Docker: ghcr.io/hitechlabtn/genio:5.0.0 @sha256:f8554f8a… (verified + pushed; no `latest`)

## Security
- secrets: 0 (scan) · signing: UNSIGNED/DEVELOPMENT (no key created) ·
  sandbox/auth/SSRF/uploads/injection/telemetry: spot suites green ·
  debug signing absent (workflows) · tarball scanned (0 .db after clean, 0 secrets/keys).

## Platform Matrix
- Linux: PASS · CLI: PASS · Docker: PASS · IPC: PASS
- Windows/macOS/Android/iOS: BLOCKED (exact prerequisites on record)

## Public Verification
- source/DEB/SBOM/manifest downloaded from release; tarball sha OK; manifest correct
- public smoke: download→sha→install (ae7dcbf3)→API 200→doctor HEALTHY→cleanup
- Docker reference unchanged; no `latest`; no false claims; no secrets public

## Limitations
GENIO_5_LIMITATIONS.md (9): notifications rendering, Xcode/iOS, Win/Mac, Android SDK+secrets, D-Bus, registry latest, PWA tasks, voice VRAM, webkit tofu.

## Problems
- Source: PASS · Version: PASS · Tag: PASS · Release: PASS
- Artifacts: PASS · Security: PASS · Docker: PASS · SBOM: PASS
- Portal/docs: PASS · Signing: BLOCKED (declared) · Platforms: see matrix
- FAIL: none · UNAVAILABLE: Xcode/iOS SDK, Win/Mac toolchains, Android SDK-use

## Final Decision

**PUBLIC RELEASE EXECUTED WITH DOCUMENTED LIMITATIONS**
