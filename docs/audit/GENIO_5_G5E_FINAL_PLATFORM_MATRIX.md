# GENIO_5_G5E_FINAL_PLATFORM_MATRIX

| Platform | Artifact | Build | Launch | Core Runtime | Security | Visual QA | Updater | Signing | Status | Evidence | Blocker |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Linux web | dist 89MB | PASS | PASS | PASS | PASS | PASS | N/A | N/A | PASS | CI+shots | — |
| Linux AppImage | 117MB AppImage | PASS | PASS | PASS | PASS | PASS | present | BLOCKED | PASS | launch+shot | signing key |
| Linux DEB | 39MB | PASS | NOT_EXECUTED | UNVERIFIED | PASS(list) | UNVERIFIED | present | BLOCKED | UNVERIFIED | artifacts exist | install test env |
| CLI installer | stdlib | PASS | PASS | PASS | PASS | N/A | PASS | N/A | PASS | 35 tests + clean-room | — |
| Docker | 356MB image | PASS | PASS | PASS | PASS | N/A | N/A | N/A | PASS | digest+probes | registry latest |
| Windows | — | — | — | — | — | — | — | — | BLOCKED | no toolchain | Rust-win/SDK |
| macOS | — | — | — | — | — | — | — | — | BLOCKED | no Xcode | Xcode |
| Android | — | — | — | — | — | — | — | — | BLOCKED | SDK unused, no dir | SDK-use+secrets |
| iOS | — | — | — | — | — | — | — | — | BLOCKED | no Xcode | Xcode |
| HiTech-OS IPC | contract | PASS | N/A | PASS | PASS | N/A | N/A | N/A | PASS | 24 tests | daemon impl |
