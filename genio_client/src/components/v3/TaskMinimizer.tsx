import { AnimatePresence, motion } from "framer-motion";
import { useEffect } from "react";

interface Props {
  result: string;
  isMinimized: boolean;
  onToggle: () => void;
  onExpand: () => void;
}

/**
 * TaskMinimizer — when result arrives, portal shrinks to top-right (fixed 20px).
 * Mascot holds mini holographic screen with shortened result.
 * Click expands.
 */
export default function TaskMinimizer({ result, isMinimized, onToggle, onExpand }: Props) {
  const short = result.length > 92 ? result.slice(0, 92) + "…" : result;

  // auto-minimize when result first populates (one-shot handled by parent)
  useEffect(() => {
    // parent controls toggle; nothing to do here
  }, [result]);

  if (!result) return null;

  return (
    <>
      {/* minimized pill — top-right fixed */}
      <AnimatePresence>
        {isMinimized && (
          <motion.button
            initial={{ opacity: 0, scale: 0.7, y: -12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.72 }}
            transition={{ type: "spring", stiffness: 380, damping: 26 }}
            onClick={onExpand}
            className="fixed right-5 top-5 z-40 flex max-w-[min(360px,88vw)] items-center gap-3 rounded-2xl border border-cyan-400/25 bg-[#020B1E]/85 px-3 py-2.5 text-left shadow-[0_0_28px_rgba(0,229,255,0.28)] backdrop-blur-xl hover:border-cyan-400/40"
            style={{ position: "fixed", top: 20, right: 20 }}
            aria-label="Expand portal"
          >
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-red-600 to-red-800 text-[18px] shadow-inner">🧞</div>
            <div className="min-w-0">
              <div className="font-mono text-[10px] tracking-[0.14em] text-cyan-300">GENIO · RESULT</div>
              <div className="truncate font-mono text-xs text-slate-200">{short}</div>
            </div>
            <span className="ml-1 shrink-0 rounded-full bg-cyan-400/15 px-2 py-1 font-mono text-[10px] text-cyan-300">expand</span>
          </motion.button>
        )}
      </AnimatePresence>

      {/* mascot mini holographic hand screen — rendered inline when minimized */}
      {isMinimized && (
        <div className="pointer-events-none fixed right-[84px] top-[88px] z-30 hidden md:block">
          <div className="rounded-xl border border-cyan-400/30 bg-cyan-400/10 px-2.5 py-1.5 font-mono text-[10px] text-cyan-200 shadow-[0_0_16px_rgba(0,229,255,0.4)] backdrop-blur">
            {short.slice(0, 42)}
          </div>
        </div>
      )}

      {/* toggle hint */}
      {!isMinimized && result && (
        <button onClick={onToggle} className="fixed right-5 top-5 z-30 hidden rounded-full border border-white/10 bg-black/40 px-3 py-1 font-mono text-[10px] text-white/70 backdrop-blur hover:bg-white/10 md:block" style={{ position: "fixed", top: 20, right: 20 }}>
          minimize ↗
        </button>
      )}
    </>
  );
}
