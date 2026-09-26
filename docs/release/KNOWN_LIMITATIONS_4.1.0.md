# Known limitations — 4.1.0

1. No installable Python package (CWD pinned per launch vector).
2. Voice/systemd clean-room partial (optional/shared host).
3. Sandbox-in-Docker needs socket mount (documented, fail-closed w/o).
4. Network required for pip/npm.
5. Non-git update = file swap.
6. `release-binaries.yml` hardened, Android build needs secrets.
7. No Docker registry push (no infra) — build locally, digest recorded.
8. Desktop/mobile apps consume HTTP API+WS only (no builds here).
