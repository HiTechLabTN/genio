"""OAuth login — Google (OIDC code flow) + GitHub (OAuth code flow).

Security contract (see task reqs 1-12):
- Identity is verified on the BACKEND only. The frontend never supplies
  names/emails/subs — it only transports the browser through provider
  pages and holds NO credential (no client secret anywhere near it).
- `state`: unpredictable, single-use, 10-min TTL, bound to provider +
  PKCE verifier + nonce + exact redirect URI. Replay/unknown/expired
  state → generic error, no login.
- Google: code exchanged server-side, then the ID token is verified
  locally (RS256 against Google JWKS, iss/aud/exp/nonce) — unverified
  claims are never accepted. No tokeninfo shortcut.
- GitHub: code exchanged server-side, identity from GET /user with the
  token; email from /user/emails (primary+verified ONLY — hidden mail
  stays None/unverified, never assumed verified).
- NO account linking by email: (provider, provider_sub) is the only
  identity key. Same email on both providers = two separate users.
- Sessions: opaque random tokens; only SHA-256 stored (user_store).
  Cookie HttpOnly + SameSite=Lax (+Secure on https/prod). Fresh token
  per login (no fixation), server-side revoke on logout/expiry.
- No access/refresh tokens stored anywhere; nothing secret is logged
  (provider + sub + truncated state at most — telemetry scrubs rest).
- Existing Bearer/API-key auth, TTLs, rate limits and the prod boot
  guard are untouched (this router only ADDS session-cookie auth).
- WS carries no credentials in query strings: browsers attach the
  session cookie automatically; see get_session_user_from_cookie() for
  the WS layer (Phase 4 wiring).
- OAuth failures never disable protection: every failure path returns
  an error (or redirects with a generic reason), never anonymous access.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import os
import secrets
import threading
import time
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlencode

import httpx
from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse

logger = logging.getLogger("oauth_login")

# NOTE: routes are plain functions registered via register_oauth_routes()
# (direct app.get/app.post, the same style as main.py) — deliberately NOT
# an APIRouter, so app.routes contains only plain Route objects (an
# existing test iterates app.routes expecting .path on every entry).
_ROUTES = []  # (method, path, handler) collected by @_route


def _route(method: str, path: str):
    def _deco(fn):
        _ROUTES.append((method, path, fn))
        return fn
    return _deco

GOOGLE_CLIENT_ID = os.getenv("GENIO_GOOGLE_CLIENT_ID", "").strip()
GOOGLE_CLIENT_SECRET = os.getenv("GENIO_GOOGLE_CLIENT_SECRET", "").strip()
GITHUB_CLIENT_ID = os.getenv("GENIO_GITHUB_CLIENT_ID", "").strip()
GITHUB_CLIENT_SECRET = os.getenv("GENIO_GITHUB_CLIENT_SECRET", "").strip()
# Public base of THIS deployment's frontend, e.g. http://localhost:8098
# (dev) or https://genio.hitechlab.tn (prod). Callbacks and post-login
# redirects derive from it — a single exact value, never request input.
OAUTH_BASE = os.getenv("GENIO_OAUTH_REDIRECT_BASE",
                       "http://localhost:8098").strip().rstrip("/")
SESSION_COOKIE = "genio_session"
# Short-lived XSRF cookie binding the handshake to the browser that
# started it (login-CSRF defense). Single cookie: concurrent logins to
# both providers resolve to the latest started (the older fails safe
# with invalid_state, user retries) — documented tradeoff.
XSRF_COOKIE = "genio_oauth_xsrf"
STATE_TTL_S = 600.0
_TIMEOUT = 20.0

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GITHUB_AUTH_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"
GITHUB_EMAILS_URL = "https://api.github.com/user/emails"

_JWKS_CACHE: Tuple[float, Dict[str, Any]] = (0.0, {})
# Serializes JWKS refreshes: on cache expiry, N concurrent logins must
# not fire N identical provider fetches (thundering herd) — and the fetch
# itself must never run on the event loop (see _exchange_google).
_JWKS_LOCK = threading.Lock()


# --------------------------------------------------------------------------- #
# Pending handshakes (short-lived, in-memory, single-use)
# --------------------------------------------------------------------------- #
_PENDING: Dict[str, Dict[str, Any]] = {}


def _purge_pending(now: Optional[float] = None) -> None:
    now = now if now is not None else time.time()
    dead = [k for k, v in _PENDING.items()
            if now - float(v.get("created", 0)) > STATE_TTL_S]
    for k in dead:
        _PENDING.pop(k, None)


def _callback_url() -> str:
    return f"{OAUTH_BASE}/api/v1/auth/oauth/callback"


def _b64url(data: bytes) -> str:
    import base64
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _new_state() -> Tuple[str, str, str, str]:
    state = "st_" + secrets.token_urlsafe(24)
    verifier = _b64url(secrets.token_bytes(32))
    nonce = "n_" + secrets.token_urlsafe(16)
    xsrf = "x_" + secrets.token_urlsafe(24)
    return state, verifier, nonce, xsrf


def _code_challenge(verifier: str) -> str:
    import base64
    import hashlib as _hl
    return base64.urlsafe_b64encode(
        _hl.sha256(verifier.encode()).digest()).rstrip(b"=").decode()


def _provider_configured(provider: str) -> bool:
    if provider == "google":
        return bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)
    if provider == "github":
        return bool(GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET)
    return False


def _secure_cookies() -> bool:
    return os.getenv("GENIO_ENV", "").strip().lower() == "prod" or \
        OAUTH_BASE.startswith("https://")


# --------------------------------------------------------------------------- #
# Helpers (no secrets in logs — provider + truncated state at most)
# --------------------------------------------------------------------------- #
def _log(action: str, provider: str = "", sub: str = "",
         state: str = "") -> None:
    tail = f" state={state[:10]}…" if state else ""
    subj = f" sub={sub[:12]}…" if sub else ""
    logger.info("oauth %s provider=%s%s%s", action, provider, subj, tail)


async def _consume_state(state: str) -> Optional[Dict[str, Any]]:
    _purge_pending()
    rec = _PENDING.pop(state, None)
    return rec


# --------------------------------------------------------------------------- #
# Google identity verification (local RS256 against Google JWKS)
# --------------------------------------------------------------------------- #
def _jwks_keys() -> Dict[str, Any]:
    global _JWKS_CACHE
    now = time.time()
    if now - _JWKS_CACHE[0] < 3600 and _JWKS_CACHE[1]:
        return _JWKS_CACHE[1]
    with _JWKS_LOCK:
        # Re-check under the lock: a sibling worker may have refreshed
        # while we waited (exactly-once refresh per expiry window).
        now = time.time()
        if now - _JWKS_CACHE[0] < 3600 and _JWKS_CACHE[1]:
            return _JWKS_CACHE[1]
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.get(GOOGLE_JWKS_URL)
            resp.raise_for_status()
            doc = resp.json()
        keys = {k.get("kid"): k for k in doc.get("keys", []) if k.get("kid")}
        _JWKS_CACHE = (now, keys)
        return keys


def verify_google_id_token(id_token: str, nonce: str) -> Dict[str, Any]:
    """Verify a Google ID token LOCALLY. Returns the claims on success.

    Checks: RS256 signature vs Google JWKS, iss, aud == our client_id,
    exp/iat windows, nonce match. Anything off → ValueError. No network
    except the (cached) JWKS fetch; the token itself is never sent
    anywhere for 'validation'.
    """
    import jwt as pyjwt
    header = pyjwt.get_unverified_header(id_token)
    if header.get("alg") != "RS256":
        raise ValueError(f"unexpected alg {header.get('alg')!r}")
    kid = header.get("kid")
    keys = _jwks_keys()
    jwk = keys.get(kid)
    if jwk is None:
        raise ValueError("unknown signing key")
    key = pyjwt.algorithms.RSAAlgorithm.from_jwk(jwk)
    claims = pyjwt.decode(
        id_token, key=key, algorithms=["RS256"],
        audience=GOOGLE_CLIENT_ID,
        issuer=["accounts.google.com", "https://accounts.google.com"],
        options={"require": ["exp", "iat", "iss", "aud", "sub"]},
        leeway=60)
    if claims.get("nonce") != nonce:
        raise ValueError("nonce mismatch (replay or foreign flow)")
    return claims


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@_route("GET", "/api/v1/auth/oauth/{provider}/start")
def oauth_start(provider: str) -> JSONResponse:
    provider = (provider or "").lower()
    if provider not in ("google", "github"):
        return JSONResponse({"ok": False, "error": "unknown_provider"},
                            status_code=404)
    if not _provider_configured(provider):
        return JSONResponse({"ok": False,
                             "error": "provider_not_configured"}, status_code=503)
    state, verifier, nonce, xsrf = _new_state()
    redirect_uri = _callback_url()
    _PENDING[state] = {"provider": provider, "verifier": verifier,
                       "nonce": nonce, "xsrf": xsrf,
                       "redirect_uri": redirect_uri,
                       "created": time.time()}
    _purge_pending()
    if provider == "google":
        params = {
            "client_id": GOOGLE_CLIENT_ID, "redirect_uri": redirect_uri,
            "response_type": "code", "scope": "openid email profile",
            "code_challenge": _code_challenge(verifier),
            "code_challenge_method": "S256",
            "state": state, "nonce": nonce,
            "access_type": "online", "prompt": "select_account",
        }
        url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"
    else:
        # GitHub supports PKCE (S256) for all client types: the verifier
        # created above travels hashed here and verbatim at exchange,
        # bound to this handshake record like Google's.
        params = {
            "client_id": GITHUB_CLIENT_ID, "redirect_uri": redirect_uri,
            "scope": "read:user user:email", "state": state,
            "code_challenge": _code_challenge(verifier),
            "code_challenge_method": "S256",
        }
        url = f"{GITHUB_AUTH_URL}?{urlencode(params)}"
    _log("start", provider, state=state)
    resp = JSONResponse({"ok": True, "auth_url": url, "state": state})
    # Bind this handshake to the starting browser: the callback must
    # present the same xsrf value (login-CSRF defense — the `state` URL
    # parameter alone travels through the provider and back, so it cannot
    # prove WHICH browser started the flow; this cookie can).
    resp.set_cookie(XSRF_COOKIE, xsrf, max_age=int(STATE_TTL_S),
                    httponly=True, samesite="lax",
                    secure=_secure_cookies(), path="/api/v1/auth")
    return resp


def _frontend_redirect(outcome: str, reason: str = "") -> RedirectResponse:
    dest = f"{OAUTH_BASE}/app?login={outcome}"
    if reason:
        dest += f"&reason={reason}"
    resp = RedirectResponse(dest, status_code=303)
    # Hygiene (review follow-up): every callback exit clears the XSRF
    # cookie — success and all six failure paths funnel through here, so
    # coverage is total by construction. Attributes MUST match the setter
    # (Path + SameSite + conditional Secure) or browsers ignore the
    # deletion. The session cookie (set separately on success) is never
    # touched, and the Path is not widened. An unexpected 500 escaping
    # this helper carries no redirect; its orphaned xsrf (if any) dies
    # with the consumed state + the 600s Max-Age.
    resp.delete_cookie(XSRF_COOKIE, path="/api/v1/auth", samesite="lax",
                       secure=_secure_cookies())
    return resp


async def _exchange_google(code: str, rec: Dict[str, Any]) -> Dict[str, Any]:
    data = {
        "client_id": GOOGLE_CLIENT_ID, "client_secret": GOOGLE_CLIENT_SECRET,
        "code": code, "code_verifier": rec["verifier"],
        "grant_type": "authorization_code",
        "redirect_uri": rec["redirect_uri"],
    }
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(GOOGLE_TOKEN_URL, data=data)
    if resp.status_code != 200:
        raise ValueError(f"token exchange failed ({resp.status_code})")
    doc = resp.json()
    id_token = doc.get("id_token")
    if not id_token:
        raise ValueError("no id_token in provider response")
    # NOTE: PyJWT verification (+ the JWKS fetch it may trigger) is
    # synchronous CPU/network work — run it in a worker thread so a slow
    # provider never blocks the event loop (WS telemetry, kill handling).
    # All checks (sig/iss/aud/exp/nonce/kid) are unchanged, inside the
    # same function.
    claims = await asyncio.to_thread(verify_google_id_token, id_token,
                                     rec["nonce"])
    return {"sub": str(claims["sub"]),
            "email": claims.get("email"),
            "email_verified": bool(claims.get("email_verified", False)),
            "name": claims.get("name"),
            "picture": claims.get("picture")}


async def _exchange_github(code: str, rec: Dict[str, Any]) -> Dict[str, Any]:
    data = {
        "client_id": GITHUB_CLIENT_ID, "client_secret": GITHUB_CLIENT_SECRET,
        "code": code, "redirect_uri": rec["redirect_uri"],
        "code_verifier": rec["verifier"],
    }
    headers = {"Accept": "application/json"}
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(GITHUB_TOKEN_URL, data=data, headers=headers)
    if resp.status_code != 200:
        raise ValueError(f"token exchange failed ({resp.status_code})")
    doc = resp.json()
    access = doc.get("access_token")
    if not access:
        raise ValueError("no access_token in provider response")
    # The provider access token authenticates THESE two calls only; it is
    # never stored, never logged, never returned.
    api_headers = {"Accept": "application/vnd.github+json",
                   "Authorization": f"Bearer {access}",
                   "X-GitHub-Api-Version": "2022-11-28"}
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        me = await client.get(GITHUB_USER_URL, headers=api_headers)
        if me.status_code != 200:
            raise ValueError(f"identity lookup failed ({me.status_code})")
        who = me.json()
        emails = await client.get(GITHUB_EMAILS_URL, headers=api_headers)
    email, verified = None, False
    if emails.status_code == 200:
        try:
            lst = emails.json() or []
            prim = next((e for e in lst
                         if isinstance(e, dict) and e.get("primary")), None)
            if prim and prim.get("email"):
                email, verified = prim["email"], bool(prim.get("verified"))
        except Exception:
            email, verified = None, False
    if not who.get("id"):
        raise ValueError("provider identity has no id")
    return {"sub": str(who["id"]),
            "email": email, "email_verified": verified,
            "name": who.get("name") or who.get("login"),
            "picture": who.get("avatar_url")}


@_route("GET", "/api/v1/auth/oauth/callback")
async def oauth_callback(request: Request, code: str = "",
                         state: str = "") -> RedirectResponse:
    # NOTE (F1 review): no Origin/Referer gate here — legitimate provider
    # callbacks legitimately arrive WITH a provider Referer in prod, so
    # such a gate rejects every real login while passing dev. CSRF defense
    # is: unpredictable single-use short-lived state + PKCE + the xsrf
    # browser-binding cookie below (+ SameSite=Lax transport).
    rec = await _consume_state(state or "")
    if rec is None:
        _log("callback-bad-state", state=state)
        return _frontend_redirect("error", "invalid_state")
    provider = rec.get("provider", "")
    # The state must have been started by THIS browser: compare the xsrf
    # cookie against the pending record (constant-time). A foreign browser
    # replaying a stolen code+state has no such cookie → refused.
    try:
        presented = (request.cookies.get(XSRF_COOKIE) or "").strip()
    except Exception:
        presented = ""
    expected = str(rec.get("xsrf") or "")
    if not expected or not presented or \
            not hmac.compare_digest(presented, expected):
        _log("callback-xsrf-mismatch", provider, state=state)
        return _frontend_redirect("error", "invalid_state")
    if not code:
        _log("callback-no-code", provider, state=state)
        return _frontend_redirect("error", "provider_error")
    try:
        if provider == "google":
            ident = await _exchange_google(code, rec)
        elif provider == "github":
            ident = await _exchange_github(code, rec)
        else:
            return _frontend_redirect("error", "unknown_provider")
    except Exception as exc:
        _log("callback-exchange-failed", provider, state=state)
        logger.debug("oauth exchange detail: %s",
                     type(exc).__name__)  # never token content
        return _frontend_redirect("error", "identity_failed")
    try:
        from genio_server.server.user_store import (
            get_user_store, SESSION_TTL_SECONDS)
        store = get_user_store()
        user = await store.get_or_create_user(
            provider, ident["sub"], email=ident.get("email"),
            email_verified=bool(ident.get("email_verified")),
            name=ident.get("name"), picture=ident.get("picture"))
        import secrets as _secrets
        raw = _secrets.token_urlsafe(32)
        await store.create_session(int(user["id"]), raw, SESSION_TTL_SECONDS)
    except Exception:
        logger.exception("oauth session creation failed")
        return _frontend_redirect("error", "session_failed")
    _log("login", provider, str(ident.get("sub") or "?"), state=state)
    resp = _frontend_redirect("ok")
    resp.set_cookie(SESSION_COOKIE, raw, max_age=int(SESSION_TTL_SECONDS),
                    httponly=True, samesite="lax",
                    secure=_secure_cookies(), path="/")
    return resp


def _session_token_from_request(request: Request) -> str:
    try:
        return (request.cookies.get(SESSION_COOKIE) or "").strip()
    except Exception:
        return ""


async def resolve_request_user(request: Request) -> Optional[Dict[str, Any]]:
    """Current logged-in user from the session cookie (None if anonymous).
    Shared helper for HTTP routes AND the WS layer (Phase 4)."""
    token = _session_token_from_request(request)
    if not token:
        return None
    try:
        from genio_server.server.user_store import get_user_store
        return await get_user_store().get_session_user(token)
    except Exception:
        return None


def get_session_user_from_cookie(cookie_header: str) -> str:
    """Extract the raw session token from a Cookie header value (sync,
    for the WS handshake path — validation stays async server-side)."""
    try:
        for part in (cookie_header or "").split(";"):
            name, _, value = part.partition("=")
            if name.strip() == SESSION_COOKIE and value.strip():
                return value.strip()
    except Exception:
        pass
    return ""


@_route("GET", "/api/v1/auth/me")
async def auth_me(request: Request) -> JSONResponse:
    user = await resolve_request_user(request)
    if user is None:
        return JSONResponse({"ok": False, "error": "anonymous"}, status_code=401)
    return JSONResponse({"ok": True, "user": {
        "id": user["id"], "provider": user["provider"],
        "email": user.get("email"),
        "email_verified": bool(user.get("email_verified")),
        "name": user.get("name"), "picture": user.get("picture"),
        "session_expires_at": user.get("session_expires_at")}})


@_route("POST", "/api/v1/auth/logout")
async def auth_logout(request: Request) -> JSONResponse:
    token = _session_token_from_request(request)
    if token:
        try:
            from genio_server.server.user_store import get_user_store
            await get_user_store().revoke_session(token)
        except Exception:
            pass
    _log("logout")
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(SESSION_COOKIE, path="/")
    return resp


# --------------------------------------------------------------------------- #
# Registration (plain app.get/app.post — see note at _ROUTES above)
# --------------------------------------------------------------------------- #
def register_oauth_routes(app) -> None:
    """Mount the four auth routes with plain decorators (no APIRouter)."""
    for method, path, fn in _ROUTES:
        if method == "GET":
            app.get(path)(fn)
        elif method == "POST":
            app.post(path)(fn)
        else:  # pragma: no cover
            raise ValueError(f"unsupported method {method}")
