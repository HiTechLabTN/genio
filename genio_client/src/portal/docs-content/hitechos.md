# HiTech-OS integration — OS-side usage (contract consumers)

Genio side: `docs/ipc/IPC_V1.md` (normative), `CAPABILITIES.md`
(catalog), `GENIO_HITECHOS_INTEGRATION_PLAN.md` (16-section plan).
This file is the OS implementer's checklist (no Genio code to import).

## Discover

1. Probe `GENIO_HITECHOS_SOCK` (default `/run/hitechos/ai.sock`,
   fallback `/run/genio/genio.sock`). Absent → Genio unavailable:
   **keep working without it** (no crash, no broken boot).
2. `hello` with your `proto_min/proto_max` → `UNSUPPORTED_PROTOCOL`
   means upgrade one side; never guess across versions.

## Adapt

3. `capabilities` → enable only advertised-available features.
   Missing capability → degrade that feature, not the OS.
4. `infer` for agent/model turns; handle `UNAVAILABLE` (no model),
   `POLICY_DENY` (rate/security), `UNAUTHORIZED` (fix UID policy).

## Fail safely

5. Timeouts durs côté OS (recommandé ≤ timeout Genio) ; `goodbye`
   on shutdown ; reconnect with backoff; duplicate `request_id`
   never retried blindly (server returns `DUPLICATE`).
6. Privileged OS actions stay OS-executed after Genio policy +
   confirmation; telemetry both sides, secrets never logged.
