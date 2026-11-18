/**
 * Backend-verified session (voice/identity mission).
 *
 * The browser holds NO credential: login state lives in an HttpOnly
 * session cookie set by the backend after a verified Google/GitHub
 * OAuth flow. This module only (a) starts the flow, (b) reads /me,
 * (c) logs out. Legacy GIS-token helpers stay for the optional Gemini
 * passthrough — they never create mock tokens anymore.
 */

export interface SessionUser {
  id: number;
  provider: string;
  email?: string | null;
  email_verified?: boolean;
  name?: string | null;
  picture?: string | null;
  session_expires_at?: number;
}

function apiBase(): string {
  // Same-origin in production; dev override for the vite preview setup.
  if (typeof window === "undefined") return "";
  const override = (window as unknown as { __GENIO_API_URL?: string })
    .__GENIO_API_URL;
  if (override) return override.replace(/\/$/, "");
  return "";
}

/** Begin login: ask the backend for the provider URL, then go there. */
export async function beginOAuthLogin(
  provider: "google" | "github",
): Promise<never> {
  const res = await fetch(`${apiBase()}/api/v1/auth/oauth/${provider}/start`, {
    credentials: "include",
  });
  if (!res.ok) {
    const doc = await res.json().catch(() => ({}));
    throw new Error(doc?.error || `login_unavailable_${res.status}`);
  }
  const doc = await res.json();
  if (!doc?.ok || !doc?.auth_url) throw new Error("login_unavailable");
  window.location.href = doc.auth_url as string;
  // Redirect leaves the page; this promise never resolves by design.
  await new Promise<never>(() => {});
  throw new Error("redirecting");
}

export async function fetchSession(): Promise<SessionUser | null> {
  try {
    const res = await fetch(`${apiBase()}/api/v1/auth/me`, {
      credentials: "include",
    });
    if (res.status === 401) return null;
    if (!res.ok) return null;
    const doc = await res.json();
    return doc?.ok && doc?.user ? (doc.user as SessionUser) : null;
  } catch {
    return null;
  }
}

export async function signOutSession(): Promise<void> {
  try {
    await fetch(`${apiBase()}/api/v1/auth/logout`, {
      method: "POST",
      credentials: "include",
    });
  } catch {
    /* offline logout still clears local state below */
  }
  try {
    localStorage.removeItem("genio:google:profile");
  } catch {
    /* ignore */
  }
}
