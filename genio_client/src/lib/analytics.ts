// Lightweight analytics — no cookies, privacy friendly, Cloudflare compatible
export function trackPageView(path: string) {
  try {
    // Plausible-compatible or simple beacon
    if (typeof window !== "undefined" && (window as unknown as { plausible?: (e: string, o?: unknown) => void }).plausible) {
      (window as unknown as { plausible: (e: string, o?: unknown) => void }).plausible("pageview", { props: { path } });
    }
    // Fallback: send beacon to /api/v1/analytics if exists (fire-and-forget).
    // G4: no user-agent in body (HTTP layer already sees it; minimize payload).
    const data = JSON.stringify({ path, ts: Date.now() });
    if (navigator.sendBeacon) {
      try { navigator.sendBeacon("/api/v1/analytics", data); } catch { /* ignore */ }
    }
    // Console for dev
    if (import.meta.env.DEV) console.debug("[analytics] pageview", path);
  } catch { /* ignore */ }
}

export function trackEvent(name: string, props?: Record<string, unknown>) {
  try {
    if (typeof window !== "undefined" && (window as unknown as { plausible?: (e: string, o?: unknown) => void }).plausible) {
      (window as unknown as { plausible: (e: string) => void }).plausible(name);
    }
    if (import.meta.env.DEV) console.debug("[analytics] event", name, props);
  } catch { /* ignore */ }
}
