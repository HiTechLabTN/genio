"""Dynamic API skill engine — parses OpenAPI specs on the fly.

Genio can load any third-party API description (local file or URL), discover
its operations, and execute them **without any hard-coded adapter logic**.
This is what makes the harness a general "API engine" rather than a static tool
list:

* ``load <name> <source>``          — load an OpenAPI 3.x JSON/YAML spec.
* ``list``                          — enumerate loaded skills + operation count.
* ``search <query>``                — find matching operations by keywords.
* ``execute <name> <method> <path>``— call an operation with params/body/auth.

Authentication is resolved from the spec's ``securitySchemes`` at call time:
apiKey (header/query/cookie), HTTP bearer, HTTP basic. Credentials come from
``set_credentials`` or ``GENIO_API_<SCHEME_NAME>`` environment variables, so
secrets live in the environment, not in the spec or the model prompt.

Every exported function returns a JSON-serialisable dict and never raises.
"""
from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore

import httpx

_TIMEOUT = 35.0
_TEXT_LIMIT = 4000


# --------------------------------------------------------------------------- #
# Spec model
# --------------------------------------------------------------------------- #
class OpenAPISpec:
    def __init__(self, name: str, source: str, doc: Dict[str, Any]) -> None:
        self.name = name
        self.source = source
        self.doc = doc
        self.title = str(doc.get("info", {}).get("title", name))
        self.version = str(doc.get("info", {}).get("version", ""))
        self.servers = [s.get("url", "") for s in doc.get("servers", [])]
        self.components = doc.get("components", {}) or {}
        self.schemes: Dict[str, Any] = self.components.get("securitySchemes", {}) or {}
        self.__paths: Dict[str, Dict[str, Any]] = doc.get("paths", {}) or {}
        self.operations: List[Dict[str, Any]] = []

        for path, item in self.__paths.items():
            for method in ("get", "post", "put", "patch", "delete", "head", "options"):
                op = item.get(method)
                if not isinstance(op, dict):
                    continue
                self.operations.append({
                    "method": method.upper(),
                    "path": path,
                    "summary": str(op.get("summary", "")),
                    "description": str(op.get("description", "") or op.get("summary", "")),
                    "operation_id": str(op.get("operationId", "")),
                    "tags": list(op.get("tags", [])) or [],
                    "parameters": list(op.get("parameters", [])) or [],
                    "security": op.get("security") or doc.get("security") or [],
                    "request_body": bool(op.get("requestBody")),
                })
        self._creds: Dict[str, str] = {}

    def index_tokens(self) -> str:
        names = []
        for op in self.operations:
            names.append(" ".join([
                op["method"], op["path"], op["operation_id"],
                op["summary"], " ".join(op["tags"]),
            ]).lower())
        return "\n".join(names)

    def summary(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "title": self.title,
            "version": self.version,
            "source": self.source,
            "operations": len(self.operations),
            "servers": self.servers,
            "schemes": sorted(self.schemes),
        }

    def set_credential(self, scheme: str, value: str) -> None:
        self._creds[scheme] = value

    def resolve_auth(self, op: Dict[str, Any]) -> Dict[str, str]:
        """Return final headers (and cookie hints) for an operation's security."""
        headers: Dict[str, str] = {}
        for requirement in op.get("security") or [{}]:
            for scheme_name in requirement:
                scheme = self.schemes.get(scheme_name)
                if not scheme:
                    continue
                value = self._credential(scheme_name)
                if not value:
                    continue
                stype = scheme.get("type", "")
                if stype == "http":
                    inner = scheme.get("scheme", "bearer").lower()
                    if inner == "bearer":
                        headers["Authorization"] = f"Bearer {value}"
                    elif inner == "basic":
                        import base64
                        token = base64.b64encode(value.encode()).decode()
                        headers["Authorization"] = f"Basic {token}"
                elif stype == "apiKey":
                    loc = scheme.get("in", "header")
                    if loc == "header":
                        headers[scheme.get("name", "X-API-Key")] = value
                    elif loc == "cookie":
                        headers.setdefault("Cookie", f"{scheme.get('name', 'api')}={value}")
                    elif loc == "query":
                        op.setdefault("_query_auth", {})[scheme.get("name", "api")] = value
                elif stype == "oauth2" or stype == "openIdConnect":
                    headers["Authorization"] = f"Bearer {value}"
        return headers

    def _credential(self, scheme_name: str) -> str:
        if scheme_name in self._creds and self._creds[scheme_name]:
            return self._creds[scheme_name]
        env_name = re.sub(r"[^A-Za-z0-9]+", "_", scheme_name).upper()
        return os.environ.get(f"GENIO_API_{env_name}", "")


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #
_SPECS: Dict[str, OpenAPISpec] = {}


def clear() -> None:
    _SPECS.clear()


def load_spec_from_dict(name: str, doc: Dict[str, Any], source: str = "inline") -> Dict[str, Any]:
    if not name or not isinstance(doc, dict):
        return {"ok": False, "error": "load requires name + OpenAPI document"}
    spec = OpenAPISpec(name, source, doc)
    _SPECS[name] = spec
    return {"ok": True, "loaded": spec.summary()}


def load_spec(name: str, source: str) -> Dict[str, Any]:
    source = (source or "").strip()
    if not source:
        return {"ok": False, "error": "load requires a 'source' (URL or local path)"}
    text: str
    try:
        if source.startswith(("http://", "https://")):
            resp = httpx.get(source, timeout=_TIMEOUT, follow_redirects=True)
            resp.raise_for_status()
            text = resp.text
        else:
            text = open(source, encoding="utf-8").read()
    except Exception as exc:
        return {"ok": False, "error": f"cannot fetch spec from '{source}': {exc}"}

    doc: Any
    try:
        doc = json.loads(text)
    except json.JSONDecodeError:
        if yaml is None:
            return {"ok": False, "error": "YAML spec but PyYAML not installed"}
        try:
            doc = yaml.safe_load(text)
        except Exception as exc:
            return {"ok": False, "error": f"spec not valid JSON/YAML: {exc}"}

    if not isinstance(doc, dict) or "paths" not in doc:
        return {"ok": False, "error": "document has no 'paths' — not an OpenAPI spec"}
    return load_spec_from_dict(name, doc, source)


def list_specs() -> Dict[str, Any]:
    return {"ok": True, "action": "list", "skills": [s.summary() for s in _SPECS.values()]}


def _score(query_terms: List[str], op: Dict[str, Any], spec: OpenAPISpec) -> int:
    hay = " ".join([op["path"], op["method"], op["operation_id"],
                    op["summary"], " ".join(op["tags"])]).lower()
    score = 0
    for term in query_terms:
        if term in op["path"].lower():
            score += 4
        if term in op["operation_id"].lower():
            score += 3
        if term in op["summary"].lower():
            score += 2
        if term in hay:
            score += 1
    return score


def search_specs(query: str, top_k: int = 5) -> Dict[str, Any]:
    terms = [t for t in re.split(r"[^a-z0-9]+", (query or "").lower()) if t]
    results = []
    for spec in _SPECS.values():
        for op in spec.operations:
            score = _score(terms, op, spec)
            if score > 0:
                results.append({"spec": spec.name, "score": score, **op})
    results.sort(key=lambda r: (-r["score"], r["spec"], r["method"]))
    return {"ok": True, "action": "search", "query": query,
            "results": results[:top_k]}


def execute(name: str, method: str, path: str,
            params: Optional[Dict[str, Any]] = None,
            body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    spec = _SPECS.get(name)
    if spec is None:
        return {"ok": False, "error": f"unknown skill '{name}' — load it first (loaded: "
                                      f"{', '.join(_SPECS) or 'none'})"}
    method = (method or "GET").upper()
    path = (path or "").strip()
    params = dict(params or {})
    body = dict(body or {})

    op = next((o for o in spec.operations
               if o["method"] == method and o["path"] == path), None)
    if op is None:
        return {"ok": False,
                "error": f"no {method} {path} in skill '{name}'. Use 'search' to find operations."}

    # path params
    url_path = path
    for m in re.findall(r"\{([^}]+)\}", path):
        if m in params:
            url_path = url_path.replace("{" + m + "}", str(params.pop(m)))

    base = spec.servers[0] if spec.servers else ""
    url = base.rstrip("/") + url_path

    headers = {"Accept": "application/json", **spec.resolve_auth(op)}
    query_params = dict(params.pop("query", {}) or {})
    for k, v in params.items():
        if k not in body and not any(p["name"] == k for p in op["parameters"]):
            query_params.setdefault(k, v)
    query_params.update(op.get("_query_auth", {}) or {})

    try:
        t0 = time.time()
        resp = httpx.request(method, url,
                             params=query_params, json=body or None,
                             headers=headers, timeout=_TIMEOUT, follow_redirects=True)
        elapsed_ms = int((time.time() - t0) * 1000)
        content: Any = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text
        payload: Dict[str, Any] = {
            "ok": 200 <= resp.status_code < 300,
            "status": resp.status_code,
            "spec": name,
            "method": method,
            "url": str(resp.url),
            "elapsed_ms": elapsed_ms,
        }
        if isinstance(content, dict):
            payload["json"] = content
        else:
            payload["text"] = str(content)[:_TEXT_LIMIT]
        return payload
    except Exception as exc:
        return {"ok": False, "error": f"{method} {path} failed: {exc}"}


def handle(payload: Any) -> Dict[str, Any]:
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return {"ok": False, "error": "malformed api payload JSON"}
    if not isinstance(payload, dict):
        return {"ok": False, "error": "api payload must be an object"}
    action = payload.get("action", "execute")
    try:
        if action == "list":
            return list_specs()
        if action == "load":
            return load_spec(str(payload.get("name", "")), str(payload.get("source", "")))
        if action == "search":
            return search_specs(str(payload.get("query", "")), int(payload.get("top_k", 5)))
        if action == "execute":
            return execute(
                str(payload.get("name", "")),
                str(payload.get("method", "GET")),
                str(payload.get("path", "")),
                params=payload.get("params"),
                body=payload.get("body"),
            )
        if action == "set_credentials":
            spec = _SPECS.get(str(payload.get("name", "")))
            if spec is None:
                return {"ok": False, "error": f"unknown skill '{payload.get('name')}'"}
            spec.set_credential(str(payload.get("scheme", "")), str(payload.get("value", "")))
            return {"ok": True, "credentialed": spec.summary()["schemes"]}
        return {"ok": False,
                "error": f"unknown api action '{action}' (list|load|search|execute|set_credentials)"}
    except Exception as exc:
        return {"ok": False, "error": f"api {action} raised: {exc}"}