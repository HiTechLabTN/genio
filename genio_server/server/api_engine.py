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

import ipaddress
import json
import os
import re
import socket
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlsplit

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore

import httpx

_TIMEOUT = 35.0
_TEXT_LIMIT = 4000


# --------------------------------------------------------------------------- #
# Network egress guard (closure gate — SSRF / internal-network protection)
# --------------------------------------------------------------------------- #
# The api tool is agent-reachable and ALLOW in development mode: without a
# destination guard, a prompt-injected model can load a spec whose servers[]
# (or a redirect) point at loopback/private/link-local/cloud-metadata and
# ride the operator's host into internal services. Guard rules:
#   * every destination (load URL, spec base URL, EVERY redirect hop) is
#     resolved and checked against forbidden IP classes — string-only checks
#     are bypassable via DNS and redirects;
#   * spec FILE loads are restricted to operator-trusted directories
#     (GENIO_API_SPEC_DIRS, default: server cwd subtree) with symlink-safe
#     realpath containment;
#   * GENIO_API_ALLOW_PRIVATE=1 is the explicit operator escape hatch.
_FORBIDDEN_HOSTNAMES = {
    "localhost", "localhost.localdomain", "ip6-localhost", "ip6-loopback",
    "metadata.google.internal", "metadata.goog", "metadata",
}

# Explicit cloud-metadata addresses, checked in ALL modes (incl. under
# GENIO_API_ALLOW_PRIVATE): some live in ranges ipaddress does NOT
# classify as private — 100.100.100.200 ∈ RFC 6598 shared space was a
# REAL allow-gap (is_private/is_reserved both False). IPv4-mapped forms
# unwrap to the same check inside _is_metadata_ip().
_METADATA_IPS = frozenset({
    "169.254.169.254",    # AWS/GCP/Azure/Oracle link-local metadata
    "100.100.100.200",    # Alibaba Cloud metadata (RFC 6598 shared space)
    "fd00:ec2::254",      # AWS IPv6 metadata
})


def _is_metadata_ip(ip_str: str) -> bool:
    """True for known cloud-metadata addresses (any mode, no exception)."""
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    forms = {ip.compressed.lower()}
    mapped = getattr(ip, "ipv4_mapped", None)
    if mapped is not None:
        forms.add(mapped.compressed.lower())
    return bool(forms & _METADATA_IPS)


def _allow_private() -> bool:
    return os.getenv("GENIO_API_ALLOW_PRIVATE", "0").strip().lower() \
        in ("1", "true", "yes")


def _ip_forbidden(ip_str: str) -> bool:
    """True for loopback / private / link-local / metadata-class addresses."""
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return True  # unparseable → fail closed
    # IPv4-mapped / -compatible IPv6 (::ffff:127.0.0.1) — unwrap first.
    mapped = getattr(ip, "ipv4_mapped", None)
    if mapped is not None:
        ip = mapped
    return bool(
        ip.is_loopback or ip.is_private or ip.is_link_local
        or ip.is_reserved or ip.is_multicast or ip.is_unspecified
        or getattr(ip, "is_site_local", False)  # IPv6-only attribute
    )


def _blocked_url(url: str) -> Optional[str]:
    """Return a refusal reason if ``url`` targets a forbidden destination.

    Hostnames are RESOLVED (all A/AAAA answers checked) — a public name
    that resolves to a private IP is refused (DNS-rebinding class).
    Resolution failure is fail-closed. Returns None when the destination
    is verifiably public (or checks are disabled by the operator).
    """
    try:
        parts = urlsplit(url or "")
        host = (parts.hostname or "").strip().lower().rstrip(".")
        port = parts.port or (443 if parts.scheme == "https" else 80)
    except ValueError as exc:
        # Malformed URL (bad port, broken brackets, …) — fail closed with
        # a refusal reason, never an escaping exception.
        return f"api guard: malformed URL {url!r} ({exc}) — refused"
    if not host:
        return f"api guard: no host in {url!r}"
    # Denylist BEFORE any exception (incl. ALLOW_PRIVATE): lifting the
    # private-IP ban never trusts cloud-metadata endpoints.
    if host in _FORBIDDEN_HOSTNAMES or host.endswith(".localhost"):
        return f"api guard: hostname {host!r} is forbidden (loopback/metadata)"
    allow_private = _allow_private()
    try:
        # IP literal: check directly, no DNS involved.
        literal = str(ipaddress.ip_address(host.strip("[]")))
    except ValueError:
        literal = None
    if literal is not None:
        # Explicit metadata endpoints hold in ALL modes; class checks
        # are the only thing the operator escape hatch lifts.
        if _is_metadata_ip(literal):
            return (f"api guard: {host!r} is a cloud-metadata address "
                    f"— refused")
        if not allow_private and _ip_forbidden(literal):
            return (f"api guard: {host!r} is a forbidden address "
                    f"(loopback/private/link-local/metadata)")
        return None
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except OSError as exc:
        return f"api guard: cannot resolve {host!r} ({exc}) — refused"
    candidates = sorted({info[4][0] for info in infos})
    if not candidates:
        return f"api guard: no addresses for {host!r} — refused"
    for cand in candidates:
        if _is_metadata_ip(cand) or \
                (not allow_private and _ip_forbidden(cand)):
            return (f"api guard: {host!r} resolves to forbidden address "
                    f"{cand} (loopback/private/link-local/metadata)")
    return None


def _pin_request(request: "httpx.Request"
               ) -> Tuple[Optional["httpx.Request"], Optional[str]]:
    """Resolve the request host, check EVERY answer, and PIN the connection
    to a verified IP literal (DNS-rebinding TOCTOU elimination).

    The stock transport resolves the hostname AGAIN at connect time, so a
    check-then-connect leaves a rebinding window. Here the URL host is
    rewritten to the verified IP literal BEFORE delegating — the inner
    transport dials a literal (no DNS possible downstream). The original
    hostname is preserved via the Host header and
    extensions["sni_hostname"] (honored by httpcore for TLS), so cert
    verification keeps working against the original name.

    IP-literal URLs are checked and passed through unmodified. Every
    redirect hop re-enters the transport and is re-resolved + re-pinned.
    Returns (new_request, None) or (None, refusal_reason). Never raises.
    """
    try:
        raw = str(request.url)
        parts = urlsplit(raw)
        host = (parts.hostname or "").strip().lower().rstrip(".")
        if not host:
            return None, f"api guard: no host in {raw!r}"
        port = parts.port or (443 if parts.scheme == "https" else 80)
    except ValueError as exc:
        return None, f"api guard: malformed URL ({exc}) — refused"
    # Denylist BEFORE any exception: metadata/loopback names stay refused
    # even when the operator lifts the private-IP ban.
    if host in _FORBIDDEN_HOSTNAMES or host.endswith(".localhost"):
        return None, (f"api guard: hostname {host!r} is forbidden "
                      f"(loopback/metadata)")
    allow_private = _allow_private()
    # IP literal → check (unless lifted), no DNS, no rewrite needed.
    try:
        literal = str(ipaddress.ip_address(host.strip("[]")))
    except ValueError:
        literal = None
    if literal is not None:
        if _is_metadata_ip(literal):
            return None, (f"api guard: {host!r} is a cloud-metadata "
                          f"address — refused")
        if not allow_private and _ip_forbidden(literal):
            return None, (f"api guard: {host!r} is a forbidden address "
                          f"(loopback/private/link-local/metadata)")
        return request, None
    # Hostname → resolve NOW, check every answer (unless lifted), and
    # ALWAYS pin: lifting private IPs must not restore the downstream-DNS
    # rebinding window (the inner transport never sees a hostname).
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except OSError as exc:
        return None, f"api guard: cannot resolve {host!r} ({exc}) — refused"
    candidates = sorted({info[4][0] for info in infos})
    if not candidates:
        return None, f"api guard: no addresses for {host!r} — refused"
    if not allow_private:
        for cand in candidates:
            if _ip_forbidden(cand) or _is_metadata_ip(cand):
                return None, (f"api guard: {host!r} resolves to forbidden "
                              f"address {cand} (loopback/private/link-local/"
                              f"metadata)")
    else:
        # Even with private IPs lifted, explicit metadata endpoints stay
        # refused (lifting private ≠ trusting metadata).
        for cand in candidates:
            if _is_metadata_ip(cand):
                return None, (f"api guard: {host!r} resolves to "
                              f"cloud-metadata address {cand} — refused")
    pinned_ip = candidates[0]
    try:
        new_url = request.url.copy_with(host=pinned_ip)
        headers = httpx.Headers(request.headers)
        if "host" not in headers:
            # Preserve the original Host, INCLUDING a non-default port —
            # rewriting to an IP literal must not misroute vhosts.
            scheme = str(request.url.scheme).lower()
            default_port = 443 if scheme in ("https", "wss") else 80
            headers["host"] = host if port == default_port \
                else f"{host}:{port}"
        try:
            request.read()
            body = request.content
        except Exception as exc:
            return None, f"api guard: unreadable request body ({exc}) — refused"
        extensions = dict(request.extensions)
        if str(request.url.scheme).lower() in ("https", "wss"):
            extensions["sni_hostname"] = host
        new_request = httpx.Request(request.method, new_url, headers=headers,
                                    extensions=extensions, content=body)
    except Exception as exc:
        return None, f"api guard: cannot pin {host!r} ({exc}) — refused"
    return new_request, None


class _GuardedTransport(httpx.BaseTransport):
    """Wraps the default transport; resolves + checks + PINS every request.

    With follow_redirects=True the client re-enters the transport for each
    3xx hop, so every hop is independently resolved, checked and pinned —
    a public first hop that redirects to an internal address is refused
    before any bytes reach the forbidden target, and a hostname whose DNS
    changes mid-flight still connects to the checked address only.
    """

    def __init__(self, inner: Optional[httpx.BaseTransport] = None) -> None:
        self._inner = inner or httpx.HTTPTransport()

    def handle_request(self, request: "httpx.Request") -> "httpx.Response":
        pinned, reason = _pin_request(request)
        if reason:
            raise httpx.RequestError(f"refused: {reason}", request=request)
        assert pinned is not None
        return self._inner.handle_request(pinned)

    def close(self) -> None:
        self._inner.close()


def _guarded_client() -> httpx.Client:
    return httpx.Client(transport=_GuardedTransport(), follow_redirects=True,
                        timeout=_TIMEOUT)


def _trusted_spec_file(source: str) -> Tuple[bool, str, str]:
    """Contain spec FILE reads to operator-trusted directories.

    Returns (ok, real_path, reason). Symlink-safe: containment is checked
    on the realpath, so a link inside a trusted dir pointing at /etc/… is
    refused. Trusted dirs: GENIO_API_SPEC_DIRS (os.pathsep-separated);
    default = server cwd subtree.

    NOTE: file containment is INDEPENDENT of GENIO_API_ALLOW_PRIVATE —
    the network escape hatch only affects destination-IP checks and never
    widens local file reads.
    """
    configured = os.getenv("GENIO_API_SPEC_DIRS", "").strip()
    dirs = [d for d in configured.split(os.pathsep) if d] \
        if configured else [os.getcwd()]
    path = os.path.realpath(source)
    for d in dirs:
        dreal = os.path.realpath(d)
        if path == dreal or path.startswith(dreal + os.sep):
            if os.path.isfile(path):
                return True, path, ""
            return False, path, f"not a regular file: {path!r}"
    return (False, path,
            f"path outside trusted spec dirs ({', '.join(dirs)}) — "
            f"set GENIO_API_SPEC_DIRS to extend")


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

    def set_credential(self, scheme: str, value: str) -> Tuple[bool, str]:
        """Agent-facing credential setter, hardened (closure gate).

        - scheme must be declared in the spec's securitySchemes (no junk
          keys);
        - first-set-wins: an already-set credential is NOT overwritten
          (a prompt-injected model cannot swap a live secret).
        """
        if scheme not in self.schemes:
            return (False,
                    f"unknown scheme {scheme!r} (declared: "
                    f"{sorted(self.schemes) or 'none'})")
        if self._creds.get(scheme):
            return False, f"credential for {scheme!r} already set — overwrite refused"
        self._creds[scheme] = value
        return True, ""

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
            # SSRF guard: destination resolved + checked BEFORE the fetch,
            # and again on every redirect hop via _GuardedTransport.
            reason = _blocked_url(source)
            if reason:
                return {"ok": False, "error": f"refused: {reason}"}
            with _guarded_client() as client:
                resp = client.get(source)
                resp.raise_for_status()
                text = resp.text
        else:
            # Spec FILE reads are contained to operator-trusted dirs.
            ok, real_path, why = _trusted_spec_file(source)
            if not ok:
                return {"ok": False, "error": f"refused: spec file {why}"}
            text = open(real_path, encoding="utf-8").read()
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
    # SSRF guard: the spec's base URL (independent of where it was loaded
    # from) is resolved + checked before any request, and every redirect
    # hop is re-checked by _GuardedTransport.
    reason = _blocked_url(base)
    if reason:
        return {"ok": False, "error": f"refused: {reason}"}
    url = base.rstrip("/") + url_path

    headers = {"Accept": "application/json", **spec.resolve_auth(op)}
    query_params = dict(params.pop("query", {}) or {})
    for k, v in params.items():
        if k not in body and not any(p["name"] == k for p in op["parameters"]):
            query_params.setdefault(k, v)
    query_params.update(op.get("_query_auth", {}) or {})

    try:
        t0 = time.time()
        with _guarded_client() as client:
            resp = client.request(method, url,
                                  params=query_params, json=body or None,
                                  headers=headers)
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
            scheme = str(payload.get("scheme", ""))
            value = str(payload.get("value", ""))
            ok, why = spec.set_credential(scheme, value)
            if not ok:
                return {"ok": False, "error": why}
            return {"ok": True, "credentialed": spec.summary()["schemes"]}
        return {"ok": False,
                "error": f"unknown api action '{action}' (list|load|search|execute|set_credentials)"}
    except Exception as exc:
        return {"ok": False, "error": f"api {action} raised: {exc}"}