"""LIVE transport tests for the api SSRF guard (pre-merge review follow-up).

Unlike test_api_engine_ssrf.py (unit + mocked inner transports), these
tests run REAL sockets: local HTTP(S) servers on loopback, real httpx
redirect machinery, real TLS handshakes, real request bodies. DNS answers
are still mocked (offline hermeticity) — but everything downstream of the
guard (TCP dial, TLS, HTTP, redirects) is genuine.

Proves, against review points 1-5:
  1. TLS/SNI: a correct cert for the ORIGINAL hostname succeeds through
     the pinned IP dial; a mismatched cert is refused (verification runs
     against the hostname, never the literal).
  2. Pinned IP comes from the checked answer set (incl. IPv4/IPv6).
  3. Real redirects: ports preserved, Host per-hop, bodies intact.
  4. Metadata alternates: Alibaba IP, numeric obfuscation, DHCP names,
     in both modes.
  5. POST bodies survive 307 redirects byte-identical (no loss/dup).

Needs: openssl CLI (cert generation), IPv6 loopback for the v6 test
(skipped if unavailable). No commit, no runtime files touched.
"""
import contextlib
import http.server
import json
import os
import socket
import ssl
import subprocess
import sys
import threading

sys.path.insert(0, "/data/ai_tools/genio")

from genio_server.server.api_engine import (
    _blocked_url, _is_metadata_ip, _pin_request, clear, execute,
    load_spec_from_dict,
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _mock_dns(monkeypatch, mapping):
    import socket as _socket
    real = _socket.getaddrinfo

    def fake(host, port, *a, **kw):
        if host in mapping:
            ips = mapping[host]
            if isinstance(ips, Exception):
                raise ips
            out = []
            for ip in ips:
                fam = socket.AF_INET6 if ":" in ip else socket.AF_INET
                sa = (ip, port, 0, 0) if fam == socket.AF_INET6 else (ip, port)
                out.append((fam, socket.SOCK_STREAM, 6, "", sa))
            return out
        return real(host, port, *a, **kw)

    monkeypatch.setattr(_socket, "getaddrinfo", fake)


def _make_handler(store, responder):
    class H(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def _handle(self):
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else b""
            store.append({"method": self.command, "path": self.path,
                          "host": self.headers.get("Host"), "body": body})
            status, headers, out = responder(self.command, self.path, body)
            self.send_response(status)
            for k, v in headers.items():
                self.send_header(k, v)
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)

        do_GET = _handle
        do_POST = _handle
        do_PUT = _handle

        def log_message(self, *a):
            pass

    return H


@contextlib.contextmanager
def _serve(handler_cls, family=socket.AF_INET, host=None, cert=None):
    host = host or ("127.0.0.1" if family == socket.AF_INET else "::1")

    class Srv(http.server.ThreadingHTTPServer):
        address_family = family
        daemon_threads = True

    srv = Srv((host, 0), handler_cls)
    if cert:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(cert[1], cert[0])
        srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield srv
    finally:
        srv.shutdown()
        srv.server_close()


def _make_cert(tmp_path, cn):
    key = tmp_path / f"{cn}.key"
    crt = tmp_path / f"{cn}.crt"
    subprocess.run(
        ["openssl", "req", "-x509", "-newkey", "rsa:2048",
         "-keyout", str(key), "-out", str(crt), "-days", "2", "-nodes",
         "-subj", f"/CN={cn}", "-addext", f"subjectAltName=DNS:{cn}"],
        check=True, capture_output=True)
    return key, crt


def _spec_with_base(base):
    return {
        "openapi": "3.0.0",
        "info": {"title": "t", "version": "1"},
        "paths": {"/x": {"get": {"summary": "x"}},
                  "/submit": {"post": {"summary": "s"}},
                  "/echo": {"post": {"summary": "e"}}},
        "servers": [{"url": base}],
    }


# --------------------------------------------------------------------------- #
# 1. TLS/SNI against the ORIGINAL hostname through the pinned dial
# --------------------------------------------------------------------------- #
def test_tls_validates_against_original_hostname(tmp_path, monkeypatch):
    # Real TLS handshake to 127.0.0.1 with a cert valid for 'pinned.test':
    # success proves SNI + Host survived pinning AND verification ran
    # against the hostname (an IP-literal check would fail: no IP SAN).
    import genio_server.server.api_engine as eng
    key, crt = _make_cert(tmp_path, "pinned.test")
    monkeypatch.setenv("GENIO_API_ALLOW_PRIVATE", "1")
    monkeypatch.setenv("SSL_CERT_FILE", str(crt))
    _mock_dns(monkeypatch, {"pinned.test": ["127.0.0.1"]})
    store = []

    def responder(method, path, body):
        return 200, {"Content-Type": "application/json"}, b'{"tls":"ok"}'

    with _serve(_make_handler(store, responder), cert=(key, crt)) as srv:
        port = srv.server_address[1]
        clear()
        eng.load_spec_from_dict(
            "tls", _spec_with_base(f"https://pinned.test:{port}"))
        res = execute("tls", "GET", "/x")
        clear()
    assert res["ok"] is True, res
    assert res.get("json") == {"tls": "ok"}
    assert len(store) == 1
    assert store[0]["host"] == f"pinned.test:{port}", store[0]


def test_tls_mismatched_cert_refused(tmp_path, monkeypatch):
    # Same pinned dial, but the server presents a cert for 'evil.test'
    # (trusted as CA so we reach hostname verification): the handshake
    # MUST fail — the guard never blindly trusts.
    import genio_server.server.api_engine as eng
    key, crt = _make_cert(tmp_path, "evil.test")
    monkeypatch.setenv("GENIO_API_ALLOW_PRIVATE", "1")
    monkeypatch.setenv("SSL_CERT_FILE", str(crt))
    _mock_dns(monkeypatch, {"pinned.test": ["127.0.0.1"]})
    store = []

    def responder(method, path, body):
        return 200, {"Content-Type": "application/json"}, b'{"tls":"ok"}'

    with _serve(_make_handler(store, responder), cert=(key, crt)) as srv:
        port = srv.server_address[1]
        clear()
        eng.load_spec_from_dict(
            "tlsbad", _spec_with_base(f"https://pinned.test:{port}"))
        res = execute("tlsbad", "GET", "/x")
        clear()
    assert res["ok"] is False, res
    assert "certificat" in res["error"].lower() or \
        "verify" in res["error"].lower() or \
        "ssl" in res["error"].lower(), res["error"]
    assert store == [], "handshake must fail before any HTTP bytes"


# --------------------------------------------------------------------------- #
# 2. Pinned IP comes from the checked answer set (v4 + v6)
# --------------------------------------------------------------------------- #
def test_pinned_ip_from_checked_set_v4_v6(monkeypatch):
    # Mixed answers: the pinned address must be exactly sorted(set)[0] —
    # deterministic, always a verified member, never an unchecked one.
    import httpx
    _mock_dns(monkeypatch, {"mix.example.com": ["93.184.216.35",
                                                "2606:4700:4700::1111",
                                                "93.184.216.34"]})
    req = httpx.Request("GET", "https://mix.example.com/x")
    from genio_server.server.api_engine import _pin_request
    pinned, reason = _pin_request(req)
    assert reason is None and pinned is not None
    # sorted() over the string forms, first wins:
    assert pinned.url.host == sorted(["93.184.216.35",
                                      "2606:4700:4700::1111",
                                      "93.184.216.34"])[0]
    assert pinned.headers["host"] == "mix.example.com"
    # Repeatability: same answers ⇒ same pin (no flapping between hops).
    pinned2, _ = _pin_request(httpx.Request("GET", "https://mix.example.com/y"))
    assert pinned2.url.host == pinned.url.host


def test_ipv6_pinning_real_socket(monkeypatch):
    # Real TCP to ::1 through the pinned literal, Host preserved.
    import genio_server.server.api_engine as eng
    try:
        probe = socket.socket(socket.AF_INET6)
        probe.bind(("::1", 0))
        probe.close()
    except OSError:
        import pytest
        pytest.skip("no IPv6 loopback here")
    monkeypatch.setenv("GENIO_API_ALLOW_PRIVATE", "1")
    _mock_dns(monkeypatch, {"v6.example.com": ["::1"]})
    store = []

    def responder(method, path, body):
        return 200, {"Content-Type": "application/json"}, b'{"v6":"ok"}'

    with _serve(_make_handler(store, responder),
                family=socket.AF_INET6) as srv:
        port = srv.server_address[1]
        clear()
        eng.load_spec_from_dict(
            "v6", _spec_with_base(f"http://v6.example.com:{port}"))
        res = execute("v6", "GET", "/x")
        clear()
    assert res["ok"] is True, res
    assert store and store[0]["host"] == f"v6.example.com:{port}", store


# --------------------------------------------------------------------------- #
# 3. Real redirects: ports, Host per hop, POST body intact through 307
# --------------------------------------------------------------------------- #
def test_post_body_preserved_through_307_redirect(tmp_path, monkeypatch):
    # Two REAL servers, REAL httpx redirect machinery: POST json →
    # 307 → second hop must receive byte-identical body (no loss, no dup),
    # with per-hop Host headers incl. non-default ports.
    import genio_server.server.api_engine as eng
    monkeypatch.setenv("GENIO_API_ALLOW_PRIVATE", "1")
    _mock_dns(monkeypatch, {"one.example.com": ["127.0.0.1"],
                            "two.example.com": ["127.0.0.1"]})
    # Server B echoes the received body as JSON; the handler-level
    # store records method/path/Host/raw body for exactness assertions.
    store_b2 = []

    def responder_b3(method, path, body):
        out = json.dumps({"echo": body.decode()}).encode()
        return 200, {"Content-Type": "application/json"}, out

    with _serve(_make_handler(store_b2, responder_b3)) as srv_b:
        pb = srv_b.server_address[1]

        def responder_a2(method, path, body):
            return 307, {"Location": f"http://two.example.com:{pb}/echo"}, b""

        store_a2 = []
        with _serve(_make_handler(store_a2, responder_a2)) as srv_a:
            pa = srv_a.server_address[1]
            clear()
            eng.load_spec_from_dict(
                "post", _spec_with_base(f"http://one.example.com:{pa}"))
            payload = {"k": "v" * 100, "n": 42}
            res = execute("post", "POST", "/submit", body=payload)
            clear()
    assert res["ok"] is True, res
    sent = json.dumps(payload)
    assert res.get("json") == {"echo": sent}, res
    # Server B received the EXACT bytes once (no loss, no duplication).
    assert len(store_b2) == 1, store_b2
    assert store_b2[0]["body"].decode() == sent
    assert store_b2[0]["host"] == f"two.example.com:{pb}", store_b2[0]
    assert store_b2[0]["method"] == "POST", store_b2[0]
    # First hop kept its own Host (per-hop correctness, non-default port).
    assert store_a2 and store_a2[0]["host"] == f"one.example.com:{pa}"


# --------------------------------------------------------------------------- #
# 4. Metadata alternates (both modes) + numeric obfuscation (real resolver)
# --------------------------------------------------------------------------- #
def test_metadata_alibaba_ip_refused_both_modes(monkeypatch):
    assert _blocked_url("http://100.100.100.200/latest/meta-data/") is not None
    monkeypatch.setenv("GENIO_API_ALLOW_PRIVATE", "1")
    # Explicit metadata set holds even under the escape hatch…
    assert _blocked_url("http://100.100.100.200/") is not None
    assert _is_metadata_ip("100.100.100.200") is True
    assert _is_metadata_ip("::ffff:100.100.100.200") is True
    # …while ordinary private IPs are lifted (operator's choice).
    assert _blocked_url("http://10.0.0.5/") is None


def test_numeric_obfuscation_refused_real_resolver():
    # Decimal/hex/octal loopback forms resolve to 127.0.0.1 via the REAL
    # libc resolver — the answer check (not the string) refuses them.
    for u in ("http://2130706433/", "http://0x7f.0.0.1/",
              "http://0177.0.0.1/", "http://2130706433:8000/x"):
        assert _blocked_url(u) is not None, u


def test_metadata_dhcp_name_resolving_private_refused(monkeypatch):
    # AWS-style DHCP hostname resolving to link-local metadata → refused.
    _mock_dns(monkeypatch, {"instance-data": ["169.254.169.254"]})
    assert _blocked_url("http://instance-data/") is not None
    _mock_dns(monkeypatch, {"data.example.com": ["100.100.100.200"]})
    assert _blocked_url("http://data.example.com/") is not None


def test_metadata_names_hold_under_allow_private(monkeypatch):
    monkeypatch.setenv("GENIO_API_ALLOW_PRIVATE", "1")
    for u in ("https://metadata.google.internal/", "https://metadata.goog/",
              "http://metadata/", "http://svc.localhost:8080/",
              "http://METADATA.GOOGLE.INTERNAL./"):
        assert _blocked_url(u) is not None, u


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
