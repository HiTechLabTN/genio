# Genio OAuth setup — Google + GitHub (operator action required)

Backend code is complete and tested (mocked providers). Real external
login needs OAuth apps the OPERATOR creates in Google/GitHub consoles.
No credentials exist yet — nothing here is a secret, only placeholders.

## 1. Environment variables (backend)

```bash
# Google (Cloud Console → APIs & Services → Credentials → OAuth client ID,
# type "Web application")
GENIO_GOOGLE_CLIENT_ID=1234567890-abcdefghijklmnopqrstuvwxyz.apps.googleusercontent.com
GENIO_GOOGLE_CLIENT_SECRET=GOCSPX-xxxxxxxxxxxxxxxxxxxxxxxx

# GitHub (Settings → Developer settings → OAuth Apps → New OAuth App)
GENIO_GITHUB_CLIENT_ID=Ov23xxxxxxxxxxxxxxxxxx
GENIO_GITHUB_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Public base URL of THIS deployment (callback + post-login redirects
# derive from it — single exact value, never request input)
GENIO_OAUTH_REDIRECT_BASE=http://localhost:8098        # dev (vite preview)
# GENIO_OAUTH_REDIRECT_BASE=https://genio.hitechlab.tn  # prod example

# Login sessions (default 7 days, seconds)
GENIO_SESSION_TTL=604800
```

After setting: `sudo systemctl restart genio.service`.

## 2. Authorized redirect URIs to register (EXACT match at providers)

```
http://localhost:8098/api/v1/auth/oauth/callback        # dev
https://genio.hitechlab.tn/api/v1/auth/oauth/callback   # prod example
```

One callback serves both providers (provider is bound server-side to
the `state`, never taken from the request).

## 3. Google Cloud Console checklist

- OAuth consent screen: External (or Internal for Workspace), scopes
  `openid`, `email`, `profile`. No sensitive/restricted scopes needed
  (publish NOT required for `.../auth/generative-language.tuning`;
  that scope is requested by the SEPARATE optional Gemini passthrough,
  not by this login).
- Credentials → Create OAuth client ID → Web application → Authorized
  redirect URIs += the URI from §2.
- The backend verifies ID tokens locally (RS256/JWKS, iss/aud/exp/nonce).

## 4. GitHub checklist

- OAuth App → Homepage URL = frontend base; Authorization callback URL
  = the URI from §2. No webhook, no permissions beyond `read:user` +
  `user:email` (requested at runtime, nothing stored).
- Identity = numeric GitHub id; hidden emails stay unverified/None.

## 5. What is deliberately NOT stored

Access/refresh tokens (used once for identity lookup, then dropped),
client secrets (env only, never frontend/git/logs), raw session tokens
(DB holds SHA-256 only). `sessions.db` gains `users`, `login_sessions`,
`session_owners` tables (CREATE IF NOT EXISTS — existing data untouched).
