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

// ---------------------------------------------------------------------------
// Platform helpers - Tauri Android detection via os.platform()
// ---------------------------------------------------------------------------

async function isAndroidPlatform(): Promise<boolean> {
  // Spec requires os.platform() === 'android' via @tauri-apps/plugin-os
  try {
    const { platform } = await import("@tauri-apps/plugin-os");
    const p = await platform();
    return p === "android";
  } catch {
    // Fallback to UA for web/dev preview
    if (typeof navigator === "undefined") return false;
    const ua = navigator.userAgent || "";
    // @ts-ignore
    const plat = (navigator as any).userAgentData?.platform || "";
    return /android/i.test(ua) || /android/i.test(plat);
  }
}

function isAndroidSync(): boolean {
  if (typeof navigator === "undefined") return false;
  const ua = navigator.userAgent || "";
  // @ts-ignore
  const plat = (navigator as any).userAgentData?.platform || "";
  return /android/i.test(ua) || /android/i.test(plat);
}

function isElectron(): boolean {
  return typeof window !== "undefined" && !!(window as unknown as { process?: { versions?: { electron?: string } } }).process?.versions?.electron;
}

/**
 * Check for a newer release. Prefers the Tauri v2 updater plugin (native,
 * signature-verified) when running inside the Tauri shell; otherwise falls
 * back to the public GitHub releases API.
 *
 * Android: bypass Tauri updater (no auto-update for APK via updater artifacts)
 * and directly query GitHub for .apk asset; this ensures os.platform() === 'android'
 * path is taken early and avoids false negatives in the update modal.
 */
export async function checkForUpdates(): Promise<UpdateInfo | null> {
  try {
    const current = await currentVersion();

    // Android-specific: directly check GitHub for APK, bypass desktop updater
    try {
      const isAndroid = await isAndroidPlatform();
      if (isAndroid) {
        // Direct GitHub check for Android APK version without invoking desktop updater
        const res = await fetch(`https://api.github.com/repos/${OWNER}/${REPO}/releases/latest`, {
          headers: { Accept: "application/vnd.github+json" },
        });
        if (res.ok) {
          const rel = (await res.json()) as { tag_name?: string; body?: string };
          const tag = rel.tag_name ?? "";
          const ver = tag.replace(/^v|^app-v/, "").replace(/^app-/, "");
          if (ver && isNewer(ver, current)) {
            return { version: ver, notes: rel.body };
          }
        }
        // Fall through to desktop check if fetch failed
      }
    } catch {
      // ignore android check errors, continue to desktop flow
    }

    // 1) Native updater plugin path (works inside the packaged desktop app)
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

    // 2) GitHub releases fallback (web / dev preview / Android direct)
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

// ---------------------------------------------------------------------------
// APK / Desktop URL resolvers
// ---------------------------------------------------------------------------

/**
 * Resolve the direct APK download URL from GitHub releases.
 * Prefers the `Genio.apk` / `.apk` asset on the latest release,
 * falling back to a version-specific tag if `version` is given.
 */
async function getApkDownloadUrl(version?: string): Promise<string | null> {
  const endpoints = version
    ? [
        `https://api.github.com/repos/${OWNER}/${REPO}/releases/tags/v${version}`,
        `https://api.github.com/repos/${OWNER}/${REPO}/releases/tags/genio-android-v${version}`,
        `https://api.github.com/repos/${OWNER}/${REPO}/releases/latest`,
      ]
    : [`https://api.github.com/repos/${OWNER}/${REPO}/releases/latest`];

  for (const url of endpoints) {
    try {
      const res = await fetch(url, { headers: { Accept: "application/vnd.github+json" } });
      if (!res.ok) continue;
      const rel = (await res.json()) as { assets?: Array<{ name: string; browser_download_url: string }> };
      const assets = rel.assets || [];
      // Prefer exact match Genio.apk, then any .apk
      const apk =
        assets.find((a) => a.name === "Genio.apk") ||
        assets.find((a) => a.name.toLowerCase().endsWith(".apk")) ||
        assets.find((a) => a.name === "app-debug.apk") ||
        assets.find((a) => a.name === "app-release.apk");
      if (apk?.browser_download_url) return apk.browser_download_url;
    } catch {
      continue;
    }
  }
  return null;
}

/**
 * Resolve desktop asset URLs (EXE for Windows, DEB for Linux).
 */
async function getDesktopDownloadUrl(version?: string): Promise<{ exe?: string; deb?: string } | null> {
  const endpoints = version
    ? [
        `https://api.github.com/repos/${OWNER}/${REPO}/releases/tags/v${version}`,
        `https://api.github.com/repos/${OWNER}/${REPO}/releases/latest`,
      ]
    : [`https://api.github.com/repos/${OWNER}/${REPO}/releases/latest`];
  for (const url of endpoints) {
    try {
      const res = await fetch(url, { headers: { Accept: "application/vnd.github+json" } });
      if (!res.ok) continue;
      const rel = (await res.json()) as { assets?: Array<{ name: string; browser_download_url: string }> };
      const assets = rel.assets || [];
      const exe = assets.find((a) => a.name.toLowerCase().endsWith(".exe"))?.browser_download_url;
      const deb = assets.find((a) => a.name.toLowerCase().endsWith(".deb"))?.browser_download_url;
      if (exe || deb) return { exe, deb };
    } catch {
      continue;
    }
  }
  return null;
}

// ---------------------------------------------------------------------------
// Android-specific: shell open + upload download
// ---------------------------------------------------------------------------

/**
 * Android 8+ restriction: programmatic background installation is blocked.
 * The system requires REQUEST_INSTALL_PACKAGES + user confirmation via
 * PackageInstaller Intent (ACTION_VIEW, application/vnd.android.package-archive).
 * This helper gracefully handles the restriction by never attempting silent
 * install; instead it either:
 *  (a) opens the APK URL in the default browser (user-initiated download), or
 *  (b) downloads to cache via tauri-plugin-upload then triggers Intent.
 * Both paths require user to tap "Install" in the system prompt.
 */
async function openApkInBrowserViaShell(apkUrl: string): Promise<boolean> {
  // Spec #1: when os.platform() === 'android', use @tauri-apps/plugin-shell open()
  try {
    // Dynamic import to keep web bundle clean; shell plugin is configured in lib.rs + capabilities
    const { open } = await import("@tauri-apps/plugin-shell");
    // open() on Android delegates to Intent.ACTION_VIEW with the URL, launching default browser
    await open(apkUrl);
    console.log("[updater] Android: opened APK URL in default browser via shell open()", apkUrl);
    return true;
  } catch (e) {
    console.warn("[updater] shell open() failed, fallback to window.open", e);
    try {
      window.open(apkUrl, "_blank");
      return true;
    } catch {
      return false;
    }
  }
}

/**
 * Android alternative: custom download via tauri-plugin-upload to local cache,
 * then trigger Android Intent to prompt package installation.
 *
 * Uses:
 *  - @tauri-apps/plugin-upload download(url, filePath, progressHandler)
 *  - @tauri-apps/api/path cacheDir() + join() to resolve cache path
 *  - @tauri-apps/plugin-shell open(filePath) to fire Intent
 *
 * Handles Android restriction gracefully: if download succeeds but Intent
 * is blocked (e.g., REQUEST_INSTALL_PACKAGES not granted or background
 * install restricted), it falls back to opening the URL in browser and
 * surfaces a user-friendly message. The caller can then show a toast
 * explaining that installation requires user confirmation.
 */
async function downloadApkViaUploadAndTriggerIntent(
  apkUrl: string,
  onProgress?: (downloaded: number, total: number) => void,
): Promise<boolean> {
  try {
    // Resolve cache path: e.g., /data/data/<pkg>/cache/genio-update.apk
    let apkPath: string;
    try {
      const { cacheDir, join } = await import("@tauri-apps/api/path");
      const cache = await cacheDir();
      apkPath = await join(cache, "genio-update.apk");
    } catch {
      // Fallback for web preview: use temp name
      apkPath = "genio-update.apk";
    }

    // Use tauri-plugin-upload to fetch APK to local cache with progress
    // download(url, filePath, progressHandler, headers)
    const { download } = await import("@tauri-apps/plugin-upload");
    console.log("[updater] Android: starting upload-plugin download", apkUrl, "->", apkPath);
    await download(
      apkUrl,
      apkPath,
      (progress) => {
        // progress: { progress, progressTotal, total, transferSpeed }
        const p = progress as unknown as { progress: number; progressTotal: number; total: number };
        if (p.total > 0) onProgress?.(p.progress, p.total);
        else if (p.progressTotal > 0) onProgress?.(p.progress, p.progressTotal);
      },
    );
    console.log("[updater] Android: APK downloaded to cache", apkPath);

    // Now trigger Android Intent to prompt installation.
    // On Android, shell open() on a file:// path with .apk extension is
    // translated to an Intent with mime application/vnd.android.package-archive
    // via FileProvider (authorities="${applicationId}.fileprovider").
    // Requires: REQUEST_INSTALL_PACKAGES, FileProvider in AndroidManifest.xml
    try {
      const { open } = await import("@tauri-apps/plugin-shell");
      await open(apkPath);
      console.log("[updater] Android: triggered Intent via shell open()", apkPath);
      return true;
    } catch (e) {
      console.warn("[updater] shell open(file) failed, trying opener plugin", e);
      // Fallback: try opener plugin which also handles FileProvider
      try {
        const { openPath, openUrl } = await import("@tauri-apps/plugin-opener");
        // Try openPath first (file), then openUrl
        try {
          // @ts-ignore
          await openPath(apkPath);
          return true;
        } catch {
          await openUrl(`file://${apkPath}`);
          return true;
        }
      } catch {
        // Last resort: open the remote URL in browser (user will download manually)
        console.warn("[updater] Intent blocked by Android restriction (REQUEST_INSTALL_PACKAGES / background install), falling back to browser");
        return await openApkInBrowserViaShell(apkUrl);
      }
    }
  } catch (e) {
    console.warn("[updater] upload download failed", e);
    return false;
  }
}

// ---------------------------------------------------------------------------
// Generic Android download via fetch + fs (existing, kept as fallback)
// ---------------------------------------------------------------------------

/**
 * Download an APK to local storage and trigger the native Android package
 * installer. This covers both Tauri Android (via opener / FileProvider) and
 * Capacitor/Cordova WebView contexts.
 *
 * Required permissions (added to AndroidManifest.xml):
 * - android.permission.INTERNET
 * - android.permission.WRITE_EXTERNAL_STORAGE (legacy, maxSdk 29)
 * - android.permission.REQUEST_INSTALL_PACKAGES (needed to launch installer)
 * - android.permission.ACCESS_NETWORK_STATE
 *
 * FileProvider is configured in AndroidManifest.xml:
 *   <provider android:name="androidx.core.content.FileProvider"
 *             android:authorities="${applicationId}.fileprovider" ...>
 */
async function downloadAndInstallApk(
  apkUrl: string,
  onProgress?: (downloaded: number, total: number) => void,
): Promise<boolean> {
  try {
    const res = await fetch(apkUrl);
    if (!res.ok) throw new Error(`APK fetch failed: ${res.status}`);
    const total = parseInt(res.headers.get("content-length") || "0", 10);

    // Stream download with progress
    let downloaded = 0;
    let chunks: Uint8Array[] = [];
    if (res.body && typeof res.body.getReader === "function") {
      const reader = res.body.getReader();
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        if (value) {
          chunks.push(value);
          downloaded += value.length;
          if (total > 0) onProgress?.(downloaded, total);
        }
      }
    } else {
      // Fallback non-streaming
      const blob = await res.blob();
      const buf = await blob.arrayBuffer();
      chunks = [new Uint8Array(buf)];
      downloaded = chunks[0].length;
      if (total > 0) onProgress?.(downloaded, total);
    }

    const totalLen = chunks.reduce((a, c) => a + c.length, 0);
    const merged = new Uint8Array(totalLen);
    let offset = 0;
    for (const c of chunks) {
      merged.set(c, offset);
      offset += c.length;
    }

    // 1) Try Tauri FS + Opener (native path with FileProvider)
    try {
      const fs = await import("@tauri-apps/plugin-fs");
      // @ts-ignore - plugin-fs may expose writeFile / BaseDirectory differently
      const { writeFile, BaseDirectory } = fs as unknown as {
        writeFile: (file: { path: string; contents: Uint8Array }, opts: { baseDir: number }) => Promise<void>;
        BaseDirectory: { Cache: number; Download: number; External: number };
      };
      const baseDir = (BaseDirectory?.Cache ?? BaseDirectory?.Download ?? 0) as number;
      await writeFile({ path: "genio-update.apk", contents: merged }, { baseDir });
      // Trigger native package installer via opener (Android FileProvider intent)
      try {
        const { openPath } = await import("@tauri-apps/plugin-opener");
        // On Android, opener will fire ACTION_VIEW with application/vnd.android.package-archive
        await (openPath as unknown as (p: string) => Promise<void>)("genio-update.apk");
        return true;
      } catch {
        // Fallback: use shell to fire intent explicitly
        try {
          const { open } = await import("@tauri-apps/plugin-shell");
          // Requires tauri-plugin-shell permission
          await open("genio-update.apk");
          return true;
        } catch {
          // continue to blob fallback
        }
      }
    } catch {
      // plugin-fs not available — continue to capacitor / blob fallback
    }

    // 2) Try Capacitor Filesystem (if present)
    try {
      const capFs = await import("@capacitor/filesystem");
      const { Filesystem, Directory } = capFs as unknown as {
        Filesystem: { writeFile: (opts: { path: string; data: string; directory: number }) => Promise<{ uri: string }> };
        Directory: { Cache: number; Documents: number; ExternalStorage: number };
      };
      // Convert to base64 for Capacitor
      let binary = "";
      const chunkSize = 0x8000;
      for (let i = 0; i < merged.length; i += chunkSize) {
        const chunk = merged.subarray(i, i + chunkSize);
        binary += String.fromCharCode(...chunk);
      }
      const base64 = btoa(binary);
      const result = await Filesystem.writeFile({
        path: "genio-update.apk",
        data: base64,
        directory: Directory.Cache,
      });
      // Capacitor can open via AppLauncher or Browser; try opener
      try {
        const { openUrl } = await import("@tauri-apps/plugin-opener");
        await openUrl(result.uri);
      } catch {
        window.location.href = result.uri;
      }
      return true;
    } catch {
      // not a Capacitor context
    }

    // 3) Pure WebView fallback: blob URL + intent system install
    const blob = new Blob([merged], { type: "application/vnd.android.package-archive" });
    const blobUrl = URL.createObjectURL(blob);

    // Save to local storage via anchor download (triggers WRITE_EXTERNAL_STORAGE path)
    try {
      const a = document.createElement("a");
      a.href = blobUrl;
      a.download = "Genio.apk";
      document.body.appendChild(a);
      a.click();
      a.remove();
    } catch {
      // ignore
    }

    // Attempt to launch native package installer via intent URI.
    // This uses REQUEST_INSTALL_PACKAGES permission and FileProvider.
    // Intent: action=android.intent.action.VIEW type=application/vnd.android.package-archive
    try {
      // Try Tauri opener with blob url
      const { openUrl } = await import("@tauri-apps/plugin-opener");
      await openUrl(blobUrl);
      return true;
    } catch {
      // Web fallback: navigate to intent
      try {
        // For Chrome/Android WebView, this triggers package installer
        window.location.href = `intent:${blobUrl}#Intent;action=android.intent.action.VIEW;type=application/vnd.android.package-archive;end`;
        // Also open direct APK URL as backup (system download manager)
        setTimeout(() => window.open(apkUrl, "_blank"), 800);
        return true;
      } catch {
        window.open(apkUrl, "_blank");
        return true;
      }
    }
  } catch (e) {
    console.error("[updater] downloadAndInstallApk failed", e);
    return false;
  }
}

/**
 * Desktop fallback: download EXE/DEB and trigger install/restart.
 * For Electron, delegates to electron-updater via window.electronAPI if exposed;
 * otherwise downloads via anchor and prompts user.
 */
async function downloadAndInstallDesktop(
  onProgress?: (downloaded: number, total: number) => void,
): Promise<boolean> {
  try {
    // If running inside Electron with IPC exposed, delegate
    const elApi = (window as unknown as { electronAPI?: { checkForUpdate?: () => Promise<boolean>; downloadUpdate?: () => Promise<boolean> } })
      .electronAPI;
    if (elApi?.downloadUpdate) {
      return await elApi.downloadUpdate();
    }
    // Tauri fallback: try tauri process? No direct DEB/EXE install from web.
    // Instead, fetch desktop assets and trigger browser download.
    const current = await currentVersion();
    const urls = await getDesktopDownloadUrl(current);
    const isWin = navigator.platform?.toLowerCase().includes("win") || /windows/i.test(navigator.userAgent);
    const targetUrl = isWin ? urls?.exe : urls?.deb || urls?.exe;
    if (!targetUrl) return false;

    // Stream download with progress
    const res = await fetch(targetUrl);
    if (!res.ok) return false;
    const total = parseInt(res.headers.get("content-length") || "0", 10);
    let downloaded = 0;
    const reader = res.body?.getReader();
    let chunks: Uint8Array[] = [];
    if (reader) {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        if (value) {
          chunks.push(value);
          downloaded += value.length;
          if (total > 0) onProgress?.(downloaded, total);
        }
      }
    }
    if (chunks.length === 0) {
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = isWin ? `Genio Setup ${current}.exe` : `genio-client_${current}_amd64.deb`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      return true;
    }
    const totalLen = chunks.reduce((a, c) => a + c.length, 0);
    const merged = new Uint8Array(totalLen);
    let off = 0;
    for (const c of chunks) {
      merged.set(c, off);
      off += c.length;
    }
    const blob = new Blob([merged], { type: "application/octet-stream" });
    const blobUrl = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = blobUrl;
    a.download = isWin ? `Genio Setup ${current}.exe` : `genio-client_${current}_amd64.deb`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    // For Tauri desktop, relaunch after install would be handled by updater plugin
    return true;
  } catch {
    return false;
  }
}

/**
 * Download and install the available update.
 * Strategy:
 * 1) Android: when os.platform() === 'android', bypass Tauri updater UI and
 *    (a) try tauri-plugin-upload download to cache + Intent, then
 *    (b) fallback to @tauri-apps/plugin-shell open(apkUrl) in browser.
 *    Handles Android background-install restriction gracefully (requires
 *    REQUEST_INSTALL_PACKAGES + user tap on system installer).
 * 2) Tauri v2 updater plugin (signature-verified, supports EXE/DEB) — handles downloadAndInstall + relaunch.
 * 3) Generic Android fetch fallback (WRITE_EXTERNAL_STORAGE + FileProvider).
 * 4) Desktop Electron: delegate to electron-updater or direct download of EXE/DEB.
 * Returns false only when no installer is available (web preview).
 */
export async function installUpdate(onProgress?: (downloaded: number, total: number) => void): Promise<boolean> {
  // 0) Android-specific branch: bypass default Tauri updater UI
  // Spec: When os.platform() === 'android' and update detected, "Install & restart"
  // should use @tauri-apps/plugin-shell open() to open direct .apk URL.
  // Alternative: custom download via tauri-plugin-upload to cache + Intent.
  try {
    const isAndroid = await isAndroidPlatform();
    if (isAndroid) {
      const current = await currentVersion();
      const apkUrl = (await getApkDownloadUrl(current)) || (await getApkDownloadUrl());
      if (apkUrl) {
        // Option 2 (alternative): custom download logic using tauri-plugin-upload
        // Fetch APK to local cache, then trigger Android Intent.
        // This is attempted first as it provides offline install + progress.
        const uploadOk = await downloadApkViaUploadAndTriggerIntent(apkUrl, onProgress);
        if (uploadOk) return true;

        // Option 1 (spec): use shell open() to open direct .apk URL in default browser
        // This gracefully handles Android's restriction on programmatic background installs:
        // Instead of silent install (blocked), we delegate to the system's download
        // manager / browser, which then shows the standard "Do you want to install
        // this application? It does not require any special permissions." prompt
        // requiring explicit user consent (REQUEST_INSTALL_PACKAGES).
        const browserOk = await openApkInBrowserViaShell(apkUrl);
        if (browserOk) return true;

        // Fallback: generic fetch + FileProvider Intent (existing robust path)
        const ok = await downloadAndInstallApk(apkUrl, onProgress);
        if (ok) return true;
      }
      // If we reach here, Android but no APK URL found — fall through to desktop logic
      // which will return false and caller can show browser fallback message.
    }
  } catch (e) {
    console.warn("[updater] Android branch failed, falling through to desktop updater", e);
  }

  // 1) Try Tauri updater plugin (native, works for Tauri Windows EXE + Linux DEB + updater artifacts)
  // On Android this is skipped above; on desktop it handles downloadAndInstall + relaunch.
  try {
    const { check } = await import("@tauri-apps/plugin-updater");
    const { relaunch } = await import("@tauri-apps/plugin-process");
    const update = await check();
    if (update) {
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
    }
  } catch {
    // plugin not available — fall through to platform-specific fallback
  }

  // 2) Generic Android fetch fallback (if OS check missed, e.g., webview without plugin-os)
  if (isAndroidSync()) {
    const current = await currentVersion();
    const apkUrl = (await getApkDownloadUrl(current)) || (await getApkDownloadUrl());
    if (apkUrl) {
      const ok = await downloadAndInstallApk(apkUrl, onProgress);
      if (ok) return true;
    }
  }

  // 3) Desktop fallback (Electron EXE / DEB)
  try {
    const isDesktop = !isAndroidSync();
    if (isDesktop) {
      const ok = await downloadAndInstallDesktop(onProgress);
      if (ok) return true;
    }
  } catch {
    // ignore
  }

  // 4) Generic web fallback: open releases page is handled by caller,
  // but we also try to directly download APK/EXE as last chance before returning false.
  if (isElectron()) {
    try {
      const ok = await downloadAndInstallDesktop(onProgress);
      if (ok) return true;
    } catch {
      // ignore
    }
  }

  return false;
}

// Also export Android helpers for testing / direct use in UpdateModal
export { isAndroidPlatform, openApkInBrowserViaShell, downloadApkViaUploadAndTriggerIntent, getApkDownloadUrl };
