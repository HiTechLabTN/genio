# CAPABILITIES — modèle first-class (implémentation)

Taxonomie : READ_ONLY, SAFE_WRITE, WORKSPACE_WRITE, NETWORK(_ACCESS),
PROCESS_EXECUTION, SYSTEM_SERVICE_CONTROL, CREDENTIAL_ACCESS, DEVICE_CONTROL,
DESTRUCTIVE, ADMINISTRATIVE, CRITICAL. Risques : LOW/MEDIUM/HIGH/CRITICAL.

`ToolDescriptor` frozen par outil : capability, risk_level, requires_network,
filesystem_scope (none/read_only_system/workspace_only/unrestricted),
execution_environment (SANDBOX_ONLY/HOST_ALLOWED), requires_confirmation.

| Outil | Capacité / Risque | Env | Confirm |
|---|---|---|---|
| bash | PROCESS_EXECUTION / HIGH | SANDBOX_ONLY | non |
| browser | NETWORK / MEDIUM | HOST_ALLOWED | non |
| computer | DEVICE_CONTROL / HIGH | HOST_ALLOWED | oui |
| screen | READ_ONLY / LOW | HOST_ALLOWED | non |
| api | NETWORK / MEDIUM | HOST_ALLOWED | non |
| social_post | NETWORK / LOW | HOST_ALLOWED | non |
| tool_forge | ADMINISTRATIVE / CRITICAL | SANDBOX_ONLY | oui |

Inconnu = `DENIED_UNKNOWN_CAPABILITY` dans tous les modes. Lookup par nom
seul (le payload LLM ne change rien). Interception dans `run()` + event
`capability.requested`. Tests : `tests/test_capabilities.py`.
