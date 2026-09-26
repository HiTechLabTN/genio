"""Schema conformance — runtime artifacts validate against published schemas."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SCHEMAS = ROOT / "schemas"


def _load(name):
    p = SCHEMAS / name
    assert p.is_file(), f"schema missing: {name}"
    return json.loads(p.read_text())


def test_ipc_schema_exists_and_closed_codes():
    import jsonschema
    schema = _load("ipc-v1.json")
    codes = schema["definitions"]["error"]["properties"]["error"]["properties"]["code"]["enum"]
    from genio.integrations.hitechos.envelope import ERROR_CODES
    assert set(codes) == set(ERROR_CODES)


def test_live_catalog_conforms():
    import jsonschema
    schema = _load("ipc-v1.json")
    from genio.integrations.hitechos.capabilities import advertise
    for cap in advertise():
        jsonschema.validate(cap, schema["definitions"]["capability"])


def test_live_errors_conform():
    import jsonschema
    schema = _load("ipc-v1.json")
    from genio.integrations.hitechos.envelope import ERROR_CODES, error_envelope
    for code in ERROR_CODES:
        jsonschema.validate(error_envelope(code, "test-msg", "r1"),
                            schema["definitions"]["error"])


def test_live_events_conform():
    import jsonschema
    schema = _load("ipc-v1.json")
    from genio.integrations.hitechos.envelope import EVENTS, make_event
    for name, spec in EVENTS.items():
        payload = {f: "x" for f in spec["fields"]}
        if name == "genio.request":
            payload.update({"request_id": "r", "method": "infer",
                            "peer_uid": 0, "decision": "ok"})
        jsonschema.validate(make_event(name, payload), schema["definitions"]["event"])


def test_openapi_covers_client_routes():
    spec = _load("openapi-genio.json")
    paths = set(spec.get("paths", {}))
    for route in ("/api/v1/status", "/api/v1/system/telemetry",
                  "/api/v1/voice/transcribe", "/health"):
        assert route in paths, f"client-used route missing from OpenAPI: {route}"
