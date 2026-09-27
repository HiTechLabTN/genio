# GENIO_5_G5D_RELEASE_CANDIDATE

| Capability | Implementation | Test | Execution Evidence | Platform | Status | Blocker |
|---|---|---|---|---|---|---|
| Chat/agent | App + WS | backend suites | live answers :8000/:18600 | Web | PASS | — |
| Install/update/rollback/doctor | installer CLI | 19 tests + clean-room #5 | public 4.1.0 cycle | Linux | PASS | — |
| IPC v1.x | UDS server+client | 18+6 tests + pub prefix run | local sockets | Linux | PASS | daemon (OS) |
| Sandbox | Docker strict | security suites + live exec | host+container, HOST=0 | Linux | PASS | nested needs group |
| Voice | VODER service | live matrix 200/422/400 | :5050 | Linux | PASS | VRAM contention |
| Presence/states | resolver+avatar | 9+11 tests + shots | browser+native | Web/Linux | PASS | — |
| Notifications pipeline | hook+bridge | lifecycle tests | codes, no OS delivery | Web | PASS | OS delivery UNVERIFIED |
| Updater verify | manifest+checks | 7 tests | tamper/downgrade/platform | all | PASS | signing key |
| Linux packaging | AppImage+DEB | build+launch+measure | 117MB/39MB, 17MB RSS, shot | Linux | PASS | signing |
| Diagnostics honest | bridge allowlist | 5 tests | codes, no secrets | Web/Linux | PASS | — |
| Desktop native | Tauri shell | launch+shot | Xvfb window | Linux | PASS | Win/Mac toolchains |
| Mobile/desktop builds | — | contract only | — | — | BLOCKED | Rust-win/Mac, SDK-use, Xcode, secrets |
| PWA offline | workbox precache | live offline reload | /download cached | Web | PASS shell only | tasks need backend |
| Slow network | real tc netem | live WS matrix | 0.03s→4.83s→timeout→recover | Linux | PASS | — |
