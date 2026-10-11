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


def test_execute_redirect_to_private_blocked():
    # A public base URL that REDIRECTS to a private address must be blocked
    # on the redirect hop (transport-level check). We simulate with a custom
    # transport that records every URL the client tried to reach.
    import httpx
    import genio_server.server.api_engine as eng
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


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
