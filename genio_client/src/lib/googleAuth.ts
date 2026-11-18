/**
 * Legacy Google token helpers — Gemini passthrough ONLY.
 *
 * These helpers expose a token stored by Google Identity Services when
 * the operator uses it directly. They NEVER create mock tokens: without
 * a real GIS credential there is simply no token (null), and the
 * backend-driven session login (lib/session.ts) is the supported path.
 */
import { signOutSession } from "./session";

export interface GoogleProfile {
  name?: string;
  email?: string;
  picture?: string;
  sub?: string;
}

const TOKEN_KEY = "genio:google:oauth:token";
const PROFILE_KEY = "genio:google:profile";

export function getGoogleToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function hasGoogleAuth(): boolean {
  return !!getGoogleToken();
}

export function getGoogleProfile(): GoogleProfile | null {
  try {
    const raw = localStorage.getItem(PROFILE_KEY);
    return raw ? (JSON.parse(raw) as GoogleProfile) : null;
  } catch {
    return null;
  }
}

export function setGoogleToken(token: string, profile?: GoogleProfile): void {
  try {
    localStorage.setItem(TOKEN_KEY, token);
    if (profile) localStorage.setItem(PROFILE_KEY, JSON.stringify(profile));
  } catch {}
}

export function clearGoogleToken(): void {
  try {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(PROFILE_KEY);
  } catch {}
  void signOutSession();
}

export interface SignInOptions {
  clientId?: string;
}

/**
 * Legacy GIS entrypoint kept for API compatibility. Real login goes
 * through beginOAuthLogin() (backend-verified). This throws instead of
 * minting mock tokens.
 */
export async function signInWithGoogle(): Promise<string> {
  throw new Error(
    "google_mock_disabled: use the backend login flow (session.ts)",
  );
}

export async function signOutGoogle(): Promise<void> {
  clearGoogleToken();
  try {
    const gsi = (window as unknown as { google?: { accounts: { id: { disableAutoSelect: ()=>void } } } }).google;
    gsi?.accounts?.id?.disableAutoSelect();
  } catch {}
}
