# IPC v1.x — Genio × HiTech-OS contract (normative)

Transport: Unix Domain Socket, JSON length-prefixed (4B big-endian),
`MAX_FRAME` 8MB. Default paths: `/run/hitechos/ai.sock` (OS daemon),
`/run/genio/genio.sock` (Genio server). Override: `GENIO_HITECHOS_SOCK`.

## Methods

| Method | Direction | Purpose |
|---|---|---|
| `hello` | OS → Genio | identity + version negotiation |
| `capabilities` | OS → Genio | advertised capability catalog |
| `infer` | OS → Genio | inference request (v1.0 schema inside envelope) |
| `goodbye` | OS → Genio | clean disconnect |
| legacy v1.0 | OS → Genio | `{request_id,model,prompt,...}` without method (accepted) |

## Envelopes

Request: `{method, request_id, ts, ...method-fields}`.
`ts` = unix seconds; skew > 300s → `EXPIRED`. Reused `request_id` →
`DUPLICATE`. Prompt > 256KB → `OVERSIZED`.

Response ok: `{protocol_version, status:"ok", request_id, ...}`.
Response error: `{protocol_version, status:"error",
error:{code,message}, request_id}`.

## Versions

Server speaks `1.0..1.0` (`PROTOCOL_MIN_SUPPORTED..PROTOCOL_VERSION`).
Client sends `proto_min/proto_max`; overlap required, else
`UNSUPPORTED_PROTOCOL`. Patch/minor evolution keeps v1.x envelope
stable; new methods are additive and optional.

## Error codes (closed set)

`UNSUPPORTED_PROTOCOL MALFORMED UNAUTHORIZED EXPIRED TIMEOUT
CANCELLED OVERSIZED DUPLICATE UNAVAILABLE POLICY_DENY NOT_CONFIGURED
INTERNAL`. Unknown codes are never emitted (asserted).

## Identity (hello response)

`{instance_id, product:"genio", product_version, protocol_version,
capabilities:[available...], request_id}`.

## Capabilities

Advertised only when proven (registry check or explicit external).
`vision` is honestly `unavailable` until configured. Full catalog:
`docs/integration/CAPABILITIES.md`.

## Events (versioned, audited)

`genio.ready/degraded/request/shutdown` v1.0 — emitted to Genio
telemetry audit trail (`hitechos-ipc`), never carrying secrets.
OS-side bus (MQTT) remains the OS transport; Genio never publishes
to it directly.

## Security (trust model)

- UDS peer UID via `SO_PEERCRED`; default policy **same-uid-only**
  (`localhost != trusted`); explicit `allow_uids` override.
- No identity → `UNAUTHORIZED` (fail closed).
- Rate limit per UID (default 600/min, burst 10) → `POLICY_DENY`.
- Every request audited (`genio.request` event: id/method/uid/decision).
- Privileged ops (os.* destructive) additionally pass Genio policy +
  confirmation gates — IPC never bypasses them.

## Failure behavior (contract)

Absent/crashed daemon → transport error (client degrades, never hangs:
timeouts durs). Malformed → `MALFORMED`. Unauthorized → `UNAUTHORIZED`.
No handler → `UNAVAILABLE` (never faked). Oversized → `OVERSIZED`.

Reference: `genio/integrations/hitechos/` (protocol.py = v1.0 figé,
envelope.py, capabilities.py, server.py, reference_client.py TEST-ONLY).
Tests: `tests/test_hitechos_contract.py` (v1.0),
`tests/test_hitechos_ipc_v1x.py` (18 tests v1.x + failure modes).
