# Security boundary — Genio × HiTech-OS

Three boundaries, one rule: **no silent bypass, no duplicated logic
that can diverge** (Genio policy is the single decision point for
Genio-side execution).

## 1. GENIO SECURITY BOUNDARY

Inside: agent runtime, policy engine, capabilities registry, sandbox,
memory, tools, IPC server. Decisions (ALLOW/DENY/ESCALATE) are made
ONLY here. Peer identities are validated (SO_PEERCRED UID), requests
are nonce-checked, rate-limited, size-bounded, audited.

## 2. HITECH-OS SECURITY BOUNDARY

Inside: OS services, hardware, inference daemon, desktop, MQTT bus.
The OS authenticates its own users/services, guards hardware access,
and decides which Genio capabilities to invoke. The OS MUST NOT
re-implement Genio policy (no duplicated sandbox/authz logic).

## 3. IPC TRUST BOUNDARY (UDS)

Crossing rules:

| Question | Answer |
|---|---|
| Who can request? | local UID authorized by Genio server policy (default: same UID) |
| Who authorizes? | Genio (execution) + OS (invocation) — both, independently |
| Where does policy live? | Genio: `core/policy_engine.py` + IPC gates; OS: own policy |
| Where does execution occur? | Genio runtime (sandboxed) or OS (for os.* ops, OS executes) |
| Where is auditing? | Both: Genio telemetry (`hitechos-ipc`), OS bus |

Privileged flow (`os.*` destructive): OS request → Genio policy →
confirmation gate (human, timeout) → OS executes → both audit.
Genio NEVER executes privileged OS ops itself; OS NEVER forces Genio
to skip policy.

## Forbidden

- OS importing Genio internals (contract only).
- Genio importing OS internals (adapters only).
- `localhost == trusted` assumptions.
- Unauthenticated local clients reaching privileged ops.
- Cloud fallback carrying protected data without explicit opt-in
  (`GENIO_ALLOW_CLOUD`, router gate, tested).
