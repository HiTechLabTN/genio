import { motion } from "framer-motion";
import { Download, X } from "lucide-react";

interface Props {
  version: string;
  notes?: string;
  onClose: () => void;
}

export default function UpdateModal({ version, notes, onClose }: Props) {
  async function openReleases() {
    try {
      const { openUrl } = await import("@tauri-apps/plugin-opener");
      await openUrl("https://github.com/HiTechLabTN/genio/releases/latest");
    } catch {
      window.open("https://github.com/HiTechLabTN/genio/releases/latest", "_blank");
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
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
              <Download size={18} />
            </span>
            <div>
              <h3 className="font-display text-base font-bold text-white">Update available</h3>
              <p className="text-[11px] font-mono text-neon-soft">v{version}</p>
            </div>
          </div>
          <button onClick={onClose} className="text-slate-500 hover:text-white transition-colors">
            <X size={18} />
          </button>
        </div>

        {notes && (
          <div className="custom-scrollbar mt-4 max-h-40 overflow-y-auto rounded-lg border border-slate-700/40 bg-slate-950/60 p-3 text-xs leading-relaxed text-slate-300">
            <pre className="whitespace-pre-wrap font-sans">{notes}</pre>
          </div>
        )}

        <div className="mt-5 flex gap-2">
          <button onClick={openReleases} className="neon-button flex-1 py-2.5">
            <Download size={14} /> Download latest
          </button>
          <button onClick={onClose} className="rounded-xl border border-slate-700 px-4 py-2.5 text-sm text-slate-300 transition-colors hover:bg-slate-800">
            Later
          </button>
        </div>
      </motion.div>
    </motion.div>
  );
}
