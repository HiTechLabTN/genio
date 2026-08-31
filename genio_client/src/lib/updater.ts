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

/**
 * Download and install the available update via the Tauri v2 updater plugin.
 * Calling this inside a packaged app triggers the native installer and restarts.
 * Returns false when the plugin isn't available (web/dev preview).
 */
export async function installUpdate(onProgress?: (downloaded: number, total: number) => void): Promise<boolean> {
  try {
    const { check } = await import("@tauri-apps/plugin-updater");
    const { relaunch } = await import("@tauri-apps/plugin-process");
    const update = await check();
    if (!update) return false;

    let downloaded = 0;
    let total = 0;
    await update.downloadAndInstall((event) => {
      if (event.event === "Started") {
        total = event.data.contentLength ?? 0;
      } else if (event.event === "Progress") {
        downloaded += event.data.chunkLength;
        if (total > 0) onProgress?.(downloaded, total);
      }
    });

    try {
      await relaunch();
    } catch {
      /* relaunch may fail on some platforms; the install is already done */
    }
    return true;
  } catch {
    return false;
  }
}
