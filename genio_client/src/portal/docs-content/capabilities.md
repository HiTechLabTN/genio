# Capabilities — advertised contract (§19)

Source of truth at runtime: `genio/integrations/hitechos/capabilities.py`
(`advertise()`/`catalog()`), queried via IPC `capabilities` method.
HiTech-OS MUST adapt to the advertised set, never assume it.

| Capability | Meaning | Availability rule |
|---|---|---|
| agent | turn-based agent execution | tool registered |
| planning | DAG planner | tool registered |
| memory | recall/session memory | tool registered |
| tools | generic tool execution | tool registered |
| sandbox | containerized exec, fail-closed | tool registered |
| browser | anti-SSRF browsing | tool registered |
| computer | desktop actuators (gated) | tool registered |
| voice | TTS/STT via external VODER | external service |
| vision | image understanding | NOT configured (honest) |
| models | local router + backends | tool registered |
| automation | multi-step tool flows | tool registered |
| filesystem | bounded FS access | tool registered |
| hitechos-integration | this IPC contract | always (v1.x) |

Entries carry `{capability, available, version, detail}`. `version`
is `1.0` when available, `null` otherwise. Unavailable entries
include the reason (`tool-absent`, `not-configured`, …).
