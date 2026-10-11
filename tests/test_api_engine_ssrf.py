"""SSRF / internal-network protection tests for the api engine.

Closure gate (pre-merge fix): the api tool is agent-reachable and ALLOW in
development mode — without a destination guard, a prompt-injected model can
load a spec whose servers[] (or a redirect) point at loopback/private/link-
local/cloud-metadata and ride the operator's host into internal services.

Guard rules under test:
  * every destination (load URL, spec base URL, EVERY redirect hop) is
    resolved and checked against forbidden IP classes;
  * spec FILE loads are restricted to operator-trusted directories with
    symlink-safe realpath containment;
  * GENIO_API_ALLOW_PRIVATE=1 is the explicit operator escape hatch;
  * NO HTTP request is made to a forbidden destination (we assert the
    transport never fired).
"""
import os
import sys
import tempfile

sys.path.insert(0, "/data/ai_tools/genio")

from genio_server.server.api_engine import (
    _blocked_url, _trusted_spec_file, clear, execute, load_spec,
)


# --------------------------------------------------------------------------- #
# _blocked_url unit tests
# --------------------------------------------------------------------------- #
def test_blocked_url_loopback():
    for u in ("http://127.0.0.1/", "http://127.0.0.1:8000/x", "https://[::1]/"):
        assert _blocked_url(u), u


def test_blocked_url_private_ranges():
    for u in ("http://10.0.0.5/", "http://192.168.1.1/",
              "http://172.16.0.1/", "http://172.31.255.255/"):
        assert _blocked_url(u), u


def test_blocked_url_link_local_and_metadata():
    for u in ("http://169.254.169.254/latest/meta-data/",
              "http://169.254.1.1/", "https://metadata.google.internal/"):
        assert _blocked_url(u), u


def test_blocked_url_unspecified_and_reserved():
    for u in ("http://0.0.0.0/", "http://240.0.0.1/", "http://255.255.255.255/"):
        assert _blocked_url(u), u


def test_blocked_url_public_allowed():
    # 8.8.8.8 is a public DNS resolver — must NOT be blocked by the IP rules.
    assert _blocked_url("http://8.8.8.8/") is None


def test_blocked_url_dns_rebinding_private():
    # A public-looking hostname that RESOLVES to a private IP must be refused.
    # We mock getaddrinfo to simulate DNS rebinding.
    import socket as _socket
    real = _socket.getaddrinfo

    def fake_getaddrinfo(host, port, *a, **kw):
        if host == "evil.example.com":
            return [(2, 1, 6, "", ("10.0.0.99", port))]
        return real(host, port, *a, **kw)

    _socket.getaddrinfo = fake_getaddrinfo
    try:
        assert _blocked_url("http://evil.example.com/") is not None
    finally:
        _socket.getaddrinfo = real


def test_blocked_url_allow_private_escape_hatch():
    os.environ["GENIO_API_ALLOW_PRIVATE"] = "1"
    try:
        assert _blocked_url("http://127.0.0.1/") is None
    finally:
        del os.environ["GENIO_API_ALLOW_PRIVATE"]


# --------------------------------------------------------------------------- #
# load_spec — URL + FILE containment
# --------------------------------------------------------------------------- #
def test_load_spec_url_forbidden_no_request():
    # A forbidden load URL must be refused BEFORE any HTTP request.
    # We monkeypatch the guarded client to detect if it was ever constructed.
    import genio_server.server.api_engine as eng
    calls = {"made": 0}
    real_client = eng._guarded_client

    def spy_client():
        calls["made"] += 1
        return real_client()

    eng._guarded_client = spy_client
    try:
        res = load_spec("probe", "http://127.0.0.1:9/openapi.json")
    finally:
        eng._guarded_client = real_client
    assert res["ok"] is False
    assert "refused" in res["error"] or "forbidden" in res["error"]
    assert calls["made"] == 0, "guard must fire before any client construction"


def test_load_spec_file_outside_trusted_dirs():
    # /etc/passwd is outside the default trusted dir (server cwd).
    res = load_spec("probe", "/etc/passwd")
    assert res["ok"] is False
    assert "refused" in res["error"] or "outside trusted" in res["error"]


def test_load_spec_file_symlink_escape(tmp_path):
    # A symlink inside a trusted dir pointing at /etc/passwd must be refused
    # (containment checked on the realpath).
    link = tmp_path / "evil-link.json"
    try:
        os.symlink("/etc/passwd", link)
    except OSError:
        # symlink creation may fail (e.g., on some filesystems) — skip
        import pytest
        pytest.skip("symlink creation not supported here")
    # tmp_path is NOT under the default trusted dir (server cwd) anyway,
    # but we also verify the realpath containment logic directly:
    ok, real_path, why = _trusted_spec_file(str(link))
    assert ok is False
    assert real_path == os.path.realpath("/etc/passwd")


def test_load_spec_file_inside_trusted_dir(tmp_path, monkeypatch):
    # A real spec file inside the server cwd (trusted by default) loads.
    monkeypatch.chdir(tmp_path)
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "t", "version": "1"},
        "paths": {"/ping": {"get": {"summary": "ping"}}},
        "servers": [{"url": "https://api.example.com"}],
    }
    import json
    p = tmp_path / "ok.json"
    p.write_text(json.dumps(spec))
    clear()
    res = load_spec("ok", str(p))
    assert res["ok"] is True, res
    clear()


# --------------------------------------------------------------------------- #
# execute — base URL guard + no request to forbidden destination
# --------------------------------------------------------------------------- #
def test_execute_base_url_forbidden_no_request():
    import json
    import genio_server.server.api_engine as eng
    clear()
    # Load a spec whose base URL points at loopback (via inline dict — the
    # FILE/URL guard is bypassed on purpose to prove the EXECUTE guard fires).
    doc = {
        "openapi": "3.0.0",
        "info": {"title": "t", "version": "1"},
        "paths": {"/x": {"get": {"summary": "x"}}},
        "servers": [{"url": "http://127.0.0.1:8000"}],
    }
    eng.load_spec_from_dict("internal", doc)
    calls = {"made": 0}
    real_client = eng._guarded_client

    def spy_client():
        calls["made"] += 1
        return real_client()

    eng._guarded_client = spy_client
    try:
        res = execute("internal", "GET", "/x")
    finally:
        eng._guarded_client = real_client
    assert res["ok"] is False
    assert "refused" in res["error"] or "forbidden" in res["error"]
    assert calls["made"] == 0, "execute guard must fire before any request"
    clear()


def test_execute_redirect_to_private_blocked(monkeypatch):
    # A public base URL that REDIRECTS to a private address must be blocked
    # on the redirect hop (transport-level check). We simulate with a custom
    # transport that records every URL the client tried to reach.
    # DNS is mocked (hermetic — no real resolver needed).
    import httpx
    import genio_server.server.api_engine as eng
    _mock_dns(monkeypatch, {"public.example.com": ["93.184.216.34"]})
    clear()
    doc = {
        "openapi": "3.0.0",
        "info": {"title": "t", "version": "1"},
        "paths": {"/x": {"get": {"summary": "x"}}},
        "servers": [{"url": "https://public.example.com"}],
    }
    eng.load_spec_from_dict("redir", doc)

    reached = []

    class SpyTransport(httpx.BaseTransport):
        def handle_request(self, request):
            reached.append(str(request.url))
            if "public.example.com" in str(request.url):
                return httpx.Response(302, headers={
                    "location": "http://127.0.0.1:8000/secret"})
            return httpx.Response(200, json={"ok": True})

    real_client = eng._guarded_client

    def fake_client():
        # Use the guard wrapper but with our spy as the inner transport so
        # the guard still runs on every hop, and we can observe attempts.
        return httpx.Client(
            transport=eng._GuardedTransport(SpyTransport()),
            follow_redirects=True, timeout=5.0)

    eng._guarded_client = fake_client
    try:
        res = execute("redir", "GET", "/x")
    finally:
        eng._guarded_client = real_client
    # The public hop may be reached; the private redirect hop must NOT be.
    assert not any("127.0.0.1" in u for u in reached), \
        f"private redirect hop was reached: {reached}"
    assert res["ok"] is False or "127.0.0.1" not in str(res.get("url", ""))
    clear()


# --------------------------------------------------------------------------- #
# set_credentials hardening
# --------------------------------------------------------------------------- #
def test_set_credentials_unknown_scheme_refused():
    import genio_server.server.api_engine as eng
    clear()
    doc = {
        "openapi": "3.0.0",
        "info": {"title": "t", "version": "1"},
        "paths": {},
        "components": {"securitySchemes": {"apiKey": {"type": "apiKey",
                                                      "in": "header",
                                                      "name": "X-Key"}}},
    }
    eng.load_spec_from_dict("cred", doc)
    res = eng.handle({"action": "set_credentials", "name": "cred",
                      "scheme": "bogus", "value": "v"})
    assert res["ok"] is False
    assert "unknown scheme" in res["error"]
    clear()


def test_set_credentials_overwrite_refused():
    import genio_server.server.api_engine as eng
    clear()
    doc = {
        "openapi": "3.0.0",
        "info": {"title": "t", "version": "1"},
        "paths": {},
        "components": {"securitySchemes": {"apiKey": {"type": "apiKey",
                                                      "in": "header",
                                                      "name": "X-Key"}}},
    }
    eng.load_spec_from_dict("cred", doc)
    r1 = eng.handle({"action": "set_credentials", "name": "cred",
                     "scheme": "apiKey", "value": "first"})
    assert r1["ok"] is True
    r2 = eng.handle({"action": "set_credentials", "name": "cred",
                     "scheme": "apiKey", "value": "second"})
    assert r2["ok"] is False
    assert "overwrite refused" in r2["error"]
    clear()


# --------------------------------------------------------------------------- #
# DNS pinning (pre-merge batch): the ACTUAL connection address is verified
# --------------------------------------------------------------------------- #
def _mock_dns(monkeypatch, mapping):
    """Map hostnames to IP lists for socket.getaddrinfo in these tests."""
    import socket as _socket
    real = _socket.getaddrinfo

    def fake(host, port, *a, **kw):
        if host in mapping:
            ips = mapping[host]
            if isinstance(ips, Exception):
                raise ips
            return [(2, 1, 6, "", (ip, port)) for ip in ips]
        return real(host, port, *a, **kw)

    monkeypatch.setattr(_socket, "getaddrinfo", fake)


def _spec_with_base(base):
    return {
        "openapi": "3.0.0",
        "info": {"title": "t", "version": "1"},
        "paths": {"/x": {"get": {"summary": "x"}}},
        "servers": [{"url": base}],
    }


def test_pin_connects_to_verified_ip_literal(monkeypatch):
    # The inner transport must NEVER see a hostname — only the verified IP
    # literal. No hostname downstream ⇒ no DNS resolution downstream ⇒ no
    # rebinding window between check and connect.
    import httpx
    import genio_server.server.api_engine as eng
    _mock_dns(monkeypatch, {"pinned.example.com": ["93.184.216.34"]})
    clear()
    eng.load_spec_from_dict("pin", _spec_with_base("https://pinned.example.com"))

    seen = []

    class SpyTransport(httpx.BaseTransport):
        def handle_request(self, request):
            seen.append(request)
            return httpx.Response(200, json={"ok": True})

    real_client = eng._guarded_client
    eng._guarded_client = lambda: httpx.Client(
        transport=eng._GuardedTransport(SpyTransport()),
        follow_redirects=True, timeout=5.0)
    try:
        res = execute("pin", "GET", "/x")
    finally:
        eng._guarded_client = real_client
    assert res["ok"] is True, res
    assert len(seen) == 1
    inner_url = str(seen[0].url)
    assert seen[0].url.host == "93.184.216.34", inner_url
    assert "pinned.example.com" not in inner_url
    # Original hostname preserved for vhost routing + TLS SNI.
    assert seen[0].headers.get("host") == "pinned.example.com"
    assert seen[0].extensions.get("sni_hostname") == "pinned.example.com"
    clear()


def test_pin_rebinding_between_check_and_connect_refused(monkeypatch):
    # DNS answers change between the pre-check and the transport hop
    # (rebinding attack): the transport re-resolves, finds private, and
    # refuses — the inner transport receives NOTHING.
    import httpx
    import socket as _socket
    import genio_server.server.api_engine as eng
    calls = {"n": 0}
    real = _socket.getaddrinfo

    def flapping(host, port, *a, **kw):
        if host == "flap.example.com":
            calls["n"] += 1
            ip = "93.184.216.34" if calls["n"] == 1 else "10.0.0.99"
            return [(2, 1, 6, "", (ip, port))]
        return real(host, port, *a, **kw)

    monkeypatch.setattr(_socket, "getaddrinfo", flapping)
    clear()
    eng.load_spec_from_dict("flap", _spec_with_base("https://flap.example.com"))

    reached = []

    class SpyTransport(httpx.BaseTransport):
        def handle_request(self, request):
            reached.append(str(request.url))
            return httpx.Response(200, json={"ok": True})

    real_client = eng._guarded_client
    eng._guarded_client = lambda: httpx.Client(
        transport=eng._GuardedTransport(SpyTransport()),
        follow_redirects=True, timeout=5.0)
    try:
        res = execute("flap", "GET", "/x")
    finally:
        eng._guarded_client = real_client
    # Pre-check saw public (passed), transport hop saw private (refused).
    assert calls["n"] >= 2, "transport must re-resolve independently"
    assert res["ok"] is False
    assert "refused" in res["error"] or "forbidden" in res["error"]
    assert reached == [], f"inner transport must receive nothing: {reached}"
    clear()


def test_pin_dns_failure_refused_no_request(monkeypatch):
    # Unresolvable host: refused at pre-check AND at transport level.
    import httpx
    import genio_server.server.api_engine as eng
    _mock_dns(monkeypatch, {"dead.example.com": OSError("no such host")})
    clear()
    eng.load_spec_from_dict("dead", _spec_with_base("https://dead.example.com"))
    assert _blocked_url("https://dead.example.com/") is not None

    reached = []

    class SpyTransport(httpx.BaseTransport):
        def handle_request(self, request):
            reached.append(str(request.url))
            return httpx.Response(200, json={"ok": True})

    real_client = eng._guarded_client
    eng._guarded_client = lambda: httpx.Client(
        transport=eng._GuardedTransport(SpyTransport()),
        follow_redirects=True, timeout=5.0)
    try:
        res = execute("dead", "GET", "/x")
    finally:
        eng._guarded_client = real_client
    assert res["ok"] is False
    assert reached == []
    clear()


def test_pin_redirect_hop_repinned(monkeypatch):
    # Redirect chain public→public: EVERY hop is pinned to a verified IP.
    # The inner transport only ever sees IP literals, never hostnames.
    import httpx
    import genio_server.server.api_engine as eng
    _mock_dns(monkeypatch, {"one.example.com": ["93.184.216.34"],
                            "two.example.com": ["93.184.216.35"]})
    clear()
    eng.load_spec_from_dict("chain", _spec_with_base("https://one.example.com"))

    reached = []

    class SpyTransport(httpx.BaseTransport):
        def handle_request(self, request):
            reached.append(str(request.url))
            if "93.184.216.34" in str(request.url):
                return httpx.Response(302, headers={
                    "location": "https://two.example.com/y"})
            return httpx.Response(200, json={"ok": True})

    real_client = eng._guarded_client
    eng._guarded_client = lambda: httpx.Client(
        transport=eng._GuardedTransport(SpyTransport()),
        follow_redirects=True, timeout=5.0)
    try:
        res = execute("chain", "GET", "/x")
    finally:
        eng._guarded_client = real_client
    assert res["ok"] is True, res
    assert len(reached) == 2, reached
    for u in reached:
        assert "example.com" not in u, f"hostname leaked downstream: {u}"
    assert "93.184.216.34" in reached[0] and "93.184.216.35" in reached[1]
    clear()


# --------------------------------------------------------------------------- #
# IPv4 / IPv6 / malformed URLs
# --------------------------------------------------------------------------- #
def test_blocked_url_ipv6():
    assert _blocked_url("http://[::1]/") is not None
    assert _blocked_url("http://[fe80::1]/") is not None
    assert _blocked_url("http://[::ffff:127.0.0.1]/") is not None
    # Public IPv6 (Cloudflare DNS) must NOT be blocked by the IP rules.
    assert _blocked_url("http://[2606:4700:4700::1111]/") is None


def test_blocked_url_malformed_never_raises():
    # Invalid ports, broken brackets, empty and hostless inputs must yield
    # a refusal reason — never an escaping exception.
    for bad in ("http://example.com:abc/", "http://[::1", "",
                "not a url", "http:///nohost", "ftp://127.0.0.1:x/"):
        try:
            reason = _blocked_url(bad)
        except Exception as exc:
            raise AssertionError(f"_blocked_url({bad!r}) raised {exc!r}")
        assert reason is not None, f"_blocked_url({bad!r}) must refuse"


def test_execute_malformed_base_no_raise():
    # A spec whose base URL has an invalid port: execute() returns an
    # error dict — no exception escapes the tool path.
    import genio_server.server.api_engine as eng
    clear()
    eng.load_spec_from_dict("bad", _spec_with_base("http://example.com:abc/"))
    try:
        res = execute("bad", "GET", "/x")
    except Exception as exc:
        raise AssertionError(f"execute() raised {exc!r}")
    assert res["ok"] is False
    clear()


# --------------------------------------------------------------------------- #
# ALLOW_PRIVATE decoupled from file policy
# --------------------------------------------------------------------------- #
def test_allow_private_does_not_widen_file_reads(monkeypatch):
    # GENIO_API_ALLOW_PRIVATE=1 lifts NETWORK checks only. Spec FILE
    # containment applies regardless.
    import os as _os
    monkeypatch.setenv("GENIO_API_ALLOW_PRIVATE", "1")
    assert _blocked_url("http://127.0.0.1/") is None  # network lifted
    ok, _, why = _trusted_spec_file("/etc/passwd")
    assert ok is False, "file containment must hold under ALLOW_PRIVATE"
    res = load_spec("probe", "/etc/passwd")
    assert res["ok"] is False
    assert "refused" in res["error"] or "outside trusted" in res["error"]


# --------------------------------------------------------------------------- #
# ALLOW_PRIVATE follow-up: pinning + denylist hold under the escape hatch
# --------------------------------------------------------------------------- #
def test_metadata_denylist_holds_under_allow_private(monkeypatch):
    # Metadata/loopback names stay refused even when the operator lifts
    # the private-IP ban — at pre-check AND at execute level, with the
    # inner transport receiving nothing.
    import httpx
    import genio_server.server.api_engine as eng
    monkeypatch.setenv("GENIO_API_ALLOW_PRIVATE", "1")
    assert _blocked_url("https://metadata.google.internal/") is not None
    assert _blocked_url("http://localhost:8000/") is not None
    assert _blocked_url("http://127.0.0.1/") is None  # plain IP: lifted
    clear()
    eng.load_spec_from_dict("meta",
                            _spec_with_base("https://metadata.google.internal/"))

    reached = []

    class SpyTransport(httpx.BaseTransport):
        def handle_request(self, request):
            reached.append(str(request.url))
            return httpx.Response(200, json={"ok": True})

    real_client = eng._guarded_client
    eng._guarded_client = lambda: httpx.Client(
        transport=eng._GuardedTransport(SpyTransport()),
        follow_redirects=True, timeout=5.0)
    try:
        res = execute("meta", "GET", "/x")
    finally:
        eng._guarded_client = real_client
    assert res["ok"] is False
    assert "refused" in res["error"] or "forbidden" in res["error"]
    assert reached == []
    clear()


def test_allow_private_still_pins_no_hostname_downstream(monkeypatch):
    # ALLOW_PRIVATE lifts the private-IP ban but must NOT restore the
    # downstream-DNS window: the inner transport still receives an IP
    # literal, never the original hostname.
    import httpx
    import genio_server.server.api_engine as eng
    monkeypatch.setenv("GENIO_API_ALLOW_PRIVATE", "1")
    _mock_dns(monkeypatch, {"internal.example.com": ["10.1.2.3"]})
    clear()
    eng.load_spec_from_dict("priv",
                            _spec_with_base("https://internal.example.com"))

    seen = []

    class SpyTransport(httpx.BaseTransport):
        def handle_request(self, request):
            seen.append(request)
            return httpx.Response(200, json={"ok": True})

    real_client = eng._guarded_client
    eng._guarded_client = lambda: httpx.Client(
        transport=eng._GuardedTransport(SpyTransport()),
        follow_redirects=True, timeout=5.0)
    try:
        res = execute("priv", "GET", "/x")
    finally:
        eng._guarded_client = real_client
    assert res["ok"] is True, res
    assert len(seen) == 1
    assert seen[0].url.host == "10.1.2.3", str(seen[0].url)
    assert "internal.example.com" not in str(seen[0].url)
    assert seen[0].headers.get("host") == "internal.example.com"
    assert seen[0].extensions.get("sni_hostname") == "internal.example.com"
    clear()


def test_allow_private_redirect_hop_repinned(monkeypatch):
    # Under ALLOW_PRIVATE, a redirect private→private is allowed BUT every
    # hop stays pinned to a verified literal (no hostname downstream).
    import httpx
    import genio_server.server.api_engine as eng
    monkeypatch.setenv("GENIO_API_ALLOW_PRIVATE", "1")
    _mock_dns(monkeypatch, {"a.example.com": ["10.1.2.3"],
                            "b.example.com": ["10.1.2.4"]})
    clear()
    eng.load_spec_from_dict("chain2",
                            _spec_with_base("https://a.example.com"))

    reached = []

    class SpyTransport(httpx.BaseTransport):
        def handle_request(self, request):
            reached.append(str(request.url))
            if "10.1.2.3" in str(request.url):
                return httpx.Response(302, headers={
                    "location": "https://b.example.com/y"})
            return httpx.Response(200, json={"ok": True})

    real_client = eng._guarded_client
    eng._guarded_client = lambda: httpx.Client(
        transport=eng._GuardedTransport(SpyTransport()),
        follow_redirects=True, timeout=5.0)
    try:
        res = execute("chain2", "GET", "/x")
    finally:
        eng._guarded_client = real_client
    assert res["ok"] is True, res
    assert len(reached) == 2, reached
    for u in reached:
        assert "example.com" not in u, f"hostname leaked downstream: {u}"
    assert "10.1.2.3" in reached[0] and "10.1.2.4" in reached[1]
    clear()


def test_host_header_preserves_nondefault_port(monkeypatch):
    # Rewriting to an IP literal must not corrupt the Host header:
    # non-default ports are preserved (vhost routing correctness).
    import httpx
    import genio_server.server.api_engine as eng
    _mock_dns(monkeypatch, {"svc.example.com": ["93.184.216.34"]})
    clear()
    eng.load_spec_from_dict("svc",
                            _spec_with_base("https://svc.example.com:8443"))

    seen = []

    class SpyTransport(httpx.BaseTransport):
        def handle_request(self, request):
            seen.append(request)
            return httpx.Response(200, json={"ok": True})

    real_client = eng._guarded_client
    eng._guarded_client = lambda: httpx.Client(
        transport=eng._GuardedTransport(SpyTransport()),
        follow_redirects=True, timeout=5.0)
    try:
        res = execute("svc", "GET", "/x")
    finally:
        eng._guarded_client = real_client
    assert res["ok"] is True, res
    assert len(seen) == 1
    assert seen[0].url.host == "93.184.216.34", str(seen[0].url)
    assert seen[0].url.port == 8443, str(seen[0].url)
    assert seen[0].headers.get("host") == "svc.example.com:8443", \
        dict(seen[0].headers)
    assert seen[0].extensions.get("sni_hostname") == "svc.example.com"
    clear()


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
