export interface UpdateInfo {
  version: string;
  notes?: string;
}

const OWNER = "HiTechLabTN";
const REPO = "genio";

async function currentVersion(): Promise<string> {
  try {
    const api = (await import("@tauri-apps/api/app")).getVersion;
    const v = await api();
    return v;
  } catch {
    return "0.1.0";
  }
}

/**
 * Check for a newer release. Prefers the Tauri v2 updater plugin (native,
 * signature-verified) when running inside the Tauri shell; otherwise falls
 * back to the public GitHub releases API.
 */
export async function checkForUpdates(): Promise<UpdateInfo | null> {
  try {
    const current = await currentVersion();

    // 1) Native updater plugin path (works inside the packaged app)
    try {
      const { check } = await import("@tauri-apps/plugin-updater");
      const update = await check();
      if (update) {
        return { version: update.version, notes: update.body ?? undefined };
      }
      return null;
    } catch {
      /* plugin not available in dev/browser — fall through to GitHub API */
    }

    // 2) GitHub releases fallback (web / dev preview)
    try {
      const res = await fetch(`https://api.github.com/repos/${OWNER}/${REPO}/releases/latest`, {
        headers: { Accept: "application/vnd.github+json" },
      });
      if (!res.ok) return null;
      const rel = (await res.json()) as { tag_name?: string; body?: string };
      const tag = rel.tag_name ?? "";
      const ver = tag.replace(/^v|^app-v/, "").replace(/^app-/, "");
      if (ver && isNewer(ver, current)) {
        return { version: ver, notes: rel.body };
      }
    } catch {
      /* offline or rate-limited — ignore */
    }
    return null;
  } catch {
    return null;
  }
}

/** Compare dotted semver strings. */
export function isNewer(candidate: string, base: string): boolean {
  const c = candidate.split(".").map((n) => parseInt(n, 10) || 0);
  const b = base.split(".").map((n) => parseInt(n, 10) || 0);
  for (let i = 0; i < Math.max(c.length, b.length); i++) {
    const cv = c[i] ?? 0;
    const bv = b[i] ?? 0;
    if (cv > bv) return true;
    if (cv < bv) return false;
  }
  return false;
}
