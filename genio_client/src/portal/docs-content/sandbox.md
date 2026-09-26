# SANDBOX — garanties exactes (implémentation)

Conteneur par session (`genio-session-*`, image `python:3.11-slim`) :
`--memory 512m`, `--pids-limit 256`, `--cpus 2.0` (env), `--read-only`
+ `--tmpfs /tmp`, volume `/work` isolé par session, réseau `none` par défaut
(bridge allowlist documenté).

Fail-closed (strict) : `SANDBOX_UNAVAILABLE` (125) si mode coupé, Docker
absent ou démarrage impossible — jamais d'hôte. En dev, repli hôte explicite
marqué `sandbox_fallback: True`.

Garanties :isolement FS (sauf /work+/tmp), quotas CPU/RAM/pids, timeout dur
par commande, cwd persistant. Non-garantis : noexec (montage hôte), egress
filtré au niveau iptables (documenté, non appliqué ici), GPU dans sandbox.
Tests : `tests/test_sandbox_security.py` (inspect réel).
