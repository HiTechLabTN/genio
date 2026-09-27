# Privacy — what Genio processes (client + product)

## Client (genio.hitech.tn)

- Page views: path + timestamp, fire-and-forget beacon to first-party
  `/api/v1/analytics` (no cookies, no third-party tracker; Plausible
  hook only if the operator injects it — absent by default).
- No keystrokes, no prompts, no file contents leave for analytics.
- Diagnostics copy (`genio doctor --json`, install log) is
  secret-scrubbed by construction; the user shares it explicitly.

## Product (self-hosted Genio)

- Local-first: prompts stay on the operator's machine unless cloud
  backends are explicitly enabled (`GENIO_ALLOW_CLOUD`).
- Telemetry: metrics + security decisions, secrets scrubbed
  (keys/tokens/cookies removed, tested).
- Logs: journald/prefix logs may contain prompts by design of a
  self-hosted assistant — operator-owned, never exfiltrated.

## Opt-in / opt-out

- No silent third-party collection exists to opt out of.
- Beacon: disable by blocking `/api/v1/analytics` (adblockers already
  do) — the app works identically (fire-and-forget, zero dependency).
- Retention: operator-controlled (own server/logs).
