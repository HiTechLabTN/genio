import { motion } from "framer-motion";
import { Check, Download, Loader2, Rocket, X } from "lucide-react";
import { useEffect, useState } from "react";
import { installUpdate } from "../lib/updater";

interface Props {
  version: string;
  notes?: string;
  onClose: () => void;
}

type Phase = "idle" | "downloading" | "installing" | "done";

export default function UpdateModal({ version, notes, onClose }: Props) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [isAndroid, setIsAndroid] = useState(false);
  const [androidOpened, setAndroidOpened] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { platform } = await import("@tauri-apps/plugin-os");
        const p = await platform();
        if (!cancelled) setIsAndroid(p === "android");
      } catch {
        // Fallback to UA check for web preview
        if (!cancelled) {
          const ua = navigator.userAgent || "";
          // @ts-ignore
          const plat = (navigator as any).userAgentData?.platform || "";
          setIsAndroid(/android/i.test(ua) || /android/i.test(plat));
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  async function openReleases() {
    try {
      const { openUrl } = await import("@tauri-apps/plugin-opener");
      await openUrl("https://github.com/HiTechLabTN/genio/releases/latest");
    } catch {
      window.open("https://github.com/HiTechLabTN/genio/releases/latest", "_blank");
    }
  }

  async function handleInstall() {
    setError(null);
    setPhase("downloading");
    // Android: isAndroid triggers the OS-specific fallback in updater.ts
    // - os.platform() === 'android' → bypass Tauri updater UI
    // - First try tauri-plugin-upload download to cache + Intent
    // - Fallback to @tauri-apps/plugin-shell open(apkUrl) in browser
    // Gracefully handles Android 8+ background-install restriction:
    // silent install is blocked; user must tap "Install" in system prompt
    // (requires REQUEST_INSTALL_PACKAGES + FileProvider).
    const ok = await installUpdate((downloaded, total) => {
      if (total > 0) setProgress(Math.min(1, downloaded / total));
    });
    if (ok) {
      if (isAndroid) {
        // On Android, installUpdate via shell open() or upload->Intent
        // does not restart automatically; browser/download manager takes over.
        // Show Android-specific success: download opened, await user confirmation.
        setAndroidOpened(true);
      }
      setPhase("done");
    } else {
      setPhase("idle");
      // Keep Android restriction message user-friendly
      if (isAndroid) {
        setError(
          "Android requires user confirmation to install. The download was opened in your browser — please tap “Install” when the system installer appears. If blocked, enable “Install unknown apps” for Genio and try again.",
        );
      } else {
        setError(
          "The in-app installer isn't available here. Please download the latest build from the releases page instead.",
        );
      }
    }
  }

  const installing = phase === "downloading" || phase === "installing";

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <motion.div
        initial={{ y: 16, opacity: 0, scale: 0.97 }}
        animate={{ y: 0, opacity: 1, scale: 1 }}
        transition={{ type: "spring", damping: 26, stiffness: 320 }}
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-md rounded-2xl border border-neon/30 bg-slate-900/95 p-6 shadow-neon-lg"
      >
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-neon/15 text-neon">
              {phase === "done" ? <Check size={18} /> : <Download size={18} />}
            </span>
            <div>
              <h3 className="font-display text-base font-bold text-white">
                {phase === "done" ? "Update installed" : "Update available"}
              </h3>
              <p className="text-[11px] font-mono text-neon-soft">v{version}</p>
            </div>
          </div>
          {!installing && (
            <button onClick={onClose} className="text-slate-500 transition-colors hover:text-white">
              <X size={18} />
            </button>
          )}
        </div>

        {notes && phase === "idle" && (
          <div className="custom-scrollbar mt-4 max-h-40 overflow-y-auto rounded-lg border border-slate-700/40 bg-slate-950/60 p-3 text-xs leading-relaxed text-slate-300">
            <pre className="whitespace-pre-wrap font-sans">{notes}</pre>
          </div>
        )}

        {isAndroid && phase === "idle" && (
          <p className="mt-3 rounded-lg border border-amber-500/20 bg-amber-500/10 px-3 py-2 text-center text-[11px] leading-relaxed text-amber-200">
            Android: “Install &amp; restart” will download the APK via{" "}
            <span className="font-mono text-amber-100">tauri-plugin-upload</span> to cache and trigger an{" "}
            <span className="font-mono text-amber-100">Intent</span> (or open the APK URL via{" "}
            <span className="font-mono text-amber-100">plugin-shell open()</span> in your browser). Background installs are blocked — you’ll be prompted to confirm.
          </p>
        )}

        {phase === "downloading" && (
          <div className="mt-4">
            <div className="h-2 w-full overflow-hidden rounded-full bg-slate-800">
              <motion.div
                className="h-full bg-neon"
                animate={{ width: `${Math.round(progress * 100)}%` }}
                transition={{ ease: "easeOut", duration: 0.2 }}
              />
            </div>
            <p className="mt-1 text-center text-[11px] font-mono text-slate-400">
              Downloading {Math.round(progress * 100)}%
            </p>
          </div>
        )}

        {phase === "done" && (
          <p className="mt-4 text-center text-sm text-slate-300">
            {isAndroid && androidOpened ? (
              <>
                Download opened in browser. When the download completes, tap{" "}
                <span className="font-semibold text-neon">Install</span> in the
                system prompt to update. Android blocks background installs — user
                confirmation is required (enable “Install unknown apps” if prompted).
              </>
            ) : isAndroid ? (
              <>
                APK downloaded to cache — system installer will prompt you to
                confirm installation. <span className="text-neon">User confirmation required</span> — Android blocks silent background installs.
              </>
            ) : (
              <>
                Genio will restart to apply the update. <Rocket size={14} className="ml-1 inline text-neon" />
              </>
            )}
          </p>
        )}

        {error && (
          <p className="mt-4 text-center text-[11px] font-mono text-rose-400">⚠ {error}</p>
        )}

        <div className="mt-5 flex gap-2">
          {phase === "done" ? (
            <button onClick={onClose} className="neon-button flex-1 py-2.5">
              <Check size={14} /> Done
            </button>
          ) : phase === "idle" ? (
            <>
              <button
                onClick={handleInstall}
                className="neon-button flex-1 py-2.5"
              >
                <Rocket size={14} /> Install & restart
              </button>
              <button
                onClick={openReleases}
                className="rounded-xl border border-slate-700 px-4 py-2.5 text-sm text-slate-300 transition-colors hover:bg-slate-800"
              >
                Release page
              </button>
              <button
                onClick={onClose}
                className="rounded-xl border border-slate-700 px-4 py-2.5 text-sm text-slate-300 transition-colors hover:bg-slate-800"
              >
                Later
              </button>
            </>
          ) : (
            <button disabled className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-slate-800 py-2.5 text-sm text-slate-400">
              <Loader2 size={14} className="animate-spin" /> Installing…
            </button>
          )}
        </div>
      </motion.div>
    </motion.div>
  );
}
