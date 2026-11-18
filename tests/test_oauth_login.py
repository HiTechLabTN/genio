"""OAuth login tests (Phase 3 — voice/identity mission).

All provider HTTP is mocked (unit-grade, hermetic); the Google ID token
itself is a REAL RS256 JWT minted with a throwaway test key and verified
against a pre-seeded JWKS cache — signature/aud/exp/nonce checks are
exercised for real, not stubbed.

Covers task reqs: callback success/failure, bad/missing state (+replay),
invalid identity (bad sig, wrong aud, expired, nonce mismatch), token
endpoint errors, redirect-URI handling, logout/expiry, cross-user
isolation, no secrets in logs, legacy Bearer intact. Real external login
is NOT claimed without operator OAuth credentials (see report).
"""
import sys
import time

sys.path.insert(0, "/data/ai_tools/genio")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import genio_server.server.oauth_login as oauth
import genio_server.server.user_store as ustore


# --------------------------------------------------------------------------- #
# Fakes
# --------------------------------------------------------------------------- #
class FakeResp:
    def __init__(self, status=200, doc=None):
        self.status_code = status
        self._doc = doc or {}

    def json(self):
        return self._doc

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx
            raise httpx.HTTPStatusError("mock", request=None,
                                        response=None)


class FakeProviderHTTP:
    """Stub for oauth_login.httpx: configurable provider answers."""

    google_token_doc = None
    github_token_doc = None
    github_user_doc = None
    github_emails_doc = None

    def __init__(self, *a, **kw):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, data=None, headers=None):
        if "googleapis" in url:
            doc = type(self).google_token_doc
            if doc is None:
                return FakeResp(400, {"error": "bad_grant"})
            return FakeResp(200, doc)
        if "github.com/login" in url:
            doc = type(self).github_token_doc
            if doc is None:
                return FakeResp(400, {"error": "bad_verification_code"})
            return FakeResp(200, doc)
        return FakeResp(404, {})

    async def get(self, url, headers=None):
        if url.endswith("/user/emails"):
            doc = type(self).github_emails_doc
            return FakeResp(200, doc if doc is not None else [])
        if url.endswith("/user"):
            doc = type(self).github_user_doc
            if doc is None:
                return FakeResp(401, {"message": "bad credentials"})
            return FakeResp(200, doc)
        return FakeResp(404, {})

    def get_sync(self, url, **kw):  # pragma: no cover
        raise AssertionError("sync provider HTTP must not be used")


@pytest.fixture()
def app(monkeypatch, tmp_path):
    # Isolated identity DB per test.
    store = ustore.UserStore(tmp_path / "t.db")
    monkeypatch.setattr(ustore, "_STORE", store)
    # Provider HTTP stub (module-level httpx name only — TestClient safe).
    monkeypatch.setattr(oauth, "httpx", FakeProviderHTTPModule())
    # Deterministic config for assertions.
    monkeypatch.setattr(oauth, "GOOGLE_CLIENT_ID", "test-google-id")
    monkeypatch.setattr(oauth, "GOOGLE_CLIENT_SECRET", "test-google-secret")
    monkeypatch.setattr(oauth, "GITHUB_CLIENT_ID", "test-gh-id")
    monkeypatch.setattr(oauth, "GITHUB_CLIENT_SECRET", "test-gh-secret")
    monkeypatch.setattr(oauth, "OAUTH_BASE", "http://testserver")
    from fastapi import FastAPI
    fast = FastAPI()
    oauth.register_oauth_routes(fast)
    with TestClient(fast, base_url="http://testserver") as client:
        yield client
    # Deterministic cleanup: every aiosqlite Connection spawns a worker
    # thread that lives until close() — an unclosed test store leaks
    # threads that stall interpreter shutdown once other suites join the
    # same pytest process (hangs the full run at exit with zero failures).
    import asyncio as _aio
    _aio.run(store.close())


class FakeProviderHTTPModule:
    """Namespace replacing oauth.httpx in tests (AsyncClient only)."""

    AsyncClient = FakeProviderHTTP

    class Client:  # pragma: no cover
        def __init__(self, *a, **kw):
            raise AssertionError("sync provider HTTP must not be used")


@pytest.fixture()
def rsa_key():
    from cryptography.hazmat.primitives.asymmetric import rsa
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture()
def jwks(rsa_key, monkeypatch):
    from cryptography.hazmat.primitives import serialization
    pub = rsa_key.public_key()
    numbers = pub.public_numbers()
    import base64

    def _b64(n, ln):
        return base64.urlsafe_b64encode(
            n.to_bytes(ln, "big")).rstrip(b"=").decode()

    jwk = {"kty": "RSA", "kid": "test-kid", "use": "sig", "alg": "RS256",
           "n": _b64(numbers.n, 256), "e": _b64(numbers.e, 3)}
    monkeypatch.setattr(oauth, "_JWKS_CACHE",
                        (time.time(), {"test-kid": jwk}))
    return rsa_key


def _google_id_token(rsa_key, aud="test-google-id", nonce="n_x",
                     exp_in=600, iss="https://accounts.google.com",
                     sub="google-sub-1"):
    import jwt as pyjwt
    from cryptography.hazmat.primitives import serialization
    now = int(time.time())
    return pyjwt.encode(
        {"iss": iss, "aud": aud, "sub": sub, "exp": now + exp_in,
         "iat": now - 10, "nonce": nonce, "email": "u@example.com",
         "email_verified": True, "name": "Tu"},
        rsa_key, algorithm="RS256", headers={"kid": "test-kid"})


def _google_token_for(jwks, state, **kw):
    """Mint a token the way Google would: echoing THIS handshake's nonce
    (read from the server pending record, like the provider echoes the
    nonce from the authorization request)."""
    nonce = oauth._PENDING[state]["nonce"]
    return _google_id_token(jwks, nonce=nonce, **kw)


def _start(client, provider):
    r = client.get(f"/api/v1/auth/oauth/{provider}/start",
                   follow_redirects=False)
    assert r.status_code == 200, r.text
    doc = r.json()
    assert doc["ok"] is True and doc["auth_url"] and doc["state"]
    return doc


def _callback(client, state, code="c0de"):
    return client.get("/api/v1/auth/oauth/callback",
                      params={"code": code, "state": state},
                      follow_redirects=False)


# --------------------------------------------------------------------------- #
# Start + callback
# --------------------------------------------------------------------------- #
def test_start_unknown_provider_404(app):
    r = app.get("/api/v1/auth/oauth/facebook/start")
    assert r.status_code == 404


def test_start_unconfigured_503(app, monkeypatch):
    monkeypatch.setattr(oauth, "GOOGLE_CLIENT_SECRET", "")
    r = app.get("/api/v1/auth/oauth/google/start")
    assert r.status_code == 503


def test_google_callback_success(app, jwks):
    doc = _start(app, "google")
    FakeProviderHTTP.google_token_doc = {
        "id_token": _google_token_for(jwks, doc["state"])}
    try:
        assert "accounts.google.com" in doc["auth_url"]
        assert "code_challenge" in doc["auth_url"]  # PKCE
        r = _callback(app, doc["state"])
        assert r.status_code == 303, r.text
        assert "login=ok" in r.headers["location"]
        cookie = r.headers.get("set-cookie", "")
        assert "genio_session=" in cookie and "HttpOnly" in cookie
        # Session resolves to the verified identity (backend-verified).
        me = app.get("/api/v1/auth/me",
                     cookies={"genio_session": cookie.split("genio_session=")[1].split(";")[0]})
        assert me.status_code == 200, me.text
        user = me.json()["user"]
        assert user["provider"] == "google" and user["email"] == "u@example.com"
        assert user["email_verified"] is True
    finally:
        FakeProviderHTTP.google_token_doc = None


def test_github_callback_success_hidden_email(app):
    FakeProviderHTTP.github_token_doc = {"access_token": "gh_tok"}
    FakeProviderHTTP.github_user_doc = {"id": 4242, "login": "octo",
                                        "name": None,
                                        "avatar_url": "http://x/y.png"}
    FakeProviderHTTP.github_emails_doc = []  # hidden → stays None
    try:
        doc = _start(app, "github")
        assert "github.com/login/oauth/authorize" in doc["auth_url"]
        r = _callback(app, doc["state"])
        assert r.status_code == 303 and "login=ok" in r.headers["location"]
        cookie = r.headers.get("set-cookie", "")
        tok = cookie.split("genio_session=")[1].split(";")[0]
        me = app.get("/api/v1/auth/me", cookies={"genio_session": tok})
        user = me.json()["user"]
        assert user["provider"] == "github"
        assert user["email"] is None and user["email_verified"] is False
    finally:
        FakeProviderHTTP.github_token_doc = None
        FakeProviderHTTP.github_user_doc = None
        FakeProviderHTTP.github_emails_doc = None


def test_github_primary_verified_email(app):
    FakeProviderHTTP.github_token_doc = {"access_token": "gh_tok"}
    FakeProviderHTTP.github_user_doc = {"id": 99, "login": "octo2"}
    FakeProviderHTTP.github_emails_doc = [
        {"email": "a@x.io", "primary": False, "verified": True},
        {"email": "b@x.io", "primary": True, "verified": True}]
    try:
        doc = _start(app, "github")
        r = _callback(app, doc["state"])
        tok = r.headers["set-cookie"].split("genio_session=")[1].split(";")[0]
        user = app.get("/api/v1/auth/me",
                       cookies={"genio_session": tok}).json()["user"]
        assert user["email"] == "b@x.io" and user["email_verified"] is True
    finally:
        FakeProviderHTTP.github_token_doc = None
        FakeProviderHTTP.github_user_doc = None
        FakeProviderHTTP.github_emails_doc = None


def test_callback_bad_state_rejected(app):
    r = _callback(app, "st_nope")
    assert r.status_code == 303 and "invalid_state" in r.headers["location"]


def test_callback_missing_state_rejected(app):
    r = app.get("/api/v1/auth/oauth/callback", params={"code": "x"},
                follow_redirects=False)
    assert r.status_code == 303 and "invalid_state" in r.headers["location"]


def test_state_single_use_replay_rejected(app, jwks):
    doc = _start(app, "google")
    FakeProviderHTTP.google_token_doc = {
        "id_token": _google_token_for(jwks, doc["state"])}
    try:
        r1 = _callback(app, doc["state"])
        assert r1.status_code == 303 and "login=ok" in r1.headers["location"]
        r2 = _callback(app, doc["state"])
        assert "invalid_state" in r2.headers["location"]
    finally:
        FakeProviderHTTP.google_token_doc = None


def test_google_bad_signature_rejected(app, jwks, rsa_key):
    from cryptography.hazmat.primitives.asymmetric import rsa as _rsa
    other = _rsa.generate_private_key(public_exponent=65537, key_size=2048)
    doc = _start(app, "google")
    FakeProviderHTTP.google_token_doc = {
        "id_token": _google_token_for(other, doc["state"])}
    try:
        r = _callback(app, doc["state"])
        assert "identity_failed" in r.headers["location"], r.headers
    finally:
        FakeProviderHTTP.google_token_doc = None


def test_google_wrong_audience_rejected(app, jwks):
    doc = _start(app, "google")
    FakeProviderHTTP.google_token_doc = {
        "id_token": _google_token_for(jwks, doc["state"],
                                      aud="other-client")}
    try:
        # Correct nonce, wrong audience: isolates the aud check.
        r = _callback(app, doc["state"])
        assert "identity_failed" in r.headers["location"]
    finally:
        FakeProviderHTTP.google_token_doc = None


def test_google_expired_rejected(app, jwks):
    doc = _start(app, "google")
    FakeProviderHTTP.google_token_doc = {
        "id_token": _google_token_for(jwks, doc["state"], exp_in=-600)}
    try:
        r = _callback(app, doc["state"])
        assert "identity_failed" in r.headers["location"]
    finally:
        FakeProviderHTTP.google_token_doc = None


def test_google_nonce_mismatch_rejected(app, jwks):
    # Correct key/aud/expiry but a FOREIGN nonce: isolates the nonce check.
    doc = _start(app, "google")
    FakeProviderHTTP.google_token_doc = {
        "id_token": _google_id_token(jwks, nonce="n_foreign")}
    try:
        r = _callback(app, doc["state"])
        assert "identity_failed" in r.headers["location"]
    finally:
        FakeProviderHTTP.google_token_doc = None


def test_token_endpoint_error_rejected(app):
    FakeProviderHTTP.google_token_doc = None  # → 400 bad_grant
    doc = _start(app, "google")
    r = _callback(app, doc["state"])
    assert "identity_failed" in r.headers["location"]


def test_forged_redirect_uri_ignored(app, jwks):
    # The server never reads redirect URIs from the request: even a
    # callback carrying ?redirect_uri=https://evil/ uses the fixed URI.
    seen = {}

    class SpyAsync(FakeProviderHTTP):
        async def post(self, url, data=None, headers=None):
            if "googleapis" in url:
                seen.update(data or {})
                return FakeResp(200, {"id_token": forged_token[0]})
            return await super().post(url, data, headers)

    import genio_server.server.oauth_login as _o
    real = _o.httpx
    forged_token = [""]
    _o.httpx = type("NS", (), {"AsyncClient": SpyAsync})()
    try:
        doc = _start(app, "google")
        forged_token[0] = _google_token_for(jwks, doc["state"])
        r = app.get("/api/v1/auth/oauth/callback",
                    params={"code": "c", "state": doc["state"],
                            "redirect_uri": "https://evil.example/"},
                    follow_redirects=False)
        assert "login=ok" in r.headers["location"], r.headers
        assert seen.get("redirect_uri", "").startswith("http://testserver"), seen
        assert "evil" not in seen.get("redirect_uri", "")
    finally:
        _o.httpx = real


# --------------------------------------------------------------------------- #
# Logout / expiry / isolation
# --------------------------------------------------------------------------- #
def _login_google(app, jwks, sub="google-sub-1"):
    doc = _start(app, "google")
    FakeProviderHTTP.google_token_doc = {
        "id_token": _google_token_for(jwks, doc["state"], sub=sub)}
    try:
        r = _callback(app, doc["state"])
        tok = r.headers["set-cookie"].split("genio_session=")[1].split(";")[0]
        return tok
    finally:
        FakeProviderHTTP.google_token_doc = None


def test_logout_revokes(app, jwks):
    tok = _login_google(app, jwks)
    assert app.get("/api/v1/auth/me",
                   cookies={"genio_session": tok}).status_code == 200
    r = app.post("/api/v1/auth/logout", cookies={"genio_session": tok})
    assert r.status_code == 200
    assert app.get("/api/v1/auth/me",
                   cookies={"genio_session": tok}).status_code == 401


def test_session_expiry_enforced(tmp_path):
    import asyncio
    store = ustore.UserStore(tmp_path / "e.db")

    async def _run():
        u = await store.get_or_create_user("google", "s1")
        await store.create_session(int(u["id"]), "raw-tok", 0.05)
        assert await store.get_session_user("raw-tok") is not None
        await asyncio.sleep(0.1)
        assert await store.get_session_user("raw-tok") is None
        await store.close()

    asyncio.run(_run())


def test_no_email_linking_across_providers(tmp_path):
    import asyncio
    store = ustore.UserStore(tmp_path / "l.db")

    async def _run():
        a = await store.get_or_create_user("google", "g1",
                                           email="same@x.io")
        b = await store.get_or_create_user("github", "h1",
                                           email="same@x.io")
        assert int(a["id"]) != int(b["id"])
        await store.close()

    asyncio.run(_run())


def test_cross_user_session_isolation(app, jwks):
    # Two separate "browsers" (isolated cookie jars): each session
    # resolves to its own user, never the other's.
    tok_a = _login_google(app, jwks, sub="user-A")
    tok_b = _login_google(app, jwks, sub="user-B")

    def _me_as(tok):
        app.cookies.clear()
        app.cookies.set("genio_session", tok)
        r = app.get("/api/v1/auth/me")
        assert r.status_code == 200, r.text
        return r.json()["user"]

    me_a = _me_as(tok_a)
    me_b = _me_as(tok_b)
    assert me_a["id"] != me_b["id"]
    assert me_a["provider"] == me_b["provider"] == "google"


def test_no_secrets_in_logs(app, jwks, caplog):
    import logging
    FakeProviderHTTP.google_token_doc = {
        "id_token": _google_id_token(jwks)}
    try:
        with caplog.at_level(logging.INFO, logger="oauth_login"):
            doc = _start(app, "google")
            _callback(app, doc["state"])
    finally:
        FakeProviderHTTP.google_token_doc = None
    blob = "\n".join(r.getMessage() for r in caplog.records)
    assert "test-google-secret" not in blob
    assert _google_id_token(jwks) not in blob


def test_legacy_bearer_intact(monkeypatch):
    monkeypatch.setenv("GENIO_API_KEY", "k-secret")
    from genio_server.server import auth_tokens
    token, ttl = auth_tokens.mint_token()
    assert ttl == 900
    assert auth_tokens.verify_token(token) is True
    assert auth_tokens.verify_token(token + "x") is False


def test_frontend_bundle_has_no_secrets():
    import pathlib
    hits = []
    for p in (pathlib.Path("/data/ai_tools/genio/genio_client/src")
              .rglob("*.ts*")):
        if "test" in p.name or ".test." in p.name:
            continue
        txt = p.read_text(errors="replace")
        for pat in ("client_secret", "CLIENT_SECRET",
                    "gho_", "github_pat_"):
            if pat in txt:
                hits.append(f"{p.name}:{pat}")
        # "ya29." only as a token-PREFIX check (startsWith/includes) is
        # detection logic, not a secret; any other occurrence is a leak.
        for i, line in enumerate(txt.splitlines()):
            if "ya29." in line and "startsWith" not in line \
                    and "includes(" not in line:
                hits.append(f"{p.name}:{i + 1}:ya29.")
    assert not hits, f"secrets in frontend sources: {hits}"


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))


# --------------------------------------------------------------------------- #
# F1 follow-up: state bound to the starting browser (xsrf cookie)
# --------------------------------------------------------------------------- #
def test_callback_xsrf_missing_rejected(app):
    # Valid state+code but the browser cookie is gone (foreign browser):
    # refused BEFORE any provider call.
    import genio_server.server.oauth_login as _o
    doc = _start(app, "google")
    app.cookies.clear()
    r = _callback(app, doc["state"])
    assert r.status_code == 303
    assert "invalid_state" in r.headers["location"]
    assert _o._PENDING.get(doc["state"]) is None  # single-use consumed


def test_callback_xsrf_wrong_rejected(app):
    import genio_server.server.oauth_login as _o
    doc = _start(app, "google")
    app.cookies.clear()
    app.cookies.set("genio_oauth_xsrf", "x_forged")
    r = _callback(app, doc["state"])
    assert "invalid_state" in r.headers["location"]
    assert _o._PENDING.get(doc["state"]) is None


def test_cross_browser_replay_rejected(app, jwks):
    # Attacker copies code+state to a SECOND browser (no xsrf cookie):
    # refused; the burned single-use state then fails for the owner too
    # (safe failure — restart login, no bypass). _PENDING is module-level
    # so a fresh TestClient app models the foreign browser faithfully.
    from fastapi import FastAPI as _FastAPI
    from fastapi.testclient import TestClient as _TC
    import genio_server.server.oauth_login as _o
    doc = _start(app, "google")
    nonce = _o._PENDING[doc["state"]]["nonce"]
    FakeProviderHTTP.google_token_doc = {
        "id_token": _google_id_token(jwks, nonce=nonce)}
    try:
        foreign = _FastAPI()
        _o.register_oauth_routes(foreign)
        with _TC(foreign, base_url="http://testserver") as evil:
            # Same DB/singleton engine: share the pending via module state.
            r = evil.get("/api/v1/auth/oauth/callback",
                         params={"code": "c0de", "state": doc["state"]},
                         follow_redirects=False)
            assert "invalid_state" in r.headers["location"]
        # Owner retry with the burned state also fails (consumed, fail-closed).
        r2 = _callback(app, doc["state"])
        assert "invalid_state" in r2.headers["location"]
    finally:
        FakeProviderHTTP.google_token_doc = None


def test_state_expired_rejected(app):
    import time as _t
    import genio_server.server.oauth_login as _o
    doc = _start(app, "google")
    _o._PENDING[doc["state"]]["created"] = _t.time() - 700
    r = _callback(app, doc["state"])
    assert "invalid_state" in r.headers["location"]


# --------------------------------------------------------------------------- #
# F2 follow-up: GitHub PKCE binding + mismatch refusal
# --------------------------------------------------------------------------- #
def test_github_pkce_challenge_matches_verifier(app):
    import genio_server.server.oauth_login as _o
    from urllib.parse import urlparse, parse_qs
    doc = _start(app, "github")
    rec = _o._PENDING.get(doc["state"])
    assert rec is not None and rec.get("verifier")
    q = parse_qs(urlparse(doc["auth_url"]).query)
    assert q.get("code_challenge_method") == ["S256"]
    assert q.get("code_challenge") == [_o._code_challenge(rec["verifier"])]


def test_github_verifier_sent_and_mismatch_refused(app):
    # The mock token endpoint validates PKCE like a real provider: it
    # recomputes S256(received verifier) against the challenge issued at
    # /start. A tampered verifier is refused end-to-end.
    import genio_server.server.oauth_login as _o
    from urllib.parse import urlparse, parse_qs
    doc = _start(app, "github")
    rec = _o._PENDING.get(doc["state"])
    challenge = parse_qs(urlparse(doc["auth_url"]).query)["code_challenge"][0]

    seen = {}

    class PkceValidatingAsync(FakeProviderHTTP):
        async def post(self, url, data=None, headers=None):
            if "github.com/login" in url:
                seen.update(data or {})
                import hashlib as _hl
                import base64 as _b64
                got = _b64.urlsafe_b64encode(
                    _hl.sha256((data or {}).get("code_verifier",
                                                "").encode()).digest()
                ).rstrip(b"=").decode()
                if got != challenge:
                    return FakeResp(400, {"error": "bad_verifier"})
                return FakeResp(200, {"access_token": "gh_tok"})
            return await super().post(url, data, headers)

    _o.httpx = type("NS", (), {"AsyncClient": PkceValidatingAsync})()
    FakeProviderHTTP.github_token_doc = {"access_token": "gh_tok"}
    FakeProviderHTTP.github_user_doc = {"id": 7, "login": "octo"}
    FakeProviderHTTP.github_emails_doc = []
    try:
        # 1) Honest flow: verifier matches → login ok.
        r = _callback(app, doc["state"])
        assert "login=ok" in r.headers["location"], r.headers
        assert seen.get("code_verifier") == rec["verifier"]
        # 2) Tampered verifier → provider 400 → identity_failed.
        doc2 = _start(app, "github")
        _o._PENDING[doc2["state"]]["verifier"] = "tampered-verifier"
        # NOTE: challenge stays the original; exchange sends tampered.
        r2 = _callback(app, doc2["state"])
        assert "identity_failed" in r2.headers["location"], r2.headers
    finally:
        import httpx as _real_httpx
        _o.httpx = _real_httpx
        FakeProviderHTTP.github_token_doc = None
        FakeProviderHTTP.github_user_doc = None
        FakeProviderHTTP.github_emails_doc = None


# --------------------------------------------------------------------------- #
# F3 follow-up: slow JWKS never blocks the event loop (deterministic)
# --------------------------------------------------------------------------- #
def test_slow_jwks_does_not_block_loop(app, jwks, monkeypatch):
    # The sync JWKS fetch blocks on an event; a control coroutine must
    # still advance on the loop BEFORE we release the fetch. No sleeps,
    # no timing thresholds — pure ordering.
    import asyncio as _aio
    import threading as _th
    import genio_server.server.oauth_login as _o
    gate = _th.Event()
    calls = {"n": 0}

    class BlockingSyncClient:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url, **kw):
            calls["n"] += 1
            assert gate.wait(timeout=30), "test gate stuck"
            return FakeResp(200, {"keys": []})

    async def _run():
        return await _o._exchange_google(
            "c0de", {"verifier": "v", "nonce": "n_ctrl",
                     "redirect_uri": "http://testserver/api/v1/auth/oauth/callback"})

    async def _main():
        # Force a cache miss so the blocking fetch path is taken.
        monkeypatch.setattr(_o, "_JWKS_CACHE", (0.0, {}))
        task = _aio.create_task(_run())
        await _aio.sleep(0)  # let the task reach the blocking fetch
        progressed = []

        async def _control():
            for _ in range(50):
                await _aio.sleep(0)
            progressed.append(True)

        await _control()
        # Control finished while exchange is still gated on JWKS: the
        # loop was never blocked.
        assert progressed == [True]
        assert not task.done()
        gate.set()
        try:
            await task
            outcome = "completed"
        except Exception as exc:
            outcome = f"{type(exc).__name__}"
        return outcome

    # Module-level httpx stub: async path fakes the token endpoint,
    # sync path blocks deterministically.
    class DualStub:
        AsyncClient = FakeProviderHTTP

        def Client(self, *a, **kw):
            return BlockingSyncClient()

    # A structurally valid token with an UNKNOWN kid: parsing succeeds so
    # execution reaches the (blocking) JWKS fetch, which then fail-closes
    # on the empty key set. This exercises the real slow path.
    import jwt as _pyjwt
    import time as _time2
    now2 = int(_time2.time())
    bad_kid_token = _pyjwt.encode(
        {"iss": "https://accounts.google.com", "aud": "x",
         "sub": "s", "exp": now2 + 600, "iat": now2 - 10, "nonce": "n_ctrl"},
        jwks, algorithm="RS256", headers={"kid": "nope-kid"})
    # NOTE: _jwks_keys instantiates httpx.Client(...) — patch the name.
    real_httpx = _o.httpx
    _o.httpx = DualStub()
    FakeProviderHTTP.google_token_doc = {"id_token": bad_kid_token}
    try:
        outcome = _aio.run(_main())
    finally:
        _o.httpx = real_httpx
        FakeProviderHTTP.google_token_doc = None
    # Empty JWKS → unknown signing key (fail-closed), but only AFTER the
    # loop-freedom proof above.
    assert outcome == "ValueError", outcome
    assert calls["n"] == 1, "exactly one refresh (lock serializes)"


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))


# --------------------------------------------------------------------------- #
# XSRF hygiene follow-up: deletion header on EVERY callback exit
# --------------------------------------------------------------------------- #
def _set_cookies(resp):
    try:
        return resp.headers.get_list("set-cookie")
    except Exception:
        return [v for k, v in resp.headers.raw
                if k.lower() == b"set-cookie" for v in [v.decode()]]


def _xsrf_deletion(headers):
    deletions = [h for h in headers
                 if h.startswith("genio_oauth_xsrf=")
                 and "Max-Age=0" in h and "Path=/api/v1/auth" in h]
    return deletions


def test_callback_clears_xsrf_on_success(app, jwks):
    doc = _start(app, "google")
    import genio_server.server.oauth_login as _o
    FakeProviderHTTP.google_token_doc = {
        "id_token": _google_token_for(jwks, doc["state"])}
    try:
        r = _callback(app, doc["state"])
        assert r.status_code == 303 and "login=ok" in r.headers["location"]
        headers = _set_cookies(r)
        # XSRF deletion present with matching attributes…
        assert _xsrf_deletion(headers), headers
        # …and the session cookie is alive, NOT deleted.
        sess = [h for h in headers if h.startswith("genio_session=")]
        assert len(sess) == 1, headers
        assert "Max-Age=0" not in sess[0]
    finally:
        FakeProviderHTTP.google_token_doc = None


def test_callback_clears_xsrf_on_failures(app, jwks):
    import genio_server.server.oauth_login as _o
    # 1) Unknown/expired state.
    r1 = _callback(app, "st_nope")
    assert _xsrf_deletion(_set_cookies(r1)), "bad-state must clear xsrf"
    # 2) XSRF mismatch (foreign browser cookie). Same Path as the real
    # cookie so the jar holds exactly one entry (like a real browser).
    doc = _start(app, "google")
    app.cookies.clear()
    app.cookies.set("genio_oauth_xsrf", "x_forged",
                    path="/api/v1/auth")
    r2 = _callback(app, doc["state"])
    assert "invalid_state" in r2.headers["location"]
    assert _xsrf_deletion(_set_cookies(r2)), "mismatch must clear xsrf"
    # 3) Exchange failure (valid handshake, bad provider answer).
    app.cookies.clear()  # drop the forged entry; _start sets the valid one
    doc3 = _start(app, "google")
    FakeProviderHTTP.google_token_doc = None  # → 400 bad_grant
    r3 = _callback(app, doc3["state"])
    assert "identity_failed" in r3.headers["location"]
    assert _xsrf_deletion(_set_cookies(r3)), "exchange-fail must clear xsrf"


def test_xsrf_deletion_attributes_match_setter(app):
    # Deletion must mirror the setter (Path + SameSite + conditional
    # Secure) or browsers ignore it; Path must NOT be widened, and the
    # session cookie must never be the deleted one.
    doc = _start(app, "google")
    r = _callback(app, doc["state"])  # no token doc → identity_failed path
    assert "identity_failed" in r.headers["location"]
    headers = _set_cookies(r)
    deletions = _xsrf_deletion(headers)
    assert len(deletions) == 1, headers
    low = deletions[0].lower()
    assert "samesite=lax" in low, deletions[0]
    assert "path=/api/v1/auth" in low, deletions[0]
    # The session cookie is never the deleted one (absent here anyway).
    assert not any(h.startswith("genio_session=") for h in headers), headers
